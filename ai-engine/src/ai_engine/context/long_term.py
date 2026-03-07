"""
长期记忆管理器
职责：
1. 基于 LangGraph AsyncPostgresStore，按 user_id Namespace 隔离存储
2. 语义记忆（SemanticProfile）：Profile 模式，按领域子文档拆分，严格 JSON 更新
3. 情景记忆（EpisodicExperience）：Collection 模式，成功任务轨迹追加写入
4. 热路径只读（retrieve_long_term_context），写入全部走后台异步 Reflection

设计原则（对应 PRD 策略）：
- 策略二：Collection 用于经验，避免大 Profile 覆写时数据丢失
- 策略三：Profile 按领域拆分 + 严格 JSON 解码，防止格式崩溃
- 策略四：检索代替加载，仅 Top-K 条写入工作记忆，Store 数据量无限增长不影响上下文
- 双轨更新：短期记忆由 checkpointer 热路径处理，长期记忆后台异步 Reflection
"""

import asyncio
import json
import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .models import EpisodicExperience, SemanticProfile

logger = logging.getLogger(__name__)

# Namespace 常量
_NS_SEMANTIC = "semantic"   # SemanticProfile 的 Store key
_NS_EPISODIC = "episodic"   # EpisodicExperience Collection 的 namespace

# 检索配置
_TOP_K_EPISODIC = 3         # 每次最多注入 3 条经验

# Reflection 提示词
_REFLECTION_SYSTEM = """你是一个智能记忆提炼专家。请分析刚刚完成的任务轨迹，判断是否产生了值得长期记忆的内容。

你需要分析两类信息：
1. **新事实（Facts）**：用户在本次任务中透露的客观信息（角色、偏好、业务背景等），用于更新 SemanticProfile
2. **优质经验（Experience）**：本次任务是否是一次成功的复杂业务执行，可以作为未来类似任务的参考样例

输出严格的 JSON 格式（不包含任何 Markdown 代码块）：
{
  "has_new_facts": true/false,
  "semantic_patch": {
    "basic_info": {},
    "work_prefs": {},
    "domain_facts": {}
  },
  "has_valuable_experience": true/false,
  "experience": {
    "task_summary": "...",
    "intent_type": "task",
    "key_entities": {},
    "execution_trace": "...",
    "outcome": "..."
  }
}

规则：
- semantic_patch 中只填写有新增/变更的字段，没有变化的领域留空 {}
- experience.execution_trace 请压缩为不超过 300 字的关键步骤描述
- experience.outcome 请压缩为不超过 200 字
- 如果任务失败或是普通闲聊，has_valuable_experience 设为 false"""

_REFLECTION_HUMAN = """任务信息：
- 用户查询：{query}
- 意图类型：{intent_type}
- 步骤执行结果：
{step_results_text}
- 最终响应摘要：{final_response}

当前用户 SemanticProfile（仅供参考，只更新有变化的字段）：
{current_profile}

请分析并输出 JSON。"""


class LongTermMemoryManager:
    """
    长期记忆管理器（单例，按 user_id Namespace 隔离）。

    存储层使用 LangGraph Store，当前后端为 AsyncPostgresStore（持久化）。
    Store 在 main.py lifespan 中初始化后通过 set_store() 注入。

    Namespace 设计：
        语义记忆：("users", user_id, "semantic") -> key="_profile"
        情景记忆：("users", user_id, "episodic") -> key=experience_id
    """

    def __init__(self):
        self._store = None   # 由外部 set_store() 注入

    def set_store(self, store) -> None:
        """注入 LangGraph Store 实例（在 lifespan 初始化后调用）"""
        self._store = store
        logger.info("[LongTermMemory] Store 已注入: %s", type(store).__name__)

    # ── 读取（热路径，同步感知）────────────────────────────────────

    async def retrieve_long_term_context(self, user_id: str, query: str) -> str:
        """
        检索与当前 query 相关的长期记忆，格式化为可注入 Prompt 的文本块。
        热路径调用，应尽量快（无 LLM 调用，只做 Store 检索）。
        """
        if not self._store or not user_id:
            return ""

        parts = []

        # 1. 语义记忆（Profile）：直接加载，通常体积小
        profile_text = await self._load_semantic_profile_text(user_id)
        if profile_text:
            parts.append(f"### 用户事实（语义记忆）\n{profile_text}")

        # 2. 情景记忆（Collection）：语义检索 Top-K
        episodic_text = await self._search_episodic_experiences(user_id, query)
        if episodic_text:
            parts.append(f"### 历史成功经验（情景记忆，可作为参考样例）\n{episodic_text}")

        return "\n\n".join(parts) if parts else ""

    async def _load_semantic_profile_text(self, user_id: str) -> str:
        """加载用户的语义记忆 Profile，转为可读文本"""
        try:
            namespace = ("users", user_id, _NS_SEMANTIC)
            item = await self._store.aget(namespace, "_profile")
            if item is None:
                return ""
            profile_data = item.value
            profile = SemanticProfile(
                user_id=user_id,
                basic_info=profile_data.get("basic_info", {}),
                work_prefs=profile_data.get("work_prefs", {}),
                domain_facts=profile_data.get("domain_facts", {}),
            )
            return profile.to_prompt_text()
        except Exception as e:
            logger.warning("[LongTermMemory] 加载 SemanticProfile 失败: %s", e)
            return ""

    async def _search_episodic_experiences(self, user_id: str, query: str) -> str:
        """在情景记忆 Collection 中检索与 query 相关的经验"""
        try:
            namespace = ("users", user_id, _NS_EPISODIC)
            # 优先尝试语义检索（需要 pgvector）；无向量时降级为全量加载取最近 Top-K
            try:
                items = await self._store.asearch(namespace, query=query, limit=_TOP_K_EPISODIC)
            except Exception:
                items = await self._store.alist(namespace, limit=_TOP_K_EPISODIC)
            if not items:
                return ""
            lines = []
            for item in items:
                exp_data = item.value
                exp = EpisodicExperience(
                    experience_id=exp_data.get("experience_id", ""),
                    user_id=user_id,
                    task_summary=exp_data.get("task_summary", ""),
                    intent_type=exp_data.get("intent_type", ""),
                    key_entities=exp_data.get("key_entities", {}),
                    execution_trace=exp_data.get("execution_trace", ""),
                    outcome=exp_data.get("outcome", ""),
                )
                lines.append(exp.to_prompt_text())
            logger.info("[LongTermMemory] 检索到情景记忆 %d 条: user=%s", len(lines), user_id)
            return "\n\n".join(lines)
        except Exception as e:
            logger.warning("[LongTermMemory] 检索情景记忆失败: %s", e)
            return ""

    # ── 写入（后台异步，不阻塞热路径）────────────────────────────

    def trigger_reflection_async(
        self,
        user_id: str,
        task_id: str,
        query: str,
        step_results: list,
        final_response: str,
        intent_type: str = "task",
    ) -> None:
        """
        触发后台异步 Reflection。非阻塞，在当前事件循环中 create_task。
        任何失败静默记录日志，不向上层抛出。
        """
        if not self._store or not user_id:
            return
        asyncio.create_task(
            self._run_reflection(user_id, task_id, query, step_results, final_response, intent_type),
            name=f"reflection_{task_id}",
        )
        logger.info("[LongTermMemory] 已触发后台 Reflection: task=%s user=%s", task_id, user_id)

    async def _run_reflection(
        self,
        user_id: str,
        task_id: str,
        query: str,
        step_results: list,
        final_response: str,
        intent_type: str = "task",
    ) -> None:
        """
        后台 Reflection 主逻辑：
        1. 调用 LLM 分析任务轨迹，输出严格 JSON
        2. 有新事实 -> JSON Patch 更新 SemanticProfile 对应子文档
        3. 有优质经验 -> 生成 EpisodicExperience 追加到 Collection
        """
        try:
            from ..config import get_settings
            settings = get_settings()

            # 构建步骤摘要文本
            step_results_text = "\n".join(
                f"  - 步骤 {getattr(r, 'step_id', '?')}（{'成功' if getattr(r, 'success', True) else '失败'}）: "
                f"{(getattr(r, 'output', '') or getattr(r, 'error', ''))[:200]}"
                for r in step_results
            )

            # 加载当前 Profile（用于传给 LLM 做参考，防止覆写已有信息）
            current_profile = await self._load_current_profile_dict(user_id)
            current_profile_text = json.dumps(current_profile, ensure_ascii=False, indent=2)

            # 调用 LLM（温度 0，严格解码）
            llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base,
                temperature=0.0,
            )

            human_content = _REFLECTION_HUMAN.format(
                query=query,
                intent_type=intent_type,
                step_results_text=step_results_text,
                final_response=final_response[:300],
                current_profile=current_profile_text,
            )

            messages = [
                SystemMessage(content=_REFLECTION_SYSTEM),
                HumanMessage(content=human_content),
            ]

            response = await llm.ainvoke(messages)
            raw = response.content.strip()

            # 解析严格 JSON（剥离可能的代码块标记）
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            result = json.loads(raw)

            # 更新语义记忆
            if result.get("has_new_facts") and result.get("semantic_patch"):
                await self._apply_semantic_patch(user_id, result["semantic_patch"])

            # 追加情景记忆
            if result.get("has_valuable_experience") and result.get("experience"):
                await self._append_episodic_experience(user_id, result["experience"])

            logger.info("[LongTermMemory] Reflection 完成: task=%s", task_id)

        except json.JSONDecodeError as e:
            logger.warning("[LongTermMemory] Reflection JSON 解析失败: %s", e)
        except Exception as e:
            logger.warning("[LongTermMemory] Reflection 异常: %s", e)

    async def _load_current_profile_dict(self, user_id: str) -> dict:
        """加载当前 SemanticProfile 的原始 dict（供 Reflection LLM 参考）"""
        try:
            namespace = ("users", user_id, _NS_SEMANTIC)
            item = await self._store.aget(namespace, "_profile")
            if item is None:
                return {"basic_info": {}, "work_prefs": {}, "domain_facts": {}}
            return item.value
        except Exception:
            return {"basic_info": {}, "work_prefs": {}, "domain_facts": {}}

    async def _apply_semantic_patch(self, user_id: str, patch: dict) -> None:
        """
        将 Reflection 生成的 JSON Patch 合并到 SemanticProfile。
        按领域子文档合并（dict.update），不覆写整个 Profile。
        """
        try:
            current = await self._load_current_profile_dict(user_id)
            for domain in ("basic_info", "work_prefs", "domain_facts"):
                if patch.get(domain):
                    current.setdefault(domain, {}).update(patch[domain])

            namespace = ("users", user_id, _NS_SEMANTIC)
            await self._store.aput(namespace, "_profile", current)
            logger.info("[LongTermMemory] SemanticProfile 已更新: user=%s", user_id)
        except Exception as e:
            logger.warning("[LongTermMemory] SemanticProfile 更新失败: %s", e)

    async def _append_episodic_experience(self, user_id: str, exp_data: dict) -> None:
        """将一条新经验追加到情景记忆 Collection"""
        try:
            exp = EpisodicExperience(
                user_id=user_id,
                task_summary=exp_data.get("task_summary", ""),
                intent_type=exp_data.get("intent_type", "task"),
                key_entities=exp_data.get("key_entities", {}),
                execution_trace=exp_data.get("execution_trace", ""),
                outcome=exp_data.get("outcome", ""),
            )
            namespace = ("users", user_id, _NS_EPISODIC)
            value = {
                "experience_id": exp.experience_id,
                "user_id": user_id,
                "task_summary": exp.task_summary,
                "intent_type": exp.intent_type,
                "key_entities": exp.key_entities,
                "execution_trace": exp.execution_trace,
                "outcome": exp.outcome,
                "created_at": exp.created_at.isoformat(),
            }
            await self._store.aput(namespace, exp.experience_id, value)
            logger.info(
                "[LongTermMemory] 情景记忆已追加: user=%s exp=%s", user_id, exp.experience_id
            )
        except Exception as e:
            logger.warning("[LongTermMemory] 情景记忆追加失败: %s", e)

    # ── 管理接口 ────────────────────────────────────────────────

    async def delete_episodic_experience(self, user_id: str, experience_id: str) -> None:
        """主动遗忘：删除指定情景记忆条目（Unlearning）"""
        try:
            namespace = ("users", user_id, _NS_EPISODIC)
            await self._store.adelete(namespace, experience_id)
            logger.info(
                "[LongTermMemory] 情景记忆已删除: user=%s exp=%s", user_id, experience_id
            )
        except Exception as e:
            logger.warning("[LongTermMemory] 删除情景记忆失败: %s", e)

    async def clear_semantic_profile(self, user_id: str) -> None:
        """主动遗忘：清空用户语义记忆 Profile"""
        try:
            namespace = ("users", user_id, _NS_SEMANTIC)
            await self._store.adelete(namespace, "_profile")
            logger.info("[LongTermMemory] SemanticProfile 已清空: user=%s", user_id)
        except Exception as e:
            logger.warning("[LongTermMemory] 清空 SemanticProfile 失败: %s", e)


# ── 全局单例 ─────────────────────────────────────────────────────
_long_term_memory_manager: Optional[LongTermMemoryManager] = None


def get_long_term_memory_manager() -> LongTermMemoryManager:
    """获取全局 LongTermMemoryManager 单例"""
    global _long_term_memory_manager
    if _long_term_memory_manager is None:
        _long_term_memory_manager = LongTermMemoryManager()
    return _long_term_memory_manager
