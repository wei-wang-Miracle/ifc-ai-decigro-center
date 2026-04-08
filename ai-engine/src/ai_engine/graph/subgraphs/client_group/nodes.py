"""客群创建子图节点实现。

共 3 个节点，按 DAG 拓扑执行：
[entry] ──首次──→ query_labels → build_group → [END](pending_confirm)
        ──打回──→ build_group → [END](pending_confirm)
        ──确认──→ create_and_verify → [END]

设计原则：
- query_labels 是确定性工具调用（无请求参数），不走 LLM
- build_group 采用 ReAct 工具循环：LLM 绑定 get_example_client_group +
  preview_client_group_count，自主学习示例结构并构建条件，循环结束后
  从对话历史中提取最后一次成功的 preview 调用参数作为 create_payload
- create_and_verify 是确定性工具调用（无 LLM 参与）：
  顺序调用 create_client_group → get_client_group_detail
  通过 API 返回 code 判断成功/失败
- 用户确认不使用 interrupt()，通过 phase 标记暂停，由主图 review 链路处理
"""

import json
import time

from langchain_core.messages import HumanMessage, ToolMessage

from ....llm_factory import create_creative_llm
from ....registry import get_tool_registry
from .state import ClientGroupState

# ReAct 工具循环最大轮次(断路器)
# 子图工具集固定(2 个工具)，正常路径: get_example → preview → (修正) → 结束，4 轮足够
_MAX_TOOL_ITERATIONS = 4


# ═══════════════════════════════════════════════════════════
#  工具调用辅助
# ═══════════════════════════════════════════════════════════


def _invoke_tool(tool_name: str, token: str, **kwargs) -> str:
    """同步调用注册中心的工具并返回结果字符串。

    用于确定性工具调用（知道调哪个工具、传什么参数），不需要 LLM 决策。

    Args:
        tool_name: 工具注册名称。
        token: 用户身份 Token。
        **kwargs: 工具参数。

    Returns:
        工具返回的原始字符串，调用失败时返回 JSON 格式错误信息。
    """
    tool_registry = get_tool_registry()
    tool = tool_registry.get_tool(tool_name, token)
    if tool is None:
        return json.dumps({"error": f"工具 '{tool_name}' 未在注册中心找到"})
    try:
        result = tool.invoke(kwargs)
        return str(result) if result is not None else ""
    except Exception as e:
        print(f"[ClientGroupSubgraph] 工具 '{tool_name}' 调用失败: {e}")
        return json.dumps({"error": f"工具调用失败: {e!s}"})


def _extract_last_preview_args(messages: list) -> dict | None:
    """从 ReAct 对话历史中提取最后一次成功调用 preview_client_group_count 的参数。

    反向遍历 messages，找到最后一个包含 preview_client_group_count 工具调用的
    AIMessage，且其对应的 ToolMessage 不含错误标记，返回该次调用的 args dict。
    零 LLM 开销，纯消息解析。
    """
    # 收集所有 ToolMessage，按 tool_call_id 索引其内容
    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = msg.content

    # 反向查找最后一次成功的 preview 调用
    for msg in reversed(messages):
        if not (hasattr(msg, "tool_calls") and msg.tool_calls):
            continue
        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("name") != "preview_client_group_count":
                continue
            call_id = tool_call.get("id", "")
            result_content = tool_results.get(call_id, "")
            if "错误" in result_content or '"error"' in result_content:
                continue
            return tool_call.get("args", {})

    return None


async def _react_tool_loop(
    llm_with_tools,
    messages: list,
    tool_registry,
    token: str,
    max_iterations: int = _MAX_TOOL_ITERATIONS,
) -> tuple[str, list[str]]:
    """ReAct 工具调用循环：LLM 思考 → 调用工具 → 观察结果 → 继续或结束。

    Returns:
        (final_output, tools_called) — 最终文本输出和实际调用的工具名称列表。
    """
    tools_called: list[str] = []
    final_output = ""

    for iteration in range(max_iterations):
        print(f"[ClientGroupSubgraph] ReAct 第 {iteration + 1}/{max_iterations} 轮")
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not (hasattr(response, "tool_calls") and response.tool_calls):
            final_output = response.content
            print(f"[ClientGroupSubgraph] 第 {iteration + 1} 轮 LLM 返回最终结果")
            break

        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tools_called.append(tool_name)
            print(f"[ClientGroupSubgraph] 调用工具 '{tool_name}'，参数: {tool_args}")

            tool_start = time.time()
            tool = tool_registry.get_tool(tool_name, token)
            if tool:
                try:
                    tool_result = await tool.ainvoke(tool_args)
                    result_str = str(tool_result) if tool_result is not None else "执行成功"
                    latency_ms = int((time.time() - tool_start) * 1000)
                    print(
                        f"[ClientGroupSubgraph] 工具 '{tool_name}' 成功，"
                        f"耗时 {latency_ms}ms，返回: {result_str[:200]}"
                    )
                    messages.append(ToolMessage(tool_call_id=tool_call["id"], content=result_str))
                except Exception as e:
                    latency_ms = int((time.time() - tool_start) * 1000)
                    print(
                        f"[ClientGroupSubgraph] 工具 '{tool_name}' 失败，耗时 {latency_ms}ms: {e}"
                    )
                    messages.append(
                        ToolMessage(tool_call_id=tool_call["id"], content=f"错误: {e!s}")
                    )
            else:
                print(f"[ClientGroupSubgraph] 工具 '{tool_name}' 未找到")
                messages.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=f"错误: 找不到工具 {tool_name}",
                    )
                )
    else:
        # 轮次耗尽，注入收尾指令让 LLM 基于已有结果给出结论
        messages.append(
            HumanMessage(
                content="工具调用轮次已用尽。请不要再调用任何工具，"
                "直接基于已获取的所有工具调用结果，给出完整的执行结论。"
            )
        )
        print("[ClientGroupSubgraph] 轮次耗尽，注入收尾指令")
        try:
            final_response = await llm_with_tools.ainvoke(messages)
            final_output = final_response.content or "执行超时"
        except Exception as e:
            print(f"[ClientGroupSubgraph] 收尾调用失败: {e}")
            final_output = messages[-2].content if len(messages) >= 2 else "执行超时"

    return final_output, tools_called


# ═══════════════════════════════════════════════════════════
#  Prompt 模板
# ═══════════════════════════════════════════════════════════

_BUILD_GROUP_PROMPT = """
你是一个极为严谨的“智能客群入参结构化与再构建专家”。你的核心使命是将用户的自然语言需求或上游 Agent 传递的条件，精准转化为系统可识别的结构化规则，并在收到用户反馈时灵活修正。

## 执行策略
1. 初次构建：严格依据【可用标签字典】，将【用户需求】转化为规范的条件查询结构。
2. 反馈再构建：如果上下文中包含【用户修改意见】，你需要重点分析原有需求与修改意见之间的差异，在原条件基础上增加、修改或删除部分条件并重新构建。注意保留且不破坏未被修改的其他有效条件。

## 可用标签字典
{labels}

## 用户需求
{query}

{feedback_context}

{prior_context}

## 执行要求（必须遵守）
1. 你**必须**先调用工具获取标准结构参考，了解参数格式。
2. 构建好条件后，你**必须**调用工具验证参数正确性并获取客群人数预览。
3. 严禁跳过工具调用直接给出最终结论。在调用工具并获得结果之前，不要输出最终回答。
"""


# ═══════════════════════════════════════════════════════════
#  节点 1: query_labels — 获取所有可用标签
# ═══════════════════════════════════════════════════════════


def query_labels_node(state: ClientGroupState) -> dict:
    """获取所有可用标签列表，写入 labels_cache。"""
    print("[ClientGroupSubgraph] 节点: query_labels")

    result = _invoke_tool("query_all_labels", state.token)

    try:
        data = json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError):
        print("[ClientGroupSubgraph] query_all_labels 失败: 返回值无法解析为JSON")
        return {"labels_cache": "", "error": "获取标签列表失败: 返回值格式错误", "success": False}

    if data.get("code") != 200:
        print(
            f"[ClientGroupSubgraph] query_all_labels 失败: code={data.get('code')}, info={data.get('info')}"
        )
        return {
            "labels_cache": "",
            "error": f"获取标签列表失败: code={data.get('code')}",
            "success": False,
        }

    info = data.get("info")
    if not info:
        print("[ClientGroupSubgraph] query_all_labels 失败: info为空")
        return {"labels_cache": "", "error": "获取标签列表失败: 标签列表为空", "success": False}

    print(f"[ClientGroupSubgraph] query_all_labels 成功，获取到 {len(info)} 个标签")
    return {"labels_cache": json.dumps(info, ensure_ascii=False)}


# ═══════════════════════════════════════════════════════════
#  节点 2: build_group — ReAct 构建条件 + 预览验证
# ═══════════════════════════════════════════════════════════


async def build_group_node(state: ClientGroupState) -> dict:
    """LLM 通过 ReAct 工具循环构建客群条件并预览验证。

    工具绑定：get_example_client_group + preview_client_group_count
    LLM 自主调用示例工具学习结构，构建条件后调用预览工具验证，
    工具返回错误时 LLM 通过 ToolMessage 自然获得反馈并自修复。

    最后一轮 LLM 不再调用工具时，直接通过 with_structured_output 产出
    _BuildGroupResult（包含 payload + summary），整个节点只有一条 LLM 调用链。
    """
    print("[ClientGroupSubgraph] 节点: build_group")

    if state.error:
        return {}
    if not state.labels_cache:
        return {"error": "标签列表为空，无法构建条件", "success": False}

    tool_registry = get_tool_registry()

    # 获取工具实例绑定给 LLM
    tool_names = ["get_example_client_group", "preview_client_group_count"]
    tools = tool_registry.get_tools_by_names(tool_names, state.token)
    if not tools:
        return {"error": "构建所需工具不可用", "success": False}

    llm = create_creative_llm()
    llm_with_tools = llm.bind_tools(tools)

    # 构建 prompt
    prior_context = ""
    if state.prior_step_outputs:
        prior_context = f"## 上游步骤产出(重要参考)\n{state.prior_step_outputs}"

    feedback_context = ""
    if state.review_feedback:
        feedback_context = (
            f"## 用户修改意见(必须响应)\n{state.review_feedback}\n请根据上述意见调整条件。"
        )

    prompt = _BUILD_GROUP_PROMPT.format(
        labels=state.labels_cache[:8000],
        query=state.query,
        prior_context=prior_context,
        feedback_context=feedback_context,
    )

    messages = [HumanMessage(content=prompt)]

    try:
        output, tools_called = await _react_tool_loop(
            llm_with_tools=llm_with_tools,
            messages=messages,
            tool_registry=tool_registry,
            token=state.token,
        )
    except Exception as e:
        print(f"[ClientGroupSubgraph] build_group 异常: {e}")
        return {"error": f"构建客群条件失败: {e!s}", "success": False}

    if "preview_client_group_count" not in tools_called:
        return {"error": "LLM 未调用预览工具，无法获取预览结果", "success": False}

    # 从 messages 中反向查找最后一次成功的 preview 工具调用参数
    # 工具调用参数已经在 AIMessage.tool_calls 中，零额外 LLM 开销
    create_payload = _extract_last_preview_args(messages)
    if create_payload is None:
        return {"error": "无法从对话历史中提取预览工具调用参数", "success": False}

    create_payload_json = json.dumps(create_payload, ensure_ascii=False)

    print(
        f"[ClientGroupSubgraph] build_group 成功: "
        f"tools_called={tools_called}, payload_length={len(create_payload_json)}"
    )

    return {
        "create_payload": create_payload_json,
        "preview_result": output,
        "phase": "pending_confirm",
        "output": output,
    }


# ═══════════════════════════════════════════════════════════
#  节点 3: create_and_verify — 确定性创建 + 验证
# ═══════════════════════════════════════════════════════════


def create_and_verify_node(state: ClientGroupState) -> dict:
    """确定性创建客群并验证，无 LLM 参与。

    两步确定性工具调用：
    1. create_client_group — 参数来自 build_group_node 产出的 create_payload，
       返回 {"code":200,"info":clientGroupId}
    2. get_client_group_detail — 使用返回的 clientGroupId 二次确认客群已创建成功，
       验证不通过则整体失败
    """
    print("[ClientGroupSubgraph] 节点: create_and_verify")

    if state.error:
        return {
            "output": f"客群创建过程中发生错误: {state.error}",
            "success": False,
        }

    if not state.create_payload:
        return {"error": "无可用的客群创建参数", "success": False}

    # 解析 create_payload
    try:
        payload = json.loads(state.create_payload)
    except (json.JSONDecodeError, TypeError):
        return {"error": "create_payload 格式错误，无法解析为 JSON", "success": False}

    # ── 步骤 1: 创建客群 ──
    print(f"[ClientGroupSubgraph] 调用 create_client_group，参数: {payload}")
    create_result = _invoke_tool("create_client_group", state.token, **payload)

    try:
        create_data = json.loads(create_result) if isinstance(create_result, str) else create_result
    except (json.JSONDecodeError, TypeError):
        return {"error": f"创建客群返回值格式错误: {create_result[:200]}", "success": False}

    if create_data.get("code") != 200:
        error_info = create_data.get("info", create_data.get("error", "未知错误"))
        print(f"[ClientGroupSubgraph] create_client_group 失败: {error_info}")
        return {"error": f"创建客群失败: {error_info}", "success": False}

    # 从返回结构中提取 clientGroupId
    client_group_id = create_data.get("info")
    if not client_group_id:
        print("[ClientGroupSubgraph] create_client_group 返回 code=200 但 info 为空")
        return {"error": "创建客群失败: 返回的 clientGroupId 为空", "success": False}

    print(f"[ClientGroupSubgraph] create_client_group 成功，clientGroupId={client_group_id}")

    # ── 步骤 2: 使用 clientGroupId 验证客群已创建 ──
    print(
        f"[ClientGroupSubgraph] 调用 get_client_group_detail 验证，clientGroupId={client_group_id}"
    )
    verify_result = _invoke_tool(
        "get_client_group_detail", state.token, clientGroupId=client_group_id
    )

    try:
        verify_data = json.loads(verify_result) if isinstance(verify_result, str) else verify_result
    except (json.JSONDecodeError, TypeError):
        print("[ClientGroupSubgraph] get_client_group_detail 返回值解析失败")
        return {
            "error": f"客群验证失败: 验证接口返回值无法解析，clientGroupId={client_group_id}",
            "success": False,
        }

    if verify_data.get("code") != 200:
        error_info = verify_data.get("info", verify_data.get("error", "未知错误"))
        print(f"[ClientGroupSubgraph] get_client_group_detail 验证失败: {error_info}")
        return {
            "error": f"客群验证失败: {error_info}，clientGroupId={client_group_id}",
            "success": False,
        }

    print(
        f"[ClientGroupSubgraph] create_and_verify 完成: 创建并验证成功，clientGroupId={client_group_id}"
    )
    return {"output": f"客群创建成功，已确认。clientGroupId={client_group_id}", "success": True}


# ═══════════════════════════════════════════════════════════
#  条件路由函数
# ═══════════════════════════════════════════════════════════


def route_entry(state: ClientGroupState) -> str:
    """子图入口路由：根据 phase 及历史反馈判断入口节点。

    Returns:
        - "query_labels": 首次执行，从头开始加载标签
        - "build_group": 带有修改意见且已有标签缓存，直接进行重构建
        - "create_and_verify": 用户确认后恢复，直接进入创建阶段
    """
    if state.phase == "resume_after_confirm":
        print("[ClientGroupSubgraph] 恢复执行: 用户已确认，直接进入创建阶段")
        return "create_and_verify"

    if state.review_feedback and state.labels_cache:
        print("[ClientGroupSubgraph] 重构建: 收到用户修改意见且已有缓存，直接进入构建阶段")
        return "build_group"

    print("[ClientGroupSubgraph] 首次执行: 从查询标签开始")
    return "query_labels"
