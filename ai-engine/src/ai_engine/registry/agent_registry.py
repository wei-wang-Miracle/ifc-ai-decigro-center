"""
Agent 注册中心
从数据库加载 agent_cards 并管理 Agent 配置
"""

import json
from functools import lru_cache
from typing import Any, Optional

from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool

from .tool_registry import get_tool_registry
from ..api.bus_kernel_client import get_bus_kernel_client


class AgentConfig:
    """
    功能: Agent 配置封装类
    支持按需加载完整信息
    """
    
    def __init__(self, summary: dict[str, Any], detail: Optional[dict[str, Any]] = None):
        """
        功能: 初始化 Agent 配置
        参数: 
            summary - 摘要信息 (agent_name, agent_description, agent_tags)
            detail - 完整详情 (可选)
        """
        self._summary = summary
        self._detail = detail
        self._tools: list[StructuredTool] = []
        self._bound_tools_loaded = False
    
    @property
    def name(self) -> str:
        return self._summary["agent_name"]
    
    @property
    def description(self) -> str:
        return self._summary.get("agent_description", "")
    
    @property
    def tags(self) -> list[str]:
        tags = self._summary.get("agent_tags", [])
        if isinstance(tags, str):
            tags = json.loads(tags) if tags else []
        return tags

    @property
    def alias(self) -> str:
        if self._detail:
            return self._detail.get("agent_alias", self.name)
        return self.name

    @property
    def system_prompt(self) -> str:
        return self._detail.get("system_prompt", "") if self._detail else ""
    
    @property
    def negative_prompt(self) -> str:
        return self._detail.get("negative_prompt", "") if self._detail else ""
    
    @property
    def reasoning_framework(self) -> str | None:
        return self._detail.get("reasoning_framework") if self._detail else None
    
    @property
    def raw_bound_tools(self) -> list[str] | None:
        if not self._detail:
            return None
        bound = self._detail.get("bound_tools")
        if bound is None:
            return None
        if isinstance(bound, str):
            return json.loads(bound) if bound else []
        return bound
    
    def set_detail(self, detail: dict[str, Any]):
        """填充详情"""
        self._detail = detail
        self._bound_tools_loaded = False

    def get_tools(self, token: str) -> list[StructuredTool]:
        """
        获取该 Agent 可用的工具列表 (触发工具详情加载)
        """
        if self._bound_tools_loaded:
            return self._tools
        
        tool_registry = get_tool_registry()
        raw_bound = self.raw_bound_tools
        
        if raw_bound is None:
            # 默认使用所有公共工具
            self._tools = tool_registry.get_public_tools(token) 
        elif len(raw_bound) == 0:
            self._tools = []
        else:
            self._tools = tool_registry.get_tools_by_names(raw_bound, token)
        
        self._bound_tools_loaded = True
        return self._tools
    
    def build_system_message(self, token: str) -> str:
        parts = []
        if self.system_prompt:
            parts.append(self.system_prompt)
        if self.negative_prompt:
            parts.append(f"\n## 禁止事项\n{self.negative_prompt}")
        
        tools = self.get_tools(token)
        if tools:
            tool_descriptions = []
            for tool in tools:
                tool_descriptions.append(f"- **{tool.name}**: {tool.description}")
            parts.append("\n## 可用工具\n" + "\n".join(tool_descriptions))
        
        return "\n\n".join(parts)
    
    def build_prompt_template(self, token: str) -> ChatPromptTemplate:
        system_message = self.build_system_message(token)
        return ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="messages"),
        ])


class AgentRegistry:
    """
    功能: Agent 注册中心，统一管理所有 Agent 配置
    支持从 API 渐进式加载
    """
    
    def __init__(self):
        self._client = get_bus_kernel_client()
        # 存储摘要: {token: {agent_name: AgentConfig}}
        self._user_agents: dict[str, dict[str, AgentConfig]] = {}

    def load(self, token: str, force: bool = False) -> None:
        """
        功能: AI 加载阶段 - 获取当前用户可用的 Agent 列表
        参数: token - 用户身份 Token
        """
        if token in self._user_agents and not force:
            return
        
        # 通过 API 获取当前用户可用的 Agent 简要信息 (POST /agent/available)
        records = self._client.get_available_agents(token)
        
        user_agents = {}
        for record in records:
            name = record.get("agentName")
            if name:
                summary = {
                    "agent_name": name,
                    "agent_description": record.get("agentDescription"),
                    "agent_tags": record.get("agentTags"),
                }
                user_agents[name] = AgentConfig(summary)
        
        self._user_agents[token] = user_agents
        
        # 确保 default agent 存在
        if "default" not in user_agents:
            user_agents["default"] = AgentConfig({
                "agent_name": "default",
                "agent_description": "系统默认助手，用于处理通用任务和闲聊",
                "agent_tags": ["general", "system"],
            })
            
        print(f"[AgentRegistry] 成功为 Token[{token[:10]}...] 加载 {len(user_agents)} 个 Agent 摘要")
    
    def get_agent(self, agent_name: str, token: str) -> AgentConfig | None:
        """
        功能: AI 使用阶段 - 获取指定 Agent 的完整配置
        参数: agent_name, token
        """
        self.load(token)
        user_agents = self._user_agents.get(token, {})
        agent = user_agents.get(agent_name)
        
        # 加载完整详情 (POST /agent/detail)
        if agent and not agent._detail:
            print(f"[AgentRegistry] 正在加载 Agent 详情: {agent_name}")
            detail_data = self._client.get_agent_detail(agent_name, token)
            if detail_data:
                detail = {
                    "agent_alias": detail_data.get("agentAlias"),
                    "system_prompt": detail_data.get("systemPrompt"),
                    "negative_prompt": detail_data.get("negativePrompt"),
                    "bound_tools": detail_data.get("boundTools"),
                    "reasoning_framework": detail_data.get("reasoningFramework"),
                }
                agent.set_detail(detail)
            elif agent_name == "default":
                # 为 default agent 提供默认详情
                detail = {
                    "agent_alias": "默认助手",
                    "system_prompt": "你是一个乐于助人的AI助手。对于用户的闲聊（如'你好'），请热情回复并引导用户使用系统功能。",
                    "negative_prompt": "",
                    "bound_tools": None 
                }
                agent.set_detail(detail)

        return agent
    
    def get_all_agents(self, token: str) -> list[AgentConfig]:
        self.load(token)
        return list(self._user_agents.get(token, {}).values())
    
    def get_agent_names(self, token: str) -> list[str]:
        self.load(token)
        return list(self._user_agents.get(token, {}).keys())
    
    def get_agent_descriptions(self, token: str) -> dict[str, str]:
        self.load(token)
        user_agents = self._user_agents.get(token, {})
        return {
            name: config.description
            for name, config in user_agents.items()
        }
    
    def find_agent_by_tag(self, tag: str, token: str) -> list[AgentConfig]:
        self.load(token)
        user_agents = self._user_agents.get(token, {})
        return [
            config for config in user_agents.values()
            if tag in config.tags
        ]
    
    def reload(self, token: str) -> None:
        if token in self._user_agents:
            del self._user_agents[token]
        self.load(token, force=True)


# 全局单例
_agent_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """
    功能: 获取全局 AgentRegistry 单例
    参数: 无
    返回: AgentRegistry 实例
    """
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
