"""
审计数据采集器
功能: 从 AgentState 中提取审计数据，异步提交到 bus-kernel
设计原则: 完全独立于核心 graph 模块，不影响主线流程
"""

import threading
import time
from typing import Optional

import httpx

from ..config import get_settings


def submit_trace(state, ai_response: str, node_traces: list = None) -> None:
    """
    功能: 异步提交审计数据到 bus-kernel（不阻塞主线程）
    参数:
        state - AgentState 实例，包含完整的工作流状态
        ai_response - AI 最终的回复文本
        node_traces - 图节点追踪记录列表（由 responder_node 传入完整列表）
    返回: 无（后台线程执行）
    """
    # 在后台线程中执行，避免阻塞 responder_node 的返回
    thread = threading.Thread(
        target=_do_submit,
        args=(state, ai_response, node_traces),
        daemon=True,  # 守护线程，主线程退出时自动结束
    )
    thread.start()


def _do_submit(state, ai_response: str, node_traces: list = None) -> None:
    """
    功能: 实际执行审计数据采集和提交的内部函数
    参数:
        state - AgentState 实例
        ai_response - AI 最终回复
        node_traces - 图节点追踪记录列表
    返回: 无
    """
    try:
        # 第一步：构建 PG 宽表数据
        trace_index = _build_trace_index(state, ai_response, node_traces)

        # 第二步：构建 ES 快照数据（新的 graph_nodes 结构）
        es_snapshot = _build_es_snapshot(state, ai_response, node_traces)

        # 第三步：通过 HTTP POST 调用 bus-kernel 的 /trace/save 接口
        settings = get_settings()
        url = f"{settings.bus_kernel_base_url}/trace/save"

        # 构建请求体：camelCase 格式（匹配 Java 后端 Jackson 反序列化）
        payload = {
            "traceIndex": trace_index,
            "esSnapshot": es_snapshot,
        }

        # 使用独立的 httpx 客户端，避免与全局客户端冲突
        with httpx.Client(timeout=10.0) as client:
            # 携带 Token 以通过后端权限校验
            headers = {}
            if state.token:
                headers["X-Auth-Token"] = state.token

            response = client.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                print(f"[Audit] 审计数据提交成功: trace_id={state.trace_id}")
            else:
                print(f"[Audit] 审计数据提交失败: status={response.status_code}, body={response.text}")

    except Exception as e:
        # 审计失败绝不影响主流程，仅打日志
        print(f"[Audit] 审计数据提交异常: {e}")


def _build_trace_index(state, ai_response: str, node_traces: list = None) -> dict:
    """
    功能: 从 AgentState 构建 PG 宽表数据字典
    参数:
        state - AgentState 实例
        ai_response - AI 最终回复
        node_traces - 图节点追踪列表（用于计算总耗时）
    返回: dict（字段名为 camelCase，匹配 Java Entity）
    """
    # 收集所有使用过的工具名称
    tools_used = []
    for sr in (state.step_results or []):
        tools_used.extend(sr.tools_called or [])
    # 去重保序
    tools_used = list(dict.fromkeys(tools_used))

    # 构建执行路径（从 node_traces 中提取节点名序列）
    execution_path = []
    if node_traces:
        execution_path = [nt.get("node_name", "") for nt in node_traces if nt.get("node_name")]
    elif state.current_executor:
        execution_path.append(state.current_executor)

    # 判断最终状态
    if state.error:
        status = "FAILED"
        failure_reason = str(state.error)[:255]
    elif state.task_completed:
        status = "SUCCESS"
        failure_reason = None
    else:
        status = "SUCCESS"  # responder_node 正常结束视为成功
        failure_reason = None

    # 从意图识别结果中获取意图类型
    user_intent = ""
    if state.intent:
        user_intent = state.intent.intent_type.value if state.intent.intent_type else ""

    # 计算总耗时（从第一个节点开始到最后一个节点结束）
    trace_latency_ms = None
    if node_traces and len(node_traces) >= 2:
        total_ms = sum(nt.get("latency_ms", 0) or 0 for nt in node_traces)
        trace_latency_ms = total_ms

    return {
        "traceId": state.trace_id,
        "sessionId": state.session_id,
        "taskId": state.task_id,
        "userId": state.user_id,
        # 以下字段当前 AgentState 中未包含，留空
        "deptId": None,
        "tenantCode": None,
        # 智能体画像
        "agentName": state.current_executor or state.current_planner or "",
        "agentVersion": None,
        "modelProvider": get_settings().llm_model,
        "userFeedback": 0,
        # 摘要与透视
        "userIntent": user_intent,
        "userTraceQuery": (state.query or "")[:500],
        "aiTraceResponse": (ai_response or "")[:500],
        "executionPath": execution_path,
        "toolsUsed": tools_used,
        # 状态
        "status": status,
        "failureReason": failure_reason,
        # 效能指标
        "traceLatencyMs": trace_latency_ms,
        "traceTotalTokens": None,
        "traceInputTokens": None,
        "traceOutputTokens": None,
    }


def _build_es_snapshot(state, ai_response: str, node_traces: list = None) -> dict:
    """
    功能: 构建 ES 完整快照文档（新的 graph_nodes 结构）
    参数:
        state - AgentState 实例
        ai_response - AI 最终回复
        node_traces - 图节点追踪记录列表
    返回: dict（ES 文档结构）

    新结构层次:
      trace_id / session_id / task_id / user_id / start_time
      └── graph_nodes[] (nested)
          ├── node_name / start_time / end_time / latency_ms / status
          └── agent_snapshots[] (nested)
              ├── agent_name / model_config / system_prompt / status
              └── tools_snapshot[] (nested)
    """
    from datetime import datetime, timezone

    # 确定起始时间：取第一个节点的 start_time，或当前时间
    start_time = datetime.now(timezone.utc).isoformat()
    if node_traces and node_traces[0].get("start_time"):
        start_time = node_traces[0]["start_time"]

    # 构建 graph_nodes 数据
    graph_nodes = []
    if node_traces:
        for nt in node_traces:
            # 构建节点快照（清理内部字段）
            node_data = {
                "node_name": nt.get("node_name", ""),
                "start_time": nt.get("start_time"),
                "end_time": nt.get("end_time"),
                "latency_ms": nt.get("latency_ms"),
                "status": nt.get("status", "UNKNOWN"),
                "node_result": nt.get("node_result"),
                "agent_snapshots": nt.get("agent_snapshots", []),
            }
            graph_nodes.append(node_data)

    # 对话摘要（内嵌到顶层，方便搜索）
    dialogue_summary = {
        "user_query": state.query or "",
        "ai_response": ai_response or "",
        "history_length": len(state.messages or []),
    }

    return {
        "trace_id": state.trace_id,
        "session_id": state.session_id,
        "task_id": state.task_id,
        "user_id": state.user_id,
        "dept_id": None,
        "start_time": start_time,
        "dialogue_summary": dialogue_summary,
        "graph_nodes": graph_nodes,
    }
