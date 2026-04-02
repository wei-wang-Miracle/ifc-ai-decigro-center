"""调度中心节点（Dispatcher）— Graph 的交通枢纽。

唯一职责：根据 State 中的信号做路由决策，将控制流转发到正确的下游节点。

不做的事：
- 不调用 LLM（零延迟、零 token 消耗）
- 不构建面向用户的消息（展示职责归各下游节点）
- 不做 Agent 选择（Planner 由意图识别节点选定，Executor 由 Planner 规划时指定）

路由决策表（按优先级从高到低）：
┌─────────────────────────────────────┬────────────┐
│ 条件                                │ 目标节点    │
├─────────────────────────────────────┼────────────┤
│ require_review = True               │ review     │
│ intent = None                       │ normal     │
│ intent = END                        │ __end__    │
│ intent = CHAT                       │ normal     │
│ intent = TASK & 无 plan             │ planner    │
│ intent = TASK & plan 全部完成        │ responder  │
│ intent = TASK & plan 有未完成步骤    │ executor   │
└─────────────────────────────────────┴────────────┘

State 写入：
- current_planner : 路由到 planner 时，从 intent.matched_planners[0] 读取
- current_executor: 路由到 executor 时，从 plan[current_step_index].assigned_agent 读取
"""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from ..state import AgentState, IntentType


async def dispatcher_node(state: AgentState, config: RunnableConfig) -> Command:
    """调度中心 — 纯路由节点，不调用 LLM。"""

    intent = state.intent
    plan = state.plan
    current_planner = state.current_planner
    current_executor = state.current_executor

    # ── 路由决策 + Agent 读取 ───────────────────────────
    if state.require_review:
        next_node = "review"

    elif intent is None:
        next_node = "normal"

    elif intent.intent_type == IntentType.END:
        next_node = "__end__"

    elif intent.intent_type == IntentType.CHAT:
        next_node = "normal"

    elif intent.intent_type == IntentType.TASK:
        if not plan:
            # 首次进入 TASK：路由到 planner，从意图识别结果中读取 Planner
            next_node = "planner"
            current_planner = intent.matched_planners[0]

        elif state.current_step_index >= len(plan):
            # plan 全部执行完毕：路由到 responder 汇总
            next_node = "__end__"

        else:
            # plan 有未完成步骤：路由到 executor，从 PlanStep 中读取 Executor
            next_node = "executor"
            current_step = plan[state.current_step_index]
            current_executor = current_step.assigned_agent

    else:
        next_node = "normal"

    print(f"[Dispatcher] {next_node} (intent={intent.intent_type.value if intent else 'None'})")

    # ── 构建 Command ───────────────────────────────────
    if next_node == "__end__":
        return Command(
            update={
                "current_executor": None,
                "messages": [AIMessage(content="[Dispatcher] 计划执行完毕，路由到 responder")],
            },
            goto="responder",
        )

    return Command(
        update={
            "current_planner": current_planner,
            "current_executor": current_executor,
            "messages": [AIMessage(content=f"[Dispatcher] → {next_node}")],
        },
        goto=next_node,
    )
