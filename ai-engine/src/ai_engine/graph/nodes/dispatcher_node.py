"""
调度中心节点
根据当前状态决定下一步路由：Planner / Executor / END
"""

from typing import Any, Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from ..state import AgentState, IntentType, IntentObject, PlanStep, ReviewStatus, StepStatus
from ...audit import start_node_trace, finish_node_trace
from ...config import get_settings
from ...registry import get_agent_registry

# Agent 选择 Prompt 模板
PLANNER_SELECTION_PROMPT = """你是一个智能调度专家。根据用户的意图，从可用的 Planner Agent 列表中选择最合适的一个来负责本次任务规划。

## 调度原则
1. **优先匹配专项 Planner**：如果意图明确属于某个业务领域，优先分配给对应的 Planner。
2. **默认 Planner**：如果意图广泛或找不到完全匹配的专项领域，选择带有"通用"或"系统"等标识的 Planner。

## 可用 Planner 列表
{agent_descriptions}

## 用户意图
{intent_description}

## 输出要求
请直接返回选中的 Planner 名称（agent_name），严禁输出任何解释性文字。

## 选择结果
"""

EXECUTOR_SELECTION_PROMPT = """你是一个任务分配专家(Planner的助手)。根据当前待执行的具体任务步骤，从 Planner 绑定的可用 Executor 列表中选择最合适的一个来执行该步骤。

## 分配原则
1. **最匹配原则**：选择职责描述最符合当前步骤要求的 Executor。
2. **兜底分配的 Executor**：如果没有最合适的，返回列表中第一个即可。

## 可用 Executor 列表
{agent_descriptions}

## 当前待执行任务步骤
{step_description}

## 输出要求
请直接返回选中的 Executor 名称（agent_name），严禁输出任何解释性文字。

## 选择结果
"""

def _get_fallback_agent(agent_names: list[str]) -> str | None:
    """获取回退 Agent"""
    if not agent_names:
        return None
    return agent_names[0]


async def _select_planner_agent(intent: IntentObject, token: str, config: RunnableConfig = None) -> str | None:
    """为全局意图选择合适的 Planner Agent"""
    agent_registry = get_agent_registry()
    descriptions = agent_registry.get_agent_descriptions(token, agent_type="PLANNER")
    agent_names = list(descriptions.keys())

    if not descriptions:
        print("[Dispatcher] 警告: 没有可用的 PLANNER Agent")
        return None
    
    if len(descriptions) == 1:
        return agent_names[0]
        
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=0.1,
        streaming=True
    )
    
    agent_desc_text = "\n".join([f"- **{name}**: {desc}" for name, desc in descriptions.items()])
    prompt = PLANNER_SELECTION_PROMPT.format(
        agent_descriptions=agent_desc_text,
        intent_description=f"意图类型: {intent.intent_type}\n实体: {intent.entities}"
    )
    
    try:
        print(f"[Dispatcher] LLM 选择 Planner，候选: {agent_names}")
        response = await llm.ainvoke(prompt, config=config)
        agent_name = response.content.strip()
        print(f"[Dispatcher] LLM 返回 Planner 选择: '{agent_name}'")
        if agent_name in descriptions:
            return agent_name
        print(f"[Dispatcher] Planner '{agent_name}' 不在候选列表，回退到: {agent_names[0]}")
        return _get_fallback_agent(agent_names)
    except Exception as e:
        print(f"[Dispatcher] Planner 选择失败: {e}")
        return _get_fallback_agent(agent_names)


async def _select_executor_agent(step: PlanStep, planner_name: str, token: str, config: RunnableConfig = None) -> str | None:
    """为任务步骤选择最合适的 bounded Executor Agent"""
    agent_registry = get_agent_registry()

    # 获取 Planner 的 bound_agents
    planner = agent_registry.get_agent(planner_name, token) if planner_name else None
    bound_agents = planner.bound_agents if planner else []

    # 获取所有的 Executor 描述，严格限定在 bound_agents 范围内
    all_executors = agent_registry.get_agent_descriptions(token, agent_type="EXECUTOR")
    descriptions = {name: desc for name, desc in all_executors.items() if name in bound_agents} if bound_agents else {}
    agent_names = list(descriptions.keys())

    if not descriptions:
        print(f"[Dispatcher] 警告: Planner '{planner_name}' 没有绑定任何可用的 EXECUTOR Agent")
        return None

    # 如果 step 已指定 agent，验证其是否在 bound_agents 范围内
    if step.assigned_agent:
        if step.assigned_agent in descriptions:
            return step.assigned_agent
        print(f"[Dispatcher] 警告: 步骤指定的 Agent '{step.assigned_agent}' 不在 Planner 绑定范围内，将重新选择")

    if len(descriptions) == 1:
        return agent_names[0]

    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=0.1,
        streaming=True
    )

    agent_desc_text = "\n".join([f"- **{name}**: {desc}" for name, desc in descriptions.items()])
    prompt = EXECUTOR_SELECTION_PROMPT.format(
        agent_descriptions=agent_desc_text,
        step_description=step.description,
    )

    try:
        print(f"[Dispatcher] LLM 选择 Executor，步骤: '{step.description[:50]}...' 候选: {agent_names}")
        response = await llm.ainvoke(prompt, config=config)
        agent_name = response.content.strip()
        print(f"[Dispatcher] LLM 返回 Executor 选择: '{agent_name}'")
        if agent_name in descriptions:
            return agent_name
        print(f"[Dispatcher] Executor '{agent_name}' 不在候选列表，回退到: {agent_names[0]}")
        return _get_fallback_agent(agent_names)
    except Exception as e:
        print(f"[Dispatcher] Executor 选择失败: {e}")
        return _get_fallback_agent(agent_names)

async def dispatcher_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能: 调度中心节点 - 负责路由决策和 Agent 选择
    
    路由逻辑（简化版）：
    - TASK 意图 → planner（需要规划的复杂任务）
    - CHAT 意图 → normal（闲聊、问答、澄清、引导等）
    - 有 plan 且未完成 → executor（继续执行）
    - plan 执行完毕 → responder（汇总结果）
    """
    # 审计埋点
    nt = start_node_trace("dispatcher")

    # 1. 路由决策逻辑
    intent = state.intent
    plan = state.plan
    require_review = state.require_review
    
    next_route = "normal"  # 默认走 normal 节点
    
    # 优先处理审核流程
    if require_review:
        next_route = "review"
    # 无意图时走 normal 兜底
    elif intent is None:
        next_route = "normal"
    # END 意图直接结束（理论上不会到这里，intent_recognition 已处理）
    elif intent.intent_type == IntentType.END:
        next_route = "__end__"
    # CHAT 意图 → normal 节点处理
    elif intent.intent_type == IntentType.CHAT:
        next_route = "normal"
    # TASK 意图 → 需要判断是否已有 plan
    elif intent.intent_type == IntentType.TASK:
        if plan is None or len(plan) == 0:
            # 无计划，需要规划
            next_route = "planner"
        else:
            current_index = state.current_step_index
            if current_index >= len(plan):
                # 计划执行完毕
                next_route = "__end__"
            else:
                # 检查当前步骤是否需要人机协同审核
                current_step = plan[current_index]
                has_feedback = bool(state.review_feedback)
                if current_step.requires_review and state.review_status != ReviewStatus.APPROVED and not has_feedback:
                    next_route = "review"
                    print(f"[Dispatcher] 步骤 {current_step.step_id} 需要人工审核确认")
                else:
                    if has_feedback:
                        print(f"[Dispatcher] 存在用户反馈，跳过审核，携带反馈重新执行步骤")
                    next_route = "executor"

    print(f"[Dispatcher] 路由决策: {next_route} (意图: {intent.intent_type.value if intent else 'None'})")
    
    # 2. 状态更新变量
    current_planner = state.current_planner
    current_executor = state.current_executor
    
    # 只有 TASK 意图且需要规划时才选择 Planner
    if next_route == "planner" and intent and intent.intent_type == IntentType.TASK:
        # 路由到 planner 之前，选择具体的 Planner Agent
        current_planner = await _select_planner_agent(intent, state.token, config=config)
        if current_planner:
            print(f"[Dispatcher] 选择 Planner: {current_planner}")

    if next_route == "executor":
        plan = state.plan or []
        current_index = state.current_step_index
        
        if plan and current_index < len(plan):
            current_step = plan[current_index]
            token = state.token
            current_executor = await _select_executor_agent(current_step, current_planner, token, config=config)
            if not current_executor:
                print(f"[Dispatcher] 警告: 无法为步骤 {current_step.step_id} 选择 Executor")
            else:
                print(f"[Dispatcher] 选择 Executor: {current_executor} 执行步骤: {current_step.description}")

    # 审计埋点：记录路由决策
    route_result = f"路由到: {next_route}"
    if current_planner and next_route == "planner":
        route_result += f", Planner: {current_planner}"
    if current_executor and next_route == "executor":
        route_result += f", Executor: {current_executor}"
    finish_node_trace(nt, "SUCCESS", node_result=route_result)

    # 3. 使用 Command 返回
    if next_route == "__end__":
        return Command(
            update={
                "current_executor": None,
                "messages": [AIMessage(content="[Dispatcher] 任务计划执行完毕，正在通过汇总节点生成响应...")],
                "node_traces": state.node_traces + [nt],
            },
            goto="responder"
        )
    elif next_route == "review":
        # 路由到 review 节点前（interrupt_before 会在此处暂停），
        # 生成对话式审核提示消息供用户阅读和回复
        plan_list = state.plan or []
        step_idx = state.current_step_index
        step_results_list = state.step_results

        current_step = plan_list[step_idx] if plan_list and step_idx < len(plan_list) else None

        # 找到最近一个需要审核的步骤结果
        pending_result = None
        for r in reversed(step_results_list):
            if r.require_review:
                pending_result = r
                break

        step_desc = current_step.description if current_step else "当前操作"
        result_output = (pending_result.output or "").strip() if pending_result else ""
        tools = pending_result.tools_called if pending_result else []

        review_parts = ["我已完成以下操作，需要您确认后才能继续：\n"]
        review_parts.append(f"**操作描述：** {step_desc}")
        if result_output:
            review_parts.append(f"\n**执行结果：**\n{result_output}")
        if tools:
            review_parts.append(f"\n**调用工具：** {', '.join(tools)}")
        review_parts.append(
            "\n\n请回复您的决定：\n"
            "- 回复「通过」或「确认」\u2192 批准并继续执行\n"
            "- 描述修改意见 \u2192 我将根据反馈调整方案"
        )
        review_msg = "\n".join(review_parts)

        return Command(
            update={
                "current_planner": current_planner,
                "current_executor": current_executor,
                "messages": [AIMessage(content=review_msg)],
                "node_traces": state.node_traces + [nt],
            },
            goto=next_route
        )
    else:
        return Command(
            update={
                "current_planner": current_planner,
                "current_executor": current_executor,
                "messages": [AIMessage(content=f"[Dispatcher] 路由到: {next_route}")],
                "node_traces": state.node_traces + [nt],
            },
            goto=next_route
        )
