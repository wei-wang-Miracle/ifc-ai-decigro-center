from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.types import Command
from ..state import AgentState
from ...audit import submit_trace, start_node_trace, finish_node_trace
from ...config import get_settings
from langchain_openai import ChatOpenAI


from langchain_core.runnables import RunnableConfig


async def responder_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能: 响应汇总节点
    职责:
    1. 提取所有步骤执行结果
    2. 调用 LLM 生成最终汇总响应 (流式)
    3. 触发审计数据采集
    """
    # 审计埋点
    nt = start_node_trace("responder")

    step_results = state.step_results
    query = state.query
    settings = get_settings()

    # 处理逻辑
    if state.error and not step_results:
        # 上游节点（如 Planner）明确给出了错误原因，直接透传给用户
        summary = state.error
    elif not step_results:
        # 闲聊/简单问答场景：step_results 为空，说明上游节点（normal_node）已生成完整回复
        # 直接透传上游生成的 AIMessage，避免重复调用 LLM 导致内容丢失
        ai_messages = [m for m in state.messages if isinstance(m, AIMessage)]
        if ai_messages:
            summary = ai_messages[-1].content
            print(f"[Responder] 透传上游回复，长度={len(summary)}")
        else:
            summary = "处理请求时发生错误。"
    else:
        # 复杂任务场景：有 step_results，需要 LLM 汇总
        # 创建 LLM 实例用于最终汇总
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.llm_temperature,
            streaming=True
        )
        
        # 准备上下文
        results_context = "\n".join([
            f"### 步骤 {r.step_id} 结果:\n{r.output if r.success else '失败: ' + r.error}"
            for r in step_results
        ])

        system_prompt = """你是一个专业的 AI 助理。你需要根据任务执行的结果，为用户生成一个友好、自然、且结构清晰的最终回答。
注意事项:
1. 如果结果中包含数据列表或表格，请使用 Markdown 格式美观地展示。
2. 保持回答的简洁性，除非用户要求详细分析。
3. 如果任务失败，请礼貌地告知用户原因。
4. 直接输出最终回答，不要包含类似 "好的"、"根据结果" 之类的废话。
"""

        human_prompt = f"""用户原始问题: {query}

执行过程结果:
{results_context}

请基于以上信息生成最终回答。"""

        try:
            # 调用 LLM 生成输出
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            response = await llm.ainvoke(messages, config=config)
            summary = response.content
        except Exception as e:
            print(f"[Responder] 调用 LLM 失败: {e}")
            # 降级方案
            last_result = step_results[-1]
            summary = last_result.output if last_result.success else f"执行失败: {last_result.error}"

    # 完成 responder 节点追踪
    finish_node_trace(nt, "SUCCESS", node_result=summary)

    # 合并完整的 node_traces
    all_node_traces = state.node_traces + [nt]

    # 异步提交审计数据
    submit_trace(state, summary, all_node_traces)

    return Command(
        update={
            "messages": [AIMessage(content=summary)],
            "node_traces": all_node_traces,
        },
        goto="__end__"
    )

