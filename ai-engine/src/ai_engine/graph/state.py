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
    """
    意图类型枚举（简化版）
    - TASK: 明确需要 PLANNER Agent 支持的复杂业务任务
    - CHAT: 其他所有场景（闲聊、问答、澄清、引导、不支持等）
    - END: 明确结束对话
    """
    TASK = "task"    # 需要 PLANNER 处理的复杂业务任务
    CHAT = "chat"    # 其他所有：闲聊、问答、澄清、引导等
    END = "end"      # 明确结束对话


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


from pydantic import BaseModel, Field, AliasChoices, field_validator


class IntentObject(BaseModel):
    """
    功能: 意图识别结果对象 (Pydantic 模型)
    """
    intent_type: IntentType = Field(description="识别出的意图类型")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="意图识别的置信度 (0-1)")
    entities: dict[str, Any] = Field(default_factory=dict, description="提取到的关键实体信息")
    clarification_needed: bool = Field(default=False, description="是否需要用户进一步澄清")
    clarification_question: str = Field(default="", description="向用户提出的澄清问题内容")




class PlanStep(BaseModel):
    """
    功能: 任务计划步骤 (Pydantic 模型)
    """
    step_id: str = Field(
        validation_alias=AliasChoices("step_id", "id", "step", "step_number", "step_num","step_order"),
        description="步骤的唯一标识符"
    )
    description: str = Field(description="步骤的具体描述")
    assigned_agent: Optional[str] = Field(default=None, description="分配执行该步骤的特定 Agent 名称")
    expected_tools: list[str] = Field(default_factory=list, description="预计该步骤需要调用的工具列表")
    status: StepStatus = Field(default=StepStatus.PENDING, description="当前步骤的执行状态")
    dependencies: list[str] = Field(
        default_factory=list, 
        validation_alias=AliasChoices("dependencies", "depends_on"),
        description="该步骤依赖的其他步骤 ID 列表"
    )
    
    # --- 人机协同字段 ---
    requires_review: bool = Field(
        default=False,
        description="是否需要人工审核确认。True 表示任务执行后需等待用户批准才能推进到下一步（用于关键决策节点）"
    )

    @field_validator("dependencies", mode="before")
    @classmethod
    def ensure_list_str(cls, v: Any) -> list[str]:
        """确保 dependencies 始终为字符串列表"""
        if isinstance(v, list):
            return [str(item) for item in v]
        return v

    @field_validator("step_id", mode="before")
    @classmethod
    def ensure_str(cls, v: Any) -> str:
        """确保 step_id 始终为字符串"""
        if isinstance(v, (int, float)):
            return str(v)
        return v


class StepResult(BaseModel):
    """
    功能: 步骤执行结果 (Pydantic 模型)
    """
    step_id: str = Field(description="对应步骤的 ID")
    success: bool = Field(default=True, description="步骤是否执行成功")
    output: str = Field(default="", description="步骤执行的输出结果或回答")
    error: str = Field(default="", description="执行失败时的错误信息")
    tools_called: list[str] = Field(default_factory=list, description="该步骤实际调用的工具名称列表")
    require_review: bool = Field(default=False, description="该步骤的结果是否触发了安全策略，需要人工审核")


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
    - current_planner: 当前 Planner
    - current_executor: 当前 Executor
    - error: 全局错误信息
    """
    pass


# TypedDict 版本的状态定义（LangGraph 使用）


class AgentState(BaseModel):
    """
    功能: LangGraph 核心状态结构 (Pydantic 模型)
    
    所有节点共享此状态，通过返回更新的字段来修改状态
    """
    # 用户输入
    query: str = Field(default="", description="用户原始输入的查询内容")
    user_id: str = Field(default="", description="发起请求的用户唯一标识符")
    session_id: str = Field(default="", description="当前对话的会话标识符")
    
    # 任务与链路追踪
    task_id: str = Field(default="", description="当前任务标识符，一个 plan 执行完毕后更新")
    trace_id: str = Field(default="", description="链路追踪 ID，用于审计和问题排查")
    task_completed: bool = Field(default=False, description="当前 plan 是否已全部执行完成")
    
    # 对话历史（使用 add_messages 自动合并）
    messages: Annotated[list[BaseMessage], add_messages] = Field(
        default_factory=list, 
        description="对话历史记录，包含用户和 AI 的交互消息"
    )
    
    # 意图识别
    intent: Optional[IntentObject] = Field(default=None, description="当前的意图识别详细结果")
    
    # 任务计划
    plan: Optional[list[PlanStep]] = Field(default=None, description="拆解后的任务执行计划步骤列表")
    current_step_index: int = Field(default=0, description="当前正在执行或准备执行的计划步骤索引")
    
    # 执行结果
    step_results: list[StepResult] = Field(default_factory=list, description="所有已执行步骤的结果记录列表")
    
    # 审核相关
    require_review: bool = Field(default=False, description="当前工作流是否由于安全策略进入‘等待审核’状态")
    review_status: Optional[ReviewStatus] = Field(default=None, description="当前人工审核的状态（待审、通过、驳回）")
    review_feedback: Optional[str] = Field(default=None, description="人工审核提供的反馈或说明意见")
    
    # Agent 选择 (Hierarchical Routing)
    current_planner: Optional[str] = Field(default=None, description="当前负责拆解和分发任务的 Planner Agent 名称")
    current_executor: Optional[str] = Field(default=None, description="当前正在执行任务的 Executor Agent 名称")
    
    # 错误信息
    error: Optional[str] = Field(default=None, description="工作流执行过程中产生的全局错误或异常信息")

    # 规划思路（planner 节点写入，供前端展示）
    plan_reasoning: Optional[str] = Field(default=None, description="Planner 制定计划时的推理过程")

    # 用户认证 Token (用于动态注册权限校验)
    token: Optional[str] = Field(default=None, description="用于 API 调用和权限控制的用户认证 Token")

    # 上下文管理：由 ContextManager 在请求开始时注入，节点直接读取使用
    context_turns_summary: str = Field(default="", description="近期对话摘要（由 ContextManager 压缩注入）")
    context_entities_summary: str = Field(default="", description="当前会话追踪到的关键实体摘要")
    context_task_memory_summary: str = Field(default="", description="历史相关任务执行结果摘要（跨轮次记忆）")
    long_term_context: str = Field(default="", description="从长期记忆检索到的用户事实与经验摘要（跨会话）")

    # 审计追踪：各图节点的执行记录（由各节点自行追加）
    node_traces: list[dict] = Field(
        default_factory=list,
        description="图节点执行追踪记录列表，每个节点完成后追加自身的 trace 数据"
    )


def create_initial_state(
    query: str,
    user_id: str,
    session_id: str,
    task_id: str = "",
    trace_id: str = "",
    token: Optional[str] = None,
    context_turns_summary: str = "",
    context_entities_summary: str = "",
    context_task_memory_summary: str = "",
    long_term_context: str = "",
) -> AgentState:
    """
    功能: 创建初始状态
    参数:
        query - 用户输入
        user_id - 用户标识
        session_id - 会话标识
        task_id - 任务标识（可选，首次请求时自动生成）
        trace_id - 链路追踪 ID（每次请求必须生成）
        token - 用户认证 Token（可选）
        context_turns_summary - 近期对话摘要（由 ContextManager 注入）
        context_entities_summary - 实体追踪摘要（由 ContextManager 注入）
        context_task_memory_summary - 历史任务记忆摘要（由 ContextManager 注入）
        long_term_context - 长期记忆检索结果（由 LongTermMemoryManager 注入）
    返回: 初始化的 AgentState
    """
    import uuid
    return AgentState(
        query=query,
        user_id=user_id,
        session_id=session_id,
        task_id=task_id or f"task_{uuid.uuid4().hex[:12]}",
        trace_id=trace_id or f"trace_{uuid.uuid4().hex[:16]}",
        task_completed=False,
        messages=[],
        intent=None,
        plan=None,
        current_step_index=0,
        step_results=[],
        require_review=False,
        review_status=None,
        review_feedback=None,
        current_planner=None,
        current_executor=None,
        error=None,
        token=token,
        context_turns_summary=context_turns_summary,
        context_entities_summary=context_entities_summary,
        context_task_memory_summary=context_task_memory_summary,
        long_term_context=long_term_context,
        node_traces=[],
    )
