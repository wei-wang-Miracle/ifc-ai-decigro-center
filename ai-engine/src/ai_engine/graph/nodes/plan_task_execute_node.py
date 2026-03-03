"""
执行节点
执行当前计划步骤，调用 Agent 和工具
"""

import json
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


async def _execute_with_tool_loop(
    llm_with_tools: Any,
    messages: list[Any],
    tool_registry: Any,
    token: str,
    config: RunnableConfig = None,
    max_iterations: int = 5
) -> tuple[str, list[str], bool, list[dict]]:
    """
    功能: 通用的工具调用循环 (Async)
    返回: (最终输出, 调用的工具列表, 是否需要审核, 工具快照列表)
    """
    tools_called = []
    tool_trace_snapshots = []  # 工具调用快照列表（审计用）
    require_review = False
    final_output = ""
    
    
    for _ in range(max_iterations):
        response = await llm_with_tools.ainvoke(messages, config=config)
        messages.append(response)
        
        # 检查是否有工具调用
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            final_output = response.content
            break
            
        # 处理工具调用
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tools_called.append(tool_name)
            tool_start_ts = time.time()  # 工具调用计时开始
            
            # 1. 检查是否为受保护工具
            if tool_registry.is_protected(tool_name, token):
                require_review = True
                print(f"[Executor] 触发受保护工具 '{tool_name}'，需要人工审核")
            
            # 2. 从注册中心获取工具
            tool = tool_registry.get_tool(tool_name, token)
            if tool:
                try:
                    tool_args = tool_call.get("args", {})
                    tool_result = await tool.ainvoke(tool_args, config=config)
                    print(f"[Executor] 工具 '{tool_name}' 执行成功")
                    
                    messages.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=str(tool_result) if tool_result is not None else "执行成功"
                    ))
                    # 审计：记录工具调用成功
                    tool_trace_snapshots.append(build_tool_snapshot(
                        tool_name=tool_name,
                        input_args=tool_args,
                        output_result=str(tool_result) if tool_result else None,
                        latency_ms=int((time.time() - tool_start_ts) * 1000),
                        status="SUCCESS",
                    ))
                except Exception as e:
                    print(f"[Executor] 工具 '{tool_name}' 执行失败: {e}")
                    messages.append(ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=f"错误: {str(e)}"
                    ))
                    # 审计：记录工具调用失败
                    tool_trace_snapshots.append(build_tool_snapshot(
                        tool_name=tool_name,
                        input_args=tool_call.get("args", {}),
                        latency_ms=int((time.time() - tool_start_ts) * 1000),
                        status="FAILED",
                        error_message=str(e),
                    ))
            else:
                messages.append(ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=f"错误: 找不到工具 {tool_name}"
                ))
        
        # 如果触发了受保护工具，且当前逻辑是不允许自动执行这类工具
        # 在这里我们可以选择中止循环并返回当前的 LLM 响应
        if require_review:
            final_output = response.content or "触发受保护操作，需要人工确认"
            break
    else:
        final_output = messages[-1].content if messages else "执行超时"

    return final_output, tools_called, require_review, tool_trace_snapshots


async def _execute_step_with_agent(
    step: PlanStep,
    agent_name: str,
    query: str,
    token: str,
    config: RunnableConfig = None,
) -> StepResult:
    """
    功能: 使用指定 Agent 执行步骤 (Async)
    参数:
        step - 当前计划步骤
        agent_name - Agent 名称
        query - 用户原始查询
        config - 运行时配置
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
        return await _execute_step_default(step, query, token, config)
    
    # 获取 Agent 可用的工具
    tools = agent_config.get_tools(token)
    
    # 构建系统消息
    system_message = agent_config.build_system_message(token)
    
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
    execution_prompt = f"""## 当前任务
{step.description}

## 用户原始需求
{query}

请执行上述任务，必要时调用可用工具。完成后返回执行结果。
"""
    
    try:
        # 初始消息列表
        messages = [
            SystemMessage(content=system_message),
            HumanMessage(content=execution_prompt),
        ]
        
        # 进入工具循环
        output, tools_called, require_review, tool_trace_snapshots = await _execute_with_tool_loop(
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
            require_review=require_review,
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
    config: RunnableConfig = None
) -> StepResult:
    """
    功能: 使用默认方式执行步骤（无特定 Agent）(Async)
    参数:
        step - 当前计划步骤
        query - 用户原始查询
        token - 用户身份 Token
        config - 运行时配置
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
    
    execution_prompt = f"""请执行以下任务：
{step.description}

用户原始需求：{query}
"""
    
    # 默认模式的系统提示词
    default_system_prompt = execution_prompt

    try:
        # 初始消息列表
        messages = [
            HumanMessage(content=execution_prompt),
        ]
        
        # 默认模式也进入工具循环
        output, tools_called, require_review, tool_trace_snapshots = await _execute_with_tool_loop(
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
            require_review=require_review,
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
    result, tool_trace_snapshots, used_system_prompt = await _execute_step_with_agent(
        step=current_step,
        agent_name=current_executor,
        query=query,
        token=token,
        config=config,
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
    if result.require_review:
        current_step.status = StepStatus.NEEDS_REVIEW

    # 收集执行结果
    step_results = list(state.step_results)
    step_results.append(result)

    # 如果需要审核，设置标记但不推进索引
    if result.require_review:
        return Command(
            update={
                "step_results": step_results,
                "require_review": True,
                "plan": plan,
                "messages": [AIMessage(content=f"[Executor] 步骤 {current_step.step_id} 需要人工审核")],
                "node_traces": state.node_traces + [nt],
            },
            goto="dispatcher"
        )

    # 推进到下一步，并重置 review_status 以便下一个需要审核的步骤能正确触发
    return Command(
        update={
            "step_results": step_results,
            "current_step_index": current_index + 1,
            "plan": plan,
            "review_status": None,
            "messages": [AIMessage(content=result.output or f"[Executor] 步骤 {current_step.step_id} 执行完成")],
            "node_traces": state.node_traces + [nt],
        },
        goto="dispatcher"
    )
