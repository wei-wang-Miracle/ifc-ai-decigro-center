"""
StateGraph 构建器
构建完整的 LangGraph 工作流
"""

from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.types import Command
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



def create_workflow_graph(checkpointer=None):
    """
    功能: 创建完整的工作流程图 (LangGraph 1.0 架构)
    参数: checkpointer - 可选的检查点保存器
    返回: 编译后的 StateGraph 实例
    
    流程图结构:
    START -> intent_recognition (内部路由) -> {dispatcher, __end__}
    dispatcher (内部路由) -> {planner, executor, review, __end__}
    planner -> dispatcher
    executor -> dispatcher
    review -> dispatcher (或被 interrupt)
    feedback -> dispatcher
    """
    # 创建 StateGraph
    workflow = StateGraph(AgentState)
    
    # 1. 添加节点
    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("dispatcher", dispatcher_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", plan_task_execute_node)
    workflow.add_node("review", human_review_node)
    workflow.add_node("feedback", feedback_handler_node)
    
    # 2. 设置入口点
    workflow.set_entry_point("intent_recognition")
    
    # 3. 添加固定边 (大部分路由已移动到节点内部的 Command 中)
    # 虽然 Command handled 很多，但明确的 node 间跳转依然可以用 add_edge
    # 注意：在 LangGraph 1.0 中，如果节点返回 Command(goto=...)，则不需要显式的边缘定义。
    # 为了保持图的清晰性，我们保留节点声明。
    
    # 4. 编译工作流
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    # 配置中断点（人工审核时暂停）
    compiled = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["review"],
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
