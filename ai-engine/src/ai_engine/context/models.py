"""
上下文管理模块 - 数据模型
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ConversationTurn:
    """
    单轮对话记录。
    记录一次完整的用户提问和系统响应，以及本轮产生的任务信息。
    """
    turn_id: str                            # 轮次唯一标识（task_id）
    query: str                              # 用户原始输入
    rewritten_query: str                    # 重写后的查询
    response: str                           # 系统最终响应
    intent_type: str                        # 意图类型（task/chat/end）
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 任务相关（intent=task 时有值）
    task_summary: str = ""                  # 任务执行摘要（各步骤结果压缩）
    entities: dict[str, Any] = field(default_factory=dict)  # 本轮提取的实体


@dataclass
class TaskMemory:
    """
    单次任务的执行记忆。
    保存一次 TASK 执行的关键输入/输出，供后续任务引用。

    场景示例（基金销售方案）：
    - fund_code: "513130"
    - fund_profile: "恒生科技 ETF，规模 8.9 亿，QDII..."
    - matched_customer_groups: ["C4积极型+港股偏好", ...]
    - marketing_plan_outline: "销售方案摘要..."
    """
    task_id: str
    turn_id: str                            # 对应的对话轮次
    entities: dict[str, Any]               # 从本次任务中提取的关键实体
    step_outputs: dict[str, str]           # step_id -> 压缩后的输出摘要
    final_output_summary: str              # 最终输出的压缩摘要（≤500 字）
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionContext:
    """
    会话级上下文容器。
    跨轮次持久化，整个会话生命周期内有效。
    """
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # 对话历史（滑动窗口，保留最近 N 轮）
    turns: list[ConversationTurn] = field(default_factory=list)

    # 任务记忆（保留最近 M 次任务的关键输出）
    task_memories: list[TaskMemory] = field(default_factory=list)

    # 跨轮次实体追踪（最近轮次提到的关键实体）
    # key: 实体类型（如 "fund_code"）, value: 实体值
    tracked_entities: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextWindow:
    """
    注入节点 Prompt 的上下文窗口（压缩后的摘要）。
    由 ContextManager.build_context_window() 生成，
    各节点直接使用其中的字符串字段拼接 Prompt。
    """
    # 近期对话摘要（供意图识别使用）
    recent_turns_summary: str = ""

    # 当前会话内追踪到的关键实体（供 Planner/Executor 使用）
    tracked_entities_summary: str = ""

    # 最近相关任务的执行结果摘要（供 Executor 使用，避免重复调用相同工具）
    relevant_task_memory_summary: str = ""

    # 当前任务的步骤间共享数据（当前请求内的黑板）
    current_task_step_context: str = ""

    def is_empty(self) -> bool:
        return not any([
            self.recent_turns_summary,
            self.tracked_entities_summary,
            self.relevant_task_memory_summary,
            self.current_task_step_context,
        ])

    def to_prompt_block(self, sections: list[str] = None) -> str:  # noqa: B006
        """
        将上下文窗口序列化为可注入 Prompt 的文本块。
        sections 指定要包含哪些部分，None 表示全部。
        """
        available = {
            "turns": ("## 近期对话记录", self.recent_turns_summary),
            "entities": ("## 当前会话关键实体", self.tracked_entities_summary),
            "task_memory": ("## 历史任务结果参考", self.relevant_task_memory_summary),
            "step_context": ("## 当前任务已完成步骤", self.current_task_step_context),
        }
        if sections is None:
            sections = list(available.keys())

        parts = []
        for key in sections:
            title, content = available.get(key, ("", ""))
            if content:
                parts.append(f"{title}\n{content}")

        if not parts:
            return ""
        return "\n\n".join(parts)


# ── 长期记忆数据模型 ──────────────────────────────────────────────

@dataclass
class SemanticProfile:
    """
    语义记忆 - 用户事实快照（Profile 模式）。
    拆分为多个领域子文档，防止单文档过大导致 LLM 生成出错。
    每个 user_id 只有一份，通过 JSON Patch 方式增量更新。
    """
    user_id: str
    basic_info: dict[str, Any] = field(default_factory=dict)   # 基本信息（角色、偏好等）
    work_prefs: dict[str, Any] = field(default_factory=dict)   # 工作偏好
    domain_facts: dict[str, Any] = field(default_factory=dict) # 领域事实（基金偏好、客群等）
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prompt_text(self) -> str:
        """序列化为可注入 Prompt 的文本"""
        parts = []
        if self.basic_info:
            parts.append(f"基本信息: {self.basic_info}")
        if self.work_prefs:
            parts.append(f"工作偏好: {self.work_prefs}")
        if self.domain_facts:
            parts.append(f"领域事实: {self.domain_facts}")
        return "\n".join(parts) if parts else ""


@dataclass
class EpisodicExperience:
    """
    情景记忆 - 成功任务经验（Collection 模式）。
    每次成功的复杂任务完成后追加一条，供后续作为 few-shot 样例语义检索。
    """
    experience_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    user_id: str = ""
    task_summary: str = ""            # 任务简要描述
    intent_type: str = ""             # 意图类型
    key_entities: dict[str, Any] = field(default_factory=dict)  # 涉及的关键实体
    execution_trace: str = ""         # 压缩的执行轨迹（步骤 + 工具调用）
    outcome: str = ""                 # 最终结论摘要
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prompt_text(self) -> str:
        """序列化为可注入 Prompt 的 few-shot 样例文本"""
        lines = [f"[经验 {self.experience_id[:8]}] {self.task_summary}"]
        if self.key_entities:
            lines.append(f"  涉及实体: {self.key_entities}")
        if self.execution_trace:
            lines.append(f"  执行路径: {self.execution_trace}")
        if self.outcome:
            lines.append(f"  执行结论: {self.outcome}")
        return "\n".join(lines)
