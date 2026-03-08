"""
规划节点
根据注册信息获取可用 Planner Agent，并以其身份执行规划，产出 PlanOutput
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..state import AgentState, PlanStep
from ...audit import start_node_trace, finish_node_trace, build_agent_snapshot
from ...config import get_settings
from ...registry import get_tool_registry, get_agent_registry


class PlanOutput(BaseModel):
    """
    功能: 规划输出容器
    """
    reasoning: str = Field(description="规划思路：简要分析用户需求，解释为什么采用这种任务组合和顺序")
    feasible: bool = Field(
        default=True,
        description="当前可用的 Executor 及其绑定的 Tool Cards 是否足以完成用户需求。"
                    "如果存在某个关键子任务无法被任何 Executor/Tool 覆盖，设为 false。"
    )
    infeasible_reason: str = Field(
        default="",
        description="当 feasible=false 时，说明哪些需求超出了当前 Executor/Tool 的能力范围，以及具体缺少什么能力。"
    )
    steps: list[PlanStep] = Field(default_factory=list, description="有序的任务执行步骤列表")


# 通用规划系统提示（当 Planner Agent 未配置 system_prompt 时作为后备）
_DEFAULT_PLANNER_SYSTEM_PROMPT = """你是一个任务规划专家。
你需要运用 Chain-of-Thought (思维链) 方法，将用户的需求拆解为清晰、有序的执行步骤。
你的核心价值在于"谋定而后动"，通过逻辑推演确保方案的专业性和可行性。"""

# 规划任务指令模板（作为 HumanMessage）
_PLANNER_TASK_PROMPT = """## 可用 Executor Agent 及其绑定工具
{tool_descriptions}

## 用户需求
{user_query}

{context}

## 注意事项
1. 步骤应该足够具体，可以直接执行
2. 步骤之间的依赖关系要明确
3. 每个步骤尽量只做一件事
4. 考虑失败情况的处理
5. **人机协同审核**：requires_review 表示该步骤执行完毕后，需要用户审核执行结论再决定是否继续，而不是执行前的授权确认。对于执行结论具有重要影响、用户需要知晓并确认的步骤（如：生成最终方案、产出关键分析报告、执行写操作或资金操作等），请将 requires_review 设为 true。纯粹的数据查询、信息收集等中间步骤通常不需要审核。
6. **能力边界评估（重要）**：在生成步骤前，你必须严格判断每一个子任务是否都有对应的 Executor 及 Tool Card 可以执行。
   - 如果用户需求中存在任何子任务，在上述可用 Executor/工具列表中找不到能完成它的能力，必须将 feasible 设为 false，并在 infeasible_reason 中详细说明缺少哪些能力。
   - 禁止在 feasible=false 时生成任何执行步骤（steps 应为空列表）。
   - 只有当所有子任务都有对应能力支撑时，才将 feasible 设为 true 并生成完整步骤。

## 执行计划 (JSON 输出要求)
每个步骤必须包含:
- step_id: 必须是字符串 (如 "1", "2")
- description: 步骤描述
- assigned_agent: 指定执行的 Executor Agent 名称（必须是上方列表中存在的 Agent）
- expected_tools: 预计需要的工具列表（必须是该 Executor 绑定的工具）
- dependencies: 依赖的步骤 ID 列表 (如 ["1"])
- requires_review: 步骤执行完毕后是否需要用户审核结论再继续 (布尔值，默认 false，仅对产出关键结果或执行写操作的最终步骤设为 true)
"""


def _build_context(state: AgentState) -> str:
    """
    功能: 构建上下文信息
    参数: state - 当前状态
    返回: 上下文字符串
    """
    context_parts = []

    if state.step_results:
        results_text = "\n".join([
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'} - {r.output or r.error}"
            for r in state.step_results
        ])
        context_parts.append(f"## 之前的执行结果\n{results_text}")

    if state.review_feedback:
        context_parts.append(f"## 人工审核反馈\n{state.review_feedback}")

    return "\n\n".join(context_parts) if context_parts else ""


async def planner_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能: 规划节点 - LangGraph 节点函数

    职责:
    1. 从注册中心加载选定的 Planner Agent 配置（system_prompt、bound_agents）
    2. 以该 Planner Agent 的身份构建规划上下文（可用工具 + 可用 Executor）
    3. 调用 LLM 生成结构化执行计划（PlanOutput）
    4. 若能力不足则直接告知用户，否则将计划写入 state 并路由回 dispatcher
    """
    query = state.query
    token = state.token
    current_planner = state.current_planner

    # 审计埋点
    nt = start_node_trace("planner")

    agent_registry = get_agent_registry()
    tool_registry = get_tool_registry()

    # 1. 加载选定 Planner Agent 的完整配置
    planner_config = agent_registry.get_agent(current_planner, token) if current_planner else None

    # 1a. 没有找到任何可用 Planner，直接告知用户
    if planner_config is None:
        reason = "当前没有可用的 Planner Agent，无法对您的需求进行任务规划。"
        print(f"[Planner] 无法找到 Planner Agent: {current_planner}")
        finish_node_trace(nt, "FAILED", node_result=reason)
        return Command(
            update={
                "error": reason,
                "node_traces": state.node_traces + [nt],
            },
            goto="responder",
        )

    # 2. 确定系统提示：优先使用 Planner Agent 自身的 system_prompt
    if planner_config.system_prompt:
        system_prompt = planner_config.system_prompt
        if planner_config.negative_prompt:
            system_prompt += f"\n\n## 禁止事项\n{planner_config.negative_prompt}"
    else:
        system_prompt = _DEFAULT_PLANNER_SYSTEM_PROMPT

    planner_name = current_planner
    print(f"[Planner] 使用 Planner Agent: {planner_name}")

    # 3. 构建可用 Executor 描述（严格限定为该 Planner 绑定的 Executor）
    bound_agents = planner_config.bound_agents
    all_executors = agent_registry.get_agent_descriptions(token, agent_type="EXECUTOR")
    agents = {name: desc for name, desc in all_executors.items() if name in bound_agents}

    # 1b. Planner 没有绑定任何可用 Executor，直接告知用户
    if not agents:
        reason = (
            f"Planner「{planner_name}」当前没有绑定任何可用的 Executor Agent，"
            "无法执行您的需求，请联系管理员配置相应的 Executor。"
        )
        print(f"[Planner] Planner '{planner_name}' 的 bound_agents={bound_agents}，均不在可用 Executor 列表中")
        finish_node_trace(nt, "FAILED", node_result=reason)
        return Command(
            update={
                "error": reason,
                "node_traces": state.node_traces + [nt],
            },
            goto="responder",
        )

    # 4. 构建工具描述：按 Executor 展示各自绑定的工具（让 Planner 了解能力边界）
    all_tool_summaries = {s["tool_name"]: s for s in tool_registry.get_all_tool_summaries(token)}
    tool_lines = []
    executor_tool_map: dict[str, list[str]] = {}  # {executor_name: [tool_name, ...]}
    for executor_name, executor_desc in agents.items():
        executor_config = agent_registry.get_agent(executor_name, token)
        if executor_config:
            executor_tools = executor_config.raw_bound_tools or []
            executor_tool_map[executor_name] = executor_tools
            tool_lines.append(f"\n### Executor: {executor_name}\n描述: {executor_desc}")
            if executor_tools:
                for tool_name in executor_tools:
                    summary = all_tool_summaries.get(tool_name)
                    if summary:
                        tool_lines.append(f"  - **{tool_name}**: {summary['tool_description']}")
            else:
                tool_lines.append("  （该 Executor 未绑定任何工具，仅具备纯对话能力）")
        else:
            executor_tool_map[executor_name] = []

    tool_descriptions = "\n".join(tool_lines) if tool_lines else "暂无可用 Executor/工具"

    # 5. 构建 HumanMessage（规划任务指令）
    human_content = _PLANNER_TASK_PROMPT.format(
        tool_descriptions=tool_descriptions,
        user_query=query,
        context=_build_context(state),
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    try:
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.llm_temperature,
            streaming=True,
        )

        structured_llm = llm.with_structured_output(PlanOutput)
        response: PlanOutput = await structured_llm.ainvoke(messages, config=config)

        # 6. LLM 自评不可行，直接告知用户
        if not response.feasible:
            reason = response.infeasible_reason or "当前可用的 Executor 及工具无法满足您的需求。"
            print(f"[Planner] LLM 评估能力不足: {reason}")
            finish_node_trace(nt, "FAILED", node_result=reason)
            return Command(
                update={
                    "error": reason,
                    "node_traces": state.node_traces + [nt],
                },
                goto="responder",
            )

        plan = response.steps

        # 7. 校验并修正每个步骤，同时收集真正无法被满足的步骤
        allowed_agents = set(agents.keys())
        unsupported_steps: list[str] = []

        for step in plan:
            # 7a. assigned_agent 必须在 bound_agents 中
            if step.assigned_agent and step.assigned_agent not in allowed_agents:
                print(f"[Planner] 警告: 步骤 [{step.step_id}] 指定了未绑定的 Agent '{step.assigned_agent}'，已清除")
                step.assigned_agent = None

            # 7b. expected_tools 必须属于对应 executor 绑定的工具
            if step.assigned_agent and step.expected_tools:
                allowed_tools = set(executor_tool_map.get(step.assigned_agent, []))
                if allowed_tools:
                    filtered = [t for t in step.expected_tools if t in allowed_tools]
                    if len(filtered) != len(step.expected_tools):
                        removed = set(step.expected_tools) - set(filtered)
                        print(f"[Planner] 警告: 步骤 [{step.step_id}] 包含超出 Executor 权限的工具 {removed}，已过滤")
                    step.expected_tools = filtered

            # 7c. 经过修正后，步骤既没有 assigned_agent 也没有任何可用工具覆盖
            if not step.assigned_agent:
                unsupported_steps.append(f"步骤[{step.step_id}]: {step.description}")

        # 8. 存在无法被任何 Executor 承接的步骤，告知用户
        if unsupported_steps:
            reason = (
                "以下任务步骤超出了当前可用 Executor/Tool 的能力范围，无法完成您的完整需求：\n"
                + "\n".join(f"  - {s}" for s in unsupported_steps)
                + "\n\n请联系管理员为相关业务配置对应的 Executor Agent 或 Tool Card。"
            )
            print(f"[Planner] 存在无法执行的步骤: {unsupported_steps}")
            finish_node_trace(nt, "FAILED", node_result=reason)
            return Command(
                update={
                    "error": reason,
                    "node_traces": state.node_traces + [nt],
                },
                goto="responder",
            )

        print(f"[Planner] LLM 响应内容: {response}")
        print(f"[Planner] 成功生成计划: {len(plan)} 个步骤")

        for step in plan:
            print(f"  - [{step.step_id}] {step.description} (Agent: {step.assigned_agent}, Tools: {step.expected_tools}, Deps: {step.dependencies})")

        # 审计埋点
        plan_result = f"生成 {len(plan)} 步计划: " + "; ".join([f"[{s.step_id}] {s.description}" for s in plan])
        agent_snap = build_agent_snapshot(
            agent_name=planner_name,
            model_config={"provider": "openai", "model_name": settings.llm_model},
            system_prompt=system_prompt,
            agent_result=plan_result,
        )
        finish_node_trace(nt, "SUCCESS", agent_snapshot=agent_snap, node_result=plan_result)

        return Command(
            update={
                "plan": plan,
                "plan_reasoning": response.reasoning,
                "current_step_index": 0,
                "messages": [AIMessage(content=f"[Planner:{planner_name}] 已生成 {len(plan)} 步计划")],
                "node_traces": state.node_traces + [nt],
            },
            goto="dispatcher"
        )

    except Exception as e:
        print(f"[Planner] 规划失败: {e}")
        finish_node_trace(nt, "FAILED")
        return Command(
            update={
                "plan": [],
                "error": f"任务规划失败: {str(e)}",
                "node_traces": state.node_traces + [nt],
            },
            goto="responder"
        )
