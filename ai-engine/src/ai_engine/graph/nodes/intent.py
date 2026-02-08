"""
意图识别节点
解析用户输入，判断意图类型并提取关键实体
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from ..state import AgentState, IntentObject, IntentType
from ...config import get_settings


# 意图识别 Prompt 模板
INTENT_RECOGNITION_PROMPT = """你是一个意图识别专家。请分析用户的输入，判断其意图类型并提取关键信息。

## 意图类型说明
- **task**: 用户需要执行具体任务（如：查询数据、生成报告、执行操作等）
- **question**: 用户在进行简单问答（如：询问概念、请求解释等）
- **chat**: 用户进行闲聊（如：你好、早上好、你是谁等），需要热情回应并引导用户使用功能
- **clarify**: 用户输入不够明确，需要进一步澄清
- **invalid**: 输入无效或无法理解
- **end**: 用户明确表示结束对话（如：谢谢、再见、不需要了等）

## 输出格式
请以 JSON 格式返回，包含以下字段：
```json
{{
    "intent_type": "task|question|clarify|invalid|end",
    "confidence": 0.0-1.0,
    "entities": {{
        "key1": "value1",
        "key2": "value2"
    }},
    "clarification_needed": true|false,
    "clarification_question": "如果需要澄清，这里填写要问用户的问题"
}}
```

## 用户输入
{query}

## 分析结果
"""


def _get_llm() -> ChatOpenAI:
    """
    功能: 获取 LLM 实例
    参数: 无
    返回: ChatOpenAI 实例
    """
    settings = get_settings()
    
    if settings.llm_provider == "azure":
        from langchain_openai import AzureChatOpenAI
        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            deployment_name=settings.azure_openai_deployment,
            api_key=settings.openai_api_key,
            temperature=settings.llm_temperature,
        )
    else:
        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.llm_temperature,
        )


def _parse_intent_response(response_text: str) -> IntentObject:
    """
    功能: 解析 LLM 返回的意图识别结果
    参数: response_text - LLM 响应文本
    返回: IntentObject 实例
    """
    try:
        # 尝试从响应中提取 JSON
        # 处理可能被 markdown 代码块包裹的情况
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        data = json.loads(text.strip())
        
        intent_type_str = data.get("intent_type", "invalid").lower()
        intent_type = IntentType(intent_type_str) if intent_type_str in [e.value for e in IntentType] else IntentType.INVALID
        
        return IntentObject(
            intent_type=intent_type,
            confidence=float(data.get("confidence", 0.5)),
            entities=data.get("entities", {}),
            clarification_needed=data.get("clarification_needed", False),
            clarification_question=data.get("clarification_question", ""),
        )
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        # 解析失败，返回默认意图
        print(f"[IntentNode] 意图解析失败: {e}")
        return IntentObject(
            intent_type=IntentType.TASK,
            confidence=0.5,
            entities={},
            clarification_needed=False,
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
    query = state.get("query", "")
    
    if not query:
        return {
            "intent": IntentObject(
                intent_type=IntentType.INVALID,
                confidence=1.0,
            ),
            "error": "用户输入为空",
        }
    
    # 构建 Prompt
    prompt = INTENT_RECOGNITION_PROMPT.format(query=query)
    
    try:
        # 调用 LLM
        llm = _get_llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 解析响应
        intent = _parse_intent_response(response.content)
        
        print(f"[IntentNode] 识别结果: type={intent.intent_type.value}, confidence={intent.confidence}")
        
        # 返回状态更新
        return {
            "intent": intent,
            "messages": [HumanMessage(content=query)],
        }
    
    except Exception as e:
        print(f"[IntentNode] 意图识别异常: {e}")
        return {
            "intent": IntentObject(
                intent_type=IntentType.INVALID,
                confidence=0.0,
            ),
            "error": f"意图识别失败: {str(e)}",
        }
