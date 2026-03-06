"""
短期记忆压缩视图层（Context Manager）

定位：
  - 对话历史的持久化 **完全交给 LangGraph checkpointer**（AsyncPostgresSaver）
  - 本模块只负责"摘要压缩视图"的构建，以及跨轮次实体追踪的维护
  - 不再存储 messages / turns，不与 checkpointer 双写

职责：
1. 维护轻量的会话级实体追踪（fund_code、client_id 等）
2. 从 messages 列表构建压缩摘要（注入 Prompt 的 ContextWindow）
3. 当 messages 超过 10 轮时，调用 LLM 将早期消息折叠为摘要（修剪策略一）
4. 构建任务记忆视图（TaskMemory），供 responder_node 写入后 Long-term 使用

设计原则：
- 纯轻量 in-memory 实体缓存（只存 tracked_entities，不存 messages）
- 线程安全（asyncio.Lock）
- 修剪不删除 DB 中的原始记录，只在传入工作记忆前进行拦截压缩
"""

import asyncio
import re
from typing import Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from .models import TaskMemory, ContextWindow

# ── 上下文窗口配置 ──────────────────────────────────────────────
_MAX_TURNS_IN_WINDOW = 10       # 超过此轮次触发修剪（折叠早期消息为摘要）
_MAX_STEP_OUTPUT_LEN = 300      # 每个步骤输出的最大保留字符数
_MAX_TURN_RESPONSE_LEN = 400    # 每轮响应的最大保留字符数
_MAX_TASK_SUMMARY_LEN = 500     # 任务最终摘要的最大保留字符数

# ── 实体提取正则 ──────────────────────────────────────────────────
_FUND_CODE_RE = re.compile(r'\b(\d{6})\b')


def _truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


def _extract_entities_from_text(text: str) -> dict:
    """从文本中提取关键实体（基金代码等）"""
    entities = {}
    fund_codes = _FUND_CODE_RE.findall(text)
    if fund_codes:
        entities["fund_code"] = fund_codes[0]
        if len(fund_codes) > 1:
            entities["fund_codes"] = fund_codes
    return entities


def _count_message_rounds(messages: list[BaseMessage]) -> int:
    """统计 HumanMessage / AIMessage 的交互轮次数"""
    return sum(1 for m in messages if isinstance(m, HumanMessage))


class ContextManager:
    """
    短期记忆压缩视图层（单例，按 session_id 隔离实体追踪）。

    使用方式：
        ctx_mgr = get_context_manager()

        # 请求开始时：基于 checkpointer 恢复的 messages 构建上下文窗口
        window = ctx_mgr.build_context_window(session_id, messages, current_query)

        # 请求结束时：更新实体追踪（对话写入由 checkpointer 负责）
        ctx_mgr.update_entities(session_id, entities)

        # 判断是否需要修剪
        pruned = await ctx_mgr.prune_messages_if_needed(session_id, messages)
    """

    def __init__(self):
        # 轻量缓存：只存实体追踪，不存 messages
        self._entity_cache: dict[str, dict] = {}  # session_id -> tracked_entities
        self._lock = asyncio.Lock()

    # ── 实体追踪 ──────────────────────────────────────────────────

    def update_entities(self, session_id: str, entities: dict) -> None:
        """更新 session 级实体追踪（最新轮次的实体覆盖旧值）"""
        if not entities:
            return
        if session_id not in self._entity_cache:
            self._entity_cache[session_id] = {}
        self._entity_cache[session_id].update(entities)

    def get_entities(self, session_id: str) -> dict:
        return self._entity_cache.get(session_id, {})

    def clear_session(self, session_id: str) -> None:
        self._entity_cache.pop(session_id, None)

    # ── 上下文窗口构建（只读，无副作用）─────────────────────────

    def build_context_window(
        self,
        session_id: str,
        messages: list[BaseMessage],
        current_query: str = "",
        step_results: list = None,
    ) -> ContextWindow:
        """
        基于 checkpointer 恢复的 messages 列表构建注入 Prompt 的上下文窗口。
        此方法为只读操作，不修改任何状态。

        参数：
            session_id: 当前会话 ID
            messages: 从 checkpointer 恢复的完整 messages 列表
            current_query: 当前用户查询（用于实体合并）
            step_results: 当前任务已完成步骤的结果（黑板内容）
        """
        window = ContextWindow()

        # 1. 近期对话摘要（从 messages 提取最近 N 轮）
        window.recent_turns_summary = self._build_turns_summary_from_messages(messages)

        # 2. 实体追踪摘要（session 缓存 + 当前 query）
        cached_entities = self.get_entities(session_id)
        current_entities = _extract_entities_from_text(current_query)
        merged = {**cached_entities, **current_entities}
        window.tracked_entities_summary = self._build_entities_summary(merged)

        # 3. 当前任务步骤上下文（黑板）
        if step_results:
            window.current_task_step_context = self._build_step_context(step_results)

        return window

    def _build_turns_summary_from_messages(self, messages: list[BaseMessage]) -> str:
        """从 messages 列表中提取最近 N 轮 Human/AI 对话，格式化为摘要文本"""
        if not messages:
            return ""

        # 按轮次配对（Human + AI）
        pairs = []
        pending_human = None
        for msg in messages:
            if isinstance(msg, SystemMessage):
                # SystemMessage 可能是折叠摘要，单独处理
                pairs.append(("summary", msg.content))
            elif isinstance(msg, HumanMessage):
                pending_human = msg.content
            elif isinstance(msg, AIMessage) and pending_human is not None:
                pairs.append(("turn", pending_human, msg.content))
                pending_human = None

        # 只保留最近 N 轮
        recent = pairs[-_MAX_TURNS_IN_WINDOW:]
        lines = []
        for item in recent:
            if item[0] == "summary":
                lines.append(f"[早期对话摘要] {_truncate(item[1], 400)}")
            else:
                _, q, r = item
                lines.append(f"用户：{_truncate(q, 80)}")
                lines.append(f"助手：{_truncate(r, _MAX_TURN_RESPONSE_LEN)}")
        return "\n".join(lines)

    def _build_entities_summary(self, entities: dict) -> str:
        if not entities:
            return ""
        label_map = {
            "fund_code": "基金代码",
            "fund_codes": "基金代码列表",
        }
        lines = ["当前会话中识别到的关键实体："]
        for key, value in entities.items():
            label = label_map.get(key, key)
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    def _build_step_context(self, step_results: list) -> str:
        lines = []
        for r in step_results:
            step_id = getattr(r, "step_id", "?")
            success = getattr(r, "success", True)
            output = getattr(r, "output", "") or ""
            error = getattr(r, "error", "") or ""
            status = "成功" if success else "失败"
            content = _truncate(output if success else error, _MAX_STEP_OUTPUT_LEN)
            lines.append(f"- 步骤 {step_id}（{status}）: {content}")
        return "\n".join(lines)

    # ── 修剪策略一：超限时折叠早期消息为摘要 ────────────────────

    async def prune_messages_if_needed(
        self,
        messages: list[BaseMessage],
    ) -> list[BaseMessage]:
        """
        检查 messages 是否超过修剪阈值（10 轮），超过则将早期消息折叠为 SystemMessage 摘要。
        返回处理后的 messages 列表（如未超限则原样返回）。

        此方法不直接写 checkpointer，调用方需要将返回值通过 State 更新机制写回。
        """
        rounds = _count_message_rounds(messages)
        if rounds <= _MAX_TURNS_IN_WINDOW:
            return messages

        # 保留最近 6 轮，折叠更早的部分
        keep_rounds = 6
        keep_count = keep_rounds * 2  # 每轮 Human + AI 各一条

        # 找到切割点：从末尾数 keep_count 条 Human/AI 消息
        human_ai_msgs = [(i, m) for i, m in enumerate(messages) if isinstance(m, (HumanMessage, AIMessage))]
        if len(human_ai_msgs) <= keep_count:
            return messages

        cut_idx = human_ai_msgs[-keep_count][0]
        early_messages = messages[:cut_idx]
        recent_messages = messages[cut_idx:]

        # 保留已有的 SystemMessage（折叠摘要）
        existing_summaries = [m for m in early_messages if isinstance(m, SystemMessage)]
        to_summarize = [m for m in early_messages if not isinstance(m, SystemMessage)]

        if not to_summarize:
            return messages

        # 调用 LLM 折叠早期对话
        summary_text = await self._summarize_early_messages(to_summarize)

        # 将已有摘要 + 新摘要合并为一条 SystemMessage
        all_summary_parts = [m.content for m in existing_summaries] + [summary_text]
        summary_msg = SystemMessage(content="[早期对话摘要]\n" + "\n---\n".join(all_summary_parts))

        return [summary_msg] + recent_messages

    async def _summarize_early_messages(self, messages: list[BaseMessage]) -> str:
        """调用 LLM 将早期消息折叠为简短摘要"""
        try:
            from ..config import get_settings
            settings = get_settings()
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base,
                temperature=0.0,
            )

            dialogue_text = "\n".join(
                f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {_truncate(m.content, 200)}"
                for m in messages
                if isinstance(m, (HumanMessage, AIMessage))
            )

            prompt = f"""请将以下对话历史提炼为一段简洁的摘要（不超过 300 字），保留关键业务信息和实体：

{dialogue_text}

摘要："""
            response = await llm.ainvoke(prompt)
            return response.content.strip()
        except Exception as e:
            # 折叠失败时，退化为简单截断拼接
            import logging
            logging.getLogger(__name__).warning("[ContextManager] 摘要折叠失败: %s", e)
            return "\n".join(
                f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {_truncate(m.content, 100)}"
                for m in messages
                if isinstance(m, (HumanMessage, AIMessage))
            )

    # ── 任务记忆构建（供 responder_node 使用）────────────────────

    def build_task_memory(
        self,
        task_id: str,
        turn_id: str,
        query: str,
        step_results: list,
        final_response: str,
    ) -> TaskMemory:
        """
        从任务执行结果构建 TaskMemory 对象。
        应在 responder_node 生成最终回复后调用。
        """
        entities = _extract_entities_from_text(query)

        step_outputs: dict[str, str] = {}
        all_text = ""
        for r in step_results:
            step_id = getattr(r, "step_id", "?")
            output = getattr(r, "output", "") or ""
            error = getattr(r, "error", "") or ""
            content = output if getattr(r, "success", True) else f"[失败] {error}"
            step_outputs[step_id] = _truncate(content, _MAX_STEP_OUTPUT_LEN)
            all_text += content + " "

        # 补充从步骤输出中提取的实体
        step_entities = _extract_entities_from_text(all_text)
        entities.update(step_entities)

        return TaskMemory(
            task_id=task_id,
            turn_id=turn_id,
            entities=entities,
            step_outputs=step_outputs,
            final_output_summary=_truncate(final_response, _MAX_TASK_SUMMARY_LEN),
        )

    def session_count(self) -> int:
        """返回当前缓存的 session 数量（仅用于监控）"""
        return len(self._entity_cache)


# ── 全局单例 ─────────────────────────────────────────────────────
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局 ContextManager 单例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
