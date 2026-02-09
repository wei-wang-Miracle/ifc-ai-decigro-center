"""
意图识别节点
解析用户输入，判断意图类型并提取关键实体
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from ..state import AgentState, IntentObject, IntentType
from ...config import get_settings
from ...registry import get_tool_registry, get_agent_registry


# 意图识别 Prompt 模板
INTENT_RECOGNITION_PROMPT = """你是一个意图识别专家。请分析用户的输入，判断其意图类型并提取关键信息。
你的职责是精准识别用户提问的需求。
你的决策过程被总结为一个精准的意图类型：
## 意图类型说明
- **task**: 用户需要执行具体任务（如：查询数据、生成报告、执行操作等）
- **question**: 用户在进行简单问答（如：询问概念、请求解释等）
- **chat**: 用户进行闲聊（如：你好、早上好、你是谁等），需要热情回应并引导用户使用功能
- **clarify**: 用户输入不够明确，需要进一步澄清
- **unsupported**: 用户需求明确，但当前系统中没有任何 Tool Card 或 Agent Card 能够支持该需求
- **invalid**: 输入无效或无法理解
- **end**: 用户明确表示结束对话（如：谢谢、再见、不需要了等）

## 可用工具 (Tool Cards)
{tool_descriptions}

## 可用代理 (Agent Cards)
{agent_descriptions}

## 用户输入
{query}

## 分析结果
"""


def _get_llm() -> ChatOpenAI:
    """
    功能: 获取 LLM 实例 (按当前统一配置)
    """
    settings = get_settings()
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base,
        temperature=settings.llm_temperature,
    )




def intent_recognition_node(state: AgentState) -> dict[str, Any]:
    """
    功能: 意图识别节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典
    
    职责:
    1. 获取用户原始 Query
    2. 调用 LLM 进行意图识别
    3. 提取关键实体信息
    4. 返回结构化意图对象
    """
    query = state.query
    token = state.token

    # 获取工具和 Agent 描述
    tool_registry = get_tool_registry()
    agent_registry = get_agent_registry()
    
    # 加载可用工具摘要
    summaries = tool_registry.get_all_tool_summaries(token)
    tool_descriptions = "\n".join([
        f"- **{s['tool_name']}**: {s['tool_description']}"
        for s in summaries
    ]) if summaries else "暂无可用工具"
    
    # 加载可用 Agent 描述
    agents = agent_registry.get_agent_descriptions(token)
    agent_descriptions = "\n".join([
        f"- **{name}**: {desc}"
        for name, desc in agents.items()
    ]) if agents else "暂无可用 Agent"

    # 构建 Prompt
    prompt = INTENT_RECOGNITION_PROMPT.format(
        query=query,
        tool_descriptions=tool_descriptions,
        agent_descriptions=agent_descriptions
    )
    
    try:
        # 调用 LLM，使用 structured_output
        llm = _get_llm()
        structured_llm = llm.with_structured_output(IntentObject)
        
        # 获得结构化意图对象
        intent = structured_llm.invoke([HumanMessage(content=prompt)])
        
        print(f"[IntentNode] 识别结果: type={intent.intent_type.value}, confidence={intent.confidence}")
        
        # 决定下一个路由
        goto = "dispatcher"
        if intent.intent_type in [IntentType.END, IntentType.INVALID]:
            goto = "__end__"
        elif intent.intent_type == IntentType.UNSUPPORTED:
            # 如果不支持，直接去 responder 节点生成引导语
            goto = "responder"
        elif intent.intent_type == IntentType.CLARIFY:
            # 简单处理：如果是澄清，也先到 dispatcher 处理或者直接结束
            goto = "dispatcher"
            
        # 使用 LangGraph 1.0 的 Command 进行状态更新和跳转
        return Command(
            update={
                "intent": intent,
                "messages": [HumanMessage(content=query)],
            },
            goto=goto
        )
    
    except Exception as e:
        print(f"[IntentNode] 意图识别异常: {e}")
        return Command(
            update={
                "intent": IntentObject(
                    intent_type=IntentType.INVALID,
                    confidence=0.0,
                ),
                "error": f"意图识别失败: {str(e)}",
            },
            goto="__end__"
        )
