"""策略创建子图节点实现。

共 5 个阶段节点 + 1 个入口路由，按 DAG 拓扑执行::

    [entry_router]
        ──首次──→ preparation → decision → [END](phase=pending_confirm)
        ──打回──→ preparation → decision → [END](phase=pending_confirm)
        ──确认──→ construction → creation_and_verify → [END]

设计原则：
- preparation 采用 ReAct 工具循环：LLM 自主调用 list_my_purposes /
  save_purpose / list_my_client_groups 确定 purpose_id 和 client_group_id
- decision 采用 ReAct 工具循环：LLM 调用 list_available_assemblies +
  get_showcase_strategy_canvas 推理最佳拓扑，产出 selected_assemblies、
  pseudo_code 和 design_intent
- 人机回环不使用 interrupt()，通过 phase=pending_confirm 标记暂停，
  由主图 review 链路处理
- construction 采用 ReAct 工具循环(带内部校验回环)：LLM 调用
  get_assembly_schemas + get_example_strategy_canvas 生成 canvas_payload，
  再调用 validate_strategy_canvas 校验，失败时 LLM 自修复重试
- creation_and_verify 是确定性工具调用(无 LLM 参与)：顺序调用
  create_strategy_canvas → get_strategy_canvas_detail，通过 API 返回
  code 硬断言判断成功/失败
"""

import json
import time

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from ....llm_factory import create_creative_llm
from ....registry import get_tool_registry
from .state import StrategyCreationState

# ═══════════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════════

# 准备/决策阶段 ReAct 最大轮次
_MAX_PREPARATION_ITERATIONS = 6
# 决策阶段 ReAct 最大轮次
_MAX_DECISION_ITERATIONS = 6
# 构建阶段 ReAct 最大轮次(含内部校验回环，需要更多轮次)
_MAX_CONSTRUCTION_ITERATIONS = 8


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
        print(f"[StrategyCreationSubgraph] 工具 '{tool_name}' 调用失败: {e}")
        return json.dumps({"error": f"工具调用失败: {e!s}"})


async def _react_tool_loop(
    llm_with_tools,
    messages: list,
    tool_registry,
    token: str,
    max_iterations: int,
    log_prefix: str = "StrategyCreationSubgraph",
    config: RunnableConfig = None,
) -> tuple[str, list[str]]:
    """ReAct 工具调用循环：LLM 思考 → 调用工具 → 观察结果 → 继续或结束。

    功能:
        实现标准的 ReAct(Reasoning + Acting) 循环模式。每轮中 LLM 决定
        调用哪些工具、传什么参数，工具执行后将结果反馈给 LLM，LLM 基于
        观察结果继续推理或给出最终答案。

    参数:
        llm_with_tools: 已绑定工具的 LLM 实例。
        messages: 初始消息列表(含 system prompt 和用户指令)。
        tool_registry: 工具注册中心实例，用于按名称获取工具。
        token: 用户身份 Token。
        max_iterations: 最大循环轮次(断路器)。
        log_prefix: 日志前缀标识。

    返回:
        (final_output, tools_called) — 最终文本输出和实际调用的工具名称列表。
    """
    tools_called: list[str] = []
    final_output = ""

    for iteration in range(max_iterations):
        print(f"[{log_prefix}] ReAct 第 {iteration + 1}/{max_iterations} 轮")
        response = await llm_with_tools.ainvoke(messages, config=config)
        messages.append(response)

        # LLM 不再调用工具 → 产出最终回答
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            final_output = response.content
            print(f"[{log_prefix}] 第 {iteration + 1} 轮 LLM 返回最终结果")
            break

        # 逐个执行 LLM 请求的工具调用
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tools_called.append(tool_name)
            print(f"[{log_prefix}] 调用工具 '{tool_name}'，参数: {tool_args}")

            tool_start = time.time()
            tool = tool_registry.get_tool(tool_name, token)
            if tool:
                try:
                    tool_result = await tool.ainvoke(tool_args)
                    result_str = str(tool_result) if tool_result is not None else "执行成功"
                    latency_ms = int((time.time() - tool_start) * 1000)
                    print(
                        f"[{log_prefix}] 工具 '{tool_name}' 成功，"
                        f"耗时 {latency_ms}ms，返回: {result_str[:200]}"
                    )
                    messages.append(ToolMessage(tool_call_id=tool_call["id"], content=result_str))
                except Exception as e:
                    latency_ms = int((time.time() - tool_start) * 1000)
                    print(
                        f"[{log_prefix}] 工具 '{tool_name}' 失败，耗时 {latency_ms}ms: {e}"
                    )
                    messages.append(
                        ToolMessage(tool_call_id=tool_call["id"], content=f"错误: {e!s}")
                    )
            else:
                print(f"[{log_prefix}] 工具 '{tool_name}' 未找到")
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
        print(f"[{log_prefix}] 轮次耗尽，注入收尾指令")
        try:
            final_response = await llm_with_tools.ainvoke(messages, config=config)
            final_output = final_response.content or "执行超时"
        except Exception as e:
            print(f"[{log_prefix}] 收尾调用失败: {e}")
            final_output = messages[-2].content if len(messages) >= 2 else "执行超时"

    return final_output, tools_called


def _extract_json_from_output(text: str) -> dict | None:
    """从 LLM 输出文本中提取 JSON 对象。

    功能:
        LLM 的输出可能包含 markdown 代码块包裹的 JSON，也可能是纯文本
        中夹杂的 JSON 片段。本函数尝试多种策略提取第一个有效的 JSON 对象。

    参数:
        text: LLM 原始输出文本。

    返回:
        解析成功的 dict，解析失败返回 None。
    """
    if not text:
        return None

    # 策略1：尝试直接解析整段文本
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # 策略2：提取 ```json ... ``` 代码块中的内容
    import re
    json_block_pattern = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)
    match = json_block_pattern.search(text)
    if match:
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # 策略3：查找第一个 { 和最后一个 } 之间的内容
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(text[first_brace : last_brace + 1])
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _extract_last_validate_args(messages: list) -> dict | None:
    """从 ReAct 对话历史中提取最后一次成功调用 validate_strategy_canvas 的参数。

    功能:
        反向遍历 messages，找到最后一个包含 validate_strategy_canvas 工具调用的
        AIMessage，且其对应的 ToolMessage 不含错误标记，返回该次调用的 args dict。
        零 LLM 开销，纯消息解析。

    参数:
        messages: ReAct 循环中累积的完整消息列表。

    返回:
        最后一次成功校验的参数 dict，未找到返回 None。
    """
    # 收集所有 ToolMessage，按 tool_call_id 索引其内容
    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = msg.content

    # 反向查找最后一次成功的 validate 调用
    for msg in reversed(messages):
        if not (hasattr(msg, "tool_calls") and msg.tool_calls):
            continue
        for tool_call in reversed(msg.tool_calls):
            if tool_call.get("name") != "validate_strategy_canvas":
                continue
            call_id = tool_call.get("id", "")
            result_content = tool_results.get(call_id, "")
            # 校验返回结果不含错误标记才算成功
            if "错误" in result_content or '"error"' in result_content:
                continue
            return tool_call.get("args", {})

    return None


# ═══════════════════════════════════════════════════════════
#  Prompt 模板
# ═══════════════════════════════════════════════════════════

_PREPARATION_PROMPT = """\
你是一个严谨的"策略画布准备专家"。你的核心使命是为策略画布的创建确定两个必备的前置参数：
**任务(purpose)** 和 **客群(clientGroup)**。

## 你的职责
1. **确定任务**: 查询当前可用的任务列表，从中选择最符合用户意图的任务。
   如果不存在合适的任务，则创建一个新任务。
2. **确定客群**: 查询当前可用的客群列表，从中选择最匹配的客群。
   如果没有可用客群，你必须明确告知无可用客群，后续需要先创建客群。

请利用你拥有的工具自主完成上述职责。

## 用户需求
{query}

{feedback_context}

{prior_context}

## 输出要求(严格遵守)
当你完成工具调用并确定了 purposeId 和 clientGroupId 后，最终回答中**必须**包含如下 JSON 块：

```json
{{"purposeId": <整数>, "clientGroupId": <整数>, "reason": "<选择理由简要说明>"}}
```

- purposeId 和 clientGroupId 必须是从工具返回数据中获取的真实整数值，禁止编造
- 如果某个 ID 无法确定，对应字段填 0 并在 reason 中说明原因
- JSON 块必须是合法 JSON，不要省略引号或添加注释
"""

_DECISION_PROMPT = """\
你是一个资深的"策略设计架构师"。你的核心使命是基于已确定的任务和客群，设计出最优的策略拓扑方案。

## 背景信息
- 已绑定任务 ID: {purpose_id}
- 已绑定客群 ID: {client_group_id}

## 你的职责
1. **了解平台能力**: 查询平台支持的所有触达/分流/出口组件类型及其业务职能。
2. **参考优秀案例**: 获取线上真实的优秀策略案例作为设计灵感。
3. **设计最佳方案**: 基于用户意图、可用组件和案例参考，推理出本次营销的最佳拓扑方案。

请利用你拥有的工具自主完成上述职责。

## 用户需求
{query}

{feedback_context}

{prior_context}

## 输出要求
请在最终回答中包含以下三部分内容：
1. **组件列表(selected_assemblies)**: 以 JSON 数组格式列出需要使用的组件类型名称，\
例如 ["START", "APP_PUSH", "END"]
2. **策略伪代码(pseudo_code)**: 描述整体拓扑结构的伪代码，展示各组件间的连接关系
3. **设计意图(design_intent)**: 面向用户的、通俗易懂的设计方案说明，解释为什么选择这些组件、\
整体营销逻辑是什么

注意：此阶段不需要生成具体的 JSON Schema 细节，只需确定高层方案。
"""

_CONSTRUCTION_PROMPT = """\
你是一个极为精确的"策略 JSON 构建工程师"。你的核心使命是将高层策略方案转化为严格满足后端校验的 \
canvasNodes JSON 结构。

## 背景信息
- 任务 ID: {purpose_id}
- 客群 ID: {client_group_id}
- 选定组件: {selected_assemblies}
- 策略伪代码: {pseudo_code}

## 你的职责
1. **获取结构约束**: 获取已选组件的精确 JSON Schema 约束。\
仅获取 selected_assemblies 对应的组件类型，避免拉取不必要的信息。
2. **学习示例结构**: 获取包含严谨节点父子嵌套指向逻辑的策略示例作为参考。
3. **构建 Payload**: 基于 Schema 和示例，生成完整的 canvas_payload 字典\
(包含 strategy 和 canvasNodes)。
4. **校验合法性**: 对生成的 payload 进行服务器级预校验。\
如果校验失败，分析错误信息中的提示，修正 payload 后重新校验，直到通过为止。

请利用你拥有的工具自主完成上述职责。

## 关键约束(必须遵守)
- **唯一根节点**: parentNodeId=null 必须且只能有一个(START 节点)。
- **节点父子关系**: 除 START 外，所有节点的 parentNodeId 必须指向有效的父节点。
- **Schema 严格对齐**: 每个节点的字段必须完全满足对应组件类型的 JSON Schema。

{prior_context}

## 输出要求
当服务器级校验通过后，输出最终的 canvas_payload JSON。
"""


# ═══════════════════════════════════════════════════════════
#  节点 1: preparation — 准备阶段(确定 purpose 和 clientGroup)
# ═══════════════════════════════════════════════════════════


async def preparation_node(state: StrategyCreationState, config: RunnableConfig) -> dict:
    """准备阶段：通过 ReAct 工具循环确定 purposeId 和 clientGroupId。

    功能:
        LLM 自主调用 list_my_purposes / save_purpose / list_my_client_groups
        等工具，根据用户需求找到或创建合适的任务和客群。

    参数:
        state: 当前子图状态。

    返回:
        包含 purpose_id、client_group_id 和输出信息的状态更新字典。
    """
    print("[StrategyCreationSubgraph] 节点: preparation")

    if state.error:
        return {}

    tool_registry = get_tool_registry()

    # 准备阶段使用的工具集
    tool_names = ["list_my_purposes", "save_purpose", "list_my_client_groups"]
    tools = tool_registry.get_tools_by_names(tool_names, state.token)
    if not tools:
        return {"error": "准备阶段所需工具不可用", "success": False}

    llm = create_creative_llm()
    llm_with_tools = llm.bind_tools(tools)

    # 构建上下文
    prior_context = ""
    if state.prior_step_outputs:
        prior_context = f"## 上游步骤产出(重要参考)\n{state.prior_step_outputs}"

    feedback_context = ""
    if state.review_feedback:
        feedback_context = (
            f"## 用户修改意见(必须响应)\n{state.review_feedback}\n"
            "请根据上述意见重新评估任务和客群的选择。"
        )

    prompt = _PREPARATION_PROMPT.format(
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
            max_iterations=_MAX_PREPARATION_ITERATIONS,
            log_prefix="StrategyCreation-Preparation",
            config=config,
        )
    except Exception as e:
        print(f"[StrategyCreationSubgraph] preparation 异常: {e}")
        return {"error": f"准备阶段执行失败: {e!s}", "success": False}

    # 从 LLM 输出中提取 purposeId 和 clientGroupId
    # LLM 可能以结构化或自然语言形式输出，尝试提取整数值
    purpose_id = state.purpose_id
    client_group_id = state.client_group_id

    result_data = _extract_json_from_output(output)
    if result_data:
        purpose_id = result_data.get("purposeId", purpose_id) or purpose_id
        client_group_id = result_data.get("clientGroupId", client_group_id) or client_group_id
    else:
        # 退化方案：通过正则从文本中提取
        import re
        # 匹配 purposeId: 123 或 purpose_id: 123 等模式
        purpose_match = re.search(r"(?:purposeId|purpose_id|任务\s*ID)\s*[:：]\s*(\d+)", output)
        if purpose_match:
            purpose_id = int(purpose_match.group(1))
        group_match = re.search(
            r"(?:clientGroupId|client_group_id|客群\s*ID)\s*[:：]\s*(\d+)", output
        )
        if group_match:
            client_group_id = int(group_match.group(1))

    if not purpose_id:
        return {"error": "准备阶段未能确定任务 ID(purposeId)", "success": False}
    if not client_group_id:
        return {"error": "准备阶段未能确定客群 ID(clientGroupId)，请先创建客群", "success": False}

    print(
        f"[StrategyCreationSubgraph] preparation 成功: "
        f"purpose_id={purpose_id}, client_group_id={client_group_id}"
    )

    return {
        "purpose_id": purpose_id,
        "client_group_id": client_group_id,
        "output": output,
    }


# ═══════════════════════════════════════════════════════════
#  节点 2: decision — 决策阶段(设计策略拓扑方案)
# ═══════════════════════════════════════════════════════════


async def decision_node(state: StrategyCreationState, config: RunnableConfig) -> dict:
    """决策阶段：LLM 通过 ReAct 工具循环设计策略拓扑方案。

    功能:
        LLM 调用 list_available_assemblies 了解可用组件，调用
        get_showcase_strategy_canvas 参考优秀案例，然后推理出最佳
        策略拓扑，产出 selected_assemblies、pseudo_code 和 design_intent。

    参数:
        state: 当前子图状态，需要 purpose_id 和 client_group_id 已确定。

    返回:
        包含 selected_assemblies、pseudo_code、design_intent 的状态更新字典。
    """
    print("[StrategyCreationSubgraph] 节点: decision")

    if state.error:
        return {}
    if not state.purpose_id or not state.client_group_id:
        return {"error": "准备阶段数据不完整，无法进入决策阶段", "success": False}

    tool_registry = get_tool_registry()

    # 决策阶段使用的工具集
    tool_names = ["list_available_assemblies", "get_showcase_strategy_canvas"]
    tools = tool_registry.get_tools_by_names(tool_names, state.token)
    if not tools:
        return {"error": "决策阶段所需工具不可用", "success": False}

    llm = create_creative_llm()
    llm_with_tools = llm.bind_tools(tools)

    # 构建上下文
    prior_context = ""
    if state.prior_step_outputs:
        prior_context = f"## 上游步骤产出(重要参考)\n{state.prior_step_outputs}"

    feedback_context = ""
    if state.review_feedback:
        feedback_context = (
            f"## 用户修改意见(必须响应)\n{state.review_feedback}\n"
            "请根据上述意见重新设计策略拓扑方案。"
        )

    prompt = _DECISION_PROMPT.format(
        purpose_id=state.purpose_id,
        client_group_id=state.client_group_id,
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
            max_iterations=_MAX_DECISION_ITERATIONS,
            log_prefix="StrategyCreation-Decision",
            config=config,
        )
    except Exception as e:
        print(f"[StrategyCreationSubgraph] decision 异常: {e}")
        return {"error": f"决策阶段执行失败: {e!s}", "success": False}

    # 从 LLM 输出中提取结构化产出
    selected_assemblies = ""
    pseudo_code = ""
    design_intent = ""

    result_data = _extract_json_from_output(output)
    if result_data:
        # JSON 模式提取
        assemblies = result_data.get("selected_assemblies", [])
        if isinstance(assemblies, list):
            selected_assemblies = json.dumps(assemblies, ensure_ascii=False)
        elif isinstance(assemblies, str):
            selected_assemblies = assemblies
        pseudo_code = result_data.get("pseudo_code", "")
        design_intent = result_data.get("design_intent", "")
    else:
        # 退化方案：从文本中按区块提取
        import re

        # 提取 selected_assemblies JSON 数组
        array_match = re.search(r"\[.*?\]", output, re.DOTALL)
        if array_match:
            try:
                parsed = json.loads(array_match.group())
                if isinstance(parsed, list):
                    selected_assemblies = json.dumps(parsed, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass

        # 提取伪代码部分(在 pseudo_code 标记之后)
        pseudo_match = re.search(
            r"(?:pseudo_code|伪代码)[：:\s]*\n?(.*?)(?=\n\s*(?:design_intent|设计意图)|$)",
            output,
            re.DOTALL | re.IGNORECASE,
        )
        if pseudo_match:
            pseudo_code = pseudo_match.group(1).strip()

        # 提取设计意图部分
        intent_match = re.search(
            r"(?:design_intent|设计意图)[：:\s]*\n?(.*?)$",
            output,
            re.DOTALL | re.IGNORECASE,
        )
        if intent_match:
            design_intent = intent_match.group(1).strip()

    if not selected_assemblies:
        return {"error": "决策阶段未能确定组件列表(selected_assemblies)", "success": False}

    # 如果 design_intent 为空，使用完整输出作为兜底
    if not design_intent:
        design_intent = output

    print(
        f"[StrategyCreationSubgraph] decision 成功: "
        f"assemblies={selected_assemblies[:100]}, pseudo_code 长度={len(pseudo_code)}"
    )

    return {
        "selected_assemblies": selected_assemblies,
        "pseudo_code": pseudo_code,
        "design_intent": design_intent,
        "output": output,
        "phase": "pending_confirm",
    }


# ═══════════════════════════════════════════════════════════
#  节点 3: construction — 构建阶段(生成 canvas_payload + 校验)
# ═══════════════════════════════════════════════════════════


async def construction_node(state: StrategyCreationState, config: RunnableConfig) -> dict:
    """构建阶段：LLM 通过 ReAct 工具循环生成并校验 canvas_payload。

    功能:
        LLM 调用 get_assembly_schemas 获取精确的 JSON Schema 约束，
        调用 get_example_strategy_canvas 获取示例结构，然后生成完整的
        canvas_payload，再调用 validate_strategy_canvas 进行服务器级
        预校验。校验失败时 LLM 通过 ToolMessage 自然获得错误反馈并
        自修复重试，直到校验通过。

    参数:
        state: 当前子图状态，需要 selected_assemblies 等决策产出已就绪。

    返回:
        包含 canvas_payload 和 is_validated 的状态更新字典。
    """
    print("[StrategyCreationSubgraph] 节点: construction")

    if state.error:
        return {}
    if not state.selected_assemblies:
        return {"error": "决策阶段数据不完整，无法进入构建阶段", "success": False}

    tool_registry = get_tool_registry()

    # 构建阶段使用的工具集
    tool_names = [
        "get_assembly_schemas",
        "get_example_strategy_canvas",
        "validate_strategy_canvas",
    ]
    tools = tool_registry.get_tools_by_names(tool_names, state.token)
    if not tools:
        return {"error": "构建阶段所需工具不可用", "success": False}

    llm = create_creative_llm()
    llm_with_tools = llm.bind_tools(tools)

    # 构建上下文
    prior_context = ""
    if state.prior_step_outputs:
        prior_context = f"## 上游步骤产出(重要参考)\n{state.prior_step_outputs}"

    prompt = _CONSTRUCTION_PROMPT.format(
        purpose_id=state.purpose_id,
        client_group_id=state.client_group_id,
        selected_assemblies=state.selected_assemblies,
        pseudo_code=state.pseudo_code,
        prior_context=prior_context,
    )

    messages = [HumanMessage(content=prompt)]

    try:
        output, tools_called = await _react_tool_loop(
            llm_with_tools=llm_with_tools,
            messages=messages,
            tool_registry=tool_registry,
            token=state.token,
            max_iterations=_MAX_CONSTRUCTION_ITERATIONS,
            log_prefix="StrategyCreation-Construction",
            config=config,
        )
    except Exception as e:
        print(f"[StrategyCreationSubgraph] construction 异常: {e}")
        return {"error": f"构建阶段执行失败: {e!s}", "success": False}

    # 判断是否调用了 validate 校验工具
    if "validate_strategy_canvas" not in tools_called:
        return {"error": "LLM 未调用校验工具(validate_strategy_canvas)，无法确认 payload 合法性", "success": False}

    # 从 messages 中提取最后一次成功的 validate 调用参数作为 canvas_payload
    validate_args = _extract_last_validate_args(messages)
    if validate_args is not None:
        # 使用校验工具的参数作为最终 payload（已通过校验的版本）
        canvas_payload_json = json.dumps(validate_args, ensure_ascii=False)
        is_validated = True
    else:
        # 退化方案：从 LLM 输出中提取 JSON
        payload_data = _extract_json_from_output(output)
        if payload_data:
            canvas_payload_json = json.dumps(payload_data, ensure_ascii=False)
            is_validated = False
            print("[StrategyCreationSubgraph] 警告: 从输出中提取 payload，但未通过校验工具确认")
        else:
            return {"error": "无法从对话历史中提取有效的 canvas_payload", "success": False}

    print(
        f"[StrategyCreationSubgraph] construction 成功: "
        f"payload_length={len(canvas_payload_json)}, validated={is_validated}"
    )

    return {
        "canvas_payload": canvas_payload_json,
        "is_validated": is_validated,
        "output": output,
    }


# ═══════════════════════════════════════════════════════════
#  节点 4: creation_and_verify — 创建和验证阶段(确定性)
# ═══════════════════════════════════════════════════════════


def creation_and_verify_node(state: StrategyCreationState) -> dict:
    """创建和验证阶段：确定性创建策略画布并验证，无 LLM 参与。

    功能:
        两步确定性工具调用 + code=200 双重断言，堵住"幻觉生成创建成功"的问题：
        1. create_strategy_canvas → 断言 code=200
        2. get_strategy_canvas_detail → 断言 code=200

    参数:
        state: 当前子图状态，需要 canvas_payload 已生成并校验。

    返回:
        包含 strategy_id、success 和输出信息的状态更新字典。
    """
    print("[StrategyCreationSubgraph] 节点: creation_and_verify")

    if state.error:
        return {
            "output": f"策略创建过程中发生错误: {state.error}",
            "success": False,
        }

    if not state.canvas_payload:
        return {"error": "无可用的策略画布创建参数(canvas_payload)", "success": False}

    # 解析 canvas_payload
    try:
        payload = json.loads(state.canvas_payload)
    except (json.JSONDecodeError, TypeError):
        return {"error": "canvas_payload 格式错误，无法解析为 JSON", "success": False}

    # ── 步骤 1: 创建策略画布，断言 code=200 ──
    print(f"[StrategyCreationSubgraph] 调用 create_strategy_canvas，payload 长度: {len(state.canvas_payload)}")
    create_result = _invoke_tool("create_strategy_canvas", state.token, **payload)

    try:
        create_data = json.loads(create_result) if isinstance(create_result, str) else create_result
    except (json.JSONDecodeError, TypeError):
        return {"error": f"创建策略画布返回值格式错误: {create_result[:200]}", "success": False}

    if create_data.get("code") != 200:
        error_info = create_data.get("info", create_data.get("error", "未知错误"))
        print(f"[StrategyCreationSubgraph] create_strategy_canvas 失败: {error_info}")
        return {"error": f"创建策略画布失败: {error_info}", "success": False}

    # 从创建成功的响应中提取 strategy_id，用于后续验证
    strategy_id = create_data.get("info", 0)
    if isinstance(strategy_id, dict):
        strategy_id = strategy_id.get("strategyId", strategy_id.get("id", 0))
    strategy_id = int(strategy_id) if strategy_id else 0

    print(f"[StrategyCreationSubgraph] create_strategy_canvas code=200，strategy_id={strategy_id}")

    # ── 步骤 2: 验证策略画布已落库，断言 code=200 ──
    # 硬断言：必须通过 get_strategy_canvas_detail 二次确认，
    # 防止 LLM 幻觉式地宣称创建成功
    print(f"[StrategyCreationSubgraph] 调用 get_strategy_canvas_detail 验证")
    verify_result = _invoke_tool(
        "get_strategy_canvas_detail",
        state.token,
        strategyId=strategy_id,
    )

    try:
        verify_data = json.loads(verify_result) if isinstance(verify_result, str) else verify_result
    except (json.JSONDecodeError, TypeError):
        return {"error": "验证接口返回值格式错误", "success": False}

    if verify_data.get("code") != 200:
        print(f"[StrategyCreationSubgraph] get_strategy_canvas_detail code≠200，验证未通过")
        return {"error": "策略画布创建后验证未通过(详情接口 code≠200)", "success": False}

    print(f"[StrategyCreationSubgraph] creation_and_verify 完成: 创建 code=200 + 验证 code=200")

    return {
        "strategy_id": strategy_id,
        "output": f"策略画布创建成功并已验证落库(ID: {strategy_id})",
        "success": True,
    }


# ═══════════════════════════════════════════════════════════
#  条件路由函数
# ═══════════════════════════════════════════════════════════


def route_after_preparation(state: StrategyCreationState) -> str:
    """preparation 之后的条件路由：失败时直接结束，成功时流转到 decision。

    参数:
        state: 当前子图状态。

    返回:
        "decision" 或 "__end__"。
    """
    if state.error or not state.purpose_id or not state.client_group_id:
        print(
            f"[StrategyCreationSubgraph] preparation 后短路退出: "
            f"error={state.error!r}, purpose_id={state.purpose_id}, "
            f"client_group_id={state.client_group_id}"
        )
        return "__end__"
    return "decision"


def route_entry(state: StrategyCreationState) -> str:
    """子图入口路由：根据 phase 及历史反馈判断入口节点。

    功能:
        根据 state.phase 判断当前是哪个阶段的执行：
        - 首次执行：从准备阶段开始完整流程
        - 带修改意见：用户驳回方案后，回到准备阶段重新评估
        - 恢复执行：用户确认方案后，进入构建阶段

    参数:
        state: 当前子图状态。

    返回:
        目标节点名称字符串。
        - "preparation": 首次执行或带修改意见，从准备阶段开始
        - "construction": 用户确认后恢复，直接进入构建阶段
    """
    if state.phase == "resume_after_confirm":
        # PRD Phase 3 路径 A: 用户确认无误，跳过准备和决策，直接进入构建
        print("[StrategyCreationSubgraph] 恢复执行: 用户已确认方案，直接进入构建阶段")
        return "construction"

    if state.review_feedback:
        # PRD Phase 3 路径 B: 用户提出修改，带着反馈回到准备阶段重新评估
        print("[StrategyCreationSubgraph] 重新评估: 收到用户修改意见，从准备阶段重新开始")
        return "preparation"

    # 首次执行
    print("[StrategyCreationSubgraph] 首次执行: 从准备阶段开始")
    return "preparation"
