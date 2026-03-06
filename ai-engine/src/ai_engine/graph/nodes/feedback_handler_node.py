"""
反馈处理节点
处理人工驳回后的反馈，调整计划或重试
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, Field

from ..state import AgentState, ReviewStatus
from ...config import get_settings


class FeedbackClassification(BaseModel):
    """反馈分类结果"""
    needs_replan: bool = Field(description="是否需要全量重新规划（含主体变更、需重新规划等场景）")
    reasoning: str = Field(default="", description="判断理由")


import re

_REPLAN_KEYWORDS = ["重新规划", "换个方案", "重做", "from scratch", "start over"]

# 匹配 6 位纯数字基金代码（如 513120、510300 等）
_FUND_CODE_PATTERN = re.compile(r'\b\d{6}\b')

_FEEDBACK_CLASSIFY_PROMPT = """判断用户对 AI 输出的反馈是否需要"全量重新规划"。

需要全量重新规划的情况（满足任意一项即是）：
1. **主体变更**：用户更换了任务的核心主体（如：更换基金代码、更换产品、更换目标对象等）
2. **任务变更**：用户要求的业务目标发生了本质改变（如：从生成销售方案改为分析客群画像、从推荐客群改为风险评估等），导致原有步骤和工具调用不再适用
3. **明确重做**：用户明确要求重新规划、重做或换个方案

仅需调整当前步骤的情况（满足以下全部条件）：
- 主体未变（相同的基金代码、产品、目标等）
- 业务目标未变（仍是同一类任务）
- 用户只是对当前步骤的执行细节有修改意见（如：聚焦某个维度、调整筛选条件、补充某些指标等）

用户反馈：{feedback}

只返回 JSON，不要额外解释。"""


def _classify_feedback_by_pattern(feedback: str) -> bool | None:
    """
    快速模式检测：关键词 + 正则，覆盖高置信度场景，返回 None 表示需要 LLM 兜底。

    True  = 需要全量重新规划
    False = 仅调整当前步骤（暂不判断，留给 LLM）
    None  = 无法确定，交给 LLM
    """
    # 明确重做关键词
    if any(kw in feedback for kw in _REPLAN_KEYWORDS):
        return True

    # 出现 6 位基金代码 → 主体变更，需全量重新规划
    if _FUND_CODE_PATTERN.search(feedback):
        return True

    return None


async def _classify_feedback(feedback: str) -> bool:
    """
    使用关键词/正则 + LLM 判断反馈是否需要全量重新规划
    返回: True=需要重新规划, False=仅调整当前步骤

    需要重新规划的三种情况：
    1. 主体变更（更换基金代码、产品、目标对象等）
    2. 任务变更（业务目标本质改变，原有步骤不再适用）
    3. 明确重做（用户明确要求重新规划/换方案）
    """
    # 关键词 + 正则快速判断（高置信度，无需 LLM）
    fast_result = _classify_feedback_by_pattern(feedback)
    if fast_result is not None:
        print(f"[FeedbackHandler] 快速匹配: needs_replan={fast_result}")
        return fast_result

    # LLM 判断（覆盖任务变更等复杂场景，关键词/正则无法识别的情况）
    try:
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            temperature=0.0,
            max_tokens=100,
        )
        structured_llm = llm.with_structured_output(FeedbackClassification)
        prompt = _FEEDBACK_CLASSIFY_PROMPT.format(feedback=feedback)
        result: FeedbackClassification = await structured_llm.ainvoke([HumanMessage(content=prompt)])
        print(f"[FeedbackHandler] LLM 分类: needs_replan={result.needs_replan}, 理由={result.reasoning}")
        return result.needs_replan
    except Exception as e:
        # LLM 不可用时（限流、超时等），保守策略：触发全量重新规划
        # 宁可多重规划一次，也不能用错误的数据继续执行
        print(f"[FeedbackHandler] LLM 分类失败，保守策略触发重新规划: {e}")
        return True


async def feedback_handler_node(state: AgentState) -> Command:
    """
    功能: 反馈处理节点 - LangGraph 节点函数
    参数: state - 当前状态
    返回: 状态更新字典

    职责:
    1. 接收人工驳回的反馈意见
    2. 判断是"全量重新规划"（含主体变更）还是"调整当前步骤"
    3. 全量重新规划：清空计划、步骤结果、索引，路由到 Planner
    4. 调整当前步骤：保留计划和已有结果，反馈注入 Executor 重试
    """
    review_feedback = state.review_feedback or ""
    review_status = state.review_status

    # 只在驳回状态下处理
    if review_status != ReviewStatus.REJECTED:
        return Command(
            update={
                "messages": [AIMessage(content="[FeedbackHandler] 非驳回状态，无需处理")],
            },
            goto="dispatcher"
        )

    print(f"[FeedbackHandler] 处理反馈: {review_feedback}")

    should_replan = await _classify_feedback(review_feedback)

    if should_replan:
        # 全量重新规划：清空计划、已有步骤结果和索引，让 Dispatcher 路由到 Planner
        print("[FeedbackHandler] 需要全量重新规划（主体变更或用户要求重做）")
        return Command(
            update={
                "plan": None,
                "current_step_index": 0,
                "step_results": [],
                "review_status": None,
                "review_feedback": review_feedback,  # 保留反馈给 Planner 参考
                "messages": [AIMessage(content=f"[FeedbackHandler] 根据反馈全量重新规划: {review_feedback}")],
            },
            goto="dispatcher"
        )
    else:
        # 仅调整当前步骤：保留计划和已有步骤结果，反馈注入 Executor 重试
        print(f"[FeedbackHandler] 调整当前步骤执行方式，反馈已保留供 Executor 使用")
        return Command(
            update={
                "review_status": None,
                "review_feedback": review_feedback,  # 保留反馈供 Executor 使用
                "messages": [AIMessage(content=f"[FeedbackHandler] 根据反馈调整: {review_feedback}")],
            },
            goto="dispatcher"
        )
