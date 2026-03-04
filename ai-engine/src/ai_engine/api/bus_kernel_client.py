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

    def _post(self, path: str, json_data: Optional[dict] = None, token: Optional[str] = None) -> Any:
        """通用 POST 请求处理，支持 Token"""
        url = f"{self.base_url}{path}"
        headers = {}
        if token:
            headers["X-Auth-Token"] = token
            
        try:
            response = self.client.post(url, json=json_data, headers=headers)
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

    def get_available_agents(self, token: str) -> list[dict[str, Any]]:
        """
        功能: 获取当前用户可用的 Agent 列表 (AI 加载阶段)
        参数: token - 用户认证 Token
        """
        result = self._post("/agent/available", token=token)
        return result if result else []

    def get_agent_detail(self, agent_name: str, token: str) -> Optional[dict[str, Any]]:
        """
        功能: 获取指定 Agent 详情 (AI 调用阶段)
        参数: agent_name, token
        """
        return self._post("/agent/detail", json_data={"agentName": agent_name}, token=token)

    def get_available_tools(self, token: str, privileges: Optional[str] = None) -> list[dict[str, Any]]:
        """
        功能: 获取当前用户可用的工具列表 (AI 加载阶段)
        参数: 
            token - 用户认证 Token
            privileges - 权限类型筛选（可选），支持 public/protected
        """
        params = f"?privileges={privileges}" if privileges else ""
        result = self._post(f"/tool/available{params}", token=token)
        return result if result else []

    def get_all_tools(self, token: str) -> list[dict[str, Any]]:
        """
        功能: 获取所有可用工具（不区分权限）
        参数: token - 用户认证 Token
        """
        result = self._post("/tool/all-tools", token=token)
        return result if result else []

    def get_tool_detail(self, tool_name: str, token: str) -> Optional[dict[str, Any]]:
        """
        功能: 获取指定工具详情 (AI 调用阶段)
        参数: tool_name, token
        """
        return self._post("/tool/detail", json_data={"toolName": tool_name}, token=token)

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
