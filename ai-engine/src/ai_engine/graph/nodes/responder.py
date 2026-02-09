"""
响应节点
负责汇总执行结果，生成最终返回给用户的自然语言响应
"""

from langchain_core.messages import AIMessage
from langgraph.types import Command
from ..state import AgentState


def responder_node(state: AgentState) -> Command:
    """
    功能: 响应汇总节点
    职责:
    1. 提取所有步骤执行结果
    2. 生成最终汇总响应
    3. 清理调试信息
    """
    step_results = state.step_results
    
    if not step_results:
        summary = "抱歉，我未能成功执行您的请求。"
    else:
        # 如果只有一个成功的步骤结果，直接取其输出作为回复基础
        last_result = step_results[-1]
        if last_result.success:
            summary = last_result.output
        else:
            summary = f"任务执行过程中遇到错误: {last_result.error}"

    return Command(
        update={
            "messages": [AIMessage(content=summary)],
        },
        goto="__end__"
    )
