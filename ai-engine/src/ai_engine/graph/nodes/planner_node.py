"""规划节点。

根据注册信息获取可用 Planner Agent，并以其身份执行规划，产出 PlanOutput。
主流程分为四个阶段：前置校验 → 构建提示词 → 执行规划 → 结果验证。
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from ...llm_factory import create_creative_llm
from ...registry import get_agent_registry
from ..state import AgentState, PlanOutput, PlanStep

# ═══════════════════════════════════════════════════════════
#  Prompt 模板
# ═══════════════════════════════════════════════════════════

# 规划任务指令模板（单条 HumanMessage，动态注入 system_prompt）
_PLANNER_TASK_PROMPT = """
## 你的角色与职责
{system_prompt}

## 推理框架: Goal Decomposition（目标分解法）

你必须按照以下思维路径进行规划：
1. **明确最终目标**：用户到底想要达成什么？
2. **拆解子目标**：最终目标可以分解为哪些独立的子目标？
3. **映射 Executor**：每个子目标由哪个 Executor 承接？（以 Executor 为最小规划单位）
4. **编排依赖**：子目标之间的信息流转和先后顺序是什么？

## 当前阶段的动态信息

- 意图摘要：{intent_summary}
- 当前上下文：
{context}
- 可用 Executor 及其能力：
{executor_descriptions}
- 用户需求：{user_query}

## 核心规划协议 (The Planning Protocol)

### 阶段 1：能力边界校验 (Feasibility Assessment)
你必须首先充当"安全网"。仔细比对【用户需求】与【可用 Executor】的能力：
1. **严格阻断**：如果用户要求执行超出当前 Executor 能力范围的任务（例如：直接代客下单买卖基金、预测明天的大盘点位、查询未授权的外部新闻等），必须将 `feasible` 设为 `false`。
2. **说明原因**：在 `infeasible_reason` 中清晰、专业地向用户解释缺少什么特定的 Executor 能力导致无法执行。
3. **终止规划**：当 `feasible=false` 时，绝对不允许生成任何后续步骤（`steps` 必须为空列表）。

### 阶段 2：目标拆解与 Executor 分配 (Goal Decomposition & Assignment)
当需求可行（`feasible=true`）时，将最终目标拆解为子目标并分配 Executor。
1. **以 Executor 为最小规划单位（最重要）**：每个步骤（Step）对应**一个 Executor 的完整职责范围**。同一个 Executor 内部拥有自己的工作流和工具，这些内部子流程**必须合并为一个步骤**，由该 Executor 在执行时自主编排。绝对禁止将同一个 Executor 的内部工作流拆分成多个步骤。
   - 正确示例：Step 1 = "基金画像生成专家"获取基金画像 → Step 2 = "客户匹配专家"匹配客群标签 → Step 3 = "智能客群生成专家"预览并创建客群（一个步骤包含该 Executor 的全部工作）
   - 错误示例：Step 3 = "智能客群生成专家"预览客群 → Step 4 = "智能客群生成专家"创建客群（同一个 Executor 被拆成两步）
2. **信息流转与依赖 (`dependencies`)**：必须精准定义跨 Executor 步骤间的先后顺序。前一个 Executor 的输出会自动传递给后续步骤作为上下文，你只需确保依赖关系正确。
3. **步骤描述 (`description`)**：清晰描述该 Executor 需要完成的子目标是什么，而非指定它应该调用哪些工具。Executor 会根据子目标自主选择合适的工具。

### 阶段 3：人机协同与风控审核 (Human-in-the-loop)
你必须基于业务风险为每个步骤设定 `requires_review` 标志：
- **设为 `false`（自动流转）**：当该 Executor 的工作仅涉及数据查询、信息收集、内部计算和匹配逻辑，不产生写操作。
- **设为 `true`（强制阻断等待审核）**：当该 Executor 的工作流中**包含系统写操作**（如创建客群、创建策略等），或产出对业务有重大影响的最终结论时。审核时机是在该 Executor 完成全部工作之后。

## 输出要求 (JSON)

### plan_summary
用一句话概括整个计划，供用户和下游节点快速理解。

### 每个步骤必须包含:
- step_id: 必须是字符串 (如 "1", "2")
- description: 该步骤的子目标描述（描述要完成什么，而非怎么做）
- assigned_agent: 指定执行的 Executor 名称（必须是上方列表中存在的 Executor）
- dependencies: 依赖的步骤 ID 列表 (如 ["1"])
- requires_review: 步骤执行完毕后是否需要用户审核结论再继续 (布尔值)
"""


# ═══════════════════════════════════════════════════════════
#  阶段 1：前置校验
# ═══════════════════════════════════════════════════════════


def _preflight_check(
    state: AgentState,
) -> tuple[str | None, object | None, dict[str, str] | None]:
    """前置校验：加载 Planner 配置并验证 Executor 可用性。

    Returns:
        (error, planner_config, executor_descriptions) 三元组。
        error 非空时表示校验失败，调用方应直接返回错误。
    """
    agent_registry = get_agent_registry()
    current_planner = state.current_planner
    token = state.token

    # 加载 Planner Agent 配置
    planner_config = agent_registry.get_agent(current_planner, token) if current_planner else None
    if planner_config is None:
        print(f"[Planner] 无法找到 Planner Agent: {current_planner}")
        return "当前没有可用的 Planner Agent，无法对您的需求进行任务规划。", None, None

    # 检查绑定的 Executor
    agents = agent_registry.get_bound_executor_descriptions(token, current_planner)
    if not agents:
        print(
            f"[Planner] Planner '{current_planner}' 的 bound_agents="
            f"{planner_config.bound_agents}，均不在可用 Executor 列表中"
        )
        return (
            (
                f"Planner「{current_planner}」当前没有绑定任何可用的 Executor Agent，"
                "无法执行您的需求，请联系管理员配置相应的 Executor。"
            ),
            None,
            None,
        )

    print(f"[Planner] 使用 Planner Agent: {current_planner}")
    return None, planner_config, agents


# ═══════════════════════════════════════════════════════════
#  阶段 2：构建提示词
# ═══════════════════════════════════════════════════════════


def _build_replan_context(state: AgentState) -> str:
    """构建重规划上下文（仅在反馈重规划场景下有内容）。

    首次规划时 step_results 和 review_feedback 均为空，返回空字符串。
    反馈重规划时注入之前的执行结果和用户审核反馈，供 Planner 参考调整方案。
    """
    context_parts = []

    if state.step_results:
        results_text = "\n".join(
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'} - {r.output or r.error}"
            for r in state.step_results
        )
        context_parts.append(f"## 之前的执行结果\n{results_text}")

    if state.review_feedback:
        context_parts.append(f"## 人工审核反馈\n{state.review_feedback}")

    return "\n\n".join(context_parts) if context_parts else ""


def _build_prompt(state: AgentState, planner_config) -> str:
    """组装完整的规划 Prompt（角色定义 + 推理框架 + 动态信息）。"""
    system_prompt = planner_config.system_prompt or ""
    if planner_config.negative_prompt:
        system_prompt += f"\n\n## 禁止事项\n{planner_config.negative_prompt}"

    agent_registry = get_agent_registry()
    executor_descriptions = agent_registry.build_planner_tool_descriptions(
        state.token, state.current_planner
    )

    return _PLANNER_TASK_PROMPT.format(
        system_prompt=system_prompt,
        executor_descriptions=executor_descriptions,
        user_query=state.query,
        context=_build_replan_context(state),
        intent_summary=state.intent_summary or "",
    )


# ═══════════════════════════════════════════════════════════
#  阶段 3：执行规划（调用 LLM）
# ═══════════════════════════════════════════════════════════


async def _invoke_planner(prompt: str, config: RunnableConfig) -> PlanOutput:
    """调用 LLM 生成结构化执行计划。"""
    llm = create_creative_llm()
    structured_llm = llm.with_structured_output(PlanOutput)
    return await structured_llm.ainvoke([HumanMessage(content=prompt)], config=config)


# ═══════════════════════════════════════════════════════════
#  阶段 4：结果验证
# ═══════════════════════════════════════════════════════════


def _validate_plan(plan: list[PlanStep], allowed_agents: set[str]) -> str | None:
    """校验规划结果，返回错误信息或 None。

    校验规则：
    - 每个步骤的 assigned_agent 必须在 Planner 绑定的 Executor 列表中
    - 不满足条件的步骤收集为 unsupported，整体不可执行时返回错误原因
    """
    unsupported_steps: list[str] = []

    for step in plan:
        if step.assigned_agent and step.assigned_agent not in allowed_agents:
            print(
                f"[Planner] 警告: 步骤 [{step.step_id}] 指定了未绑定的 Agent "
                f"'{step.assigned_agent}'，已清除"
            )
            step.assigned_agent = None

        if not step.assigned_agent:
            unsupported_steps.append(f"步骤[{step.step_id}]: {step.description}")

    if unsupported_steps:
        return (
            "以下任务步骤超出了当前可用 Executor 的能力范围，无法完成您的完整需求：\n"
            + "\n".join(f"  - {s}" for s in unsupported_steps)
            + "\n\n请联系管理员为相关业务配置对应的 Executor Agent。"
        )

    return None


# ═══════════════════════════════════════════════════════════
#  主流程：LangGraph 节点函数
# ═══════════════════════════════════════════════════════════


def _fail(reason: str) -> Command:
    """构建失败路由 Command，统一出口。"""
    return Command(update={"error": reason}, goto="responder")


async def planner_node(state: AgentState, config: RunnableConfig) -> Command:
    """规划节点 — 主流程编排。

    四个阶段：
    1. 前置校验：加载 Planner 配置，验证 Executor 可用性
    2. 构建提示词：组装角色定义 + 推理框架 + 动态信息
    3. 执行规划：调用 LLM 生成 PlanOutput
    4. 结果验证：校验 assigned_agent 合法性
    """
    planner_name = state.current_planner

    # ── 阶段 1：前置校验 ──────────────────────────────────
    error, planner_config, agents = _preflight_check(state)
    if error:
        return _fail(error)

    # ── 阶段 2：构建提示词 ────────────────────────────────
    prompt = _build_prompt(state, planner_config)

    # ── 阶段 3：执行规划 ──────────────────────────────────
    try:
        response = await _invoke_planner(prompt, config)
    except Exception as e:
        print(f"[Planner] 规划失败: {e}")
        return _fail(f"任务规划失败: {e!s}")

    # LLM 自评不可行
    if not response.feasible:
        reason = response.infeasible_reason or "当前可用的 Executor 无法满足您的需求。"
        print(f"[Planner] LLM 评估能力不足: {reason}")
        return _fail(reason)

    # ── 阶段 4：结果验证 ──────────────────────────────────
    plan = response.steps
    validation_error = _validate_plan(plan, set(agents.keys()))
    if validation_error:
        print(f"[Planner] 计划验证失败: {validation_error}")
        return _fail(validation_error)

    # ── 成功：写入 state，路由到 dispatcher ───────────────
    print(f"[Planner] 成功生成计划: {len(plan)} 个步骤")
    for step in plan:
        print(
            f"  - [{step.step_id}] {step.description} "
            f"(Agent: {step.assigned_agent}, Deps: {step.dependencies})"
        )

    return Command(
        update={
            "plan": plan,
            "plan_reasoning": response.reasoning,
            "plan_summary": response.plan_summary,
            "current_step_index": 0,
            "messages": [AIMessage(content=f"[Planner:{planner_name}] 已生成 {len(plan)} 步计划")],
        },
        goto="dispatcher",
    )
