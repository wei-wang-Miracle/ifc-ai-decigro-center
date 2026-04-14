"""人工审核节点。

处理需要人工审核的敏感操作，包括构建审核提示消息和等待用户决策。
支持两种模式：
- 纯文本审核：原有 markdown 审核消息
- 结构化审核：ProfessionalAuditResponse 数据透传前端渲染
"""

from langchain_core.messages import AIMessage
from langgraph.types import Command, interrupt

from ..hitl_models import HumanDecisionPayload
from ..state import AgentState, ReviewStatus


def _build_review_message(state: AgentState) -> tuple[str, dict | None]:
    """构建人工审核提示消息。

    审核内容仅展示步骤描述和核心结论，
    用户对结论负责，不感知工具细节和推理过程。
    当 Agent 配置了 human_review_config 时，注入审核引导语和维度提示。

    Returns:
        (review_message, structured_audit) 二元组。
        structured_audit 非 None 时表示有结构化审核数据供前端渲染。
    """
    plan_list = state.plan or []
    step_idx = state.current_step_index
    step_results_list = state.step_results

    current_step = plan_list[step_idx] if plan_list and step_idx < len(plan_list) else None

    # 找到当前步骤（NEEDS_REVIEW 状态）的执行结果
    current_step_id = current_step.step_id if current_step else None
    pending_result = None
    if current_step_id:
        for r in reversed(step_results_list):
            if r.step_id == current_step_id:
                pending_result = r
                break

    step_desc = current_step.description if current_step else "当前操作"

    # 提取结构化审核数据（如果有）
    structured_audit = pending_result.structured_audit if pending_result else None

    # 优先使用 conclusion（结论摘要），回落到 output 截断
    conclusion = (
        (pending_result.conclusion or pending_result.output or "").strip() if pending_result else ""
    )
    if not conclusion and pending_result:
        conclusion = (pending_result.output or "")[:300].strip()

    review_parts = ["我已完成以下操作，需要您确认后才能继续：\n"]
    review_parts.append(f"**步骤描述：** {step_desc}")
    if conclusion:
        review_parts.append(f"\n**执行结论：**\n{conclusion}")

    # 尝试加载 Agent 的审核配置，注入审核引导语和维度提示
    hr_config = None
    if state.current_executor and state.token:
        try:
            from ...registry import get_agent_registry
            agent_reg = get_agent_registry()
            agent_cfg = agent_reg.get_agent(state.current_executor, state.token)
            if agent_cfg:
                hr_config = agent_cfg.human_review_config
        except Exception:
            pass

    if hr_config:
        instruction = hr_config.get("review_instruction", "")
        dimensions = hr_config.get("review_dimensions", [])
        if instruction:
            review_parts.append(f"\n**审核引导：** {instruction}")
        if dimensions:
            dims_text = "\n".join(f"  - {d}" for d in dimensions)
            review_parts.append(f"\n**请重点关注以下维度：**\n{dims_text}")

    # 结构化审核时，提示用户通过审核面板操作；否则提示文字回复
    if structured_audit:
        review_parts.append(
            "\n\n请在审核面板中完成操作：勾选确认项、选择建议方案，然后提交您的决定。"
        )
    else:
        review_parts.append(
            "\n\n请回复您的决定：\n"
            "- 回复「通过」或「确认」→ 批准并继续执行\n"
            "- 描述修改意见 → 我将根据反馈调整方案"
        )
    return "\n".join(review_parts), structured_audit


async def human_review_node(state: AgentState) -> Command:
    """人工审核节点 - LangGraph 节点函数。

    职责：
    1. 构建审核提示消息，展示执行结论供用户确认
    2. 使用 interrupt() 主动暂停，等待用户回复
    3. 恢复时根据用户决策路由到下一节点

    支持两种 resume 格式：
    - 文本审核: {"action": "approve"|"reject", "feedback": "..."}
    - 结构化审核: {"action": "structured", "structured_decision": {...}}
    """
    # 构建审核提示消息
    review_msg, structured_audit = _build_review_message(state)

    # interrupt() 暂停图执行，返回值是外部通过 Command(resume=...) 传入的数据
    resume_data = interrupt(
        {
            "require_review": True,
            "step_index": state.current_step_index,
            "review_message": review_msg,
            "structured_audit": structured_audit,
        }
    )

    action = resume_data.get("action", "approve")
    feedback = resume_data.get("feedback", "")

    # 结构化决策处理：前端通过 ReviewPanel 提交 HumanDecisionPayload
    if action == "structured":
        raw_decision = resume_data.get("structured_decision", {})
        try:
            decision = HumanDecisionPayload.model_validate(raw_decision)
        except Exception as e:
            print(f"[HumanReview] 结构化决策解析失败，回退为驳回: {e}")
            return _reject(f"结构化决策格式错误: {e}")

        if decision.quick_decision_flag == "approve_all_ai_recommendations":
            print("[HumanReview] 用户全部接受 AI 建议")
            return _approve(state)
        elif decision.quick_decision_flag == "reject_all":
            feedback_text = decision.to_feedback_text()
            print(f"[HumanReview] 用户全部驳回: {feedback_text[:60]}")
            return _reject(feedback_text)
        else:
            # custom: 将结构化决策转换为反馈文本
            feedback_text = decision.to_feedback_text()
            # 有接受项时视为部分通过，走 approve 路径（反馈作为补充信息）
            has_accepted = bool(decision.accepted.check_list or decision.accepted.proposals)
            has_rejected = bool(decision.rejected.check_list or decision.rejected.proposals)
            if has_accepted and not has_rejected:
                print(f"[HumanReview] 用户自定义决策(全部接受): {feedback_text[:60]}")
                return _approve(state)
            else:
                print(f"[HumanReview] 用户自定义决策(含拒绝): {feedback_text[:60]}")
                return _reject(feedback_text)

    # 原有文本审核路径
    if action == "approve":
        return _approve(state)
    else:
        return _reject(feedback)


def _approve(state: AgentState) -> Command:
    """审核通过路由。"""
    current_index = state.current_step_index or 0

    # 子图分阶段执行：approve 后需要重新进入 executor 完成后续阶段
    if state.subgraph_resume_meta:
        print(
            f"[HumanReview] 用户已批准子图步骤 {current_index}，"
            "重新进入 executor 完成后续阶段"
        )
        return Command(
            update={
                "require_review": False,
                "review_status": ReviewStatus.APPROVED,
                "review_feedback": None,
                "messages": [AIMessage(content="[HumanReview] 用户批准，继续执行子图后续阶段")],
            },
            goto="dispatcher",
        )

    print(f"[HumanReview] 用户已批准，推进步骤索引 {current_index} → {current_index + 1}")
    return Command(
        update={
            "require_review": False,
            "review_status": ReviewStatus.APPROVED,
            "review_feedback": None,
            "current_step_index": current_index + 1,
            "messages": [AIMessage(content="[HumanReview] 用户批准，继续执行")],
        },
        goto="dispatcher",
    )


def _reject(feedback: str) -> Command:
    """审核驳回路由。"""
    print(f"[HumanReview] 用户驳回，进入反馈处理。反馈: {feedback[:60]}")
    return Command(
        update={
            "require_review": False,
            "review_status": ReviewStatus.REJECTED,
            "review_feedback": feedback,
            "messages": [AIMessage(content=f"[HumanReview] 审核驳回: {feedback}")],
        },
        goto="feedback",
    )
