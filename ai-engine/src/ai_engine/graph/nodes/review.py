"""
人工审核节点
处理需要人工审核的敏感操作
"""

from typing import Any

from langchain_core.messages import AIMessage
from langgraph.types import Command

from ..state import AgentState, ReviewStatus


def human_review_node(state: AgentState) -> dict[str, Any]:
    """
    功能: 人工审核节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典
    
    职责:
    1. 暂停执行流程，等待人工审核
    2. 生成审核上下文信息
    3. 返回审核状态
    
    注意: 此节点使用 LangGraph 的 interrupt_before 机制
    实际的审核操作通过 API 完成
    """
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
        current_index = state.current_step_index
    
        return {
            "require_review": False,
            "review_status": ReviewStatus.APPROVED,
            "review_feedback": None,
            "current_step_index": current_index + 1,  # 推进到下一步
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
