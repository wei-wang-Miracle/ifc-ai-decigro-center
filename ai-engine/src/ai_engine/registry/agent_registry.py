"""Agent 注册中心。

职责：
    1. 从数据库加载 agent_cards 并管理 Agent 配置
    2. 提供按类型过滤、格式化描述等元数据查询能力
    3. 封装 Planner/Executor 场景下的 Prompt 构建方法，确保职责内聚

设计决策：
    - AgentConfig 属性分为「元数据」和「详情」两层，分别在 load 和 get_agent 阶段加载
    - AgentType 枚举统一管理角色类型，杜绝魔法字符串
    - 构建 Prompt、系统消息等逻辑内聚在 AgentConfig/AgentRegistry 中，
      各 graph node 仅做编排调用，不自行拼接
"""

import json
from enum import Enum
from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool

from ..api.bus_kernel_client import get_bus_kernel_client
from .tool_registry import get_tool_registry

# ═══════════════════════════════════════════════════════════
#  AgentType 枚举
# ═══════════════════════════════════════════════════════════


class AgentType(str, Enum):
    """Agent 角色类型枚举。

    继承 str 以支持与外部 API 返回的字符串直接比较和 JSON 序列化。

    Attributes:
        PLANNER: 规划型 Agent，负责任务拆解与编排，拥有 bound_agents
        EXECUTOR: 执行型 Agent，负责具体任务执行，拥有 bound_tools
    """

    PLANNER = "PLANNER"
    EXECUTOR = "EXECUTOR"


# ═══════════════════════════════════════════════════════════
#  AgentConfig — 单个 Agent 的配置封装
# ═══════════════════════════════════════════════════════════


class AgentConfig:
    """单个 Agent 的配置封装，支持按需懒加载详情。

    属性分层设计：
        - 元数据（summary 阶段加载）：name / description / tags / alias / agent_type
          用于 Agent 决策与选择阶段（意图识别、Dispatcher 路由）。
        - 关系属性（summary 阶段加载）：bound_agents
          仅 PLANNER 有意义，表示可调度的 Executor 列表。
        - 详情（detail 阶段懒加载）：system_prompt / negative_prompt / reasoning_framework
          / require_review / raw_bound_tools
          仅在执行阶段使用，通过 get_agent() 触发加载。
    """

    def __init__(self, summary: dict[str, Any], detail: dict[str, Any] | None = None):
        """初始化 Agent 配置。

        Args:
            summary: 摘要信息，包含元数据和关系属性。
            detail: 完整详情，可选，支持懒加载。
        """
        self._summary = summary
        self._detail = detail
        self._tools: list[StructuredTool] = []
        self._bound_tools_loaded = False

    # ── 元数据属性（summary 阶段，用于 Agent 决策/选择）──────

    @property
    def name(self) -> str:
        """Agent 唯一标识名称。"""
        return self._summary["agent_name"]

    @property
    def description(self) -> str:
        """Agent 功能描述，用于 LLM 选择匹配。"""
        return self._summary.get("agent_description", "")

    @property
    def tags(self) -> list[str]:
        """Agent 标签列表，用于按业务域分类检索。"""
        tags = self._summary.get("agent_tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags) if tags else []
        return tags

    @property
    def alias(self) -> str:
        """Agent 别名，用于前端展示。detail 优先于 summary。"""
        if self._detail:
            return self._detail.get("agent_alias", self._summary.get("agent_alias", self.name))
        return self._summary.get("agent_alias", self.name)

    @property
    def agent_type(self) -> AgentType:
        """Agent 角色类型（PLANNER / EXECUTOR）。"""
        raw = self._summary.get("agent_type", "EXECUTOR")
        try:
            return AgentType(raw)
        except ValueError:
            return AgentType.EXECUTOR

    # ── 关系属性（summary 阶段，仅 PLANNER 有意义）─────────

    @property
    def bound_agents(self) -> list[str]:
        """Planner 绑定的 Executor 名称列表。

        仅 PLANNER 类型有意义，用于限定可调度的 Executor 范围。
        summary 和 detail 都可能携带此字段，detail 优先。
        """
        if self._detail:
            bound = self._detail.get("bound_agents")
            if bound is None:
                return self._summary.get("bound_agents", [])
            if isinstance(bound, str):
                return json.loads(bound) if bound else []
            return bound
        return self._summary.get("bound_agents", [])

    # ── 详情属性（detail 阶段懒加载，仅执行阶段使用）────────

    @property
    def system_prompt(self) -> str:
        """系统提示词，定义 Agent 的角色和行为规范。"""
        return self._detail.get("system_prompt", "") if self._detail else ""

    @property
    def negative_prompt(self) -> str:
        """禁止事项提示词，定义 Agent 不应执行的行为。"""
        return self._detail.get("negative_prompt", "") if self._detail else ""

    @property
    def reasoning_framework(self) -> str | None:
        """推理框架标识（如 CoT、ReAct），影响 LLM 推理模式。"""
        return self._detail.get("reasoning_framework") if self._detail else None

    @property
    def require_review(self) -> bool:
        """Agent 级别兜底审核开关，由管理员在 AgentCard 中配置。"""
        return self._detail.get("require_review", False) if self._detail else False

    @property
    def raw_bound_tools(self) -> list[str] | None:
        """Agent 绑定的工具名称列表（原始值）。

        返回值语义：
            - None: 未配置工具绑定
            - []: 明确不使用任何工具（纯对话模式）
            - ["tool_a", ...]: 仅使用指定工具
        """
        if not self._detail:
            return None
        bound = self._detail.get("bound_tools")
        if bound is None:
            return None
        if isinstance(bound, str):
            return json.loads(bound) if bound else []
        return bound

    # ── 生命周期方法 ─────────────────────────────────────

    def set_detail(self, detail: dict[str, Any]):
        """填充详情数据，重置工具缓存。

        Args:
            detail: 从 API 获取的 Agent 详情数据。
        """
        self._detail = detail
        self._bound_tools_loaded = False

    # ── 工具相关方法（执行阶段）────────────────────────────

    def get_tools(self, token: str) -> list[StructuredTool]:
        """获取该 Agent 可用的工具列表。

        工具绑定规则：
            - raw_bound_tools = None: 未配置工具绑定，返回空列表
            - raw_bound_tools = []: 不使用任何工具（纯对话模式）
            - raw_bound_tools = ["tool_a", ...]: 仅使用指定工具

        Args:
            token: 用户身份 Token。

        Returns:
            StructuredTool 实例列表。
        """
        if self._bound_tools_loaded:
            return self._tools

        tool_registry = get_tool_registry()
        raw_bound = self.raw_bound_tools

        if raw_bound is None or len(raw_bound) == 0:
            self._tools = []
        else:
            self._tools = tool_registry.get_tools_by_names(raw_bound, token)

        self._bound_tools_loaded = True
        return self._tools

    def get_filtered_tools(
        self, token: str, allowed_tools: list[str] | None = None
    ) -> list[StructuredTool]:
        """获取该 Agent 的可用工具，支持按白名单二次过滤。

        Args:
            token: 用户身份 Token。
            allowed_tools: 工具名称白名单。若提供，仅返回交集。

        Returns:
            过滤后的 StructuredTool 实例列表。
        """
        tools = self.get_tools(token)
        if allowed_tools:
            allowed_set = set(allowed_tools)
            tools = [t for t in tools if t.name in allowed_set]
        return tools

    # ── Prompt / 系统消息构建方法 ────────────────────────

    def build_execution_system_message(
        self, token: str, allowed_tools: list[str] | None = None
    ) -> str:
        """构建 Executor 执行阶段的完整系统消息。

        组合 system_prompt + negative_prompt。
        工具描述由 llm.bind_tools() 在 API 层面提供，此处不再重复注入，
        避免与 bind_tools 的结构化工具定义冗余。

        Args:
            token: 用户身份 Token。
            allowed_tools: 可选的工具白名单，传入时仅展示交集内的工具。

        Returns:
            完整的系统消息文本。若 Agent 无 system_prompt，返回默认提示。
        """
        parts = []
        if self.system_prompt:
            parts.append(self.system_prompt)
        if self.negative_prompt:
            parts.append(f"\n## 禁止事项\n{self.negative_prompt}")

        return "\n\n".join(parts) if parts else "你是一个任务执行助手，请完成分配给你的任务。"

    def build_system_message(self, token: str) -> str:
        """构建通用系统消息（兼容已有调用）。

        Args:
            token: 用户身份 Token。

        Returns:
            系统消息文本。
        """
        return self.build_execution_system_message(token)

    def build_prompt_template(self, token: str) -> ChatPromptTemplate:
        """构建 LangChain ChatPromptTemplate。

        Args:
            token: 用户身份 Token。

        Returns:
            包含 system message 和 messages placeholder 的模板。
        """
        system_message = self.build_system_message(token)
        return ChatPromptTemplate.from_messages(
            [
                ("system", system_message),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

    def get_tool_summaries_text(self, token: str) -> str:
        """生成该 Executor 的结构化能力描述，用于注入 Planner 规划 Prompt。

        输出格式示例::

            ### Executor: etf_fund_profile_expert（别名：基金画像生成专家）
            - 职责: 负责基金画像数据的获取与生成
            - 绑定工具:
              - get_fund_portrait: 获取指定基金的画像数据
              - get_fund_comparison: 多基金对比分析

        注意：assigned_agent 必须使用 Executor 的唯一标识（agent_name），而非别名。

        Args:
            token: 用户身份 Token。
        """
        tool_registry = get_tool_registry()
        all_tool_summaries = {
            s["tool_name"]: s for s in tool_registry.get_all_tool_summaries(token)
        }

        alias_hint = f"（别名：{self.alias}）" if self.alias != self.name else ""
        header = f"\n### Executor: {self.name}{alias_hint}"

        lines = [header]
        lines.append(f"- 职责: {self.description}")

        executor_tools = self.raw_bound_tools or []

        if executor_tools:
            lines.append("- 绑定工具:")
            for tool_name in executor_tools:
                summary = all_tool_summaries.get(tool_name)
                if summary:
                    tool_alias = summary.get("tool_alias", "")
                    tool_desc = summary.get("tool_description", "")
                    if tool_alias and tool_alias != tool_name:
                        lines.append(f"  - {tool_name}（别名：{tool_alias}）: {tool_desc}")
                    else:
                        lines.append(f"  - {tool_name}: {tool_desc}")
        else:
            lines.append("- 绑定工具: 无（该 Executor 仅具备纯对话能力）")

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  AgentRegistry — Agent 注册中心
# ═══════════════════════════════════════════════════════════


class AgentRegistry:
    """Agent 注册中心，统一管理所有 Agent 配置。

    支持两阶段加载：
        1. load()  — 批量加载摘要（元数据 + 关系属性）
        2. get_agent() — 按需加载单个 Agent 的详情

    提供三类方法：
        - 元数据查询：按类型过滤、格式化描述等
        - Planner 场景：获取绑定 Executor 描述、构建工具描述文本
        - Executor 场景：通过 AgentConfig 的内聚方法完成
    """

    def __init__(self):
        self._client = get_bus_kernel_client()
        # {token: {agent_name: AgentConfig}}
        self._user_agents: dict[str, dict[str, AgentConfig]] = {}

    # ── 加载与刷新 ──────────────────────────────────────

    def load(self, token: str, force: bool = False) -> None:
        """批量加载当前用户可用的 Agent 摘要列表。

        通过 API (POST /agent/available) 获取元数据，构建 AgentConfig 缓存。

        Args:
            token: 用户身份 Token。
            force: 是否强制刷新缓存。
        """
        if token in self._user_agents and not force:
            return

        records = self._client.get_available_agents(token)

        user_agents = {}
        for record in records:
            name = record.get("agentName")
            if name:
                summary = {
                    "agent_name": name,
                    "agent_alias": record.get("agentAlias", name),
                    "agent_description": record.get("agentDescription"),
                    "agent_tags": record.get("agentTags"),
                    "agent_type": record.get("agentType", AgentType.EXECUTOR.value),
                    "bound_agents": record.get("boundAgents", []),
                }
                user_agents[name] = AgentConfig(summary)

        self._user_agents[token] = user_agents

        print(
            f"[AgentRegistry] 成功为 Token[{token[:10]}...] 加载 {len(user_agents)} 个 Agent 摘要"
        )

    def reload(self, token: str) -> None:
        """强制刷新指定用户的 Agent 缓存。

        Args:
            token: 用户身份 Token。
        """
        if token in self._user_agents:
            del self._user_agents[token]
        self.load(token, force=True)

    # ── 单个 Agent 查询（触发详情懒加载）────────────────

    def get_agent(self, agent_name: str, token: str) -> AgentConfig | None:
        """获取指定 Agent 的完整配置，自动触发详情懒加载。

        通过 API (POST /agent/detail) 获取详情数据并填充到 AgentConfig。

        Args:
            agent_name: Agent 名称。
            token: 用户身份 Token。

        Returns:
            AgentConfig 实例，若不存在返回 None。
        """
        self.load(token)
        user_agents = self._user_agents.get(token, {})
        agent = user_agents.get(agent_name)

        if agent is None:
            return None

        if not agent._detail:
            print(f"[AgentRegistry] 正在加载 Agent 详情: {agent_name}")
            detail_data = self._client.get_agent_detail(agent_name, token)
            if detail_data:
                detail = {
                    "agent_alias": detail_data.get("agentAlias"),
                    "system_prompt": detail_data.get("systemPrompt"),
                    "negative_prompt": detail_data.get("negativePrompt"),
                    "bound_tools": detail_data.get("boundTools"),
                    "bound_agents": detail_data.get("boundAgents", []),
                    "agent_type": detail_data.get("agentType", AgentType.EXECUTOR.value),
                    "reasoning_framework": detail_data.get("reasoningFramework"),
                    "require_review": detail_data.get("requireReview", False),
                }
                agent.set_detail(detail)
            else:
                print(f"[AgentRegistry] 无法获取 Agent 详情: {agent_name}")

        return agent

    # ── 元数据查询方法 ──────────────────────────────────

    def get_all_agents(self, token: str) -> list[AgentConfig]:
        """获取当前用户所有可用的 Agent 配置列表。

        Args:
            token: 用户身份 Token。
        """
        self.load(token)
        return list(self._user_agents.get(token, {}).values())

    def get_agent_names(self, token: str, agent_type: AgentType = None) -> list[str]:
        """获取 Agent 名称列表，支持按类型过滤。

        Args:
            token: 用户身份 Token。
            agent_type: 按角色类型过滤，None 表示全部。
        """
        self.load(token)
        return [
            name
            for name, config in self._user_agents.get(token, {}).items()
            if not agent_type or config.agent_type == agent_type
        ]

    def get_agent_descriptions(self, token: str, agent_type: AgentType = None) -> dict[str, str]:
        """获取 Agent 名称→描述的映射。

        返回原始 dict，供需要二次处理的场景使用。

        Args:
            token: 用户身份 Token。
            agent_type: 按角色类型过滤，None 表示全部。
        """
        self.load(token)
        user_agents = self._user_agents.get(token, {})
        return {
            name: config.description
            for name, config in user_agents.items()
            if not agent_type or config.agent_type == agent_type
        }

    def format_agent_descriptions(
        self,
        token: str,
        agent_type: AgentType = None,
        fallback: str = "暂无可用 Agent",
    ) -> str:
        """获取格式化的 Agent 描述文本，可直接注入 Prompt。

        返回格式示例::

            - **基金画像规划师**: 负责基金画像生成的任务规划
            - **通用规划师**: 处理通用业务任务的规划

        Args:
            token: 用户身份 Token。
            agent_type: 按角色类型过滤，None 表示全部。
            fallback: 无可用 Agent 时的回退文本。
        """
        descriptions = self.get_agent_descriptions(token, agent_type)
        if not descriptions:
            return fallback
        return "\n".join(f"- **{name}**: {desc}" for name, desc in descriptions.items())

    def find_agent_by_tag(self, tag: str, token: str) -> list[AgentConfig]:
        """按标签检索 Agent 列表。

        Args:
            tag: 目标标签。
            token: 用户身份 Token。
        """
        self.load(token)
        user_agents = self._user_agents.get(token, {})
        return [config for config in user_agents.values() if tag in config.tags]

    # ── Planner 场景方法 ────────────────────────────────

    def get_bound_executor_descriptions(
        self,
        token: str,
        planner_name: str,
    ) -> dict[str, str]:
        """获取指定 Planner 绑定范围内的 Executor 描述。

        严格限定在 Planner 的 bound_agents 列表内，
        不在范围内的 Executor 不会返回。

        Args:
            token: 用户身份 Token。
            planner_name: Planner Agent 名称。

        Returns:
            Executor 名称→描述的映射；Planner 无绑定则返回空 dict。
        """
        planner = self.get_agent(planner_name, token) if planner_name else None
        bound_agents = planner.bound_agents if planner else []
        if not bound_agents:
            return {}
        all_executors = self.get_agent_descriptions(token, agent_type=AgentType.EXECUTOR)
        return {name: desc for name, desc in all_executors.items() if name in bound_agents}

    def build_planner_tool_descriptions(
        self, token: str, planner_name: str
    ) -> str:
        """构建 Planner 规划阶段所需的 Executor + 工具描述文本。

        遍历该 Planner 绑定的所有 Executor，展示各自的描述和绑定工具。
        供 planner_node 注入规划 Prompt 的 {executor_descriptions} 占位符，
        帮助 Planner 了解每个 Executor 的能力边界。

        Args:
            token: 用户身份 Token。
            planner_name: Planner Agent 名称。

        Returns:
            格式化的 Executor 及其工具描述文本。
        """
        bound_descs = self.get_bound_executor_descriptions(token, planner_name)

        if not bound_descs:
            return "暂无可用 Executor/工具"

        tool_lines = []

        for executor_name in bound_descs:
            executor_config = self.get_agent(executor_name, token)
            if executor_config:
                tool_lines.append(executor_config.get_tool_summaries_text(token))

        return "\n".join(tool_lines) if tool_lines else "暂无可用 Executor/工具"


# ═══════════════════════════════════════════════════════════
#  全局单例
# ═══════════════════════════════════════════════════════════

_agent_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """获取全局 AgentRegistry 单例。"""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
