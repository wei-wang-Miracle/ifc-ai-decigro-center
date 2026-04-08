# 📌 AI 策略创建子图 (Strategy Creation Sub-graph) 实现 PRD

## 1. 背景与目标 (Background & Goals)

本子图旨在以自动化加“人机协作”的方式，协助业务人员零门槛通过对话创建**营销/触达策略 (Strategy Canvas)**。
子图采用 5 阶段工作流（**准备**、**决策**、**人机回环**、**构建**、**验证**），结合硬代码级状态校验，确保数据不仅能在大型语言模型处理中对齐意图，也能精确满足后端 OpenAPI JSON Schema 数据结构校验，最终 100% 成功落库。

---

## 2. 状态定义建议 (State Definition)

在图（Graph）的运转过程中，需要在上下文（State / Context）中持续传递并迭代以下关键信息：

```python
class StrategyCreationState(TypedDict):
    # --- 1. 准备阶段状态 ---
    purpose_id: Optional[int]          # 绑定的任务 ID
    client_group_id: Optional[int]     # 绑定的客群 ID

    # --- 2. 决策阶段状态 ---
    selected_assemblies: List[str]     # 评估后决定需要用的组件列表 (例如: ["START", "APP_PUSH", "END"])
    pseudo_code: str                   # 模型生成的策略伪代码
    design_intent: str                 # 易于向用户展示的设计意图说明

    # --- 3. 人机回环状态 ---
    user_feedback: Optional[str]       # 用户的反馈/批示内容
    is_approved: bool                  # 用户是否已确认 (True/False)

    # --- 4. 构建阶段状态 ---
    canvas_payload: dict               # 生成的、待提交的策略JSON结构 (包含 strategy 和 canvasNodes)
    is_validated: bool                 # 是否已通过 validate_strategy_canvas 参数合法性校验

    # --- 5. 创建验证状态 ---
    strategy_id: Optional[int]         # 成功落库后返回的策略流水 ID
    is_created_successfully: bool      # `code=200` 确认完成的最终状态
```

---

## 3. 阶段拆解与节点设计 (Phase Breakdown & Node Design)

整个子图包含如下 5 个串联和带条件循环（Conditional Edges）的核心节点。

### Phase 1: 准备阶段 (Preparation Node)

- **核心目标**: 确定策略画布初始化必备的两大源头参数 —— 任务(`purposeId`) 和 客群(`clientGroupId`)。
- **关联工具 (Tools)**:
  - `list_my_purposes` / `save_purpose`
  - `list_my_client_groups`
- **处理逻辑**:
  1. 调用 `list_my_purposes` 查询存在且符合意图的任务，若无，调用 `save_purpose` 等级联创建任务逻辑。
  2. 调用 `list_my_client_groups` 查询最匹配的客群，作为 START 节点的准入目标。
  3. 如果系统中无可用客群，当前节点必须**中断当前流并触发**（可发往消息队列、子状态机调度等调用形式）**客群创建的子图（Client Group Sub-graph）**，执行完毕回调拿到 ID 后再恢复本节点。

### Phase 2: 决策阶段 (Decision Node)

- **核心目标**: 基于确定好的前提，产出结构化的构建方案（伪代码）与可读性高的设计意图。
- **关联工具 (Tools)**:
  - `list_available_assemblies` (获取抽象的类型名片)
  - `get_showcase_strategy_canvas` (参考优秀线上实际场景配置设计)
- **处理逻辑**:
  1. 调用可用组件接口，了解平台支持的触达/分流/出口组件（包括其业务职能，并非 Schema）。
  2. 调用 Showcase 获取优秀的真实活动范例。
  3. AI 依靠此两项输入，推理出本次营销的最佳拓扑，并明确将写入 state 的 `selected_assemblies`、`pseudo_code` 及 `design_intent`。

### Phase 3: 人机回环阶段 (Human-In-The-Loop Node)

- **核心目标**: 使用断点机制（Breakpoint），向用户确认 Phase 2 产出的意图。
- **处理逻辑**:
  1. 暂停节点执行，前端向用户展示 `design_intent` 和 `pseudo_code`。
  2. 等待用户输入（Approve or Feedback）。
- **路由逻辑 (Routing)**:
  - **路径 A: 确认无误 (`is_approved=True`)** → 流转到 **4.构建阶段**。
  - **路径 B: 提出修改 (`is_approved=False` 有新 feedback)** → 在引入全新的要求或对客群任务微调后，**流转回 1.准备阶段**，重新确认任务与客群条件，覆盖评估。

### Phase 4: 构建阶段 (Construction Node)

- **核心目标**: 将高层伪代码意图转化为满足严格树级 JSON 原理的可执行 `canvasNodes` 结构。
- **关联工具 (Tools)**:
  - `get_assembly_schemas` (基于 `selected_assemblies` 获取精细的 JSON 约束)
  - `get_example_strategy_canvas` (获取包含严谨节点父子嵌套指向逻辑的 Dummy Context)
  - `validate_strategy_canvas` (进行服务器级校验)
- **处理逻辑**:
  1. Agent 拿到具体的 Schema 和 example 后，生成复杂的 `canvas_payload` 字典。
  2. 调用 `validate_strategy_canvas` 预检查。
- **内部回环 (Inner loop)**:
  - 如果 validate 报错，提取 Error Message 中提示的缺失/越界原因，让 AI 带有记忆重新生成并再次 validate，直到接口抛回通过为止，再流转至 Phase 5。

### Phase 5: 创建和验证阶段 (Creation & Verification Node)

- **核心目标**: 硬件级下发创建，利用硬编码方式堵住“幻觉生成创建成功”的问题。
- **关联工具 (Tools)**:
  - `create_strategy_canvas` (真正下发落库动作)
  - `get_strategy_canvas_detail` (通过 StrategyId 读取详情)
- **处理逻辑**:
  1. 执行 `create_strategy_canvas`，传入经过校验的最终 Payload。记录返回的 `strategy_id`。
  2. Agent **必须**使用 `strategy_id` 触发 `get_strategy_canvas_detail`。
  3. 在 Agent Executor 或 Tool Interceptor 外层增加硬断言逻辑：如果该查询返回结果里带有 HTTP/JSON 标准状态如 `code=200` 和对应有效节点数据，子图才将最终 `is_created_successfully` 写为 `True` 并宣布 **END**。

---

## 4. 异常与边界约束 (Edge Cases & Requirements)

1. **Token 使用限制**:
   - `get_assembly_schemas` 接口必须批量调用（只传入 `selected_assemblies` 对应值）以防 Schema 过长引发上下文爆炸。
   - `list_strategies` 等通用查询应当在分页上给出强制约束 (`pageSize <= 5`)。
2. **唯一根节点保证**:
   - `validate_strategy_canvas` 中关于 `parentNodeId=null` 必须且只能有一个(START)的约束是高频报错点，需要在 Agent System Prompt 中预置。
3. **安全拦截**:
   - 无用户的反馈通过（即 `is_approved == False` 的情况下），绝对禁止图路由抵达 Phase 4 或 Phase 5 进行创建相关操作。
