"""
意图识别节点（简化版）
职责：
1. 查询重写（基于上下文理解用户真实意图）
2. 二元意图判断：TASK（需要 PLANNER）或 CHAT（其他所有）
"""

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..state import AgentState, IntentObject, IntentType
from langchain_core.runnables import RunnableConfig
from ...config import get_settings
from ...registry import get_agent_registry
from ...audit import start_node_trace, finish_node_trace, build_agent_snapshot
from ...context import get_context_manager, get_long_term_memory_manager


class IntentResult(BaseModel):
    """意图识别结果结构"""
    rewritten_query: str = Field(description="重写后的用户查询，补充上下文使其更明确；如果无需重写则保持原样")
    intent_type: str = Field(description="意图类型：task 或 chat 或 end")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="置信度")
    reasoning: str = Field(default="", description="判断理由（简要说明）")


INTENT_RECOGNITION_PROMPT = """你是一个意图识别与查询重写专家。

## 你的职责
1. **查询重写**：根据对话上下文，将用户的模糊表达重写为明确的查询语句（补充指代、省略的主体等）
2. **意图分类**：判断用户需求是否需要 PLANNER Agent 处理

## 意图类型（只有三种）
- **task**: 用户需求明确，且需要调用下方列出的 PLANNER Agent 来完成复杂业务任务
- **chat**: 其他所有情况（闲聊、简单问答、功能咨询、模糊需求、系统不支持的请求等）
- **end**: 用户明确表示结束对话（如：谢谢、再见、不需要了、没有了）

## 判断 TASK 的关键标准
只有同时满足以下条件时，才判定为 task：
1. 用户需求涉及下方 PLANNER Agent 的核心能力范围
2. 需求的主体由**用户在当前输入或近期对话**中明确提及（如：具体的基金代码、产品名称等关键信息）
3. 需要多步骤规划和执行

否则，一律判定为 chat（由普通对话节点处理闲聊、引导或澄清）

## 查询重写规则（重要）
- **只补充用户在本轮或近期对话中已提及的信息**（如代词指代、省略的主语）
- **严禁**将长期记忆中的历史信息擅自填入查询主体。若当前上下文中缺乏明确主体，应保持查询原样，判定为 chat 等待用户澄清
- 长期记忆仅供意图判断参考，不得直接作为查询补全的依据

## 可用 PLANNER Agent（只有这些能处理 TASK）
{planner_descriptions}

## 会话上下文（近期对话记录与关键实体）
{context_summary}

## 当前用户输入
{query}

## 输出要求
返回 JSON 格式的意图识别结果。查询重写时请结合会话上下文补全指代词和省略信息。
"""


def _get_llm() -> ChatOpenAI:
    """获取 LLM 实例"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=0.1,
        streaming=True
    )


def _build_context_summary(state: AgentState, long_term_ctx: str = "") -> str:
    """
    构建注入 Prompt 的上下文摘要。
    按优先级合并：长期记忆 > 跨轮次历史摘要 > 实体追踪 > 历史任务结论
    """
    parts = []

    # 长期记忆（跨会话事实与经验）
    if long_term_ctx:
        parts.append(f"### 用户长期记忆（事实与经验）\n{long_term_ctx}")

    # 跨轮次历史摘要（由 ContextManager 在请求入口注入）
    if state.context_turns_summary:
        parts.append(f"### 近期对话记录\n{state.context_turns_summary}")

    # 实体追踪
    if state.context_entities_summary:
        parts.append(f"### 关键实体\n{state.context_entities_summary}")

    # 历史任务结论（跨轮次）
    if state.context_task_memory_summary:
        parts.append(f"### 历史相关任务结论\n{state.context_task_memory_summary}")

    return "\n\n".join(parts) if parts else "无历史对话上下文"


async def intent_recognition_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能：意图识别节点（简化版）
    职责:
    1. 使用初始化阶段准备的长期记忆（优先）或自行检索（备用）
    2. 查询重写（基于 ContextManager 注入的跨轮次上下文）
    3. 二元意图判断：TASK / CHAT / END
    4. 统一路由到 dispatcher
    """
    query = state.query
    token = state.token

    nt = start_node_trace("intent_recognition")

    # ── 使用初始化阶段准备的长期记忆 ────────────
    # 优先使用 state 中已有的 long_term_context（由 routes.py 初始化时检索）
    long_term_ctx = state.long_term_context or ""
    agent_registry = get_agent_registry()

    # 只获取 PLANNER Agent 描述（这是判断 TASK 的关键依据）
    planner_agents = agent_registry.get_agent_descriptions(token, agent_type="PLANNER")
    planner_descriptions = "\n".join([
        f"- **{name}**: {desc}"
        for name, desc in planner_agents.items()
    ]) if planner_agents else "暂无可用 PLANNER Agent"

    # 构建上下文摘要（跨轮次 + 实体追踪 + 长期记忆）
    context_summary = _build_context_summary(state, long_term_ctx)

    prompt = INTENT_RECOGNITION_PROMPT.format(
        planner_descriptions=planner_descriptions,
        context_summary=context_summary,
        query=query,
    )

    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(IntentResult)

        result: IntentResult = await structured_llm.ainvoke(
            [HumanMessage(content=prompt)],
            config=config
        )

        # 映射到 IntentType 枚举
        intent_type_map = {
            "task": IntentType.TASK,
            "chat": IntentType.CHAT,
            "end": IntentType.END,
        }
        mapped_type = intent_type_map.get(result.intent_type.lower(), IntentType.CHAT)

        intent = IntentObject(
            intent_type=mapped_type,
            confidence=result.confidence,
            entities={
                "rewritten_query": result.rewritten_query,
                "reasoning": result.reasoning,
                "original_query": query,
            },
        )

        # 使用重写后的查询（如果有变化）
        effective_query = result.rewritten_query if result.rewritten_query else query

        print(f"[IntentNode] 原始查询: {query}")
        if effective_query != query:
            print(f"[IntentNode] 重写查询: {effective_query}")
        print(f"[IntentNode] 识别结果: type={mapped_type.value}, confidence={result.confidence}")
        print(f"[IntentNode] 判断理由: {result.reasoning}")

        # 路由决策：END 直接结束，其他走 dispatcher 统一调度
        goto = "__end__" if mapped_type == IntentType.END else "dispatcher"

        # 审计埋点
        intent_result = f"type={mapped_type.value}, rewritten={effective_query != query}"
        agent_snap = build_agent_snapshot(
            model_config={"provider": "openai", "model_name": get_settings().llm_model},
            system_prompt=prompt,
            agent_result=intent_result,
        )
        finish_node_trace(nt, "SUCCESS", agent_snapshot=agent_snap, node_result=intent_result)

        return Command(
            update={
                "intent": intent,
                "query": effective_query,
                "long_term_context": long_term_ctx,     # 写入 State 供后续节点使用
                "messages": [HumanMessage(content=query)],
                "node_traces": state.node_traces + [nt],
            },
            goto=goto
        )

    except Exception as e:
        print(f"[IntentNode] 意图识别异常: {e}")
        finish_node_trace(nt, "FAILED")
        # 异常时默认走 CHAT 路径，让 normal_node 兜底处理
        return Command(
            update={
                "intent": IntentObject(intent_type=IntentType.CHAT, confidence=0.5),
                "error": f"意图识别失败: {str(e)}",
                "node_traces": state.node_traces + [nt],
            },
            goto="dispatcher"
        )
