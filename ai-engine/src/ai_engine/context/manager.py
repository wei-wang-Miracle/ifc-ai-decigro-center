"""
上下文管理器
职责：
1. 维护会话级 SessionContext（跨轮次对话历史 + 任务记忆 + 实体追踪）
2. 在每次请求开始时构建 ContextWindow（压缩后的上下文摘要）
3. 在每次请求结束时更新 SessionContext（记录本轮对话和任务结果）
4. 提取和追踪关键实体（基金代码、客户群体等）

设计原则：
- 纯内存实现（InMemory），按 session_id 隔离
- 无外部依赖（不依赖数据库、Redis）
- 线程安全（asyncio.Lock）
- 上下文压缩：防止 Token 膨胀，历史轮次摘要化
"""

import asyncio
import re
import uuid
from datetime import datetime
from typing import Optional

from .models import ConversationTurn, TaskMemory, SessionContext, ContextWindow

# ── 上下文窗口配置 ──────────────────────────────────────────────
_MAX_TURNS = 10              # 最多保留最近 N 轮对话
_MAX_TASK_MEMORIES = 5       # 最多保留最近 M 次任务记忆
_MAX_STEP_OUTPUT_LEN = 300   # 每个步骤输出的最大保留字符数
_MAX_TURN_RESPONSE_LEN = 400 # 每轮响应的最大保留字符数
_MAX_TASK_SUMMARY_LEN = 500  # 任务最终摘要的最大保留字符数

# ── 实体提取正则 ──────────────────────────────────────────────────
# 基金代码：6 位数字
_FUND_CODE_RE = re.compile(r'\b(\d{6})\b')
# 客户 ID（纯数字，通常 8-12 位）
_CLIENT_ID_RE = re.compile(r'\b(client_id[:=\s]*(\w+))\b', re.IGNORECASE)


def _truncate(text: str, max_len: int) -> str:
    """截断文本，保留前 max_len 个字符"""
    if not text:
        return ""
    return text[:max_len] + "..." if len(text) > max_len else text


def _extract_entities_from_query(query: str) -> dict:
    """
    从用户查询中提取关键实体。
    当前支持：基金代码（6 位数字）。
    """
    entities = {}
    fund_codes = _FUND_CODE_RE.findall(query)
    if fund_codes:
        # 保留第一个匹配（最常见场景只有一个基金代码）
        entities["fund_code"] = fund_codes[0]
        if len(fund_codes) > 1:
            entities["fund_codes"] = fund_codes
    return entities


def _extract_entities_from_step_outputs(step_outputs: dict[str, str]) -> dict:
    """从步骤输出中提取关键实体（补充 query 提取的结果）"""
    entities = {}
    all_text = " ".join(step_outputs.values())

    fund_codes = _FUND_CODE_RE.findall(all_text)
    if fund_codes:
        entities["fund_codes_mentioned"] = list(set(fund_codes))

    return entities


class ContextManager:
    """
    会话上下文管理器（单例，按 session_id 隔离）。

    使用方式：
        ctx_mgr = get_context_manager()

        # 请求开始时构建上下文窗口
        window = ctx_mgr.build_context_window(session_id, task_id, step_results)

        # 请求结束时记录本轮结果
        await ctx_mgr.record_turn(session_id, turn, task_memory)
    """

    def __init__(self):
        self._sessions: dict[str, SessionContext] = {}
        self._lock = asyncio.Lock()

    # ── 会话管理 ──────────────────────────────────────────────────

    def _get_or_create_session(self, session_id: str, user_id: str = "") -> SessionContext:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionContext(
                session_id=session_id,
                user_id=user_id,
            )
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> Optional[SessionContext]:
        return self._sessions.get(session_id)

    # ── 上下文窗口构建（只读，无副作用）─────────────────────────

    def build_context_window(
        self,
        session_id: str,
        current_query: str = "",
        step_results: list = None,      # list[StepResult]，当前任务已完成的步骤
        relevant_task_ids: list[str] = None,  # 指定要引用的历史任务 ID
    ) -> ContextWindow:
        """
        构建注入 Prompt 的上下文窗口。
        此方法为只读操作，不修改任何状态。

        参数：
            session_id: 当前会话 ID
            current_query: 当前用户查询（用于筛选相关历史）
            step_results: 当前任务已完成步骤的结果（黑板内容）
            relevant_task_ids: 指定参考的历史任务（None 表示自动筛选）
        """
        session = self._sessions.get(session_id)
        window = ContextWindow()

        if session is None:
            return window

        # 1. 近期对话摘要
        window.recent_turns_summary = self._build_turns_summary(session)

        # 2. 实体追踪摘要
        window.tracked_entities_summary = self._build_entities_summary(
            session, current_query
        )

        # 3. 历史任务记忆摘要
        window.relevant_task_memory_summary = self._build_task_memory_summary(
            session, current_query, relevant_task_ids
        )

        # 4. 当前任务步骤上下文（黑板）
        if step_results:
            window.current_task_step_context = self._build_step_context(step_results)

        return window

    def _build_turns_summary(self, session: SessionContext) -> str:
        """将最近几轮对话压缩为可读摘要"""
        if not session.turns:
            return ""
        recent = session.turns[-_MAX_TURNS:]
        lines = []
        for turn in recent:
            ts = turn.timestamp.strftime("%H:%M")
            q = _truncate(turn.query, 80)
            r = _truncate(turn.response, _MAX_TURN_RESPONSE_LEN)
            intent_tag = f"[{turn.intent_type}]" if turn.intent_type != "chat" else ""
            lines.append(f"[{ts}]{intent_tag} 用户：{q}")
            lines.append(f"         助手：{r}")
            if turn.entities:
                entity_str = ", ".join(f"{k}={v}" for k, v in turn.entities.items())
                lines.append(f"         实体：{entity_str}")
        return "\n".join(lines)

    def _build_entities_summary(
        self, session: SessionContext, current_query: str
    ) -> str:
        """将追踪到的关键实体序列化为摘要文本"""
        # 合并 session 级实体 + 当前 query 中的实体（current_query 优先级更高）
        entities = dict(session.tracked_entities)
        current_entities = _extract_entities_from_query(current_query)
        entities.update(current_entities)

        if not entities:
            return ""

        lines = ["当前会话中识别到的关键实体："]
        label_map = {
            "fund_code": "基金代码",
            "fund_codes": "基金代码列表",
            "fund_codes_mentioned": "提及的基金代码",
        }
        for key, value in entities.items():
            label = label_map.get(key, key)
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    def _build_task_memory_summary(
        self,
        session: SessionContext,
        current_query: str,
        relevant_task_ids: list[str] = None,
    ) -> str:
        """
        构建历史任务记忆摘要。
        优先返回与当前 query 最相关的历史任务结果。
        """
        if not session.task_memories:
            return ""

        memories = session.task_memories[-_MAX_TASK_MEMORIES:]

        # 如果指定了 task_ids，按指定过滤
        if relevant_task_ids:
            memories = [m for m in memories if m.task_id in relevant_task_ids]
            if not memories:
                return ""

        # 否则按实体相关性过滤：当前 query 提到的基金代码
        else:
            current_entities = _extract_entities_from_query(current_query)
            if current_entities:
                current_fund = current_entities.get("fund_code", "")
                if current_fund:
                    relevant = [
                        m for m in memories
                        if m.entities.get("fund_code") == current_fund
                        or current_fund in str(m.entities.get("fund_codes_mentioned", []))
                    ]
                    if relevant:
                        memories = relevant

        lines = []
        for mem in memories[-3:]:  # 最多引用 3 条
            ts = mem.timestamp.strftime("%m/%d %H:%M")
            lines.append(f"[任务 {mem.task_id[:8]}... @ {ts}]")
            if mem.entities:
                entity_str = ", ".join(f"{k}={v}" for k, v in mem.entities.items() if k != "fund_codes_mentioned")
                lines.append(f"  涉及实体: {entity_str}")
            # 关键步骤输出（只保留有内容的）
            for step_id, output in mem.step_outputs.items():
                if output:
                    lines.append(f"  步骤{step_id}结果: {_truncate(output, _MAX_STEP_OUTPUT_LEN)}")
            if mem.final_output_summary:
                lines.append(f"  最终结论: {_truncate(mem.final_output_summary, 200)}")

        return "\n".join(lines) if lines else ""

    def _build_step_context(self, step_results: list) -> str:
        """将当前任务已完成的步骤结果格式化为上下文文本"""
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

    # ── 状态更新（写操作，加锁）─────────────────────────────────

    async def record_turn(
        self,
        session_id: str,
        user_id: str,
        turn_id: str,
        query: str,
        rewritten_query: str,
        response: str,
        intent_type: str,
        entities: dict = None,
        task_memory: Optional[TaskMemory] = None,
    ) -> None:
        """
        记录一轮对话结果，并更新会话级状态。
        应在 responder_node 生成最终回复后调用。
        """
        async with self._lock:
            session = self._get_or_create_session(session_id, user_id)

            turn = ConversationTurn(
                turn_id=turn_id,
                query=query,
                rewritten_query=rewritten_query,
                response=_truncate(response, _MAX_TURN_RESPONSE_LEN),
                intent_type=intent_type,
                entities=entities or {},
            )

            # 滑动窗口：超出限制时移除最早的记录
            session.turns.append(turn)
            if len(session.turns) > _MAX_TURNS:
                session.turns = session.turns[-_MAX_TURNS:]

            # 更新实体追踪（当前轮次的实体会覆盖旧值）
            if entities:
                session.tracked_entities.update(entities)

            # 记录任务记忆
            if task_memory is not None:
                session.task_memories.append(task_memory)
                if len(session.task_memories) > _MAX_TASK_MEMORIES:
                    session.task_memories = session.task_memories[-_MAX_TASK_MEMORIES:]

            session.updated_at = datetime.utcnow()

    def build_task_memory(
        self,
        task_id: str,
        turn_id: str,
        query: str,
        step_results: list,       # list[StepResult]
        final_response: str,
    ) -> TaskMemory:
        """
        从任务执行结果构建 TaskMemory 对象，供 record_turn 写入会话记忆。
        应在 responder_node 生成最终回复后调用（在 record_turn 之前）。
        """
        # 提取实体
        entities = _extract_entities_from_query(query)

        # 压缩步骤输出
        step_outputs: dict[str, str] = {}
        all_outputs = {}
        for r in step_results:
            step_id = getattr(r, "step_id", "?")
            output = getattr(r, "output", "") or ""
            error = getattr(r, "error", "") or ""
            content = output if getattr(r, "success", True) else f"[失败] {error}"
            step_outputs[step_id] = _truncate(content, _MAX_STEP_OUTPUT_LEN)
            all_outputs[step_id] = content

        # 补充从步骤输出提取的实体
        entities.update(_extract_entities_from_step_outputs(all_outputs))

        return TaskMemory(
            task_id=task_id,
            turn_id=turn_id,
            entities=entities,
            step_outputs=step_outputs,
            final_output_summary=_truncate(final_response, _MAX_TASK_SUMMARY_LEN),
        )

    # ── 会话清理 ──────────────────────────────────────────────────

    def clear_session(self, session_id: str) -> None:
        """清除指定会话的所有上下文（用于重置或测试）"""
        self._sessions.pop(session_id, None)

    def session_count(self) -> int:
        return len(self._sessions)


# ── 全局单例 ─────────────────────────────────────────────────────
_context_manager: Optional[ContextManager] = None


def get_context_manager() -> ContextManager:
    """获取全局 ContextManager 单例"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
