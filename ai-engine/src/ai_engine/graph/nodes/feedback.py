"""
反馈处理节点
处理人工驳回后的反馈，调整计划或重试
"""

from typing import Any

from langchain_core.messages import AIMessage

from ..state import AgentState, ReviewStatus


def feedback_handler_node(state: AgentState) -> dict[str, Any]:
    """
    功能: 反馈处理节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典
    
    职责:
    1. 接收人工驳回的反馈意见
    2. 分析反馈内容
    3. 决定是重新规划还是调整当前步骤
    4. 更新状态以便后续处理
    """
    review_feedback = state.get("review_feedback", "")
    review_status = state.get("review_status")
    
    # 只在驳回状态下处理
    if review_status != ReviewStatus.REJECTED:
        return {
            "messages": [AIMessage(content="[FeedbackHandler] 非驳回状态，无需处理")],
        }
    
    print(f"[FeedbackHandler] 处理反馈: {review_feedback}")
    
    # 分析反馈类型
    # 如果反馈包含"重新规划"、"换个方案"等关键词，清空计划重新开始
    replan_keywords = ["重新规划", "换个方案", "重做", "from scratch", "start over"]
    should_replan = any(keyword in review_feedback.lower() for keyword in replan_keywords)
    
    if should_replan:
        # 清空计划，让 Dispatcher 路由到 Planner 重新规划
        print("[FeedbackHandler] 需要重新规划")
        return {
            "plan": None,
            "current_step_index": 0,
            "review_status": None,
            "review_feedback": review_feedback,  # 保留反馈给 Planner 参考
            "messages": [AIMessage(content=f"[FeedbackHandler] 根据反馈重新规划: {review_feedback}")],
        }
    else:
        # 保留计划，让 Agent 根据反馈调整当前步骤的执行方式
        # 反馈会被传递给执行节点
        print("[FeedbackHandler] 调整当前步骤执行方式")
        return {
            "review_status": None,
            "messages": [AIMessage(content=f"[FeedbackHandler] 根据反馈调整: {review_feedback}")],
        }
