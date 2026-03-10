"""
动态工具工厂模块
将 tool_cards 表中的 JSONB 参数动态转换为 LangChain StructuredTool
"""

import json
from typing import Any, Callable, Type

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from ..config import get_settings


# ========================================
# 类型映射：将数据库中的类型字符串转换为 Python 类型
# ========================================
TYPE_MAPPING: dict[str, Type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _parse_param_type(param_type: str) -> Type:
    """
    功能: 将数据库中的参数类型字符串转换为 Python 类型
    参数: param_type - 类型字符串 (string/integer/number/boolean/array/object)
    返回: 对应的 Python 类型
    """
    return TYPE_MAPPING.get(param_type.lower(), str)


def create_pydantic_model_from_params(
    tool_name: str,
    parameters: list[dict[str, Any]]
) -> Type[BaseModel]:
    """
    功能: 根据 tool_parameters JSON 数组动态创建 Pydantic 模型
    参数:
        tool_name - 工具名称，用于生成模型类名
        parameters - 参数定义列表，每个元素包含 param_name, param_type, param_description, param_required
    返回: 动态创建的 Pydantic 模型类
    
    示例 parameters:
    [
        {"param_name": "city", "param_type": "string", "param_description": "城市名称", "param_required": true},
        {"param_name": "unit", "param_type": "string", "param_description": "温度单位", "param_required": false}
    ]
    """
    # 字段定义字典：field_name -> (type, Field(...))
    field_definitions: dict[str, tuple[Type, Any]] = {}
    
    for param in parameters:
        param_name = param.get("param_name", "unknown")
        param_type = param.get("param_type", "string")
        param_desc = param.get("param_description", "")
        param_required = param.get("param_required", True)
        param_example = param.get("param_example")
        
        # 获取 Python 类型
        python_type = _parse_param_type(param_type)
        
        # 如果是可选参数，包装为 Optional 类型
        if not param_required:
            python_type = python_type | None
            default_value = None
        else:
            # 必填参数使用 ... 作为默认值（表示必填）
            default_value = ...
        
        # 创建 Field 定义
        field_kwargs = {"description": param_desc}
        if param_example is not None:
            field_kwargs["examples"] = [param_example]
        
        field_definitions[param_name] = (
            python_type,
            Field(default=default_value, **field_kwargs)
        )
    
    # 使用 create_model 动态创建 Pydantic 模型
    # 模型类名采用 PascalCase 格式
    model_name = "".join(word.capitalize() for word in tool_name.split("_")) + "Input"
    
    return create_model(model_name, **field_definitions)


def create_http_executor(
    url_path: str,
    method: str = "POST",
    token: str = None,
    extra_headers: dict[str, str] | None = None
) -> Callable[..., str]:
    """
    功能: 创建 HTTP 工具执行器
    参数:
        url_path - API 路径（相对路径走 Bus Kernel，完整 URL 直接请求）
        method - HTTP 方法 (GET/POST/PUT/DELETE)
        token - 用户身份 Token（自动注入 X-Auth-Token，仅对 Bus Kernel 请求有效）
        extra_headers - 工具卡片中配置的自定义请求头
    返回: 可调用的执行器函数
    """
    settings = get_settings()
    is_bus_kernel = not (url_path.startswith("http://") or url_path.startswith("https://"))

    # 判断是相对路径还是完整 URL
    if is_bus_kernel:
        # 相对路径，拼接 Bus Kernel 基础 URL
        base_url = settings.bus_kernel_base_url.rstrip("/")
        full_url = f"{base_url}{url_path}"
    else:
        full_url = url_path

    def executor(**kwargs) -> str:
        """
        功能: 执行 HTTP 请求并返回结果
        参数: kwargs - 传递给工具的参数（GET 作为查询参数，POST/PUT 作为 JSON 请求体）
        返回: API 响应的 JSON 字符串
        """
        headers = {}
        # 注入自定义请求头
        if extra_headers:
            headers.update(extra_headers)
        # Bus Kernel 请求自动注入 Token
        if token and is_bus_kernel:
            headers["X-Auth-Token"] = token

        try:
            with httpx.Client(timeout=30.0) as client:
                if method.upper() == "GET":
                    response = client.get(full_url, params=kwargs, headers=headers)
                elif method.upper() == "POST":
                    response = client.post(full_url, json=kwargs, headers=headers)
                elif method.upper() == "PUT":
                    response = client.put(full_url, json=kwargs, headers=headers)
                elif method.upper() == "DELETE":
                    response = client.delete(full_url, params=kwargs, headers=headers)
                else:
                    return json.dumps({"error": f"不支持的 HTTP 方法: {method}"})

                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            return json.dumps({
                "error": f"HTTP 请求失败",
                "status_code": e.response.status_code,
                "detail": e.response.text
            })
        except httpx.RequestError as e:
            return json.dumps({
                "error": f"请求异常: {str(e)}"
            })

    return executor


def create_dynamic_tool(tool_card: dict[str, Any], token: str = None) -> StructuredTool:
    """
    功能: 根据 tool_card 数据动态创建 LangChain StructuredTool
    参数: 
        tool_card - 从数据库读取的工具卡片字典
        token - 用户身份 Token (用于透传)
    返回: LangChain StructuredTool 实例
    
    tool_card 结构示例:
    {
        "tool_name": "get_weather",
        "tool_description": "获取指定城市的天气信息",
        "tool_protocol": "http",
        "url_path": "/api/weather",
        "tool_parameters": [{"param_name": "city", ...}],
        ...
    }
    """
    tool_name = tool_card["tool_name"]
    tool_description = tool_card["tool_description"]
    tool_protocol = tool_card.get("tool_protocol", "http")
    tool_parameters = tool_card.get("tool_parameters", [])
    
    # 第一步：创建 Pydantic 参数模型
    # 如果 tool_parameters 是字符串（JSON），先解析
    if isinstance(tool_parameters, str):
        tool_parameters = json.loads(tool_parameters) if tool_parameters else []

    if not tool_parameters:
        print(f"[ToolFactory] 警告: 工具 '{tool_name}' 的 tool_parameters 为空，"
              f"LLM 传入的参数将被全部丢弃！请在管理端补充参数定义。")

    args_schema = create_pydantic_model_from_params(tool_name, tool_parameters)
    
    # 第二步：根据协议创建执行器
    if tool_protocol == "http":
        url_path = tool_card.get("url_path", "")
        method = tool_card.get("tool_method", "POST") or "POST"
        extra_headers = tool_card.get("tool_headers") or {}
        executor = create_http_executor(url_path, method=method, token=token, extra_headers=extra_headers)
    elif tool_protocol == "reference":
        # Reference 协议：本地引用，暂时返回模拟执行器
        reference_target = tool_card.get("reference_target", "")
        def executor(**kwargs) -> str:
            return json.dumps({
                "message": f"Reference tool '{tool_name}' called with target '{reference_target}'",
                "params": kwargs
            })
    else:
        # 未知协议
        def executor(**kwargs) -> str:
            return json.dumps({"error": f"未知的工具协议: {tool_protocol}"})
    
    # 第三步：构建 StructuredTool
    return StructuredTool.from_function(
        func=executor,
        name=tool_name,
        description=tool_description,
        args_schema=args_schema,
        return_direct=False  # 返回结果给 Agent 继续处理
    )


class ToolFactory:
    """
    功能: 工具工厂类，批量创建和管理动态工具
    参数: tool_cards - 工具卡片列表
    返回: ToolFactory 实例
    """
    
    def __init__(self, tool_cards: list[dict[str, Any]]):
        """
        功能: 初始化工具工厂
        参数: tool_cards - 从数据库读取的工具卡片列表
        返回: None
        """
        self._tool_cards = tool_cards
        self._tools: dict[str, StructuredTool] = {}
        self._build_tools()
    
    def _build_tools(self):
        """
        功能: 构建所有工具
        参数: 无
        返回: None
        """
        for card in self._tool_cards:
            try:
                tool = create_dynamic_tool(card)
                self._tools[card["tool_name"]] = tool
            except Exception as e:
                # 记录错误但继续处理其他工具
                print(f"[ToolFactory] 创建工具 '{card.get('tool_name')}' 失败: {e}")
    
    def get_tool(self, tool_name: str) -> StructuredTool | None:
        """
        功能: 根据名称获取工具
        参数: tool_name - 工具唯一标识
        返回: StructuredTool 实例，如果不存在则返回 None
        """
        return self._tools.get(tool_name)
    
    def get_tools_by_names(self, tool_names: list[str]) -> list[StructuredTool]:
        """
        功能: 根据名称列表获取多个工具
        参数: tool_names - 工具名称列表
        返回: StructuredTool 列表
        """
        return [
            self._tools[name]
            for name in tool_names
            if name in self._tools
        ]
    
    def get_all_tools(self) -> list[StructuredTool]:
        """
        功能: 获取所有工具
        参数: 无
        返回: 所有 StructuredTool 的列表
        """
        return list(self._tools.values())
    
    def get_public_tools(self) -> list[StructuredTool]:
        """
        功能: 获取所有公开工具（privileges = 'public'）
        参数: 无
        返回: 公开工具列表
        """
        public_names = [
            card["tool_name"]
            for card in self._tool_cards
            if card.get("tool_privileges", "public") == "public"
        ]
        return self.get_tools_by_names(public_names)
    
    def get_tool_names(self) -> list[str]:
        """
        功能: 获取所有工具名称
        参数: 无
        返回: 工具名称列表
        """
        return list(self._tools.keys())
