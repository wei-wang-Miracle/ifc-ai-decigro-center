"""
StateGraph 构建器
构建完整的 LangGraph 工作流
"""

from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import (
    intent_recognition_node,
    dispatcher_node,
    planner_node,
    plan_task_execute_node,
    human_review_node,
    feedback_handler_node,
    responder_node,
    normal_node,
)


def _build_workflow(checkpointer) -> object:
    """内部：构建并编译 StateGraph，注入指定 checkpointer"""
    workflow = StateGraph(AgentState)

    workflow.add_node("intent_recognition", intent_recognition_node)
    workflow.add_node("dispatcher", dispatcher_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", plan_task_execute_node)
    workflow.add_node("review", human_review_node)
    workflow.add_node("feedback", feedback_handler_node)
    workflow.add_node("responder", responder_node)
    workflow.add_node("normal", normal_node)

    workflow.set_entry_point("intent_recognition")

    return workflow.compile(checkpointer=checkpointer)


def create_workflow_graph(checkpointer=None):
    """
    同步入口（兼容测试与非持久化场景）。
    checkpointer 为 None 时使用 MemorySaver（进程内存，重启即失）。
    """
    return _build_workflow(checkpointer or MemorySaver())


async def create_workflow_graph_async(pool) -> object:
    """
    异步入口（生产场景）：使用 AsyncPostgresSaver 持久化短期记忆。
    在 lifespan 中调用，pool 为已初始化的 AsyncConnectionPool。

    同时初始化长期记忆 Store（AsyncPostgresStore），注入全局单例。
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.store.postgres.aio import AsyncPostgresStore
    from ..context import get_long_term_memory_manager
    from ..config import get_settings

    settings = get_settings()

    # setup() 内含 CREATE INDEX CONCURRENTLY，必须通过 from_conn_string
    # （内部使用 autocommit=True 的单连接）执行迁移，不能在事务块中运行
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as tmp:
        await tmp.setup()

    async with AsyncPostgresStore.from_conn_string(settings.database_url) as tmp_store:
        await tmp_store.setup()

    # 运行时 checkpointer / store 使用连接池（高并发复用）
    checkpointer = AsyncPostgresSaver(pool)
    store = AsyncPostgresStore(pool)

    # 将 Store 注入长期记忆管理器单例
    ltm = get_long_term_memory_manager()
    ltm.set_store(store)

    return _build_workflow(checkpointer)


# 全局工作流实例（开发/测试场景使用）
_workflow = None


def get_workflow():
    """获取全局工作流实例（MemorySaver，仅用于开发/测试）"""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow_graph()
    return _workflow
