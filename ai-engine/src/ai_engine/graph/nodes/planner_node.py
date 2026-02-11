"""
规划节点
将用户需求拆解为有序的执行步骤
"""

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command

from ..state import AgentState, PlanStep, StepStatus
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from ...audit import start_node_trace, finish_node_trace, build_agent_snapshot

class PlanOutput(BaseModel):
    """
    功能: 规划输出容器
    """
    reasoning: str = Field(description="规划思路：简要分析用户需求，解释为什么采用这种任务组合和顺序")
    steps: list[PlanStep] = Field(description="有序的任务执行步骤列表")

from ...config import get_settings
from ...registry import get_tool_registry, get_agent_registry


# 任务规划 Prompt 模板
PLANNER_PROMPT = """你是一个任务规划专家。
你需要运用 Chain-of-Thought (思维链) 方法，请将用户的需求拆解为清晰、有序的执行步骤，你的核心价值在于"谋定而后动"，通过逻辑推演确保方案的专业性和可行性。
## 可用工具
{tool_descriptions}

## 可用 Agent
{agent_descriptions}

## 用户需求
{user_query}

{context}

## 注意事项
1. 步骤应该足够具体，可以直接执行
2. 步骤之间的依赖关系要明确
3. 每个步骤尽量只做一件事
4. 考虑失败情况的处理
5. **人机协同判断**：对于涉及敏感操作（如删除数据、修改配置、资金操作等）或需要用户确认的关键决策节点，请将 requires_review 设为 true

## 执行计划 (JSON 输出要求)
每个步骤必须包含:
- step_id: 必须是字符串 (如 "1", "2")
- description: 步骤描述
- assigned_agent: 指定执行的 Agent (可选)
- expected_tools: 预计需要的工具列表 (可选)
- dependencies: 依赖的步骤 ID 列表 (如 ["1"])
- requires_review: 是否需要人工审核确认 (布尔值，默认 false，对于关键决策节点设为 true)
"""


def _build_context(state: AgentState) -> str:
    """
    功能: 构建上下文信息
    参数: state - 当前状态
    返回: 上下文字符串
    """
    context_parts = []
    
    # 添加之前的执行结果
    step_results = state.step_results
    if step_results:
        results_text = "\n".join([
            f"- 步骤 {r.step_id}: {'成功' if r.success else '失败'} - {r.output or r.error}"
            for r in step_results
        ])
        context_parts.append(f"## 之前的执行结果\n{results_text}")
    
    # 添加审核反馈
    review_feedback = state.review_feedback
    if review_feedback:
        context_parts.append(f"## 人工审核反馈\n{review_feedback}")
    
    return "\n\n".join(context_parts) if context_parts else ""


async def planner_node(state: AgentState, config: RunnableConfig) -> Command:
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
    query = state.query
    token = state.token

    # 审计埋点
    nt = start_node_trace("planner")
    
    # 获取工具和 Agent 描述
    tool_registry = get_tool_registry()
    agent_registry = get_agent_registry()
    
    # 构建工具描述
    summaries = tool_registry.get_all_tool_summaries(token)
    tool_descriptions = "\n".join([
        f"- **{s['tool_name']}**: {s['tool_description']}"
        for s in summaries
    ]) if summaries else "暂无可用工具"
    
    # 构建 Agent 描述
    agents = agent_registry.get_agent_descriptions(token)
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
            streaming=True
        )
        
        # 使用 structured_output
        structured_llm = llm.with_structured_output(PlanOutput)
        response = await structured_llm.ainvoke(prompt, config=config)
        
        plan = response.steps
        
        print(f"[Planner] LLM 响应内容: {response}")
        print(f"[Planner] 成功生成计划: {len(plan)} 个步骤")
        for step in plan:
            print(f"  - [{step.step_id}] {step.description} (Agent: {step.assigned_agent}, Tools: {step.expected_tools}, Deps: {step.dependencies})")
        
        # 审计埋点：记录规划成功
        plan_result = f"生成 {len(plan)} 步计划: " + "; ".join([f"[{s.step_id}] {s.description}" for s in plan])
        agent_snap = build_agent_snapshot(
            model_config={"provider": "openai", "model_name": settings.llm_model},
            system_prompt=prompt,
            agent_result=plan_result,
        )
        finish_node_trace(nt, "SUCCESS", agent_snapshot=agent_snap, node_result=plan_result)

        return Command(
            update={
                "plan": plan,
                "current_step_index": 0,
                "messages": [AIMessage(content=f"[Planner] 已生成 {len(plan)} 步计划")],
                "node_traces": state.node_traces + [nt],
            },
            goto="dispatcher"
        )
    
    except Exception as e:
        print(f"[Planner] 规划失败: {e}")
        finish_node_trace(nt, "FAILED")
        return Command(
            update={
                "plan": [],
                "error": f"任务规划失败: {str(e)}",
                "node_traces": state.node_traces + [nt],
            },
            goto="responder"
        )
