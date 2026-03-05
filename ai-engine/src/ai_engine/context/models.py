"""
上下文管理模块 - 数据模型
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


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
    timestamp: datetime = field(default_factory=datetime.utcnow)

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
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SessionContext:
    """
    会话级上下文容器。
    跨轮次持久化，整个会话生命周期内有效。
    """
    session_id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

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

    def to_prompt_block(self, sections: list[str] = None) -> str:
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
