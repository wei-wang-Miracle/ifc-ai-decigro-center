"""
审计模块初始化
功能: 提供异步审计数据提交入口

使用方式:
    from ai_engine.audit import submit_trace
    submit_trace(state, ai_response)  # 异步提交，不阻塞主线程
"""

from .collector import submit_trace

__all__ = ["submit_trace"]
