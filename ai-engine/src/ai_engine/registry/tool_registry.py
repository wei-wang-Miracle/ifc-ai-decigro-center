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
        # 存储摘要: {tool_name: {tool_name, tool_description}}
        self._tool_summaries: dict[str, dict[str, Any]] = {}
        # 存储已构建的完整工具: {tool_name: StructuredTool}
        self._tools: dict[str, StructuredTool] = {}
        # 存储完整的卡片数据: {tool_name: tool_card}
        self._tool_cards: dict[str, dict[str, Any]] = {}
        self._loaded = False
    
    def load(self, force: bool = False) -> None:
        """
        功能: AI 加载阶段 - 仅加载工具摘要 (name, description, privileges)
        参数: force - 是否强制重新加载
        返回: None
        """
        if self._loaded and not force:
            return
        
        # 通过 API 获取工具列表摘要
        records = self._client.get_tool_page(page=1, size=100)
        
        self._tool_summaries = {}
        for record in records:
            name = record.get("toolName")
            if name:
                self._tool_summaries[name] = {
                    "tool_name": name,
                    "tool_description": record.get("toolDescription"),
                    "tool_privileges": record.get("toolPrivileges", "public"),
                }
        
        self._loaded = True
        print(f"[ToolRegistry] 成功加载 {len(self._tool_summaries)} 个工具摘要")
    
    def get_tool(self, tool_name: str) -> StructuredTool | None:
        """
        功能: AI 使用阶段 - 获取完整工具，如果未加载则从 API 获取详情并构建
        参数: tool_name - 工具唯一标识
        返回: StructuredTool 实例，如果不存在则返回 None
        """
        self.load()
        
        # 检查是否已经构建过
        if tool_name in self._tools:
            return self._tools[tool_name]
        
        # 如果只有摘要没有详情，则从 API 获取详情
        if tool_name in self._tool_summaries:
            print(f"[ToolRegistry] 正在加载工具详情: {tool_name}")
            detail = self._client.get_tool_detail(tool_name)
            if detail:
                # 转换 Java CamelCase 到 Python snake_case (如果需要)
                # 目前 factory 里的 create_dynamic_tool 使用了与数据库列名一致的 key
                # 我们需要确保映射一致
                tool_card = {
                    "tool_name": detail.get("toolName"),
                    "tool_description": detail.get("toolDescription"),
                    "tool_protocol": detail.get("toolProtocol"),
                    "url_path": detail.get("urlPath"),
                    "tool_parameters": detail.get("toolParameters"),
                    "tool_privileges": detail.get("toolPrivileges"),
                    "reference_target": detail.get("referenceTarget"),
                }
                
                try:
                    tool = create_dynamic_tool(tool_card)
                    self._tools[tool_name] = tool
                    self._tool_cards[tool_name] = tool_card
                    return tool
                except Exception as e:
                    print(f"[ToolRegistry] 构建工具 {tool_name} 失败: {e}")
        
        return None
    
    def get_tools_by_names(self, tool_names: list[str]) -> list[StructuredTool]:
        """
        功能: 根据名称列表获取多个工具（触发详情加载）
        参数: tool_names - 工具名称列表
        返回: StructuredTool 列表
        """
        tools = []
        for name in tool_names:
            tool = self.get_tool(name)
            if tool:
                tools.append(tool)
        return tools
    
    def get_all_tool_summaries(self) -> list[dict[str, Any]]:
        """
        功能: 获取所有可用工具的摘要信息
        返回: 摘要列表
        """
        self.load()
        return list(self._tool_summaries.values())
    
    def get_tool_names(self) -> list[str]:
        """
        功能: 获取所有工具名称列表
        """
        self.load()
        return list(self._tool_summaries.keys())
    
    def get_tool_card(self, tool_name: str) -> dict[str, Any] | None:
        """
        功能: 获取工具原始详情卡片
        """
        self.get_tool(tool_name) # 确保已加载
        return self._tool_cards.get(tool_name)

    def get_public_tools(self) -> list[StructuredTool]:
        """
        获取所有公开工具（触发所有公开工具的详情加载）
        """
        self.load()
        public_names = [
            name for name, summary in self._tool_summaries.items()
            if summary.get("tool_privileges") == "public"
        ]
        return self.get_tools_by_names(public_names)

    def is_protected(self, tool_name: str) -> bool:
        """
        判断是否为受保护工具
        """
        self.load()
        # 优先通过摘要判断
        summary = self._tool_summaries.get(tool_name)
        if summary:
            return summary.get("tool_privileges") == "protected"
        
        # 如果摘要没有（新工具？），检查完整卡片
        card = self.get_tool_card(tool_name)
        if card:
            return card.get("tool_privileges", "public") == "protected"
        return False

    def reload(self) -> None:
        """热更新"""
        self._loaded = False
        self._tools = {}
        self._tool_cards = {}
        self.load(force=True)


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
