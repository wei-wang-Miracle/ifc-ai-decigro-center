"""
调度中心节点
根据当前状态决定下一步路由：Planner / Executor / END
"""

from typing import Any, Literal

from langchain_core.messages import AIMessage
from langgraph.types import Command

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


def dispatcher_node(state: AgentState) -> Command:
    """
    功能: 调度中心节点 - 负责路由决策和 Agent 选择
    """
    # 1. 路由决策逻辑 (原 _get_next_route)
    intent = state.get("intent")
    plan = state.get("plan")
    require_review = state.get("require_review", False)
    
    next_route = "intent"  # 默认返回意图识别
    
    if require_review:
        next_route = "review"
    elif intent is None:
        next_route = "intent"
    elif intent.intent_type == IntentType.END or intent.intent_type == IntentType.INVALID:
        next_route = "__end__"
    elif plan is None or len(plan) == 0:
        next_route = "planner"
    else:
        current_index = state.get("current_step_index", 0)
        if current_index >= len(plan):
            next_route = "__end__"
        else:
            next_route = "executor"

    print(f"[Dispatcher] 路由决策: {next_route}")
    
    # 2. 如果是跳转到执行器，选择具体的 Agent
    selected_agent = None
    if next_route == "executor":
        plan = state.get("plan", [])
        current_index = state.get("current_step_index", 0)
        
        if plan and current_index < len(plan):
            current_step = plan[current_index]
            selected_agent = _select_agent_for_step(current_step)
            print(f"[Dispatcher] 选择 Agent: {selected_agent} 执行步骤: {current_step.description}")

    # 3. 使用 Command 返回
    return Command(
        update={
            "selected_agent": selected_agent,
            "messages": [AIMessage(content=f"[Dispatcher] 路由到: {next_route}")],
        },
        goto=next_route
    )
