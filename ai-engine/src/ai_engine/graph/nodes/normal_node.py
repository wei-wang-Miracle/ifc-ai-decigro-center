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
from ...registry import get_tool_registry, get_agent_registry


_NORMAL_SYSTEM_PROMPT_TEMPLATE = """你是一个专业、友好的 AI 助理。
你擅长回答用户的日常问题、进行轻松的对话，并在需要时调用可用工具来获取准确信息。

## 系统能力
除了日常对话外，本系统还支持以下核心功能：

### 可直接使用的工具
{public_tools_section}

### 可调用的智能体（复杂任务）
当用户有更复杂的需求时，系统会自动选择合适的智能体来处理：
{planner_agents_section}

## 行为准则
1. 闲聊时保持热情自然，如果用户表达了特定需求，引导他们详细描述，以便系统更好地处理。
2. 问答时直接、简洁地回答，如果有可用工具能够提升答案质量，请优先调用。
3. 不要编造数据，如果不确定请如实说明。
4. 回答使用中文，格式清晰。
5. 当用户的需求涉及复杂任务时，告知用户可以直接描述需求，系统将自动进行任务规划和执行。
6. 根据上述系统能力，主动引导用户了解可以使用的功能。

## 引导示例
- 如果用户问"你能做什么"，根据上述系统能力详细介绍可用的工具和智能体功能。
- 如果用户有复杂的业务需求，引导他们详细描述，说明系统会智能规划并执行。
"""


def _build_system_prompt(token: str) -> str:
    """
    动态构建系统提示词，包含实际可用的工具和智能体信息
    """
    tool_registry = get_tool_registry()
    agent_registry = get_agent_registry()
    
    # 获取 public 工具摘要
    all_tool_summaries = tool_registry.get_all_tool_summaries(token)
    public_tool_summaries = [
        s for s in all_tool_summaries 
        if s.get("tool_privileges") == "public"
    ]
    
    if public_tool_summaries:
        tool_lines = []
        for summary in public_tool_summaries:
            alias = summary.get("tool_alias", summary.get("tool_name"))
            desc = summary.get("tool_description", "")
            tool_lines.append(f"- **{alias}**: {desc}")
        public_tools_section = "\n".join(tool_lines)
    else:
        public_tools_section = "当前无可直接使用的工具。"
    
    # 获取 PLANNER 类型的 Agent 摘要
    planner_descriptions = agent_registry.get_agent_descriptions(token, agent_type="PLANNER")
    
    if planner_descriptions:
        agent_lines = []
        for name, desc in planner_descriptions.items():
            agent_lines.append(f"- **{name}**: {desc}")
        planner_agents_section = "\n".join(agent_lines)
    else:
        planner_agents_section = "当前无可调用的复杂任务智能体。"
    
    return _NORMAL_SYSTEM_PROMPT_TEMPLATE.format(
        public_tools_section=public_tools_section,
        planner_agents_section=planner_agents_section,
    )


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

    # 动态构建系统提示词（包含 PLANNER agent 和工具信息）
    system_prompt = _build_system_prompt(token) if token else _NORMAL_SYSTEM_PROMPT_TEMPLATE.format(
        public_tools_section="当前无可直接使用的工具。",
        planner_agents_section="当前无可调用的复杂任务智能体。",
    )

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
                prompt=system_prompt,
            )
            agent_input = {"messages": [HumanMessage(content=query)]}
            result = await react_agent.ainvoke(agent_input, config=config)
            # 取最后一条 AI 消息作为回复
            ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
            answer = ai_messages[-1].content if ai_messages else ""
        else:
            # 无工具时，直接对话
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]
            response = await llm.ainvoke(messages, config=config)
            answer = response.content

        print(f"[Normal] 意图={intent_label}, 回复长度={len(answer)}")

        # 审计埋点
        agent_snap = build_agent_snapshot(
            model_config={"provider": "openai", "model_name": settings.llm_model},
            system_prompt=system_prompt,
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
