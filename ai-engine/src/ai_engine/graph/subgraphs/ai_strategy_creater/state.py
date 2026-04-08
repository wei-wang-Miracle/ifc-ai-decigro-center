"""策略创建子图 State 定义。

StrategyCreationState 是子图内部的独立状态，不污染主图 AgentState。
子图通过输入/输出映射与主图交换数据：
- 输入：query, token, prior_step_outputs, phase, review_feedback
- 输出：output, success, phase, canvas_payload, design_intent, pseudo_code

5 阶段状态流转::

    准备阶段 → purpose_id, client_group_id 确定
    决策阶段 → selected_assemblies, pseudo_code, design_intent 产出
    人机回环 → is_approved 标记(子图通过 phase=pending_confirm 暂停)
    构建阶段 → canvas_payload 生成并通过 validate 校验
    创建验证 → strategy_id 写入，is_created_successfully 最终确认
"""

from pydantic import BaseModel, Field


class StrategyCreationState(BaseModel):
    """策略创建子图的状态定义。

    字段按职责分层：
    - 输入层：由主图 Executor 传入，子图只读
    - 工作层：子图节点读写，驱动 5 阶段流程推进
    - 输出层：子图完成后由主图 Executor 读取
    """

    # ── 输入层（主图 → 子图）──────────────────────────────
    query: str = Field(default="", description="用户原始需求")
    token: str = Field(default="", description="用户身份 Token，用于工具调用鉴权")
    prior_step_outputs: str = Field(
        default="",
        description="前序步骤的执行产出，供各阶段 LLM 作为上下文参考",
    )
    phase: str = Field(
        default="",
        description=(
            "执行阶段标识。空=首次执行(从准备阶段开始)；"
            "'resume_after_confirm'=用户确认后恢复执行(进入构建阶段)"
        ),
    )
    review_feedback: str = Field(
        default="",
        description="用户驳回时的修改意见，触发回滚到准备阶段重新评估",
    )

    # ── 工作层：Phase 1 准备阶段 ──────────────────────────
    purpose_id: int = Field(
        default=0,
        description="绑定的任务 ID，由准备阶段通过 list_my_purposes / save_purpose 确定",
    )
    client_group_id: int = Field(
        default=0,
        description="绑定的客群 ID，由准备阶段通过 list_my_client_groups 确定",
    )

    # ── 工作层：Phase 2 决策阶段 ──────────────────────────
    selected_assemblies: str = Field(
        default="",
        description='评估后决定需要使用的组件列表 JSON，例如 ["START", "APP_PUSH", "END"]',
    )
    pseudo_code: str = Field(
        default="",
        description="模型生成的策略伪代码，描述整体拓扑结构",
    )
    design_intent: str = Field(
        default="",
        description="易于向用户展示的设计意图说明",
    )

    # ── 工作层：Phase 4 构建阶段 ──────────────────────────
    canvas_payload: str = Field(
        default="",
        description=(
            "生成的、待提交的策略 JSON 结构(包含 strategy 和 canvasNodes)，"
            "由构建阶段 LLM 产出并经过 validate_strategy_canvas 校验"
        ),
    )
    is_validated: bool = Field(
        default=False,
        description="是否已通过 validate_strategy_canvas 参数合法性校验",
    )

    # ── 工作层：Phase 5 创建验证阶段 ──────────────────────
    strategy_id: int = Field(
        default=0,
        description="成功落库后返回的策略流水 ID",
    )

    # ── 工作层：通用 ────────────────────────────────────
    error: str = Field(
        default="",
        description="执行过程中的错误信息",
    )

    # ── 输出层（子图 → 主图）──────────────────────────────
    output: str = Field(
        default="",
        description="最终输出文本，供主图 StepResult.output 消费",
    )
    success: bool = Field(
        default=True,
        description="子图执行是否成功",
    )
