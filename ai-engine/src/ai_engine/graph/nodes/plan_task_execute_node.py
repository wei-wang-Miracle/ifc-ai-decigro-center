"""执行节点。

每次执行当前计划中的一个步骤：加载对应 Executor Agent 的角色定义和工具，
通过 ReAct 工具循环完成子目标，产出 StepResult。

主流程五阶段：前置校验 → 步骤执行 → 观察评估 → 审核判定 → 构建返回。
"""

import time
from typing import Any

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from pydantic import BaseModel, Field

from ...llm_factory import create_creative_llm, create_deterministic_llm, create_extraction_llm
from ...registry import get_agent_registry, get_tool_registry
from ..state import AgentState, EvalVerdict, PlanStep, StepResult, StepStatus

# ═══════════════════════════════════════════════════════════
#  结论提取（审核场景）
# ═══════════════════════════════════════════════════════════


async def _extract_conclusion(
    output: str,
    step_description: str,
    tools_called: list[str] | None = None,
    config: RunnableConfig = None,
) -> str:
    """从完整输出中提取结构化结论，供人工审核时展示。

    输出三段式结构: 执行动作 → 核心结论 → 置信度与风险。
    短输出直接返回；长输出通过 LLM 结构化提取，失败时回退截断。
    """
    if not output:
        return ""
    if len(output) <= 300:
        return output

    tools_desc = f"实际调用的工具: {', '.join(tools_called)}" if tools_called else "未调用任何工具"
    try:
        llm = create_extraction_llm(max_tokens=800)
        prompt = (
            f"以下是 AI 完成「{step_description}」后的完整输出。\n\n"
            f"工具调用情况: {tools_desc}\n\n"
            f"请按以下三段式结构提取，使用 Markdown 格式，总字数控制在 400 字以内:\n\n"
            f"**执行动作**: 做了什么(调用了哪些工具、查询了什么数据、执行了什么操作)，一两句话概括。\n\n"
            f"**核心结论**: 得出了什么结果(保留关键数据和结论性语句)，去除推理分析过程。\n\n"
            f"**置信度与风险**: 结论的可靠程度如何，数据来源是否充分，有哪些不确定性或潜在风险需要关注。"
            f"如果数据完全来自工具调用则置信度高；如果部分结论缺乏数据支撑则明确指出。\n\n"
            f"完整输出:\n{output}"
        )
        response = await llm.ainvoke([HumanMessage(content=prompt)], config=config)
        conclusion = response.content.strip()
        print(f"[Executor] 结论提取完成，原始长度={len(output)}，结论长度={len(conclusion)}")
        return conclusion
    except Exception as e:
        print(f"[Executor] 结论提取失败，回退截断: {e}")
        return output[:300] + "…"


# ═══════════════════════════════════════════════════════════
#  执行结果观察评估（反馈循环 — 观察层）
# ═══════════════════════════════════════════════════════════

# 套话/拒绝模式关键词，命中即判定输出无实质内容
_HOLLOW_PATTERNS = ["我无法", "作为AI", "我没有能力", "抱歉，我无法", "我不能直接"]


class _EvalResult(BaseModel):
    """评估结果：三路分流判定。"""

    verdict: EvalVerdict
    reason: str = ""
    feedback: str = ""  # 纠偏提示，RETRY 时注入重试 prompt


class _SemanticEvalOutput(BaseModel):
    """语义校验 LLM 的 structured output schema。"""

    goal_achieved: bool = Field(description="输出是否回答了步骤目标的核心要求")
    data_credible: bool = Field(description="输出中的数据是否有工具调用支撑，无编造嫌疑")
    reason: str = Field(description="判断理由，一句话")


def _rule_check(
    result: StepResult,
    agent_has_tools: bool,
) -> _EvalResult | None:
    """规则校验(确定性，零 LLM 成本)。

    返回 None 表示规则校验通过，需继续语义校验。
    """
    output = (result.output or "").strip()

    # R1: 输出非空且非套话
    if not output:
        return _EvalResult(
            verdict=EvalVerdict.RETRY,
            reason="输出为空",
            feedback="上一次执行未产出任何内容，请重新执行任务并确保输出有实质结果。",
        )
    if any(p in output for p in _HOLLOW_PATTERNS):
        return _EvalResult(
            verdict=EvalVerdict.RETRY,
            reason="输出命中拒绝模式",
            feedback="上一次执行输出了拒绝/无能力声明，请使用可用工具完成任务而非拒绝。",
        )

    # R2: 工具调用一致性 — Agent 配了工具但一个都没调
    if agent_has_tools and not result.tools_called:
        return _EvalResult(
            verdict=EvalVerdict.RETRY,
            reason="Agent 配置了工具但未调用任何工具",
            feedback="上一次执行未调用任何工具。请使用可用工具获取真实数据，不要凭空生成答案。",
        )

    return None


async def _semantic_check(
    result: StepResult,
    step: PlanStep,
    config: RunnableConfig = None,
) -> _EvalResult:
    """语义校验(需要一次轻量 LLM 调用)。

    检查目标达成度和数据可信度，返回三路判定。
    """
    tools_desc = (
        f"实际调用的工具: {', '.join(result.tools_called)}"
        if result.tools_called
        else "未调用任何工具"
    )
    prompt = (
        f"你是一个执行结果质量审查员。请判断以下步骤的执行输出是否达标。\n\n"
        f"## 步骤目标\n{step.description}\n\n"
        f"## 工具调用情况\n{tools_desc}\n\n"
        f"## 执行输出\n{result.output[:2000]}\n\n"
        f"请判断:\n"
        f"1. goal_achieved: 输出是否回答了步骤目标的核心要求(不要求完美，但必须有实质性回答)\n"
        f"2. data_credible: 输出中涉及的具体数据/数值是否有工具调用支撑。"
        f"如果输出包含精确数据但未调用相关工具，则不可信。"
        f"如果输出仅是文本分析/建议且不涉及精确数据，则视为可信。"
    )
    try:
        llm = create_deterministic_llm(temperature=0.1, streaming=False, max_tokens=200)
        structured_llm = llm.with_structured_output(_SemanticEvalOutput)
        eval_output: _SemanticEvalOutput = await structured_llm.ainvoke(
            [HumanMessage(content=prompt)], config=config
        )
        print(
            f"[Executor] 语义校验: goal={eval_output.goal_achieved}, "
            f"credible={eval_output.data_credible}, reason={eval_output.reason}"
        )

        if not eval_output.goal_achieved:
            return _EvalResult(
                verdict=EvalVerdict.RETRY,
                reason=eval_output.reason,
                feedback=f"上一次执行未达成步骤目标。问题: {eval_output.reason}。请重新执行并确保回答步骤要求。",
            )
        if not eval_output.data_credible:
            return _EvalResult(
                verdict=EvalVerdict.ESCALATE,
                reason=eval_output.reason,
                feedback=f"数据可信度存疑: {eval_output.reason}",
            )
        return _EvalResult(verdict=EvalVerdict.PASS, reason=eval_output.reason)

    except Exception as e:
        # 语义校验失败时保守放行，不阻塞主流程
        print(f"[Executor] 语义校验异常，保守放行: {e}")
        return _EvalResult(verdict=EvalVerdict.PASS, reason=f"语义校验异常，保守放行: {e}")


async def _evaluate_result(
    result: StepResult,
    step: PlanStep,
    agent_has_tools: bool,
    config: RunnableConfig = None,
) -> _EvalResult:
    """执行结果观察评估 — 反馈循环的"观察+对比"环节。

    分两层: 规则校验(零成本) → 语义校验(一次 LLM 调用)。
    仅对执行成功的结果进行评估，失败结果直接跳过。
    """
    # 执行失败的结果不评估，直接放行(由原有失败处理逻辑兜底)
    if not result.success:
        return _EvalResult(verdict=EvalVerdict.PASS, reason="执行失败，跳过评估")

    # 第一层: 规则校验
    rule_result = _rule_check(result, agent_has_tools)
    if rule_result:
        print(f"[Executor] 规则校验未通过: {rule_result.verdict.value} - {rule_result.reason}")
        return rule_result

    # 第二层: 语义校验
    return await _semantic_check(result, step, config)


# ═══════════════════════════════════════════════════════════
#  ReAct 工具循环
# ═══════════════════════════════════════════════════════════


async def _execute_with_tool_loop(
    llm_with_tools: Any,
    messages: list[Any],
    tool_registry: Any,
    token: str,
    config: RunnableConfig = None,
    max_iterations: int = 8,
) -> tuple[str, list[str]]:
    """ReAct 工具调用循环：LLM 思考 → 调用工具 → 观察结果 → 继续或结束。

    每轮 LLM 可请求多个工具调用，全部执行后进入下一轮，
    直到 LLM 不再请求工具（产出最终回答）或达到最大轮次。

    Returns:
        (final_output, tools_called) — 最终文本输出和实际调用的工具名称列表。
    """
    tools_called = []
    final_output = ""

    for iteration in range(max_iterations):
        print(f"[Executor] 工具循环第 {iteration + 1}/{max_iterations} 轮，LLM 请求中...")
        response = await llm_with_tools.ainvoke(messages, config=config)
        messages.append(response)

        # LLM 未请求工具调用 → 产出最终回答，退出循环
        if not (hasattr(response, "tool_calls") and response.tool_calls):
            final_output = response.content
            print(
                f"[Executor] 第 {iteration + 1} 轮无工具调用，LLM 直接返回，"
                f"内容长度: {len(final_output or '')}"
            )
            break

        print(
            f"[Executor] 第 {iteration + 1} 轮 LLM 请求 "
            f"{len(response.tool_calls)} 个工具: "
            f"{[tc.get('name') for tc in response.tool_calls]}"
        )

        # 逐个执行工具调用，将结果以 ToolMessage 追加到消息列表
        for tool_call in response.tool_calls:
            tool_name = tool_call.get("name", "")
            tools_called.append(tool_name)
            tool_start_ts = time.time()
            tool_args = tool_call.get("args", {})
            print(f"[Executor] 调用工具 '{tool_name}'，参数: {tool_args}")

            tool = tool_registry.get_tool(tool_name, token)
            if tool:
                try:
                    tool_result = await tool.ainvoke(tool_args, config=config)
                    latency_ms = int((time.time() - tool_start_ts) * 1000)
                    result_str = str(tool_result) if tool_result is not None else "执行成功"
                    print(
                        f"[Executor] 工具 '{tool_name}' 执行成功，"
                        f"耗时 {latency_ms}ms，返回: {result_str[:200]}"
                    )
                    messages.append(ToolMessage(tool_call_id=tool_call["id"], content=result_str))
                except Exception as e:
                    latency_ms = int((time.time() - tool_start_ts) * 1000)
                    print(f"[Executor] 工具 '{tool_name}' 执行失败，耗时 {latency_ms}ms，错误: {e}")
                    messages.append(
                        ToolMessage(tool_call_id=tool_call["id"], content=f"错误: {e!s}")
                    )
            else:
                print(f"[Executor] 工具 '{tool_name}' 未在注册中心找到")
                messages.append(
                    ToolMessage(
                        tool_call_id=tool_call["id"],
                        content=f"错误: 找不到工具 {tool_name}",
                    )
                )
    else:
        # 达到最大轮次仍未结束，取最后一条消息内容
        final_output = messages[-1].content if messages else "执行超时"

    return final_output, tools_called


# ═══════════════════════════════════════════════════════════
#  步骤执行（Prompt 构建 + 工具循环）
# ═══════════════════════════════════════════════════════════


async def _execute_step_with_agent(
    step: PlanStep,
    agent_name: str,
    query: str,
    token: str,
    config: RunnableConfig = None,
    review_feedback: str = None,
    eval_feedback: str = None,
    step_results: list[StepResult] = None,
    task_memory_summary: str = "",
) -> StepResult:
    """使用指定 Executor Agent 执行一个计划步骤。

    将 Agent 的角色定义（system_prompt + 工具描述）和执行指令
    合并为单条 HumanMessage，通过 ReAct 工具循环完成子目标。

    Args:
        step: 当前计划步骤（含 description、assigned_agent 等）
        agent_name: Executor Agent 名称
        query: 用户原始查询
        token: 用户身份 Token
        config: LangGraph 运行时配置
        review_feedback: 用户审核反馈（驳回重试场景）
        eval_feedback: 系统校验反馈（观察层内部重试场景）
        step_results: 之前步骤的执行结果（共享黑板，跨步骤信息传递）
        task_memory_summary: 历史相关任务记忆摘要（跨轮次上下文）
    """
    agent_registry = get_agent_registry()
    tool_registry = get_tool_registry()

    agent_config = agent_registry.get_agent(agent_name, token)
    if agent_config is None:
        print(f"[Executor] Agent '{agent_name}' 不存在")
        return StepResult(step_id=step.step_id, success=False, error=f"Agent '{agent_name}' 不存在")

    # 加载当前 Agent 的工具和角色定义
    tools = agent_config.get_tools(token)
    system_message = agent_config.build_execution_system_message(token)

    llm = create_creative_llm()
    llm_with_tools = llm.bind_tools(tools) if tools else llm

    # 构建单条 HumanMessage：角色定义 + 任务指令 + 上下文
    prompt_parts = [
        f"## 你的角色与职责\n{system_message}",
        f"\n## 当前任务\n{step.description}",
        f"\n## 用户原始需求\n{query}",
    ]

    if task_memory_summary:
        prompt_parts.append(
            f"\n## 历史相关任务结论（可直接参考，无需重复查询相同数据）\n{task_memory_summary}"
        )

    if step_results:
        prev_text = "\n".join(
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'}\n  输出: {r.output or r.error}"
            for r in step_results
        )
        prompt_parts.append(
            f"\n## 之前步骤的执行结果（重要参考）\n{prev_text}\n"
            "请充分利用上述步骤的产出信息来完成当前任务。"
        )

    if review_feedback:
        prompt_parts.append(
            f"\n## 用户修改意见（重要）\n{review_feedback}\n请根据上述反馈调整执行方式。"
        )

    if eval_feedback:
        prompt_parts.append(
            f"\n## 系统校验反馈（重要）\n{eval_feedback}\n"
            "请根据上述反馈修正执行方式，确保使用工具获取真实数据。"
        )

    prompt_parts.append("\n请执行上述任务，必要时调用可用工具。完成后返回执行结果。")

    try:
        messages = [HumanMessage(content="\n".join(prompt_parts))]
        output, tools_called = await _execute_with_tool_loop(
            llm_with_tools=llm_with_tools,
            messages=messages,
            tool_registry=tool_registry,
            token=token,
            config=config,
        )
        return StepResult(
            step_id=step.step_id,
            success=True,
            output=output or "步骤执行完成",
            tools_called=tools_called,
        )
    except Exception as e:
        print(f"[Executor] 步骤执行异常: {e}")
        return StepResult(step_id=step.step_id, success=False, error=str(e))


# ═══════════════════════════════════════════════════════════
#  阶段 1: 前置校验
# ═══════════════════════════════════════════════════════════


def _preflight_check(
    state: AgentState,
) -> tuple[str | None, tuple[list[PlanStep], PlanStep, str, str, object] | None]:
    """前置校验: 检查待执行步骤和可用 Agent。

    Returns:
        (error, context) 二元组。
        error 非空时表示校验失败; context 为 (plan, step, token, agent_alias, agent_config)。
    """
    plan = state.plan or []
    current_index = state.current_step_index
    current_executor = state.current_executor

    if not plan or current_index >= len(plan):
        return "[Executor] 没有待执行的步骤", None

    if not current_executor:
        return "没有可用的 Agent 执行此步骤", None

    step = plan[current_index]
    token = state.token

    agent_registry = get_agent_registry()
    agent_config = agent_registry.get_agent(current_executor, token)
    agent_alias = agent_config.alias if agent_config else current_executor

    print(
        f"[Executor] 执行步骤 {step.step_id} "
        f"(Token: {token[:10] if token else 'None'}...): {step.description}"
    )
    return None, (plan, step, token, agent_alias, agent_config)


# ═══════════════════════════════════════════════════════════
#  阶段 3: 审核判定
# ═══════════════════════════════════════════════════════════


async def _check_review(
    step: PlanStep,
    result: StepResult,
    agent_config: object | None,
    config: RunnableConfig,
    force_review: bool = False,
) -> tuple[bool, StepResult]:
    """判定步骤是否需要人工审核，需要时提取结论。

    触发条件(满足任一):
    - force_review=True(观察层 ESCALATE 强制触发)
    - Planner 标记 requires_review 或 AgentCard 配置 require_review，且执行成功

    Returns:
        (needs_review, updated_result) — needs_review 为 True 时 result 已附带 conclusion。
    """
    agent_requires_review = bool(agent_config and agent_config.require_review)
    should_review = force_review or (
        (step.requires_review or agent_requires_review) and result.success
    )
    if not should_review:
        return False, result

    step.status = StepStatus.NEEDS_REVIEW
    conclusion = await _extract_conclusion(
        result.output, step.description, result.tools_called, config
    )
    updated_result = result.model_copy(update={"conclusion": conclusion})
    print(f"[Executor] 步骤 {step.step_id} 标记为需要人工审核")
    return True, updated_result


# ═══════════════════════════════════════════════════════════
#  构建返回 Command
# ═══════════════════════════════════════════════════════════


def _fail(reason: str) -> Command:
    """构建失败路由 Command，统一出口。"""
    return Command(
        update={
            "error": reason,
            "messages": [AIMessage(content=f"[Executor] 错误: {reason}")],
        },
        goto="dispatcher",
    )


def _build_command(
    state: AgentState,
    plan: list[PlanStep],
    step: PlanStep,
    result: StepResult,
    step_results: list[StepResult],
    needs_review: bool,
) -> Command:
    """根据审核判定结果构建最终 Command。"""
    if needs_review:
        return Command(
            update={
                "step_results": step_results,
                "require_review": True,
                "plan": plan,
                "messages": [
                    AIMessage(content=f"[Executor] 步骤 {step.step_id} 执行完毕，等待人工审核确认")
                ],
            },
            goto="dispatcher",
        )

    return Command(
        update={
            "step_results": step_results,
            "current_step_index": state.current_step_index + 1,
            "plan": plan,
            "review_status": None,
            "review_feedback": None,
            "messages": [
                AIMessage(content=result.output or f"[Executor] 步骤 {step.step_id} 执行完成")
            ],
        },
        goto="dispatcher",
    )


# ═══════════════════════════════════════════════════════════
#  主流程: LangGraph 节点函数
# ═══════════════════════════════════════════════════════════


async def plan_task_execute_node(state: AgentState, config: RunnableConfig) -> Command:
    """执行节点 — 每次执行计划中的一个步骤。

    五个阶段:
    1. 前置校验: 检查待执行步骤和可用 Agent
    2. 步骤执行: 加载 Agent 配置，构建 Prompt，进入 ReAct 工具循环
    3. 观察评估: 规则校验 + 语义校验，三路分流(PASS/RETRY/ESCALATE)
    4. 审核判定: 收集 StepResult，判定是否触发人工审核
    5. 构建返回: 审核 → dispatcher(review)，正常 → dispatcher(下一步)
    """
    max_eval_retries = 1  # 内部最多重试 1 次，总共最多执行 2 次

    # ── 阶段 1: 前置校验 ──────────────────────────────────
    error, step_ctx = _preflight_check(state)
    if error:
        return _fail(error)

    plan, step, token, agent_alias, agent_config = step_ctx

    # 判断 Agent 是否配置了工具(用于观察层规则校验)
    agent_has_tools = bool(agent_config and agent_config.raw_bound_tools)

    # ── 阶段 2 + 3: 步骤执行 + 观察评估(含内部重试循环) ────
    await adispatch_custom_event(
        "agent_start",
        {"agent": state.current_executor, "alias": agent_alias, "step_id": step.step_id},
        config=config,
    )
    step.status = StepStatus.IN_PROGRESS

    eval_feedback = None
    force_escalate = False

    for attempt in range(max_eval_retries + 1):
        result = await _execute_step_with_agent(
            step=step,
            agent_name=state.current_executor,
            query=state.query,
            token=token,
            config=config,
            review_feedback=state.review_feedback,
            eval_feedback=eval_feedback,
            step_results=list(state.step_results),
            task_memory_summary=state.context_task_memory_summary or "",
        )

        # 观察评估
        eval_result = await _evaluate_result(result, step, agent_has_tools, config)
        print(
            f"[Executor] 步骤 {step.step_id} 第 {attempt + 1} 次执行，"
            f"评估结果: {eval_result.verdict.value} - {eval_result.reason}"
        )

        if eval_result.verdict == EvalVerdict.PASS:
            break
        elif eval_result.verdict == EvalVerdict.ESCALATE:
            force_escalate = True
            break
        elif eval_result.verdict == EvalVerdict.RETRY:
            if attempt < max_eval_retries:
                print(f"[Executor] 内部重试，纠偏反馈: {eval_result.feedback}")
                eval_feedback = eval_result.feedback
                continue
            else:
                # 重试耗尽，自动升级为 ESCALATE
                print("[Executor] 重试耗尽，自动升级为人工审核")
                force_escalate = True
                break

    # 记录实际执行次数
    result = result.model_copy(update={"eval_attempts": attempt + 1})

    await adispatch_custom_event(
        "agent_end",
        {"agent": state.current_executor, "step_id": step.step_id, "success": result.success},
        config=config,
    )

    # ── 阶段 4: 审核判定 ──────────────────────────────────
    step.status = StepStatus.COMPLETED if result.success else StepStatus.FAILED
    step_results = [*list(state.step_results), result]

    needs_review, result = await _check_review(
        step, result, agent_config, config, force_review=force_escalate
    )
    if needs_review:
        step_results[-1] = result

    # ── 阶段 5: 构建返回 ──────────────────────────────────
    return _build_command(state, plan, step, result, step_results, needs_review)
