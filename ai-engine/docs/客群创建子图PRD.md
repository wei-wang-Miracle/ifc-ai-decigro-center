# 智能客群创建子图 PRD（基于代码实现反向维护）

> **文档性质**：本文档由代码实现反向生成，忠实反映 `ai-engine/src/ai_engine/graph/subgraphs/client_group/` 的实际行为。
>
> **最后同步版本**：commit `d449692`（subgraph-0403 分支）

---

## 1. 概述

### 1.1 子图定位

**智能客群创建子图**（注册名 `ai_client_group_creater`）是主图 Executor 节点的一个可插拔子流程，
负责将用户自然语言需求转化为系统可识别的客群条件，并在人工确认后落地创建客群实体。

核心价值：
- **流程强制**：查标签 → 学结构 → 构建条件 → 预览人数 → 用户确认 → 创建 → 验证，步步不可跳过
- **人机回环**：通过 `phase` 标记暂停，由主图 `human_review_node` 统一处理确认/驳回
- **条件一致性**：创建时复用预览阶段的参数快照，确保"所见即所得"

### 1.2 职能边界

| 维度 | 子图职责（IN） | 子图不管（OUT） |
|------|---------------|----------------|
| **需求解析** | 将自然语言映射为 groupConditions 结构 | 不负责意图识别（由 Planner 判定是否需要创建客群） |
| **标签字典** | 调用 `query_all_labels` 获取并缓存 | 不维护标签元数据，不做标签 CRUD |
| **条件构建** | LLM ReAct 循环：学习示例 → 构建 → 预览验证 → 自修复 | 不硬编码任何字段名/枚举值，完全依赖标签字典 |
| **预览验证** | 调用 `preview_client_group_count` 获取匹配人数 | 不判断人数是否"合理"（由 LLM 自主决策） |
| **人工确认** | 产出 `phase=pending_confirm` 信号 + 预览摘要 | 不实现 interrupt()，不直接与前端交互 |
| **驳回重构** | 接收 `review_feedback`，在已有标签缓存上重新构建 | 不处理"需要整体重新规划"的场景（由主图 feedback 节点分流） |
| **创建执行** | 确定性调用 `create_client_group` | 不生成客群名称/备注（来自上游参数或 LLM 产出） |
| **创建验证** | 调用 `get_client_group_detail` 二次确认 | 不做创建失败后的自动重试 |
| **状态持久化** | 通过 `subgraph_resume_meta` 在两次调用间传递中间状态 | 不自带 checkpointer，由主图 PostgreSQL checkpoint 统一管理 |
| **工具管理** | 通过 `ToolRegistry` 动态获取工具实例 | 不定义工具 schema，工具定义来自 bus-kernel ToolCard |

### 1.3 触发条件

Planner 在生成 PlanStep 时，将 `assigned_agent` 设为 `"ai_client_group_creater"` 即触发子图。
Planner 需预先知晓子图描述信息：

> **智能客群生成专家**专用于将业务需求转化为系统规则，并实际落地创建目标客群。
> 严格遵循"查询标签字典 → 预览客群规模 → 正式创建客群"的强制工作流，确保规则 100% 合法。
> 当用户需要根据标签、条件圈选并最终生成一个真实客群实体时，必须调用此专家。

---

## 2. 工具清单

子图依赖 5 个 ToolCard 工具，全部通过 `ToolRegistry` 动态获取，按调用方式分两类：

### 2.1 确定性调用（无 LLM 参与）

| 工具名称 | 调用节点 | 调用方式 | 输入 | 输出 |
|---------|---------|---------|------|------|
| `query_all_labels` | `query_labels_node` | `_invoke_tool()` 同步 | 无参数 | `{code:200, info: [标签列表]}` |
| `create_client_group` | `create_and_verify_node` | `_invoke_tool()` 同步 | `create_payload`（来自预览快照） | `{code:200, info: clientGroupId}` |
| `get_client_group_detail` | `create_and_verify_node` | `_invoke_tool()` 同步 | `clientGroupId` | `{code:200, info: 客群详情}` |

### 2.2 LLM 绑定调用（ReAct 工具循环）

| 工具名称 | 调用节点 | 调用方式 | 用途 |
|---------|---------|---------|------|
| `get_example_client_group` | `build_group_node` | `llm.bind_tools()` → LLM 自主决策 | LLM 学习标准客群结构 |
| `preview_client_group_count` | `build_group_node` | `llm.bind_tools()` → LLM 自主决策 | 预览匹配人数、验证条件合法性 |

---

## 3. 子图拓扑

### 3.1 节点与边

```
[entry_router]
    │
    ├─ 首次执行（phase="" & 无 feedback）──→ query_labels → build_group → [END]
    │                                                         ↑ phase=pending_confirm
    │
    ├─ 驳回重构（有 feedback & 有 labels_cache）──→ build_group → [END]
    │                                                  ↑ phase=pending_confirm
    │
    └─ 确认恢复（phase="resume_after_confirm"）──→ create_and_verify → [END]
```

### 3.2 入口路由逻辑（`route_entry`）

```python
if phase == "resume_after_confirm":
    return "create_and_verify"          # 用户已确认，直接创建
elif review_feedback and labels_cache:
    return "build_group"                # 驳回重构，跳过标签查询
else:
    return "query_labels"               # 首次执行，从头开始
```

### 3.3 节点职责

| 节点 | 类型 | 职责 | 输出到 State |
|------|------|------|-------------|
| `query_labels_node` | 确定性 | 调用 `query_all_labels`，缓存标签列表 JSON | `labels_cache` |
| `build_group_node` | ReAct（异步） | LLM 学习示例 → 构建条件 → 预览验证 → 自修复循环 | `create_payload`, `preview_result`, `phase`, `output` |
| `create_and_verify_node` | 确定性 | 调用 `create_client_group` → `get_client_group_detail` 二步验证 | `output`, `success` |

---

## 4. 核心流程详解

### 4.1 首次执行（Happy Path）

```
用户："帮我创建一个30岁以上、资产50万以上的高净值客群"
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│  query_labels_node                                  │
│  · _invoke_tool("query_all_labels", token)          │
│  · 解析返回 JSON，写入 labels_cache                  │
└──────────────────────┬──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│  build_group_node（ReAct 循环，最多 4 轮）            │
│                                                     │
│  Prompt 注入：                                       │
│  · {labels} ← labels_cache（截断 8000 字符）         │
│  · {query} ← 用户原始需求                            │
│  · {prior_context} ← 上游步骤产出（可选）             │
│  · {feedback_context} ← 用户修改意见（首次为空）      │
│                                                     │
│  LLM 决策循环：                                      │
│  ┌──────────────────────────────────────────┐       │
│  │ 第1轮: LLM → 调用 get_example_client_group │      │
│  │ 第2轮: LLM → 构建条件 → 调用 preview       │      │
│  │ 第3轮: (如 preview 报错) LLM → 修正 → 再 preview │ │
│  │ 第N轮: LLM 不再调用工具 → 输出结论          │      │
│  └──────────────────────────────────────────┘       │
│                                                     │
│  后处理：                                            │
│  · 从 messages 反向提取最后一次成功 preview 的参数    │
│  · 作为 create_payload 存入 State                    │
│  · 设置 phase = "pending_confirm"                    │
└──────────────────────┬──────────────────────────────┘
                       ▼
                   [子图 END]
                       │
          主图接管：phase=pending_confirm
                       │
                       ▼
              human_review_node
              (interrupt 暂停等待用户)
```

### 4.2 用户确认后恢复

```
用户确认："没问题，创建吧"
                    │
          主图恢复：phase="resume_after_confirm"
          subgraph_resume_meta 注入 create_payload + labels_cache
                    │
                    ▼
          route_entry → "create_and_verify"
                    │
                    ▼
┌─────────────────────────────────────────────────────┐
│  create_and_verify_node                             │
│                                                     │
│  步骤 1: create_client_group                        │
│  · 解析 create_payload JSON                         │
│  · _invoke_tool("create_client_group", token, **payload) │
│  · 校验返回 code=200，提取 clientGroupId             │
│                                                     │
│  步骤 2: get_client_group_detail                    │
│  · _invoke_tool("get_client_group_detail", token,   │
│                  clientGroupId=clientGroupId)        │
│  · 校验返回 code=200                                │
│                                                     │
│  输出: "客群创建成功，已确认。clientGroupId=xxx"      │
└─────────────────────────────────────────────────────┘
```

### 4.3 用户驳回重构

```
用户："年龄改成25岁以上，另外加一个性别女的条件"
                    │
          主图 feedback 节点分流：步骤级调整
          review_feedback = "年龄改成25岁以上..."
          labels_cache 从 resume_meta 恢复
                    │
                    ▼
          route_entry → "build_group"（跳过 query_labels）
                    │
                    ▼
          build_group_node 重新执行 ReAct 循环
          Prompt 额外注入 {feedback_context}
                    │
                    ▼
          再次产出 phase=pending_confirm → 等待确认
```

---

## 5. State 定义

```
ClientGroupState (Pydantic BaseModel)
├── 输入层（主图 → 子图，只读）
│   ├── query: str              # 用户原始需求
│   ├── token: str              # 用户身份 Token
│   ├── prior_step_outputs: str # 前序步骤产出（跨步骤上下文）
│   ├── phase: str              # 执行阶段："" | "resume_after_confirm"
│   └── review_feedback: str    # 用户驳回修改意见
│
├── 工作层（子图内部读写）
│   ├── labels_cache: str       # query_all_labels 返回的标签 JSON
│   ├── create_payload: str     # 可直接用于 create 的参数 JSON（预览快照）
│   ├── preview_result: str     # 最后一次 preview 返回结果
│   └── error: str              # 执行错误信息
│
└── 输出层（子图 → 主图）
    ├── output: str             # 最终输出文本
    └── success: bool           # 执行是否成功
```

**条件一致性保证**：`create_payload` 来自 `_extract_last_preview_args(messages)`，
即从 ReAct 对话历史中提取最后一次成功的 `preview_client_group_count` 调用参数。
创建时直接 `**payload` 展开，确保预览与创建使用完全相同的条件。

---

## 6. 与主图的集成契约

### 6.1 生命周期

```
builder.py _build_graph()
    │
    ├─ build_client_group_subgraph()   # 返回未编译 StateGraph
    ├─ .compile()                       # 无 checkpointer
    └─ register_subgraph("ai_client_group_creater", compiled)
                                        # 写入全局 _SUBGRAPH_REGISTRY
```

### 6.2 调用方式

主图 `plan_task_execute_node` 中：
- `is_subgraph_executor("ai_client_group_creater")` → True → 走子图路径
- `get_subgraph(name).ainvoke(sub_input)` → 异步调用，子图作为普通函数在节点内执行

### 6.3 两次调用间的状态桥接

| 时机 | 机制 | 传递内容 |
|------|------|---------|
| 第 1 次调用结束 | Executor 将子图非通用字段存入 `AgentState.subgraph_resume_meta` | `create_payload`, `labels_cache`, `preview_result` 等 |
| 第 2 次调用开始 | Executor 从 `resume_meta` 恢复字段注入 `sub_input` | 同上 + `phase="resume_after_confirm"` |

### 6.4 主图路由协议

| 子图输出 | 主图行为 |
|---------|---------|
| `phase="pending_confirm"` | Executor 设置 `require_review=True` → Dispatcher → `human_review_node`（interrupt） |
| `success=True` | Executor 记录 StepResult → 推进 `current_step_index` |
| `success=False` / `error` 非空 | Executor 记录失败 StepResult → 由 Dispatcher 决定是否重试或终止 |

---

## 7. ReAct 工具循环设计

### 7.1 循环参数

| 参数 | 值 | 说明 |
|------|---|------|
| `_MAX_TOOL_ITERATIONS` | 4 | 断路器上限。正常路径：get_example → preview → (修正) → 结束 |
| LLM | `create_creative_llm()` | 创意型 LLM，用于条件构建 |
| 绑定工具 | `get_example_client_group`, `preview_client_group_count` | 仅 2 个工具，职责收敛 |

### 7.2 循环终止条件

1. **LLM 主动结束**：返回的 AIMessage 不含 `tool_calls` → 提取 `content` 作为 `final_output`
2. **轮次耗尽**：注入收尾指令 → 强制 LLM 基于已有结果给出结论（不再允许调用工具）

### 7.3 预览参数提取

`_extract_last_preview_args(messages)` 逻辑：
1. 正向遍历收集所有 ToolMessage，按 `tool_call_id` 索引
2. 反向遍历找最后一个 `preview_client_group_count` 调用
3. 跳过对应 ToolMessage 含"错误"或 `"error"` 的调用
4. 返回该调用的 `args` dict → 直接作为 `create_payload`

---

## 8. 错误处理

### 8.1 错误分层

| 层级 | 场景 | 处理方式 | 是否阻断 |
|------|------|---------|---------|
| **工具层** | `_invoke_tool` 调用异常 | 捕获异常，返回 JSON 格式错误信息 | 否，由上层判断 |
| **节点层 - query_labels** | API 返回非 200 / info 为空 | 设置 `error` + `success=False`，后续节点短路 | 是 |
| **节点层 - build_group** | labels_cache 为空 / 工具不可用 / LLM 未调用 preview / 无法提取参数 | 设置 `error` + `success=False` | 是 |
| **节点层 - create_and_verify** | payload 解析失败 / create 非 200 / verify 非 200 | 设置 `error` + `success=False`，含具体错误原因 | 是 |
| **ReAct 循环** | 工具调用失败 | ToolMessage 注入错误内容 → LLM 通过自然语言反馈自修复 | 否 |
| **ReAct 循环** | 轮次耗尽 | 注入收尾指令，强制 LLM 产出结论 | 否 |

### 8.2 短路机制

`build_group_node` 和 `create_and_verify_node` 入口均检查 `state.error`：
```python
if state.error:
    return {}  # 或返回失败结果
```
上游节点产生的错误会阻止下游节点执行。

---

## 9. 与旧版 PRD 的差异说明

| 维度 | 旧版 PRD 描述 | 实际实现 |
|------|-------------|---------|
| **验证工具** | `list_my_client_groups`（列表查询） | `get_client_group_detail`（精确查询，传入 clientGroupId） |
| **人机回环** | 子图内部 interrupt | 子图产出 `phase` 信号 → 主图 `human_review_node` 统一 interrupt |
| **Ralph 循环** | 子图内含 Predict-Act-Feedback-Adjust 四阶段循环 | ReAct 工具循环在 `build_group_node` 单节点内完成，无独立 Feedback/Adjust 节点 |
| **条件构建** | 多节点分步（fetch_examples → learn_structure → build_conditions） | 单节点 `build_group_node` 内 LLM 自主决定调用顺序 |
| **标签缓存** | 作为是否跳过的条件分支 | 作为入口路由判断依据 + 驳回重构时复用 |
| **数据流** | State 含 `examples_cache`, `group_conditions`, `preview_conditions` 等多字段 | State 精简为 `labels_cache` + `create_payload`，无独立 examples/conditions 字段 |
| **错误重试** | verify 失败重试 3 次 | 无重试，verify 失败直接返回 `success=False` |
| **子图架构** | 描述为 Mermaid 流程图中含多个条件分支节点 | 3 节点 DAG + 条件入口路由，拓扑简洁 |

---

## 附录 A: 文件清单

| 文件 | 职责 |
|------|------|
| `subgraphs/client_group/__init__.py` | 包声明 |
| `subgraphs/client_group/state.py` | `ClientGroupState` 定义 |
| `subgraphs/client_group/graph.py` | `build_client_group_subgraph()` — 构建 StateGraph 拓扑 |
| `subgraphs/client_group/nodes.py` | 3 个节点函数 + 入口路由 + 工具辅助 + ReAct 循环 + Prompt 模板 |
| `subgraphs/registry.py` | 全局子图注册表 |
| `graph/builder.py` | 编译子图并注册 |
| `graph/nodes/plan_task_execute_node.py` | Executor 子图调用 + resume_meta 桥接 |
| `graph/nodes/human_review_node.py` | 人工确认 interrupt |
