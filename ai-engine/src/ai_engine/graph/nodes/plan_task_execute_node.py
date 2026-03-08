"""
执行节点
执行当前计划步骤，调用 Agent 和工具
"""

import time
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI

from langgraph.types import Command

from ..state import AgentState, PlanStep, StepResult, StepStatus
from ...config import get_settings
from ...registry import get_tool_registry, get_agent_registry
from ...audit import (
    start_node_trace, finish_node_trace,
    build_agent_snapshot, build_tool_snapshot,
)
from langchain_core.callbacks.manager import adispatch_custom_event


async def _extract_conclusion(output: str, step_description: str, config: RunnableConfig = None) -> str:
    """
    功能: 从步骤完整输出中提取核心结论（去除推理过程），供人工审核时展示
    策略: 使用 LLM 精简，失败时回退到截断输出
    """
    if not output:
        return ""
    # 输出较短时无需调用 LLM
    if len(output) <= 300:
        return output
    try:
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=0.0,
            max_tokens=600,
        )
        prompt = (
            f"以下是 AI 完成「{step_description}」后的完整输出，其中包含分析推理过程和最终结论。\n\n"
            f"请提取其中的**核心结论**，以简洁的 Markdown 格式输出（保留关键数据和结论性语句），"
            f"去除推理分析过程。字数控制在 300 字以内。\n\n"
            f"完整输出：\n{output}"
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)], config=config)
        conclusion = response.content.strip()
        print(f"[Executor] 结论提取完成，原始长度={len(output)}，结论长度={len(conclusion)}")
        return conclusion
    except Exception as e:
        print(f"[Executor] 结论提取失败，回退截断: {e}")
        return output[:300] + "…"


async def _execute_with_tool_loop(
    llm_with_tools: Any,
    messages: list[Any],
    tool_registry: Any,
    token: str,
    config: RunnableConfig = None,
    max_iterations: int = 5
) -> tuple[str, list[str], list[dict]]:
    """
    功能: 通用的工具调用循环 (Async)
    返回: (最终输出, 调用的工具列表, 工具快照列表)
    
    注意: 工具照常执行，不在工具层中断。
    是否需要人工审核由步骤的 requires_review 字段决定，在步骤完成后由上层判断。
    """
    tools_called = []
    tool_trace_snapshots = []  # 工具调用快照列表（审计用）
    final_output = ""
    
    for iteration in range(max_iterations):
        print(f"[Executor] 工具循环第 {iteration + 1}/{max_iterations} 轮，LLM 请求中...")
        response = await llm_with_tools.ainvoke(messages, config=config)
        messages.append(response)

        # 检查是否有工具调用
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            final_output = response.content
            print(f"[Executor] 第 {iteration + 1} 轮无工具调用，LLM 直接返回，内容长度: {len(final_output or '')}")
            break

        print(f"[Executor] 第 {iteration + 1} 轮 LLM 请求 {len(response.tool_calls)} 个工具: {[tc.get('name') for tc in response.tool_calls]}")
        # 处理工具调用
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tools_called.append(tool_name)
            tool_start_ts = time.time()  # 工具调用计时开始
            tool_args = tool_call.get("args", {})
            print(f"[Executor] 调用工具 '{tool_name}'，参数: {tool_args}")

            # 从注册中心获取工具并执行
            tool = tool_registry.get_tool(tool_name, token)
            if tool:
                try:
                    tool_result = await tool.ainvoke(tool_args, config=config)
                    latency_ms = int((time.time() - tool_start_ts) * 1000)
                    result_str = str(tool_result) if tool_result is not None else "执行成功"
                    print(f"[Executor] 工具 '{tool_name}' 执行成功，耗时 {latency_ms}ms，返回: {result_str[:200]}")

                    messages.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=result_str
                    ))
                    # 审计：记录工具调用成功
                    tool_trace_snapshots.append(build_tool_snapshot(
                        tool_name=tool_name,
                        input_args=tool_args,
                        output_result=str(tool_result) if tool_result else None,
                        latency_ms=latency_ms,
                        status="SUCCESS",
                    ))
                except Exception as e:
                    latency_ms = int((time.time() - tool_start_ts) * 1000)
                    print(f"[Executor] 工具 '{tool_name}' 执行失败，耗时 {latency_ms}ms，错误: {e}")
                    messages.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=f"错误: {str(e)}"
                    ))
                    # 审计：记录工具调用失败
                    tool_trace_snapshots.append(build_tool_snapshot(
                        tool_name=tool_name,
                        input_args=tool_call.get("args", {}),
                        latency_ms=latency_ms,
                        status="FAILED",
                        error_message=str(e),
                    ))
            else:
                print(f"[Executor] 工具 '{tool_name}' 未在注册中心找到")
                messages.append(ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=f"错误: 找不到工具 {tool_name}"
                ))
    else:
        final_output = messages[-1].content if messages else "执行超时"

    return final_output, tools_called, tool_trace_snapshots


async def _execute_step_with_agent(
    step: PlanStep,
    agent_name: str,
    query: str,
    token: str,
    config: RunnableConfig = None,
    review_feedback: str = None,
    step_results: list[StepResult] = None,
    task_memory_summary: str = "",
) -> StepResult:
    """
    功能: 使用指定 Agent 执行步骤 (Async)
    参数:
        step - 当前计划步骤
        agent_name - Agent 名称
        query - 用户原始查询
        config - 运行时配置
        review_feedback - 用户审核反馈
        step_results - 之前步骤的执行结果（共享黑板）
        task_memory_summary - 历史相关任务记忆摘要（跨轮次上下文）
    返回: StepResult 执行结果
    """
    agent_registry = get_agent_registry()
    tool_registry = get_tool_registry()
    settings = get_settings()
    
    # 获取 Agent 配置
    agent_config = agent_registry.get_agent(agent_name, token)
    
    if agent_config is None:
        # 如果指定的 Agent 不存在，使用默认方式执行
        print(f"[Executor] Agent '{agent_name}' 不存在，使用默认执行方式")
        return await _execute_step_default(step, query, token, config, step_results)
    
    # 获取 Agent 可用的工具（严格限定为 bound_tools）
    tools = agent_config.get_tools(token)

    # 二次过滤：若 Planner 在步骤中明确指定了 expected_tools，
    # 则仅保留交集，确保 Executor 不会使用超出计划授权范围的工具
    if step.expected_tools:
        allowed = set(step.expected_tools)
        tools = [t for t in tools if t.name in allowed]

    # 构建系统消息（基于过滤后的工具列表，避免 system prompt 中展示超权工具）
    parts = []
    if agent_config.system_prompt:
        parts.append(agent_config.system_prompt)
    if agent_config.negative_prompt:
        parts.append(f"\n## 禁止事项\n{agent_config.negative_prompt}")
    if tools:
        tool_desc = "\n".join(f"- **{t.name}**: {t.description}" for t in tools)
        parts.append(f"\n## 可用工具\n{tool_desc}")
    system_message = "\n\n".join(parts) if parts else "你是一个任务执行助手，请完成分配给你的任务。"
    
    # 创建 LLM
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=settings.llm_temperature,
        streaming=True
    )
    
    # 如果有工具，绑定工具
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm
    
    # 构建执行 Prompt
    execution_prompt_parts = [
        f"## 当前任务\n{step.description}",
        f"\n## 用户原始需求\n{query}",
    ]

    # 历史任务记忆：如有相关历史结论可直接复用，避免重复调用工具
    if task_memory_summary:
        execution_prompt_parts.append(
            f"\n## 历史相关任务结论（可直接参考，无需重复查询相同数据）\n{task_memory_summary}"
        )
    
    # 共享黑板：加入之前步骤的执行结果，供当前步骤参考
    if step_results:
        prev_results_text = "\n".join([
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'}\n  输出: {r.output or r.error}"
            for r in step_results
        ])
        execution_prompt_parts.append(
            f"\n## 之前步骤的执行结果（重要参考）\n{prev_results_text}\n"
            "请充分利用上述步骤的产出信息来完成当前任务。"
        )
    
    # 如果有用户反馈，加入 Prompt 让 Agent 参考
    if review_feedback:
        execution_prompt_parts.append(
            f"\n## 用户修改意见（重要）\n{review_feedback}\n"
            "请根据上述反馈调整执行方式。"
        )
    
    execution_prompt_parts.append("\n请执行上述任务，必要时调用可用工具。完成后返回执行结果。")
    execution_prompt = "\n".join(execution_prompt_parts)
    
    try:
        # 初始消息列表
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=execution_prompt),
        ]
        
        # 进入工具循环
        output, tools_called, tool_trace_snapshots = await _execute_with_tool_loop(
            llm_with_tools=llm_with_tools,
            messages=messages,
            tool_registry=tool_registry,
            token=token,
            config=config
        )
        
        return StepResult(
            step_id=step.step_id,
            success=True,
            output=output or "步骤执行完成",
            tools_called=tools_called,
            require_review=False,
        ), tool_trace_snapshots, system_message
    
    except Exception as e:
        print(f"[Executor] 步骤执行异常: {e}")
        return StepResult(
            step_id=step.step_id,
            success=False,
            error=str(e),
        ), [], system_message


async def _execute_step_default(
    step: PlanStep, 
    query: str, 
    token: str,
    config: RunnableConfig = None,
    step_results: list[StepResult] = None,
) -> StepResult:
    """
    功能: 使用默认方式执行步骤（无特定 Agent）(Async)
    参数:
        step - 当前计划步骤
        query - 用户原始查询
        token - 用户身份 Token
        config - 运行时配置
        step_results - 之前步骤的执行结果（共享黑板）
    返回: StepResult 执行结果
    """
    settings = get_settings()
    tool_registry = get_tool_registry()
    
    # 获取所有公开工具
    tools = tool_registry.get_public_tools(token)
    
    # 创建 LLM
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=settings.llm_temperature,
        streaming=True
    )
    
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm
    
    # 构建执行 Prompt
    execution_prompt_parts = [
        f"请执行以下任务：\n{step.description}",
        f"\n用户原始需求：{query}",
    ]
    
    # 共享黑板：加入之前步骤的执行结果，供当前步骤参考
    if step_results:
        prev_results_text = "\n".join([
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'}\n  输出: {r.output or r.error}"
            for r in step_results
        ])
        execution_prompt_parts.append(
            f"\n## 之前步骤的执行结果（重要参考）\n{prev_results_text}\n"
            "请充分利用上述步骤的产出信息来完成当前任务。"
        )
    
    execution_prompt = "\n".join(execution_prompt_parts)
    
    # 默认模式的系统提示词
    default_system_prompt = execution_prompt

    try:
        # 初始消息列表
        messages = [
            HumanMessage(content=execution_prompt),
        ]
        
        # 默认模式也进入工具循环
        output, tools_called, tool_trace_snapshots = await _execute_with_tool_loop(
            llm_with_tools=llm_with_tools,
            messages=messages,
            tool_registry=tool_registry,
            token=token,
            config=config
        )
        
        return StepResult(
            step_id=step.step_id,
            success=True,
            output=output or "执行完成",
            tools_called=tools_called,
            require_review=False,
        ), tool_trace_snapshots, default_system_prompt
    
    except Exception as e:
        return StepResult(
            step_id=step.step_id,
            success=False,
            error=str(e),
        ), [], default_system_prompt



async def plan_task_execute_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能: 执行节点 - LangGraph 节点函数 (Async)
    参数: 
        state - 当前状态
        config - 运行时配置
    返回: 状态更新字典

    
    职责:
    1. 获取当前待执行的步骤
    2. 使用指定的 Agent 执行任务
    3. 调用必要的工具
    4. 检查是否需要人工审核
    5. 更新执行结果和步骤索引
    """
    plan = state.plan or []
    current_index = state.current_step_index
    query = state.query
    current_executor = state.current_executor
    
    # 检查是否有待执行的步骤
    if not plan or current_index >= len(plan):
        return Command(
            update={
                "messages": [AIMessage(content="[Executor] 没有待执行的步骤")],
            },
            goto="dispatcher"
        )
    
    # 检查是否有可用的 Agent
    if not current_executor:
        return Command(
            update={
                "error": "没有可用的 Agent 执行此步骤",
                "messages": [AIMessage(content="[Executor] 错误: 没有可用的 Agent")],
            },
            goto="dispatcher"
        )
    
    # 获取当前步骤
    current_step = plan[current_index]
    token = state.token
    print(f"[Executor] 执行步骤 {current_step.step_id} (Token: {token[:10] if token else 'None'}...): {current_step.description}")
    
    # 发送 Agent 开始事件
    agent_registry = get_agent_registry()
    agent_config = agent_registry.get_agent(current_executor, token)
    agent_alias = agent_config.alias if agent_config else current_executor
    
    await adispatch_custom_event("agent_start", {
        "agent": current_executor,
        "alias": agent_alias,
        "step_id": current_step.step_id,
    }, config=config)

    # 更新步骤状态
    current_step.status = StepStatus.IN_PROGRESS

    # 审计埋点
    nt = start_node_trace("executor")

    # 执行步骤
    token = state.token
    review_feedback = state.review_feedback  # 获取用户反馈（如有）
    previous_step_results = list(state.step_results)  # 共享黑板：之前步骤的执行结果
    task_memory_summary = state.context_task_memory_summary or ""  # 跨轮次历史记忆
    result, tool_trace_snapshots, used_system_prompt = await _execute_step_with_agent(
        step=current_step,
        agent_name=current_executor,
        query=query,
        token=token,
        config=config,
        review_feedback=review_feedback,
        step_results=previous_step_results,
        task_memory_summary=task_memory_summary,
    )

    # 发送 Agent 结束事件
    await adispatch_custom_event("agent_end", {
        "agent": current_executor,
        "step_id": current_step.step_id,
        "success": result.success,
    }, config=config)

    # 审计：构建 Agent 快照（包含工具调用详情、system_prompt 和 agent_result）
    settings = get_settings()
    agent_snap = build_agent_snapshot(
        agent_name=current_executor,
        model_config={"provider": "openai", "model_name": settings.llm_model},
        tools_snapshot=tool_trace_snapshots,
        system_prompt=used_system_prompt,
        agent_result=result.output if result.success else result.error,
    )
    finish_node_trace(
        nt,
        status="SUCCESS" if result.success else "FAILED",
        agent_snapshot=agent_snap,
        node_result=result.output if result.success else result.error,
    )

    # 更新步骤状态
    current_step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED

    # 收集执行结果
    step_results = list(state.step_results)
    step_results.append(result)

    # 审核触发条件（步骤执行完毕后判断）：
    # 1. 步骤自身 requires_review=True（由 Planner LLM 判断的关键输出步骤）
    # 2. 执行该步骤的 AgentCard 配置了 require_review=True（管理员在 Executor 级别配置的兜底审核）
    agent_requires_review = bool(agent_config and agent_config.require_review)
    if (current_step.requires_review or agent_requires_review) and result.success:
        current_step.status = StepStatus.NEEDS_REVIEW

        # 提取结论摘要（仅含核心结论，去除推理过程，供用户审核时阅读）
        conclusion = await _extract_conclusion(result.output, current_step.description, config)
        result = result.model_copy(update={"conclusion": conclusion})
        step_results[-1] = result

        print(f"[Executor] 步骤 {current_step.step_id} 标记为需要人工审核（步骤已执行完毕，等待确认）")
        return Command(
            update={
                "step_results": step_results,
                "require_review": True,
                "plan": plan,
                "messages": [AIMessage(content=f"[Executor] 步骤 {current_step.step_id} 执行完毕，等待人工审核确认")],
                "node_traces": state.node_traces + [nt],
            },
            goto="dispatcher"
        )

    # 推进到下一步，并重置 review_status/review_feedback
    return Command(
        update={
            "step_results": step_results,
            "current_step_index": current_index + 1,
            "plan": plan,
            "review_status": None,
            "review_feedback": None,
            "messages": [AIMessage(content=result.output or f"[Executor] 步骤 {current_step.step_id} 执行完成")],
            "node_traces": state.node_traces + [nt],
        },
        goto="dispatcher"
    )
