"""
执行节点
执行当前计划步骤，调用 Agent 和工具
"""

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from langgraph.types import Command

from ..state import AgentState, PlanStep, StepResult, StepStatus
from ...config import get_settings
from ...registry import get_tool_registry, get_agent_registry


def _execute_step_with_agent(
    step: PlanStep,
    agent_name: str,
    query: str,
    token: str,
) -> StepResult:
    """
    功能: 使用指定 Agent 执行步骤
    参数:
        step - 当前计划步骤
        agent_name - Agent 名称
        query - 用户原始查询
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
        return _execute_step_default(step, query, token)
    
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
        # 调用 LLM (可能会触发工具调用)
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": execution_prompt},
        ]
        
        response = llm_with_tools.invoke(messages)
        
        # 检查是否有工具调用
        tools_called = []
        require_review = False
        
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_name = tool_call.get("name", "")
                tools_called.append(tool_name)
                
                # 检查是否为受保护工具
                if tool_registry.is_protected(tool_name, token):
                    require_review = True
                    print(f"[Executor] 触发受保护工具 '{tool_name}'，需要人工审核")
                
                # 执行工具调用
                tool = tool_registry.get_tool(tool_name, token)
                if tool:
                    try:
                        tool_args = tool_call.get("args", {})
                        tool_result = tool.invoke(tool_args)
                        print(f"[Executor] 工具 '{tool_name}' 执行结果: {tool_result[:200]}...")
                    except Exception as e:
                        print(f"[Executor] 工具 '{tool_name}' 执行失败: {e}")
        
        return StepResult(
            step_id=step.step_id,
            success=True,
            output=response.content or "步骤执行完成",
            tools_called=tools_called,
            require_review=require_review,
        )
    
    except Exception as e:
        print(f"[Executor] 步骤执行异常: {e}")
        return StepResult(
            step_id=step.step_id,
            success=False,
            error=str(e),
        )


def _execute_step_default(step: PlanStep, query: str, token: str) -> StepResult:
    """
    功能: 使用默认方式执行步骤（无特定 Agent）
    参数:
        step - 当前计划步骤
        query - 用户原始查询
        token - 用户身份 Token
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
    )
    
    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm
    
    execution_prompt = f"""请执行以下任务：
{step.description}

用户原始需求：{query}
"""
    
    try:
        response = llm_with_tools.invoke(execution_prompt)
        
        tools_called = []
        if hasattr(response, "tool_calls") and response.tool_calls:
            tools_called = [tc.get("name", "") for tc in response.tool_calls]
        
        return StepResult(
            step_id=step.step_id,
            success=True,
            output=response.content or "执行完成",
            tools_called=tools_called,
        )
    
    except Exception as e:
        return StepResult(
            step_id=step.step_id,
            success=False,
            error=str(e),
        )


def plan_task_execute_node(state: AgentState) -> dict[str, Any]:
    """
    功能: 执行节点 - LangGraph 节点函数
    参数: state - 当前状态
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
    selected_agent = state.selected_agent or "default"
    
    # 检查是否有待执行的步骤
    if not plan or current_index >= len(plan):
        return Command(
            update={
                "messages": [AIMessage(content="[Executor] 没有待执行的步骤")],
            },
            goto="dispatcher"
        )
    
    # 获取当前步骤
    current_step = plan[current_index]
    token = state.token
    print(f"[Executor] 执行步骤 {current_step.step_id} (Token: {token[:10] if token else 'None'}...): {current_step.description}")
    
    # 更新步骤状态
    current_step.status = StepStatus.IN_PROGRESS
    
    # 执行步骤
    token = state.token
    result = _execute_step_with_agent(
        step=current_step,
        agent_name=selected_agent or "default",
        query=query,
        token=token,
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
            },
            goto="dispatcher"
        )
    
    # 推进到下一步
    return Command(
        update={
            "step_results": step_results,
            "current_step_index": current_index + 1,
            "plan": plan,
            "messages": [AIMessage(content=result.output or f"[Executor] 步骤 {current_step.step_id} 执行完成")],
        },
        goto="dispatcher"
    )
