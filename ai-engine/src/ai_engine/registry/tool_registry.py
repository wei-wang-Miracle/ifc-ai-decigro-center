"""
工具注册中心
从数据库加载 tool_cards 并管理动态工具
"""

import time
from functools import lru_cache
from typing import Any

from langchain_core.tools import StructuredTool

from ..api.bus_kernel_client import get_bus_kernel_client
from ..tools.factory import create_dynamic_tool


def _safe_serialize(obj: Any, max_len: int = 300) -> str:
    """安全序列化任意对象。"""
    import json
    try:
        text = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(obj)
    return text[:max_len] + "..." if len(text) > max_len else text


class ToolRegistry:
    """
    功能: 工具注册中心，统一管理所有动态工具
    支持从 bus-kernel API 渐进式加载
    """
    
    def __init__(self):
        """
        功能: 初始化工具注册中心
        """
        self._client = get_bus_kernel_client()
        # 存储摘要: {token: {tool_name: summary}}
        self._user_tool_summaries: dict[str, dict[str, dict[str, Any]]] = {}
        # 存储已构建的完整工具: {token: {tool_name: StructuredTool}}
        self._user_tools: dict[str, dict[str, StructuredTool]] = {}
        # 存储完整的卡片数据: {tool_name: tool_card} (详情全局缓存即可，反正有权限校验)
        self._tool_cards: dict[str, dict[str, Any]] = {}
    
    def load(self, token: str, force: bool = False, privileges: str | None = None) -> None:
        """
        功能: AI 加载阶段 - 仅加载当前用户可用的工具摘要
        参数:
            token - 用户身份 Token
            force - 是否强制重新加载
            privileges - 权限类型筛选（可选），支持 public/protected
        """
        start_ts = time.time()
        if token in self._user_tool_summaries and not force:
            print(f"[ToolRegistry] 工具摘要已存在，跳过加载 (Token: {token[:10]}...)")
            return

        print(f"[ToolRegistry] 开始加载工具摘要 (Token: {token[:10]}..., Force: {force}, Privileges: {privileges})")

        records = self._client.get_available_tools(token, privileges)

        user_summaries = {}
        for record in records:
            name = record.get("toolName")
            if name:
                user_summaries[name] = {
                    "tool_name": name,
                    "tool_alias": record.get("toolAlias", name),
                    "tool_description": record.get("toolDescription"),
                    "tool_tags": record.get("toolTags"),
                    "tool_privileges": record.get("toolPrivileges", "public"),
                }

        self._user_tool_summaries[token] = user_summaries
        if token not in self._user_tools:
            self._user_tools[token] = {}

        latency_ms = int((time.time() - start_ts) * 1000)
        print(f"[ToolRegistry] 工具摘要加载完成，耗时 {latency_ms}ms")
        print(f"[ToolRegistry] 摘要详情: 共 {len(user_summaries)} 个工具")
        if user_summaries:
            tool_list = [f"{name}({info.get('tool_privileges', 'public')})" for name, info in user_summaries.items()]
            print(f"[ToolRegistry] 工具列表: {_safe_serialize(tool_list)}")
    
    def get_tool(self, tool_name: str, token: str) -> StructuredTool | None:
        """
        功能: AI 使用阶段 - 获取完整工具，如果未加载则从 API 获取详情并构建
        参数:
            tool_name - 工具唯一标识
            token - 用户身份 Token
        返回: StructuredTool 实例
        """
        start_ts = time.time()
        print(f"[ToolRegistry] 获取工具: {tool_name} (Token: {token[:10]}...)")

        self.load(token)

        user_summaries = self._user_tool_summaries.get(token, {})
        if tool_name not in user_summaries:
            print(f"[ToolRegistry] 用户无权访问或工具不存在: {tool_name}")
            return None

        if tool_name in self._user_tools[token]:
            print(f"[ToolRegistry] 工具命中缓存: {tool_name}")
            return self._user_tools[token][tool_name]

        print(f"[ToolRegistry] 正在从 API 加载工具详情: {tool_name}")
        detail = self._client.get_tool_detail(tool_name, token)
        if detail:
            tool_card = {
                "tool_name": detail.get("toolName"),
                "tool_description": detail.get("toolDescription"),
                "tool_protocol": detail.get("toolProtocol"),
                "url_path": detail.get("urlPath"),
                "tool_method": detail.get("toolMethod", "POST"),
                "tool_headers": detail.get("toolHeaders"),
                "tool_parameters": detail.get("toolParameters"),
                "reference_target": detail.get("referenceTarget"),
            }

            print(f"[ToolRegistry] 工具详情已获取:")
            print(f"[ToolRegistry]   - 名称: {tool_card['tool_name']}")
            print(f"[ToolRegistry]   - 描述: {tool_card['tool_description']}")
            print(f"[ToolRegistry]   - 协议: {tool_card['tool_protocol']}")
            print(f"[ToolRegistry]   - URL: {tool_card['url_path']}")
            print(f"[ToolRegistry]   - 方法: {tool_card['tool_method']}")
            print(f"[ToolRegistry]   - 参数: {_safe_serialize(tool_card['tool_parameters'], 200)}")

            try:
                tool = create_dynamic_tool(tool_card, token=token)
                self._user_tools[token][tool_name] = tool
                self._tool_cards[tool_name] = tool_card
                latency_ms = int((time.time() - start_ts) * 1000)
                print(f"[ToolRegistry] 工具构建完成: {tool_name}，总耗时 {latency_ms}ms")
                return tool
            except Exception as e:
                print(f"[ToolRegistry] 构建工具 {tool_name} 失败: {e}")

        latency_ms = int((time.time() - start_ts) * 1000)
        print(f"[ToolRegistry] 获取工具失败: {tool_name}，耗时 {latency_ms}ms")
        return None
    
    def get_tools_by_names(self, tool_names: list[str], token: str) -> list[StructuredTool]:
        """
        功能: 根据名称列表获取多个工具（触发详情加载）
        参数: tool_names - 工具名称列表
        返回: StructuredTool 列表
        """
        start_ts = time.time()
        print(f"[ToolRegistry] 批量获取工具: {tool_names} (Token: {token[:10]}...)")
        tools = []
        for name in tool_names:
            tool = self.get_tool(name, token)
            if tool:
                tools.append(tool)
        latency_ms = int((time.time() - start_ts) * 1000)
        print(f"[ToolRegistry] 批量获取完成: 请求 {len(tool_names)} 个，成功 {len(tools)} 个，耗时 {latency_ms}ms")
        return tools

    def get_all_tool_summaries(self, token: str) -> list[dict[str, Any]]:
        """
        功能: 获取所有可用工具的摘要信息
        返回: 摘要列表
        """
        print(f"[ToolRegistry] 获取所有工具摘要 (Token: {token[:10]}...)")
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        print(f"[ToolRegistry] 工具摘要列表: {_safe_serialize(list(user_summaries.keys()))}")
        return list(user_summaries.values())

    def get_tool_names(self, token: str) -> list[str]:
        """
        功能: 获取所有工具名称列表
        """
        print(f"[ToolRegistry] 获取所有工具名称 (Token: {token[:10]}...)")
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        tool_names = list(user_summaries.keys())
        print(f"[ToolRegistry] 工具名称列表: {_safe_serialize(tool_names)}")
        return tool_names

    def get_tool_card(self, tool_name: str, token: str) -> dict[str, Any] | None:
        """
        功能: 获取工具原始详情卡片
        """
        print(f"[ToolRegistry] 获取工具原始卡片: {tool_name}")
        self.get_tool(tool_name, token)
        card = self._tool_cards.get(tool_name)
        if card:
            print(f"[ToolRegistry] 工具卡片已获取: {tool_name}")
        else:
            print(f"[ToolRegistry] 工具卡片不存在: {tool_name}")
        return card

    def get_public_tools(self, token: str) -> list[StructuredTool]:
        """
        获取所有公开工具（触发所有公开工具的详情加载）
        """
        print(f"[ToolRegistry] 获取所有公开工具 (Token: {token[:10]}...)")
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        public_names = [
            name for name, summary in user_summaries.items()
            if summary.get("tool_privileges") == "public"
        ]
        print(f"[ToolRegistry] 公开工具列表: {_safe_serialize(public_names)}")
        return self.get_tools_by_names(public_names, token)

    def is_protected(self, tool_name: str, token: str) -> bool:
        """
        判断是否为受保护工具
        """
        print(f"[ToolRegistry] 检查工具权限: {tool_name}")
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        summary = user_summaries.get(tool_name)
        if summary:
            is_protected = summary.get("tool_privileges") == "protected"
            print(f"[ToolRegistry] 工具 {tool_name} 权限检查结果: {'受保护' if is_protected else '公开'}")
            return is_protected

        card = self.get_tool_card(tool_name, token)
        if card:
            is_protected = card.get("tool_privileges", "public") == "protected"
            print(f"[ToolRegistry] 工具 {tool_name} 权限检查结果(从卡片): {'受保护' if is_protected else '公开'}")
            return is_protected
        print(f"[ToolRegistry] 工具 {tool_name} 不存在或无权限")
        return False

    def reload(self, token: str) -> None:
        """热更新"""
        start_ts = time.time()
        print(f"[ToolRegistry] 开始热更新 (Token: {token[:10]}...)")
        if token in self._user_tool_summaries:
            del self._user_tool_summaries[token]
        if token in self._user_tools:
            del self._user_tools[token]
        self.load(token, force=True)
        latency_ms = int((time.time() - start_ts) * 1000)
        print(f"[ToolRegistry] 热更新完成，耗时 {latency_ms}ms")

    def get_all_tool_summaries_from_api(self, token: str) -> list[dict[str, Any]]:
        """
        功能: 直接从 API 获取所有可用工具摘要（不区分权限）
        参数: token - 用户身份 Token
        返回: 工具摘要列表
        """
        start_ts = time.time()
        print(f"[ToolRegistry] 从 API 获取所有工具摘要 (Token: {token[:10]}...)")
        records = self._client.get_all_tools(token)
        summaries = []
        for record in records:
            name = record.get("toolName")
            if name:
                summaries.append({
                    "tool_name": name,
                    "tool_alias": record.get("toolAlias", name),
                    "tool_description": record.get("toolDescription"),
                    "tool_tags": record.get("toolTags"),
                    "tool_privileges": record.get("toolPrivileges", "public"),
                })
        latency_ms = int((time.time() - start_ts) * 1000)
        print(f"[ToolRegistry] API 获取完成: {len(summaries)} 个工具，耗时 {latency_ms}ms")
        return summaries


# 全局单例
_tool_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """
    功能: 获取全局 ToolRegistry 单例
    参数: 无
    返回: ToolRegistry 实例
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry
