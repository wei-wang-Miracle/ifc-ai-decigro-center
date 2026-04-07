"""客群创建子图 State 定义。

ClientGroupState 是子图内部的独立状态，不污染主图 AgentState。
子图通过输入/输出映射与主图交换数据：
- 输入：query, token, prior_step_outputs, phase, review_feedback
- 输出：output, success, phase, create_payload, preview_result
"""

from pydantic import BaseModel, Field


class ClientGroupState(BaseModel):
    """客群创建子图的状态定义。

    字段按职责分层：
    - 输入层：由主图 Executor 传入，子图只读
    - 工作层：子图节点读写，驱动流程推进
    - 输出层：子图完成后由主图 Executor 读取
    """

    # ── 输入层（主图 → 子图）──────────────────────────────
    query: str = Field(default="", description="用户原始需求")
    token: str = Field(default="", description="用户身份 Token，用于工具调用鉴权")
    prior_step_outputs: str = Field(
        default="",
        description="前序步骤的执行产出，供 LLM 构建条件时作为上下文参考",
    )
    phase: str = Field(
        default="",
        description="执行阶段标识。空=首次执行；'resume_after_confirm'=用户确认后恢复执行",
    )
    review_feedback: str = Field(
        default="",
        description="用户驳回时的修改意见，供 build_group 重新构建条件",
    )

    # ── 工作层（子图内部读写）──────────────────────────────
    labels_cache: str = Field(
        default="",
        description="query_all_labels 返回的标签列表 JSON，避免重复调用",
    )
    create_payload: str = Field(
        default="",
        description="可直接用于 create_client_group 的完整参数 JSON dict，"
        "由 build_group_node 的 LLM structured output 产出，不硬编码任何字段名",
    )
    preview_result: str = Field(
        default="",
        description="最后一次 preview_client_group_count 的返回结果",
    )
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
