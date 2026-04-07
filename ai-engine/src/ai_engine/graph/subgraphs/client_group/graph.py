"""客群创建子图构建与编译。

构建 ClientGroupState 驱动的 StateGraph，返回未编译的 StateGraph，
由主图 builder.py 统一编译并注册到子图注册表。

子图拓扑::

    [entry_router] ──首次──→ query_labels → build_group → [END]  (phase=pending_confirm)
                   ──重构──→ build_group → [END]  (phase=pending_confirm)
                   ──恢复──→ create_and_verify → [END]
"""

from langgraph.graph import END, StateGraph

from .nodes import (
    build_group_node,
    create_and_verify_node,
    query_labels_node,
    route_entry,
)
from .state import ClientGroupState


def build_client_group_subgraph() -> StateGraph:
    """构建客群创建子图(未编译)。

    返回未编译的 StateGraph，由调用方(builder.py)执行 compile()。
    子图不自带 checkpointer，作为普通函数在 Executor 节点内被 invoke。

    Returns:
        配置好节点和边的 StateGraph 实例。
    """
    sg = StateGraph(ClientGroupState)

    # ── 注册节点 ──────────────────────────────────────────
    sg.add_node("query_labels", query_labels_node)
    sg.add_node("build_group", build_group_node)
    sg.add_node("create_and_verify", create_and_verify_node)

    # ── 入口路由 ──────────────────────────────────────────
    # 根据 phase 及 feedback 判断是首次执行、重构还是确认后恢复
    sg.set_conditional_entry_point(route_entry)

    # ── 首次执行路径 ──────────────────────────────────────
    sg.add_edge("query_labels", "build_group")
    sg.add_edge("build_group", END)

    # ── 恢复执行路径 ──────────────────────────────────────
    sg.add_edge("create_and_verify", END)

    return sg
