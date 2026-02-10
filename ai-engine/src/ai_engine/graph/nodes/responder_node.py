"""
响应节点
负责汇总执行结果，生成最终返回给用户的自然语言响应
"""

from langchain_core.messages import AIMessage
from langgraph.types import Command
from ..state import AgentState, IntentType
from ...audit import submit_trace, start_node_trace, finish_node_trace


def responder_node(state: AgentState) -> Command:
    """
    功能: 响应汇总节点
    职责:
    1. 提取所有步骤执行结果
    2. 生成最终汇总响应
    3. 触发审计数据采集
    """
    # 审计埋点
    nt = start_node_trace("responder")

    step_results = state.step_results
    intent = state.intent
    
    # 优先处理不支持的情况
    if intent and intent.intent_type == IntentType.UNSUPPORTED:
        summary = "抱歉，根据我目前拥有的 Tool Card 和 Agent Card 权限，我暂时无法直接处理您的这项请求。您可以尝试换一种方式提问，或者查看我支持的功能列表（如：查询、分析等）。"
    elif not step_results:
        summary = "抱歉，我未能成功执行您的请求。"
    else:
        # 如果只有一个成功的步骤结果，直接取其输出作为回复基础
        last_result = step_results[-1]
        if last_result.success:
            summary = last_result.output
        else:
            summary = f"任务执行过程中遇到错误: {last_result.error}"

    # 完成 responder 节点追踪
    finish_node_trace(nt, "SUCCESS")

    # 合并完整的 node_traces（包含 responder 自身）
    all_node_traces = state.node_traces + [nt]

    # 异步提交审计数据（后台线程，不阻塞主流程）
    submit_trace(state, summary, all_node_traces)

    return Command(
        update={
            "messages": [AIMessage(content=summary)],
            "node_traces": all_node_traces,
        },
        goto="__end__"
    )

