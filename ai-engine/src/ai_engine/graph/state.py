"""
AgentState 定义
LangGraph 状态机的核心数据结构
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Any, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages


class IntentType(str, Enum):
    """意图类型枚举"""
    TASK = "task"            # 需要执行任务
    QUESTION = "question"    # 简单问答
    CLARIFY = "clarify"      # 需要澄清
    CHAT = "chat"            # 闲聊
    INVALID = "invalid"      # 无效输入
    END = "end"              # 结束对话


class ReviewStatus(str, Enum):
    """审核状态枚举"""
    PENDING = "pending"      # 待审核
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已驳回


class StepStatus(str, Enum):
    """步骤状态枚举"""
    PENDING = "pending"      # 待执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 执行失败
    NEEDS_REVIEW = "needs_review"  # 需要审核


@dataclass
class IntentObject:
    """
    功能: 意图识别结果对象
    参数:
        intent_type - 意图类型
        confidence - 置信度 (0-1)
        entities - 提取的实体信息
        clarification_needed - 是否需要澄清
    """
    intent_type: IntentType
    confidence: float = 0.0
    entities: dict[str, Any] = field(default_factory=dict)
    clarification_needed: bool = False
    clarification_question: str = ""


@dataclass
class PlanStep:
    """
    功能: 任务计划步骤
    参数:
        step_id - 步骤唯一标识
        description - 步骤描述
        assigned_agent - 分配的 Agent 名称
        expected_tools - 预期使用的工具列表
        status - 步骤状态
        dependencies - 依赖的前置步骤 ID 列表
    """
    step_id: str
    description: str
    assigned_agent: str | None = None
    expected_tools: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    dependencies: list[str] = field(default_factory=list)


@dataclass
class StepResult:
    """
    功能: 步骤执行结果
    参数:
        step_id - 对应的步骤 ID
        success - 是否成功
        output - 输出内容
        error - 错误信息（如果失败）
        tools_called - 实际调用的工具列表
        require_review - 是否触发审核
    """
    step_id: str
    success: bool = True
    output: str = ""
    error: str = ""
    tools_called: list[str] = field(default_factory=list)
    require_review: bool = False


class AgentState:
    """
    功能: LangGraph 状态定义 (TypedDict 风格)
    
    使用说明:
    - query: 用户原始输入
    - user_id: 用户标识
    - session_id: 会话标识
    - thread_id: LangGraph 线程 ID
    - messages: 对话历史（使用 add_messages reducer 自动合并）
    - intent: 意图识别结果
    - plan: 任务计划（步骤列表）
    - current_step_index: 当前执行的步骤索引
    - step_results: 所有步骤的执行结果
    - require_review: 是否需要人工审核
    - review_status: 审核状态
    - review_feedback: 审核反馈
    - selected_agent: 当前选择的 Agent 名称
    - error: 全局错误信息
    """
    pass


# TypedDict 版本的状态定义（LangGraph 使用）
from typing import TypedDict


class AgentState(TypedDict):
    """
    功能: LangGraph 核心状态结构
    
    所有节点共享此状态，通过返回更新的字段来修改状态
    """
    # 用户输入
    query: str
    user_id: str
    session_id: str
    thread_id: str
    
    # 对话历史（使用 add_messages 自动合并）
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 意图识别
    intent: Optional[IntentObject]
    
    # 任务计划
    plan: Optional[list[PlanStep]]
    current_step_index: int
    
    # 执行结果
    step_results: list[StepResult]
    
    # 审核相关
    require_review: bool
    review_status: Optional[ReviewStatus]
    review_feedback: Optional[str]
    
    # Agent 选择
    selected_agent: Optional[str]
    
    # 错误信息
    error: Optional[str]


def create_initial_state(
    query: str,
    user_id: str,
    session_id: str,
    thread_id: str = ""
) -> AgentState:
    """
    功能: 创建初始状态
    参数:
        query - 用户输入
        user_id - 用户标识
        session_id - 会话标识
        thread_id - 线程标识（可选）
    返回: 初始化的 AgentState
    """
    return AgentState(
        query=query,
        user_id=user_id,
        session_id=session_id,
        thread_id=thread_id or f"{session_id}_{user_id}",
        messages=[],
        intent=None,
        plan=None,
        current_step_index=0,
        step_results=[],
        require_review=False,
        review_status=None,
        review_feedback=None,
        selected_agent=None,
        error=None,
    )
