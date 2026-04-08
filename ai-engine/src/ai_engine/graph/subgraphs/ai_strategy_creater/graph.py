"""策略创建子图构建与编译。

构建 StrategyCreationState 驱动的 StateGraph，返回未编译的 StateGraph，
由主图 builder.py 统一编译并注册到子图注册表。

子图拓扑(对应 PRD 5 阶段)::

    [entry_router]
        ──首次/打回──→ preparation ──成功──→ decision → [END]  (phase=pending_confirm)
                                   ──失败──→ [END]            (success=False)
        ──确认恢复──→ construction → creation_and_verify → [END]

流程说明::

    Phase 1 (准备)   : preparation → 确定 purposeId + clientGroupId
    Phase 2 (决策)   : decision → 设计策略拓扑方案(组件、伪代码、设计意图)
    Phase 3 (人机回环): 子图通过 phase=pending_confirm 暂停返回主图，
                       由主图 review 链路展示 design_intent 并收集用户反馈
                       - 确认 → 主图以 phase=resume_after_confirm 重新 invoke
                       - 驳回 → 主图以 review_feedback 重新 invoke(走首次路径)
    Phase 4 (构建)   : construction → 基于 Schema 生成 canvas_payload + validate
    Phase 5 (创建验证): creation_and_verify → 确定性落库 + 硬断言校验
"""

from langgraph.graph import END, StateGraph

from .nodes import (
    construction_node,
    creation_and_verify_node,
    decision_node,
    preparation_node,
    route_after_preparation,
    route_entry,
)
from .state import StrategyCreationState


def build_strategy_creation_subgraph() -> StateGraph:
    """构建策略创建子图(未编译)。

    功能:
        返回未编译的 StateGraph，由调用方(builder.py)执行 compile()。
        子图不自带 checkpointer，作为普通函数在 Executor 节点内被 invoke。

    返回:
        配置好节点和边的 StateGraph 实例。
    """
    sg = StateGraph(StrategyCreationState)

    # ── 注册节点 ──────────────────────────────────────────
    sg.add_node("preparation", preparation_node)          # Phase 1: 准备阶段
    sg.add_node("decision", decision_node)                # Phase 2: 决策阶段
    sg.add_node("construction", construction_node)        # Phase 4: 构建阶段
    sg.add_node("creation_and_verify", creation_and_verify_node)  # Phase 5: 创建验证

    # ── 入口路由 ──────────────────────────────────────────
    # 根据 phase 及 feedback 判断是首次执行、驳回重来还是确认后恢复
    sg.set_conditional_entry_point(route_entry)

    # ── 首次/驳回执行路径(Phase 1 → 2 → END) ─────────────
    # 准备完成后检查是否成功，成功则流转到决策，失败则直接结束
    sg.add_conditional_edges("preparation", route_after_preparation)
    sg.add_edge("decision", END)

    # ── 恢复执行路径(Phase 4 → 5 → END) ──────────────────
    # 用户确认后从构建开始，构建完成后自动流转到创建验证
    sg.add_edge("construction", "creation_and_verify")
    sg.add_edge("creation_and_verify", END)

    return sg
