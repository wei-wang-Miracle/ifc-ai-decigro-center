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


def submit_trace(state, ai_response: str) -> None:
    """
    功能: 异步提交审计数据到 bus-kernel（不阻塞主线程）
    参数:
        state - AgentState 实例，包含完整的工作流状态
        ai_response - AI 最终的回复文本
    返回: 无（后台线程执行）
    """
    # 在后台线程中执行，避免阻塞 responder_node 的返回
    thread = threading.Thread(
        target=_do_submit,
        args=(state, ai_response),
        daemon=True,  # 守护线程，主线程退出时自动结束
    )
    thread.start()


def _do_submit(state, ai_response: str) -> None:
    """
    功能: 实际执行审计数据采集和提交的内部函数
    参数:
        state - AgentState 实例
        ai_response - AI 最终回复
    返回: 无
    """
    try:
        # 第一步：计算总耗时（从创建到现在的毫秒数）
        start_ts = time.time()  # 简化处理：记录提交时间作为结束时间参考

        # 第二步：构建 PG 宽表数据
        trace_index = _build_trace_index(state, ai_response)

        # 第三步：构建 ES 快照数据
        es_snapshot = _build_es_snapshot(state, ai_response)

        # 第四步：通过 HTTP POST 调用 bus-kernel 的 /trace/save 接口
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


def _build_trace_index(state, ai_response: str) -> dict:
    """
    功能: 从 AgentState 构建 PG 宽表数据字典
    参数:
        state - AgentState 实例
        ai_response - AI 最终回复
    返回: dict（字段名为 camelCase，匹配 Java Entity）
    """
    # 收集所有使用过的工具名称
    tools_used = []
    for sr in (state.step_results or []):
        tools_used.extend(sr.tools_called or [])
    # 去重保序
    tools_used = list(dict.fromkeys(tools_used))

    # 构建执行路径（从 step_results 中提取）
    execution_path = []
    if state.selected_agent:
        execution_path.append(state.selected_agent)

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

    return {
        "traceId": state.trace_id,
        "sessionId": state.session_id,
        "taskId": state.task_id,
        "userId": state.user_id,
        # 以下字段当前 AgentState 中未包含，留空
        "deptId": None,
        "tenantCode": None,
        # 智能体画像
        "agentName": state.selected_agent or "",
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
        # 效能指标（Token 相关当前由 LLM 内部消耗，这里暂留空）
        "traceLatencyMs": None,
        "traceTotalTokens": None,
        "traceInputTokens": None,
        "traceOutputTokens": None,
    }


def _build_es_snapshot(state, ai_response: str) -> dict:
    """
    功能: 构建 ES 完整快照文档
    参数:
        state - AgentState 实例
        ai_response - AI 最终回复
    返回: dict（ES 文档结构）
    """
    from datetime import datetime, timezone

    settings = get_settings()

    # 构建历史窗口（从 messages 中提取）
    history_window = []
    for msg in (state.messages or []):
        history_window.append({
            "role": msg.type if hasattr(msg, 'type') else "unknown",
            "content": str(msg.content)[:2000] if msg.content else "",
        })

    # 构建工具执行快照
    tool_snapshots = []
    for sr in (state.step_results or []):
        for tool_name in (sr.tools_called or []):
            tool_snapshots.append({
                "tool_name": tool_name,
                "tool_type": "HTTP",  # 默认 HTTP 类型
                "start_time": None,
                "end_time": None,
                "latency_ms": None,
                "status": "SUCCESS" if sr.success else "FAILED",
                "input_args": None,
                "output_result": (sr.output or "")[:5000],
                "error_message": sr.error if not sr.success else None,
            })

    return {
        "trace_id": state.trace_id,
        "session_id": state.session_id,
        "task_id": state.task_id,
        "user_id": state.user_id,
        "dept_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "env_snapshot": {
            "agent_name": state.selected_agent or "",
            "agent_version": None,
            "model_config": {
                "provider": "openai",
                "model_name": settings.llm_model,
                "temperature": settings.llm_temperature,
                "top_p": 0.9,
                "max_tokens": 4096,
            },
            "system_prompt": None,  # 可后续从 Agent Card 中注入
        },

        "dialogue_snapshot": {
            "user_query_full": state.query or "",
            "history_window": history_window[-10:],  # 最近10条对话
            "ai_response_full": ai_response or "",
            "finish_reason": "stop",
            "total_tokens": None,
        },

        "tool_snapshots": tool_snapshots,
    }
