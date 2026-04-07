"""
人工审核节点
处理需要人工审核的敏感操作，包括构建审核提示消息和等待用户决策。
"""

from langchain_core.messages import AIMessage
from langgraph.types import Command, interrupt

from ..state import AgentState, ReviewStatus


def _build_review_message(state: AgentState) -> str:
    """构建人工审核提示消息。

    审核内容仅展示步骤描述和核心结论，
    用户对结论负责，不感知工具细节和推理过程。
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
    review_parts.append(
        "\n\n请回复您的决定：\n"
        "- 回复「通过」或「确认」→ 批准并继续执行\n"
        "- 描述修改意见 → 我将根据反馈调整方案"
    )
    return "\n".join(review_parts)


async def human_review_node(state: AgentState) -> Command:
    """
    功能: 人工审核节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: Command，路由到下一节点

    职责：
    1. 构建审核提示消息，展示执行结论供用户确认
    2. 使用 interrupt() 主动暂停，等待用户回复
    3. 恢复时根据用户决策路由到下一节点
    """
    # 构建审核提示消息，写入 messages 供前端展示
    review_msg = _build_review_message(state)

    # interrupt() 暂停图执行，返回值是外部通过 Command(resume=...) 传入的数据
    # 首次进入时暂停；恢复时直接拿到 resume 值，不会再次暂停
    resume_data = interrupt(
        {
            "require_review": True,
            "step_index": state.current_step_index,
            "review_message": review_msg,
        }
    )

    action = resume_data.get("action", "approve")
    feedback = resume_data.get("feedback", "")

    if action == "approve":
        current_index = state.current_step_index or 0

        # 子图分阶段执行：approve 后需要重新进入 executor 完成后续阶段，
        # 不递增 step_index，保留 subgraph_resume_meta 供 executor 读取
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
    else:
        print(f"[HumanReview] 用户驳回，进入反馈处理。反馈: {feedback}")
        return Command(
            update={
                "require_review": False,
                "review_status": ReviewStatus.REJECTED,
                "review_feedback": feedback,
                "messages": [AIMessage(content=f"[HumanReview] 审核驳回: {feedback}")],
            },
            goto="feedback",
        )
