from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langgraph.types import Command
from ..state import AgentState
from ...audit import submit_trace, start_node_trace, finish_node_trace
from ...config import get_settings
from ...context import get_context_manager, get_long_term_memory_manager
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableConfig


async def responder_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能: 响应汇总节点
    职责:
    1. 提取所有步骤执行结果
    2. 调用 LLM 生成最终汇总响应 (流式)
    3. 触发审计数据采集
    4. 记录本轮对话和任务结果到 ContextManager（跨轮次记忆）
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
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.llm_temperature,
            streaming=True
        )

        results_context = "\n\n".join([
            f"### 步骤 {r.step_id}"
            + f"\n**状态**: {'✅ 成功' if r.success else '❌ 失败'}"
            + (f"\n**调用工具**: {', '.join(r.tools_called)}" if r.tools_called else "")
            + (f"\n**核心结论**: {r.conclusion}" if r.conclusion else "")
            + (f"\n**详细输出**:\n{r.output}" if r.output else "")
            + (f"\n**失败原因**: {r.error}" if not r.success else "")
            + (f"\n**⚠️ 需要人工审核**" if r.require_review else "")
            for r in step_results
        ])

        system_prompt = """你是一个专业的 AI 助理。你需要根据任务执行的结果，为用户生成一个结构清晰、逻辑完整的最终回答。

输出结构要求（使用以下 Markdown 标题，按顺序输出）:

## 步骤执行过程
逐步骤说明：该步骤调用了哪些工具、为什么这么做、得出了什么结论。每个步骤单独列出，逻辑连贯。如有数据或表格，使用 Markdown 格式展示。

## 最终结论
直接回答用户的原始问题，基于上述步骤的结论汇总，简洁明了。

## 建议
基于执行结果给出后续建议或注意事项。如果有失败步骤，说明其影响及规避方式。

注意事项:
1. 步骤说明要有实质内容，体现工具调用的意义和结论，避免空泛描述。
2. 如果任务部分失败，在对应步骤中说明原因，不要隐藏。
3. 直接输出内容，不要以 "好的"、"根据结果" 等废话开头。
"""

        human_prompt = f"""用户原始问题: {query}

执行过程结果:
{results_context}

请按照「步骤执行过程 / 最终结论 / 建议」三个部分组织回答。"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]
            response = await llm.ainvoke(messages, config=config)
            summary = response.content
        except Exception as e:
            print(f"[Responder] 调用 LLM 失败: {e}")
            last_result = step_results[-1]
            summary = last_result.output if last_result.success else f"执行失败: {last_result.error}"

    # 完成 responder 节点追踪
    finish_node_trace(nt, "SUCCESS", node_result=summary)

    # 合并完整的 node_traces
    all_node_traces = state.node_traces + [nt]

    # ── 记录本轮实体追踪 + 触发长期记忆 Reflection ──────────────
    if state.session_id:
        ctx_mgr = get_context_manager()
        intent_type = state.intent.intent_type.value if state.intent else "chat"
        original_query = (state.intent.entities.get("original_query", "") or query) if state.intent else query
        entities = state.intent.entities if state.intent else {}

        # 更新 session 级实体追踪缓存（轻量，不写 DB）
        ctx_mgr.update_entities(state.session_id, entities)

        # 触发后台异步 Reflection，更新长期记忆（不阻塞）
        ltm = get_long_term_memory_manager()
        ltm.trigger_reflection_async(
            user_id=state.user_id,
            task_id=state.task_id,
            query=original_query,
            step_results=step_results,
            final_response=summary,
            intent_type=intent_type,
        )

        print(f"[Responder] 已更新实体追踪: session={state.session_id}, intent={intent_type}")

    # 异步提交审计数据
    submit_trace(state, summary, all_node_traces)

    return Command(
        update={
            "messages": [AIMessage(content=summary)],
            "node_traces": all_node_traces,
        },
        goto="__end__"
    )
