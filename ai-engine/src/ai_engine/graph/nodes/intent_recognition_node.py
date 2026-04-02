"""意图识别节点。

职责（三件事，不多不少）：
1. 指代消解与查询重写（仅基于近期对话上下文）
2. 意图三分类：TASK / CHAT / END
3. 生成 intent_summary 供下游节点直接消费

设计决策：
- 上下文裁剪：只注入 context_turns_summary + context_entities_summary，
  不注入 long_term_context 和 context_task_memory_summary，避免历史结论
  干扰意图判定（如重复查询同一基金画像被误判为 chat）
- 职责边界：意图识别只判"是否需要 Planner"，不选择具体 Planner，
  Agent 选择权归 Dispatcher
- planner_descriptions 的作用：让 LLM 知道系统的能力边界，
  作为 intent_type 判定的依据，不是 Planner 选择的输入
"""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from ...llm_factory import create_deterministic_llm
from ...registry import AgentType, get_agent_registry
from ..state import AgentState, IntentObject, IntentType

INTENT_RECOGNITION_PROMPT = """你是一个意图识别与查询重写专家。

## 你的职责
1. **指代消解与查询重写**：仅基于近期对话上下文，将用户的模糊表达重写为明确的查询语句（补充指代、省略的主体等）
2. **意图分类**：判断用户需求是否需要 PLANNER Agent 处理
3. **意图摘要**：用一句话概括用户的真实需求，供下游节点直接消费

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
- **只使用近期对话上下文**中的信息进行指代消解和省略补全，进行补全时要严格遵循上下文逻辑
- **严禁**凭空补充用户未在近期对话中提及的信息
- 若当前上下文中缺乏明确主体，应保持查询原样，判定为 chat 等待用户澄清

## 意图摘要规则
- 用一句自然语言概括用户的完整需求，包含关键实体和动作
- 摘要应足够清晰，让下游节点无需再解读原始 query
- 示例："用户需要获取基金 110011 的最新画像数据，属于基金分析类任务"
- 示例："用户在闲聊，询问今天天气如何"

## 可用 PLANNER Agent（只有这些能处理 TASK）
{planner_descriptions}

## 近期对话上下文
{context_summary}

## 当前用户输入
{query}

## 输出要求
返回 JSON 格式的意图识别结果。查询重写时仅基于近期对话上下文补全指代词和省略信息。

**重要**：当 intent_type 为 task 时，必须在 matched_planners 字段中返回最匹配的 PLANNER Agent 名称（agent_name）。
- 单任务场景：返回 1 个最匹配的 Planner 名称
- 多任务场景（用户需求涉及多个业务领域）：按优先级返回多个 Planner 名称
- 名称必须严格使用上方 PLANNER Agent 列表中出现的 agent_name，不得编造
"""


def _build_context_summary(state: AgentState) -> str:
    """构建意图识别所需的精简上下文。

    **设计决策**：意图识别的目标是指代消解 + 意图分类，
    只需要近期对话摘要和实体追踪。long_term_context 和
    context_task_memory_summary 会引入历史结论，可能导致
    LLM 误判"信息已有，不需要走 TASK"的问题（如用户重复
    查询同一基金画像时被错误判定为 chat），因此不在此注入。
    这两个字段在 State 中正常流转，由真正需要它们的下游节点
    （Normal / Planner）消费。
    """
    parts = []

    # 近期对话摘要：用于指代消解（"帮我看看它" → 确定"它"是什么）
    if state.context_turns_summary:
        parts.append(f"### 近期对话记录\n{state.context_turns_summary}")

    # 实体追踪：用于补全省略主体（如上文提到的基金代码）
    if state.context_entities_summary:
        parts.append(f"### 关键实体\n{state.context_entities_summary}")

    return "\n\n".join(parts) if parts else "无历史对话上下文"


async def intent_recognition_node(state: AgentState, config: RunnableConfig) -> Command:
    """意图识别节点 — 图的入口，追求轻、快、稳。

    职责：
    1. 指代消解与查询重写（仅基于近期对话上下文）
    2. 意图三分类：TASK / CHAT / END
    3. 生成 intent_summary 供下游 Dispatcher/Planner 直接消费
    4. 路由：END → __end__，其他 → dispatcher

    不做的事：
    - 不选择具体 Planner（归 Dispatcher）
    - 不注入 long_term_context / task_memory_summary（避免误判）
    """
    query = state.query
    token = state.token

    agent_registry = get_agent_registry()

    # PLANNER 描述作为 intent_type 判定的能力边界依据
    planner_descriptions = agent_registry.format_agent_descriptions(
        token, agent_type=AgentType.PLANNER, fallback="暂无可用 PLANNER Agent"
    )

    # 构建精简上下文（只含近期对话 + 实体追踪）
    context_summary = _build_context_summary(state)

    prompt = INTENT_RECOGNITION_PROMPT.format(
        planner_descriptions=planner_descriptions,
        context_summary=context_summary,
        query=query,
    )

    try:
        llm = create_deterministic_llm()
        structured_llm = llm.with_structured_output(IntentObject)

        intent: IntentObject = await structured_llm.ainvoke(
            [HumanMessage(content=prompt)],
            config=config,
        )

        # 回填 LLM 不感知的字段：原始查询
        intent.original_query = query

        # 重写后的查询供下游节点使用
        effective_query = intent.rewritten_query if intent.rewritten_query else query

        print(f"[IntentNode] 原始查询: {query}")
        if effective_query != query:
            print(f"[IntentNode] 重写查询: {effective_query}")
        print(
            f"[IntentNode] 识别结果: "
            f"type={intent.intent_type.value}, "
            f"confidence={intent.confidence}"
        )
        print(f"[IntentNode] 意图摘要: {intent.intent_summary}")
        if intent.matched_planners:
            print(f"[IntentNode] 匹配 Planner: {intent.matched_planners}")
        print(f"[IntentNode] 判断理由: {intent.reasoning}")

        # 路由：END 直接结束，其他走 dispatcher 统一调度
        goto = "__end__" if intent.intent_type == IntentType.END else "dispatcher"

        return Command(
            update={
                "intent": intent,
                "intent_summary": intent.intent_summary,
                "query": effective_query,
                # messages 保留原始 query（对话历史应反映用户原话）
                "messages": [HumanMessage(content=query)],
            },
            goto=goto,
        )

    except Exception as e:
        print(f"[IntentNode] 意图识别异常: {e}")
        # 异常时默认走 CHAT 路径，让 normal_node 兜底处理
        return Command(
            update={
                "intent": IntentObject(
                    intent_type=IntentType.CHAT,
                    confidence=0.5,
                ),
                "error": f"意图识别失败: {e!s}",
            },
            goto="dispatcher",
        )
