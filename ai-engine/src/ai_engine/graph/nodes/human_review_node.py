"""
人工审核节点
处理需要人工审核的敏感操作
"""

from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import Command

from ..state import AgentState, ReviewStatus


async def human_review_node(state: AgentState) -> Command:
    """
    功能: 人工审核节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典
    
    职责:
    1. 暂停执行流程，等待人工审核
    2. 生成审核上下文信息
    3. 返回审核状态
    
    注意: 
    - 此节点使用 LangGraph 的 interrupt_before 机制
    - 当从 interrupt 恢复时，review_status 已被 handle_review_decision 设置，
      需要根据该状态路由，而不是覆盖它
    """
    review_status = state.review_status
    
    # ── 检查是否已有用户响应（从 interrupt 恢复时） ──────────────────
    if review_status == ReviewStatus.APPROVED:
        # 用户已批准，清除审核状态，继续执行
        print("[HumanReview] 用户已批准，继续执行")
        return Command(
            update={
                "require_review": False,
                "review_status": None,
                "messages": [AIMessage(content="[HumanReview] 用户批准，继续执行")],
            },
            goto="dispatcher"
        )
    elif review_status == ReviewStatus.REJECTED:
        # 用户已驳回，跳转到反馈处理节点
        print(f"[HumanReview] 用户驳回，进入反馈处理。反馈: {state.review_feedback}")
        return Command(
            update={
                "require_review": False,
                # 保持 REJECTED 和 review_feedback，供 feedback_handler_node 使用
            },
            goto="feedback"
        )
    
    # ── 原有逻辑：首次进入，等待审核 ─────────────────────────────────
    # 注意：由于 interrupt_before=["review"]，正常流程不会执行到这里
    # 只有在 interrupt 机制未生效时才会走到这段代码
    step_results = state.step_results
    plan = state.plan or []
    current_index = state.current_step_index
    
    # 获取最近需要审核的步骤结果
    pending_result = None
    if step_results:
        for result in reversed(step_results):
            if result.require_review:
                pending_result = result
                break
    
    # 构建审核上下文
    review_context = {
        "query": state.query,
        "current_step": plan[current_index].description if plan and current_index < len(plan) else "",
        "tools_called": pending_result.tools_called if pending_result else [],
        "output": pending_result.output if pending_result else "",
    }
    
    print(f"[HumanReview] 等待人工审核...")
    print(f"[HumanReview] 上下文: {review_context}")
    
    return Command(
        update={
            "review_status": ReviewStatus.PENDING,
            "messages": [AIMessage(content=f"[HumanReview] 需要人工审核，已暂停执行")],
        },
        goto="dispatcher"
    )


def handle_review_decision(
    state: AgentState,
    action: str,
    feedback: str = ""
) -> dict[str, Any]:
    """
    功能: 处理人工审核决定
    参数:
        state - 当前状态
        action - 审核动作 (approve/reject)
        feedback - 审核反馈（驳回时必填）
    返回: 状态更新字典
    
    此函数由 API 调用，用于恢复被暂停的工作流
    """
    if action.lower() == "approve":
        # 审核通过，继续执行
        # 注意: 不推进 current_step_index，让调度器路由到 executor 执行当前步骤
        # 对于 requires_review 场景：执行完当前步骤后，executor 会自动推进索引
    
        return {
            "require_review": False,
            "review_status": ReviewStatus.APPROVED,
            "review_feedback": None,
            "messages": [AIMessage(content="[HumanReview] 审核通过，继续执行")],
        }
    else:
        # 审核驳回，需要反馈处理
        return {
            "require_review": False,
            "review_status": ReviewStatus.REJECTED,
            "review_feedback": feedback,
            "messages": [AIMessage(content=f"[HumanReview] 审核驳回: {feedback}")],
        }
