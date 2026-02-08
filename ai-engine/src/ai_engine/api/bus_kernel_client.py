"""
Bus Kernel API 客户端
负责从业务内核获取 Agent 和 Tool 的定义
"""

import httpx
from typing import Any, Optional
from ..config import get_settings


class BusKernelClient:
    """
    功能: 与 bus-kernel 通信的客户端
    参数: base_url - bus-kernel 的 API 基础路径
    返回: BusKernelClient 实例
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=10.0)

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        """通用 GET 请求处理"""
        url = f"{self.base_url}{path}"
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("code") == 200:
                return data.get("data")
            else:
                print(f"[BusKernelClient] API 错误: {data.get('message')}")
                return None
        except Exception as e:
            print(f"[BusKernelClient] 请求异常 {url}: {e}")
            return None

    def get_agent_page(self, page: int = 1, size: int = 100) -> list[dict[str, Any]]:
        """获取 Agent 分页列表 (用于加载摘要)"""
        result = self._get("/agent/page", params={"page": page, "size": size})
        if result and "records" in result:
            return result["records"]
        return []

    def get_agent_detail(self, agent_name: str) -> Optional[dict[str, Any]]:
        """获取 Agent 完整详情"""
        return self._get(f"/agent/detail/{agent_name}")

    def get_tool_page(self, page: int = 1, size: int = 100) -> list[dict[str, Any]]:
        """获取 Tool 分页列表 (用于加载摘要)"""
        result = self._get("/tool/page", params={"page": page, "size": size})
        if result and "records" in result:
            return result["records"]
        return []

    def get_tool_detail(self, tool_name: str) -> Optional[dict[str, Any]]:
        """获取 Tool 完整详情"""
        return self._get(f"/tool/detail/{tool_name}")

    def close(self):
        self.client.close()


_bus_kernel_client: Optional[BusKernelClient] = None

def get_bus_kernel_client() -> BusKernelClient:
    """获取全局客户端单例"""
    global _bus_kernel_client
    if _bus_kernel_client is None:
        settings = get_settings()
        _bus_kernel_client = BusKernelClient(settings.bus_kernel_base_url)
    return _bus_kernel_client
