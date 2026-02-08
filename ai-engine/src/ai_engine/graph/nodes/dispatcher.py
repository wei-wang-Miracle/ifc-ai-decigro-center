"""
调度中心节点
根据当前状态决定下一步路由：Planner / Executor / END
"""

from typing import Any, Literal

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from ..state import AgentState, IntentType, PlanStep, StepStatus
from ...config import get_settings
from ...registry import get_agent_registry


# Agent 选择 Prompt 模板
AGENT_SELECTION_PROMPT = """你是一个智能调度专家。根据当前任务步骤，从可用的 Agent 列表中选择最合适的执行者。

## 可用 Agent
{agent_descriptions}

## 当前任务步骤
{step_description}

## 输出要求
请直接返回最合适的 Agent 名称（agent_name），不要返回其他内容。
如果没有合适的 Agent，返回 "default"。

## 选择结果
"""


def _get_next_route(state: AgentState) -> Literal["planner", "executor", "review", "end", "intent"]:
    """
    功能: 根据当前状态决定下一步路由
    参数: state - 当前状态
    返回: 路由目标节点名称
    """
    intent = state.get("intent")
    plan = state.get("plan")
    require_review = state.get("require_review", False)
    
    # 如果需要人工审核
    if require_review:
        return "review"
    
    # 意图检查
    if intent is None:
        return "intent"
    
    # 如果是结束意图
    if intent.intent_type == IntentType.END:
        return "end"
    
    # 如果是无效意图
    if intent.intent_type == IntentType.INVALID:
        return "end"
    
    # 如果没有计划，需要规划
    if plan is None or len(plan) == 0:
        return "planner"
    
    # 检查是否所有步骤都已完成
    current_index = state.get("current_step_index", 0)
    if current_index >= len(plan):
        return "end"
    
    # 否则执行当前步骤
    return "executor"


def _select_agent_for_step(step: PlanStep) -> str:
    """
    功能: 为任务步骤选择最合适的 Agent
    参数: step - 当前计划步骤
    返回: Agent 名称
    """
    # 如果步骤已经指定了 Agent，直接使用
    if step.assigned_agent:
        return step.assigned_agent
    
    agent_registry = get_agent_registry()
    descriptions = agent_registry.get_agent_descriptions()
    
    if not descriptions:
        return "default"
    
    # 构建 Agent 描述文本
    agent_desc_text = "\n".join([
        f"- **{name}**: {desc}"
        for name, desc in descriptions.items()
    ])
    
    # 使用 LLM 选择 Agent
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=0.1,  # 调度推荐低温度
    )
    
    prompt = AGENT_SELECTION_PROMPT.format(
        agent_descriptions=agent_desc_text,
        step_description=step.description,
    )
    
    try:
        response = llm.invoke(prompt)
        agent_name = response.content.strip()
        
        # 验证返回的 Agent 是否存在
        if agent_name in descriptions:
            return agent_name
        return "default"
    except Exception as e:
        print(f"[Dispatcher] Agent 选择失败: {e}")
        return "default"


def dispatcher_node(state: AgentState) -> dict[str, Any]:
    """
    功能: 调度中心节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典
    
    职责:
    1. 根据当前状态决定路由（Planner / Executor / END）
    2. 如果需要执行任务，选择合适的 Agent
    3. 更新状态中的路由信息
    """
    # 获取下一步路由
    next_route = _get_next_route(state)
    
    print(f"[Dispatcher] 路由决策: {next_route}")
    
    # 如果是执行路由，需要选择 Agent
    selected_agent = None
    if next_route == "executor":
        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        if plan and current_index < len(plan):
            current_step = plan[current_index]
            selected_agent = _select_agent_for_step(current_step)
            print(f"[Dispatcher] 选择 Agent: {selected_agent} 执行步骤: {current_step.description}")
    
    return {
        "selected_agent": selected_agent,
        "messages": [AIMessage(content=f"[Dispatcher] 路由到: {next_route}")],
    }


def dispatcher_route_decision(state: AgentState) -> Literal["planner", "executor", "review", "end", "intent"]:
    """
    功能: 调度路由决策函数 - 用于 LangGraph conditional_edges
    参数: state - 当前状态
    返回: 目标节点名称
    """
    return _get_next_route(state)
