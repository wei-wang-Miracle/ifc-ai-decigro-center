"""
规划节点
将用户需求拆解为有序的执行步骤
"""

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from ..state import AgentState, PlanStep, StepStatus
from ...config import get_settings
from ...registry import get_tool_registry, get_agent_registry


# 任务规划 Prompt 模板
PLANNER_PROMPT = """你是一个任务规划专家。请将用户的需求拆解为清晰、有序的执行步骤。

## 可用工具
{tool_descriptions}

## 可用 Agent
{agent_descriptions}

## 用户需求
{user_query}

{context}

## 输出格式
请以 JSON 数组格式返回计划步骤，每个步骤包含：
- step_id: 步骤唯一 ID (如 "step_1")
- description: 步骤描述（清晰说明要做什么）
- assigned_agent: 建议执行的 Agent 名称（可选，留空由系统自动分配）
- expected_tools: 预期使用的工具名称列表（可选）
- dependencies: 依赖的前置步骤 ID 列表（可选）

```json
[
    {{
        "step_id": "step_1",
        "description": "第一步要做的事情",
        "assigned_agent": null,
        "expected_tools": ["tool_name"],
        "dependencies": []
    }}
]
```

## 注意事项
1. 步骤应该足够具体，可以直接执行
2. 步骤之间的依赖关系要明确
3. 每个步骤尽量只做一件事
4. 考虑失败情况的处理

## 执行计划
"""


def _build_context(state: AgentState) -> str:
    """
    功能: 构建上下文信息
    参数: state - 当前状态
    返回: 上下文字符串
    """
    context_parts = []
    
    # 添加之前的执行结果
    step_results = state.get("step_results", [])
    if step_results:
        results_text = "\n".join([
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'} - {r.output or r.error}"
            for r in step_results
        ])
        context_parts.append(f"## 之前的执行结果\n{results_text}")
    
    # 添加审核反馈
    review_feedback = state.get("review_feedback")
    if review_feedback:
        context_parts.append(f"## 人工审核反馈\n{review_feedback}")
    
    return "\n\n".join(context_parts) if context_parts else ""


def _parse_plan_response(response_text: str) -> list[PlanStep]:
    """
    功能: 解析 LLM 返回的规划结果
    参数: response_text - LLM 响应文本
    返回: PlanStep 列表
    """
    try:
        # 尝试从响应中提取 JSON
        text = response_text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        data = json.loads(text.strip())
        
        steps = []
        for item in data:
            step = PlanStep(
                step_id=item.get("step_id", f"step_{uuid.uuid4().hex[:8]}"),
                description=item.get("description", ""),
                assigned_agent=item.get("assigned_agent"),
                expected_tools=item.get("expected_tools", []),
                status=StepStatus.PENDING,
                dependencies=item.get("dependencies", []),
            )
            steps.append(step)
        
        return steps
    
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[Planner] 规划解析失败: {e}")
        # 返回一个默认步骤
        return [
            PlanStep(
                step_id="step_1",
                description="执行用户请求的任务",
                status=StepStatus.PENDING,
            )
        ]


def planner_node(state: AgentState) -> dict[str, Any]:
    """
    功能: 规划节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典
    
    职责:
    1. 获取用户需求和上下文
    2. 获取可用工具和 Agent 列表
    3. 调用 LLM 生成执行计划
    4. 返回计划步骤列表
    """
    query = state.get("query", "")
    
    # 获取工具和 Agent 描述
    tool_registry = get_tool_registry()
    agent_registry = get_agent_registry()
    
    # 构建工具描述
    summaries = tool_registry.get_all_tool_summaries()
    tool_descriptions = "\n".join([
        f"- **{s['tool_name']}**: {s['tool_description']}"
        for s in summaries
    ]) if summaries else "暂无可用工具"
    
    # 构建 Agent 描述
    agents = agent_registry.get_agent_descriptions()
    agent_descriptions = "\n".join([
        f"- **{name}**: {desc}"
        for name, desc in agents.items()
    ]) if agents else "暂无可用 Agent"
    
    # 构建上下文
    context = _build_context(state)
    
    # 构建 Prompt
    prompt = PLANNER_PROMPT.format(
        tool_descriptions=tool_descriptions,
        agent_descriptions=agent_descriptions,
        user_query=query,
        context=context,
    )
    
    try:
        # 调用 LLM
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=settings.llm_temperature,
        )
        
        response = llm.invoke(prompt)
        
        # 解析计划
        plan = _parse_plan_response(response.content)
        
        print(f"[Planner] 生成计划: {len(plan)} 个步骤")
        for step in plan:
            print(f"  - {step.step_id}: {step.description}")
        
        return {
            "plan": plan,
            "current_step_index": 0,
            "messages": [AIMessage(content=f"[Planner] 已生成 {len(plan)} 步计划")],
        }
    
    except Exception as e:
        print(f"[Planner] 规划失败: {e}")
        return {
            "plan": [],
            "error": f"任务规划失败: {str(e)}",
        }
