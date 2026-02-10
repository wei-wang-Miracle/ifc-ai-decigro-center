"""
审计追踪工具函数
功能: 为图节点提供轻量级埋点工具，每个节点仅需 2~3 行代码即可完成追踪记录
设计原则: 零侵入、极简 API、线程安全
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional


def start_node_trace(node_name: str) -> dict:
    """
    功能: 创建一个节点追踪记录的起始骨架
    参数:
        node_name - 图节点名称（如 "intent_recognition", "executor"）
    返回: dict 追踪记录骨架，后续通过 finish_node_trace 补充完整
    """
    return {
        "node_name": node_name,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "end_time": None,
        "latency_ms": None,
        "status": "IN_PROGRESS",
        # 每个节点可以有多个 agent 快照（绝大多数节点只有 1 个）
        "agent_snapshots": [],
        # 计时器（内部使用，不会被序列化到 ES）
        "_start_ts": time.time(),
    }


def finish_node_trace(
    trace: dict,
    status: str = "SUCCESS",
    agent_snapshot: Optional[dict] = None,
) -> dict:
    """
    功能: 完成节点追踪记录（填充结束时间、耗时、状态）
    参数:
        trace - start_node_trace 返回的追踪记录
        status - 节点执行状态: SUCCESS / FAILED / SKIPPED
        agent_snapshot - 可选的 Agent 快照数据
    返回: 完整的追踪记录 dict
    """
    end_ts = time.time()
    trace["end_time"] = datetime.now(timezone.utc).isoformat()
    trace["latency_ms"] = int((end_ts - trace["_start_ts"]) * 1000)
    trace["status"] = status

    # 添加 Agent 快照
    if agent_snapshot:
        trace["agent_snapshots"].append(agent_snapshot)

    # 清理内部计时字段（不进入 ES）
    trace.pop("_start_ts", None)

    return trace


def build_agent_snapshot(
    agent_name: str = "",
    agent_version: str = None,
    model_config: dict = None,
    system_prompt: str = None,
    tools_snapshot: list = None,
) -> dict:
    """
    功能: 构建 Agent 快照结构
    参数:
        agent_name - Agent 名称
        agent_version - Agent 版本
        model_config - 模型配置（provider, model_name, temperature 等）
        system_prompt - 系统提示词
        tools_snapshot - 工具调用快照列表
    返回: Agent 快照 dict
    """
    return {
        "agent_name": agent_name,
        "agent_version": agent_version,
        "model_config": model_config,
        "system_prompt": system_prompt,
        "status": "COMPLETED",
        "tools_snapshot": tools_snapshot or [],
    }


def build_tool_snapshot(
    tool_name: str,
    tool_type: str = "HTTP",
    input_args: Any = None,
    output_result: str = None,
    latency_ms: int = None,
    status: str = "SUCCESS",
    error_message: str = None,
    start_time: str = None,
) -> dict:
    """
    功能: 构建单次工具调用快照
    参数:
        tool_name - 工具名称
        tool_type - 工具类型（HTTP / REFERENCE）
        input_args - 工具入参
        output_result - 工具出参（截断到 5000 字符）
        latency_ms - 耗时毫秒
        status - 执行状态: SUCCESS / FAILED
        error_message - 失败时错误信息
        start_time - 调用开始时间
    返回: 工具调用快照 dict
    """
    return {
        "tool_name": tool_name,
        "tool_type": tool_type,
        "start_time": start_time or datetime.now(timezone.utc).isoformat(),
        "latency_ms": latency_ms,
        "status": status,
        "input_args": _safe_serialize(input_args),
        "output_result": (str(output_result) or "")[:5000] if output_result else None,
        "error_message": error_message,
    }


def _safe_serialize(obj: Any) -> Any:
    """
    功能: 安全序列化对象（dict/list 直接返回，其他转字符串）
    参数: obj - 任意对象
    返回: 可 JSON 序列化的值
    """
    if obj is None:
        return None
    if isinstance(obj, (dict, list)):
        return obj
    try:
        return str(obj)[:2000]
    except Exception:
        return "<无法序列化>"
