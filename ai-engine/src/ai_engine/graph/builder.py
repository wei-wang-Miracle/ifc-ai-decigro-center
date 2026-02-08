"""
StateGraph 构建器
构建完整的 LangGraph 工作流
"""

from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState, IntentType, ReviewStatus
from .nodes import (
    intent_recognition_node,
    dispatcher_node,
    planner_node,
    plan_task_execute_node,
    human_review_node,
    feedback_handler_node,
)
from .nodes.dispatcher import dispatcher_route_decision


def _should_continue_after_intent(state: AgentState) -> Literal["dispatcher", "end"]:
    """
    功能: 意图识别后的路由决策
    参数: state - 当前状态
    返回: 下一个节点名称
    """
    intent = state.get("intent")
    
    if intent is None:
        return "end"
    
    # 无效或结束意图直接结束
    if intent.intent_type in [IntentType.INVALID, IntentType.END]:
        return "end"
    
    return "dispatcher"


def _should_continue_after_review(state: AgentState) -> Literal["dispatcher", "feedback"]:
    """
    功能: 审核后的路由决策
    参数: state - 当前状态
    返回: 下一个节点名称
    """
    review_status = state.get("review_status")
    
    if review_status == ReviewStatus.REJECTED:
        return "feedback"
    
    return "dispatcher"


def create_workflow_graph(checkpointer=None):
    """
    功能: 创建完整的工作流程图
    参数: checkpointer - 可选的检查点保存器（用于状态持久化）
    返回: 编译后的 StateGraph 实例
    
    流程图结构:
    START -> intent_recognition -> dispatcher -> {planner, executor, review, end}
           -> planner -> dispatcher
           -> executor -> dispatcher (或 review)
           -> review -> dispatcher (或 feedback)
           -> feedback -> dispatcher
    """
    # 创建 StateGraph
    workflow = StateGraph(AgentState)
    
    # ========================================
    # 添加节点
    # ========================================
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("dispatcher", dispatcher_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", plan_task_execute_node)
    workflow.add_node("review", human_review_node)
    workflow.add_node("feedback", feedback_handler_node)
    
    # ========================================
    # 设置入口点
    # ========================================
    workflow.set_entry_point("intent_recognition")
    
    # ========================================
    # 添加边和条件边
    # ========================================
    
    # 意图识别 -> 调度中心或结束
    workflow.add_conditional_edges(
        "intent_recognition",
        _should_continue_after_intent,
        {
            "dispatcher": "dispatcher",
            "end": END,
        }
    )
    
    # 调度中心 -> 基于决策路由
    workflow.add_conditional_edges(
        "dispatcher",
        dispatcher_route_decision,
        {
            "planner": "planner",
            "executor": "executor",
            "review": "review",
            "intent": "intent_recognition",
            "end": END,
        }
    )
    
    # 规划节点 -> 调度中心
    workflow.add_edge("planner", "dispatcher")
    
    # 执行节点 -> 调度中心
    workflow.add_edge("executor", "dispatcher")
    
    # 审核节点 -> 调度中心或反馈处理
    workflow.add_conditional_edges(
        "review",
        _should_continue_after_review,
        {
            "dispatcher": "dispatcher",
            "feedback": "feedback",
        }
    )
    
    # 反馈处理 -> 调度中心
    workflow.add_edge("feedback", "dispatcher")
    
    # ========================================
    # 编译工作流
    # ========================================
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    # 配置中断点（人工审核时暂停）
    compiled = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["review"],  # 在审核节点前中断
    )
    
    return compiled


# 全局工作流实例
_workflow = None


def get_workflow():
    """
    功能: 获取全局工作流实例
    参数: 无
    返回: 编译后的 StateGraph
    """
    global _workflow
    if _workflow is None:
        _workflow = create_workflow_graph()
    return _workflow
