"""HITL 结构化审核数据契约。

定义多智能体人机回环（Human-in-the-Loop）全生命周期中流转的三个核心实体：
- Entity A: AgentHITLConfig — Agent 级别的人机回环配置（持久化在 AgentCard.humanReviewConfig）
- Entity B: ProfessionalAuditResponse — LLM 结构化输出，前端渲染为可交互审核面板
- Entity C: HumanDecisionPayload — 用户交互结果，传回后端驱动下游决策
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    """snake_case → camelCase（Pydantic alias 生成器）。"""
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


# ═══════════════════════════════════════════════════════════
#  Entity A: Agent 级别 HITL 配置
#  注意：Java/前端用 camelCase 存入 DB，Python 用 snake_case。
#  通过 alias_generator + populate_by_name 同时兼容两种命名。
# ═══════════════════════════════════════════════════════════


class HITLUISwitches(BaseModel):
    """UI 模块开关，控制前端渲染哪些审核板块。"""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    visual_data_enable: bool = Field(default=False, description="是否启用 ECharts 可视化图表")
    check_list_enable: bool = Field(default=False, description="是否启用结构化审核清单")
    proposals_enable: bool = Field(default=False, description="是否启用多维建议方案")


class HITLGenerationConstraints(BaseModel):
    """LLM 生成约束，引导大模型按指定维度输出审核内容。"""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    predictive_foresight_focus: list[str] = Field(
        default_factory=list,
        description="深度洞察方向：指导AI朝着什么方向多想一步（如合规、收益、未来趋势）",
    )
    executive_summary_perspectives: list[str] = Field(
        default_factory=list, description="摘要约束视角"
    )
    visual_data_perspectives: list[str] = Field(
        default_factory=list, description="图表约束视角"
    )
    check_list_dimensions: list[str] = Field(
        default_factory=list, description="CheckList 审核维度"
    )
    proposal_perspectives: list[str] = Field(
        default_factory=list, description="建议方案约束视角"
    )


class AgentHITLConfig(BaseModel):
    """Agent 级别的 HITL 完整配置。

    存储在 AgentCard.humanReviewConfig 中，由产品经理或产研在管理端配置。
    Python 侧从 agent_config.human_review_config 字典解析得到。
    数据从 Java/前端传入时为 camelCase，通过 alias_generator 自动映射到 snake_case。
    """

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    ui_switches: HITLUISwitches = Field(default_factory=HITLUISwitches)
    generation_constraints: HITLGenerationConstraints = Field(
        default_factory=HITLGenerationConstraints
    )

    # 兼容旧版字段（不含 ui_switches 的纯文本审核配置）
    review_dimensions: list[str] = Field(default_factory=list, description="审核维度（旧版兼容）")
    review_instruction: str = Field(default="", description="面向用户的审核引导语（旧版兼容）")
    summary_prompt: str = Field(default="", description="自定义审核摘要 prompt（旧版兼容）")

    def has_structured_hitl(self) -> bool:
        """判断是否启用了结构化 HITL（至少一个 UI 模块开启）。"""
        sw = self.ui_switches
        return sw.visual_data_enable or sw.check_list_enable or sw.proposals_enable


# ═══════════════════════════════════════════════════════════
#  Entity B: LLM 结构化输出 — ProfessionalAuditResponse
# ═══════════════════════════════════════════════════════════


class EChartsConfig(BaseModel):
    """ECharts 图表配置，前端直接调用 setOption(option) 渲染。"""

    title: str | None = Field(default=None, description="图表标题")
    chart_type: Literal["radar", "bar", "pie", "funnel", "sankey", "line", "none"] = Field(
        ..., description="图表的主要类型，前端据此决定容器尺寸或做降级处理"
    )
    option: dict[str, Any] = Field(
        ...,
        description="完全符合 Apache ECharts 官方 option 规范的 JSON 对象，"
        "前端收到后直接执行 myChart.setOption(option)",
    )
    insight_text: str = Field(..., description="对该图表数据的一句话专业解读")


class AuditCheckItem(BaseModel):
    """结构化审核清单条目。"""

    item_id: str = Field(..., description="条目唯一标识")
    task_label: str = Field(..., description="待办任务描述，如'核对基金经理变更时间'")
    ai_observation: str = Field(..., description="AI 的观察发现，如'公告与持仓变动存在2周偏差'")
    severity: Literal["low", "medium", "high"] = Field(
        default="medium", description="严重程度"
    )
    is_confirmed: bool = Field(default=False, description="是否已确认（默认未确认）")


class StrategicProposal(BaseModel):
    """多维建议方案。"""

    option_id: str = Field(..., description="方案唯一标识")
    title: str = Field(..., description="方案标题")
    is_recommond: bool = Field(..., description="是否是最推荐的方案")
    recommond_reason: str = Field(..., description="推荐理由")
    effort_estimation: Literal["low", "medium", "high"] = Field(
        ..., description="实施该方案的工作量/落地成本评估"
    )
    impact_analysis: str = Field(
        ...,
        description="采纳该方案可能带来的深远影响"
        "（如：风险化解程度、可能的副作用、时间窗口）",
    )


class ProfessionalAuditResponse(BaseModel):
    """综合审核输出模型 — LLM 结构化输出的 schema。

    前端收到后按模块渲染为可交互审核面板：
    - 摘要区：summary_title + executive_summary + advanced_foresight
    - 图表区：visual_data → ECharts setOption
    - 清单区：check_list → Checkbox 交互
    - 方案区：proposals → Radio Card 选择
    """

    summary_title: str = Field(..., description="审核摘要标题")
    executive_summary: str = Field(..., description="专业总结，体现洞察力")
    advanced_foresight: str = Field(
        ...,
        description="超出常规视角的深度预警或机会提示"
        "（例如关联宏观环境或同类资产历史教训，体现专家系统价值）",
    )
    visual_data: list[EChartsConfig] = Field(
        default_factory=list, description="前端直接提取并渲染的图表协议"
    )
    check_list: list[AuditCheckItem] = Field(
        default_factory=list, description="结构化审核清单"
    )
    proposals: list[StrategicProposal] = Field(
        default_factory=list, description="专家级建议列表"
    )


# ═══════════════════════════════════════════════════════════
#  Entity C: 用户决策 — HumanDecisionPayload
# ═══════════════════════════════════════════════════════════


class AcceptedCheckItem(BaseModel):
    """用户确认的审核清单条目（精简版，仅保留标识和描述）。"""

    item_id: str
    task_label: str
    ai_observation: str


class AcceptedProposal(BaseModel):
    """用户接受的建议方案（精简版）。"""

    option_id: str
    title: str


class DecisionGroup(BaseModel):
    """用户决策分组（接受/拒绝）。"""

    check_list: list[AcceptedCheckItem] = Field(default_factory=list)
    proposals: list[AcceptedProposal] = Field(default_factory=list)


class HumanDecisionPayload(BaseModel):
    """用户结构化决策载荷，由前端表单组装后传回后端。

    quick_decision_flag 决定处理路径：
    - approve_all_ai_recommendations: 全盘接受 AI 建议
    - reject_all: 全盘驳回
    - custom: 自定义选择（需解析 accepted/rejected）
    """

    session_id: str = Field(default="", description="会话标识")
    quick_decision_flag: Literal[
        "approve_all_ai_recommendations", "reject_all", "custom"
    ] = Field(..., description="快捷交互标识")
    accepted: DecisionGroup = Field(default_factory=DecisionGroup, description="用户接受的部分")
    rejected: DecisionGroup = Field(default_factory=DecisionGroup, description="用户拒绝的部分")
    comprehensive_supplementary_notes: str = Field(
        default="", description="用户对当前审批方案的整体补充说明"
    )

    def to_feedback_text(self) -> str:
        """将结构化决策转换为自然语言反馈文本，供下游 Agent 消费。"""
        if self.quick_decision_flag == "approve_all_ai_recommendations":
            return "用户已全部接受 AI 建议。"
        if self.quick_decision_flag == "reject_all":
            notes = self.comprehensive_supplementary_notes
            return f"用户全部驳回。补充说明：{notes}" if notes else "用户全部驳回，未提供补充说明。"

        parts = []
        if self.accepted.check_list:
            items = ", ".join(c.task_label for c in self.accepted.check_list)
            parts.append(f"接受的审核项: {items}")
        if self.accepted.proposals:
            opts = ", ".join(p.title for p in self.accepted.proposals)
            parts.append(f"采纳的方案: {opts}")
        if self.rejected.check_list:
            items = ", ".join(c.task_label for c in self.rejected.check_list)
            parts.append(f"拒绝的审核项: {items}")
        if self.rejected.proposals:
            opts = ", ".join(p.title for p in self.rejected.proposals)
            parts.append(f"拒绝的方案: {opts}")
        if self.comprehensive_supplementary_notes:
            parts.append(f"补充说明: {self.comprehensive_supplementary_notes}")
        return "\n".join(parts) if parts else "用户提交了自定义决策，但未选择任何条目。"
