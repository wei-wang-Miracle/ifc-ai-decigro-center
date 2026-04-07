"""子图注册表。

维护 Executor 名称 → 编译后子图的映射，供 plan_task_execute_node 在运行时
判断某个 Executor 是否应走子图执行路径。

典型用法::

    from .registry import is_subgraph_executor, get_subgraph

    if is_subgraph_executor(executor_name):
        subgraph = get_subgraph(executor_name)
        result = await subgraph.ainvoke(sub_input)
"""

from typing import Any

# Executor 名称 → 编译后的 CompiledStateGraph
_SUBGRAPH_REGISTRY: dict[str, Any] = {}


def register_subgraph(name: str, compiled_graph: Any) -> None:
    """注册一个子图，绑定到指定的 Executor 名称。"""
    _SUBGRAPH_REGISTRY[name] = compiled_graph
    print(f"[SubgraphRegistry] 已注册子图: {name}")


def get_subgraph(name: str) -> Any | None:
    """根据 Executor 名称获取编译后的子图。"""
    return _SUBGRAPH_REGISTRY.get(name)


def is_subgraph_executor(name: str) -> bool:
    """判断指定 Executor 名称是否对应一个子图实现。"""
    return name in _SUBGRAPH_REGISTRY
