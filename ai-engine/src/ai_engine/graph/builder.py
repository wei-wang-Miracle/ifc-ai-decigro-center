"""StateGraph 构建器模块。

负责构建完整的 LangGraph 工作流（StateGraph），将各业务节点（Node）
按照 DAG 拓扑组装，并注入 PostgreSQL checkpointer 实现对话状态持久化。

本模块仅提供异步入口 ``create_workflow_graph_async``，供 FastAPI lifespan 调用。

工作流节点拓扑::

    intent_recognition → dispatcher → planner → executor → review
                                   ↘ normal     ↘ feedback   ↘ responder

Typical usage::

    graph = await create_workflow_graph_async(pool)
    result = await graph.ainvoke(state, config)
"""

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import StateGraph
from langgraph.store.postgres.aio import AsyncPostgresStore

from ..config import get_settings
from ..context import get_long_term_memory_manager
from .nodes import (
    dispatcher_node,
    feedback_handler_node,
    human_review_node,
    intent_recognition_node,
    normal_node,
    plan_task_execute_node,
    planner_node,
    responder_node,
)
from .state import AgentState
from .subgraphs.client_group.graph import build_client_group_subgraph
from .subgraphs.registry import register_subgraph


def _build_graph(checkpointer) -> object:
    """构建并编译 StateGraph，注入指定的 checkpointer。

    将所有业务节点注册到 StateGraph 中，设置入口节点为 intent_recognition，
    最终编译为可执行的 CompiledGraph。

    Note:
        节点之间的条件边（conditional edges）由各节点内部通过返回的
        ``Command(goto=...)`` 控制跳转，因此此处只需注册节点，无需显式 add_edge。

    Args:
        checkpointer: LangGraph 检查点持久化后端，用于保存每一步的对话状态，
            支持断点恢复和 human-in-the-loop 场景。

    Returns:
        CompiledGraph: 编译后的状态图，可直接调用 ``ainvoke`` / ``astream`` 执行。
    """
    # --- 编译并注册子图 ---
    client_group_sg = build_client_group_subgraph()
    register_subgraph("ai_client_group_creater", client_group_sg.compile())

    workflow = StateGraph(AgentState)

    # --- 注册业务节点 ---
    workflow.add_node("intent_recognition", intent_recognition_node)  # 意图识别
    workflow.add_node("dispatcher", dispatcher_node)  # 路由分发
    workflow.add_node("planner", planner_node)  # 任务规划
    workflow.add_node("executor", plan_task_execute_node)  # 计划执行
    workflow.add_node("review", human_review_node)  # 人工审核
    workflow.add_node("feedback", feedback_handler_node)  # 反馈处理
    workflow.add_node("responder", responder_node)  # 最终响应
    workflow.add_node("normal", normal_node)  # 普通对话

    # 入口节点：所有请求从意图识别开始
    workflow.set_entry_point("intent_recognition")

    return workflow.compile(checkpointer=checkpointer)


async def create_workflow_graph_async(pool) -> object:
    """创建异步工作流图（生产环境入口）。

    在 FastAPI lifespan 中调用，完成以下初始化：

    1. 使用 ``from_conn_string`` 建立 autocommit 单连接，执行 DDL 迁移（setup）。
    2. 切换为连接池模式，构建运行时 checkpointer 和 store。
    3. 将 AsyncPostgresStore 注入长期记忆管理器全局单例。
    4. 编译并返回 StateGraph。

    Args:
        pool: 已初始化的 ``AsyncConnectionPool``（psycopg 连接池），
            由调用方负责生命周期管理。

    Returns:
        CompiledGraph: 编译后的状态图，内含 PostgreSQL checkpointer，
            支持异步调用 ``ainvoke`` / ``astream``。
    """
    settings = get_settings()

    # ---- 第一步：DDL 迁移 ----
    # setup() 内含 CREATE INDEX CONCURRENTLY，必须在 autocommit 模式下执行，
    # 因此通过 from_conn_string 建立独立的短生命周期连接来完成迁移
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
        await saver.setup()

    async with AsyncPostgresStore.from_conn_string(settings.database_url) as store:
        await store.setup()

    # ---- 第二步：构建运行时实例（连接池模式，高并发复用） ----
    checkpointer = AsyncPostgresSaver(pool)
    store = AsyncPostgresStore(pool)

    # ---- 第三步：注入长期记忆 Store 到全局单例 ----
    get_long_term_memory_manager().set_store(store)

    return _build_graph(checkpointer)
