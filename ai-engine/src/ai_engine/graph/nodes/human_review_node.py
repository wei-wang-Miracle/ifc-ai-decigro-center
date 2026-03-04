"""
人工审核节点
处理需要人工审核的敏感操作
"""

from langchain_core.messages import AIMessage
from langgraph.types import Command, interrupt

from ..state import AgentState, ReviewStatus


async def human_review_node(state: AgentState) -> Command:
    """
    功能: 人工审核节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: Command，路由到下一节点

    使用 interrupt() 主动暂停，等待用户回复。
    恢复时 interrupt() 返回用户传入的 review action（"approve"/"reject"）和 feedback。
    """
    # interrupt() 暂停图执行，返回值是外部通过 Command(resume=...) 传入的数据
    # 首次进入时暂停；恢复时直接拿到 resume 值，不会再次暂停
    resume_data = interrupt({
        "require_review": True,
        "step_index": state.current_step_index,
    })

    action = resume_data.get("action", "approve")
    feedback = resume_data.get("feedback", "")

    if action == "approve":
        current_index = state.current_step_index or 0
        print(f"[HumanReview] 用户已批准，推进步骤索引 {current_index} → {current_index + 1}")
        return Command(
            update={
                "require_review": False,
                "review_status": ReviewStatus.APPROVED,
                "review_feedback": None,
                "current_step_index": current_index + 1,
                "messages": [AIMessage(content="[HumanReview] 用户批准，继续执行")],
            },
            goto="dispatcher"
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
            goto="feedback"
        )
