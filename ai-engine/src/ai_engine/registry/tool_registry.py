"""
工具注册中心
从数据库加载 tool_cards 并管理动态工具
"""

from functools import lru_cache
from typing import Any

from langchain_core.tools import StructuredTool

from ..api.bus_kernel_client import get_bus_kernel_client
from ..tools.factory import create_dynamic_tool


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
    
    def load(self, token: str, force: bool = False) -> None:
        """
        功能: AI 加载阶段 - 仅加载当前用户可用的工具摘要
        参数: 
            token - 用户身份 Token
            force - 是否强制重新加载
        """
        if token in self._user_tool_summaries and not force:
            return
        
        # 通过 API 获取当前用户可用的工具列表摘要 (POST /tool/available)
        records = self._client.get_available_tools(token)
        
        user_summaries = {}
        for record in records:
            name = record.get("toolName")
            if name:
                user_summaries[name] = {
                    "tool_name": name,
                    "tool_description": record.get("toolDescription"),
                    "tool_tags": record.get("toolTags"),
                }
        
        self._user_tool_summaries[token] = user_summaries
        if token not in self._user_tools:
            self._user_tools[token] = {}
            
        print(f"[ToolRegistry] 成功为 Token[{token[:10]}...] 加载 {len(user_summaries)} 个工具摘要")
    
    def get_tool(self, tool_name: str, token: str) -> StructuredTool | None:
        """
        功能: AI 使用阶段 - 获取完整工具，如果未加载则从 API 获取详情并构建
        参数: 
            tool_name - 工具唯一标识
            token - 用户身份 Token
        返回: StructuredTool 实例
        """
        self.load(token)
        
        # 1. 权限预检：检查摘要中是否存在该工具
        user_summaries = self._user_tool_summaries.get(token, {})
        if tool_name not in user_summaries:
            print(f"[ToolRegistry] 用户无权访问或工具不存在: {tool_name}")
            return None

        # 2. 检查会话缓存
        if tool_name in self._user_tools[token]:
            return self._user_tools[token][tool_name]
        
        # 3. 从 API 获取详情 (POST /tool/detail)
        print(f"[ToolRegistry] 正在加载工具详情: {tool_name}")
        detail = self._client.get_tool_detail(tool_name, token)
        if detail:
            tool_card = {
                "tool_name": detail.get("toolName"),
                "tool_description": detail.get("toolDescription"),
                "tool_protocol": detail.get("toolProtocol"),
                "url_path": detail.get("urlPath"),
                "tool_parameters": detail.get("toolParameters"),
                "reference_target": detail.get("referenceTarget"),
            }
            
            try:
                tool = create_dynamic_tool(tool_card, token=token)
                self._user_tools[token][tool_name] = tool
                self._tool_cards[tool_name] = tool_card
                return tool
            except Exception as e:
                print(f"[ToolRegistry] 构建工具 {tool_name} 失败: {e}")
        
        return None
    
    def get_tools_by_names(self, tool_names: list[str], token: str) -> list[StructuredTool]:
        """
        功能: 根据名称列表获取多个工具（触发详情加载）
        参数: tool_names - 工具名称列表
        返回: StructuredTool 列表
        """
        tools = []
        for name in tool_names:
            tool = self.get_tool(name, token)
            if tool:
                tools.append(tool)
        return tools
    
    def get_all_tool_summaries(self, token: str) -> list[dict[str, Any]]:
        """
        功能: 获取所有可用工具的摘要信息
        返回: 摘要列表
        """
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        return list(user_summaries.values())
    
    def get_tool_names(self, token: str) -> list[str]:
        """
        功能: 获取所有工具名称列表
        """
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        return list(user_summaries.keys())
    
    def get_tool_card(self, tool_name: str, token: str) -> dict[str, Any] | None:
        """
        功能: 获取工具原始详情卡片
        """
        self.get_tool(tool_name, token) # 确保已加载
        return self._tool_cards.get(tool_name)

    def get_public_tools(self, token: str) -> list[StructuredTool]:
        """
        获取所有公开工具（触发所有公开工具的详情加载）
        """
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        public_names = [
            name for name, summary in user_summaries.items()
            if summary.get("tool_privileges") == "public"
        ]
        return self.get_tools_by_names(public_names, token)
    
    def is_protected(self, tool_name: str, token: str) -> bool:
        """
        判断是否为受保护工具
        """
        self.load(token)
        user_summaries = self._user_tool_summaries.get(token, {})
        # 优先通过摘要判断
        summary = user_summaries.get(tool_name)
        if summary:
            return summary.get("tool_privileges") == "protected"
        
        # 如果摘要没有（新工具？），检查完整卡片
        card = self.get_tool_card(tool_name, token)
        if card:
            return card.get("tool_privileges", "public") == "protected"
        return False

    def reload(self, token: str) -> None:
        """热更新"""
        if token in self._user_tool_summaries:
            del self._user_tool_summaries[token]
        if token in self._user_tools:
            del self._user_tools[token]
        self.load(token, force=True)


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
