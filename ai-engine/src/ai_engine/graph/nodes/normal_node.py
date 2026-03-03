"""
普通对话节点
处理简单需求（闲聊、简单问答），绑定权限为 public 的 Tool Cards
使用 ReAct 模式让 LLM 按需调用工具
"""

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

from ..state import AgentState, IntentType
from ...audit import start_node_trace, finish_node_trace, build_agent_snapshot
from ...config import get_settings
from ...registry import get_tool_registry


_NORMAL_SYSTEM_PROMPT = """你是一个专业、友好的 AI 助理。
你擅长回答用户的日常问题、进行轻松的对话，并在需要时调用可用工具来获取准确信息。

## 行为准则
1. 闲聊时保持热情自然，适当引导用户了解系统能够提供的功能。
2. 问答时直接、简洁地回答，如果有可用工具能够提升答案质量，请优先调用。
3. 不要编造数据，如果不确定请如实说明。
4. 回答使用中文，格式清晰。
"""


async def normal_node(state: AgentState, config: RunnableConfig) -> Command:
    """
    功能: 普通对话节点 - 处理 chat / question 意图
    职责:
    1. 从工具注册中心获取 public Tool Cards
    2. 构建绑定了 public 工具的 ReAct Agent
    3. 执行对话并生成回复
    4. 路由到 responder 节点输出最终结果
    """
    query = state.query
    token = state.token
    intent = state.intent

    # 审计埋点
    nt = start_node_trace("normal")

    settings = get_settings()
    tool_registry = get_tool_registry()

    # 获取权限为 public 的工具列表
    public_tools = tool_registry.get_public_tools(token) if token else []
    print(f"[Normal] 加载 public 工具数量: {len(public_tools)}")

    intent_label = intent.intent_type.value if intent else "unknown"

    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.llm_temperature,
            streaming=True,
        )

        if public_tools:
            # 有可用工具时，使用 ReAct Agent
            react_agent = create_react_agent(
                model=llm,
                tools=public_tools,
                prompt=_NORMAL_SYSTEM_PROMPT,
            )
            agent_input = {"messages": [HumanMessage(content=query)]}
            result = await react_agent.ainvoke(agent_input, config=config)
            # 取最后一条 AI 消息作为回复
            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            answer = ai_messages[-1].content if ai_messages else ""
        else:
            # 无工具时，直接对话
            messages = [
                SystemMessage(content=_NORMAL_SYSTEM_PROMPT),
                HumanMessage(content=query),
            ]
            response = await llm.ainvoke(messages, config=config)
            answer = response.content

        print(f"[Normal] 意图={intent_label}, 回复长度={len(answer)}")

        # 审计埋点
        agent_snap = build_agent_snapshot(
            model_config={"provider": "openai", "model_name": settings.llm_model},
            system_prompt=_NORMAL_SYSTEM_PROMPT,
            agent_result=answer,
        )
        finish_node_trace(nt, "SUCCESS", agent_snapshot=agent_snap, node_result=answer)

        return Command(
            update={
                "messages": [AIMessage(content=answer)],
                "node_traces": state.node_traces + [nt],
            },
            goto="responder",
        )

    except Exception as e:
        print(f"[Normal] 执行失败: {e}")
        finish_node_trace(nt, "FAILED")
        return Command(
            update={
                "error": f"普通对话处理失败: {str(e)}",
                "node_traces": state.node_traces + [nt],
            },
            goto="responder",
        )
