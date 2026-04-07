# AI 引擎架构共识文档

| 项目 | 内容 |
|------|------|
| **文档性质** | 架构评审共识，记录已确认的设计决策与待修复项 |
| **形成时间** | 2026-04-01 |
| **参与方** | 项目负责人 / AI 架构审查 |
| **适用范围** | `ai-engine/src/ai_engine/graph/nodes/` 全部图节点 |

---

## 一、核心设计理念（已确认）

### 1.1 架构哲学

**工具可靠性 + 流程可靠性 = 多智能体可靠性**

- 工具可靠性：通过工具注册中心（Tool Registry）外部维护工具定义、参数、权限，graph node 仅引用
- 流程可靠性：通过智能体注册中心（Agent Registry）外部维护智能体配置、绑定关系，Planner → Executor 的层级路由严格受控
- 两者叠加确保：即使 LLM 产生幻觉，也无法调用未授权的工具或越级执行

### 1.2 执行模式

**Plan-and-Execute + Human-in-the-Loop（人机回环）**

- Plan-and-Execute：Planner 负责任务拆解，Executor 负责逐步执行，职责分离
- 人机回环：在关键节点引入人工审核，建立人机共识

### 1.3 人工审核的定位（关键共识）

> **人工审核 = 建立共识，而非质量评估**

人工审核的初衷是：
- 用户要**知道** AI 在干什么（知情权）
- 用户要**认同或不认同** AI 的做法（决策权）
- 用户要能**及时阻断或调整**（控制权）

人工审核**不承担**专业质量评估职责。审核者的专业性参差不齐，不应假设审核者能发现数据完整性、指标合理性等专业问题。

---

## 二、当前架构评估结论

### 2.1 节点设计合理性

**8 个节点，Dispatcher 中枢模式，各司其职：**

| 节点 | 职责 | 评价 |
|------|------|------|
| intent_recognition | 查询重写 + 意图分类（TASK/CHAT/END） | 合理，含异常兜底 |
| dispatcher | 中央路由枢纽 + Agent 选择 | 合理，辐射型架构核心 |
| planner | 任务拆解 + 能力边界校验 + 人机协同标记 | 合理，feasibility 校验有价值 |
| executor (plan_task_execute) | Agent + Tool Loop 执行 + 共享黑板 | 合理，但缺少输出校验 |
| human_review | interrupt() 暂停等待用户决策 | 合理，LangGraph 原生机制 |
| feedback_handler | 反馈智能分流（全量重规划 / 局部调整） | 合理，关键词 + LLM 双层分类 |
| normal | ReAct Agent 处理闲聊/问答 | 合理，但经 responder 中转有冗余 |
| responder | 结果汇总 + 审计提交 + 长期记忆 | 合理，统一出口 |

### 2.2 已确认的风险项（需修复）

#### 风险 1：Dispatcher 无限回环缺乏断路器

**问题**：所有节点回环到 Dispatcher，无全局最大迭代次数限制。用户反复驳回、或 Planner 异常时可能死循环。

**修复方案**：在 `AgentState` 中增加 `iteration_count` 字段，Dispatcher 每次执行 +1，超过阈值（如 20）强制路由到 Responder。

#### 风险 2：plan=[] 与 plan=None 的语义歧义

**问题**：Planner 异常时设置 `plan=[]`，Dispatcher 判断 `plan is None or len(plan) == 0` 会再次路由到 Planner，形成 Planner <-> Dispatcher 循环。

**修复方案**：Planner 失败时设置 `plan=None` 并带上 `error`。Dispatcher 增加对 `state.error` 的判断——有 error 且无 plan 时不再重进 Planner，直接走 Responder。

#### 风险 3：_execute_step_default 暴露全部 public 工具

**问题**：当指定 Agent 不存在时，回退函数 `_execute_step_default` 调用 `get_public_tools()` 获取所有公开工具，绕过了 Planner 的权限边界。

**修复方案**：`_execute_step_default` 应不绑定任何工具或直接 fail，不开放全部 public 工具。

#### 风险 4：messages 膨胀

**问题**：内部调度消息（如 `[Dispatcher] 路由到: planner`）与用户可见消息混写到 `messages` 中，在多步骤+多轮审核场景下快速膨胀。

**修复方案**：调度日志仅写入 `node_traces`，`messages` 只保留用户可见内容。

---

## 三、关于引入 Evaluator Agent 的决策（关键共识）

### 3.1 结论：不引入独立的 Evaluator Agent 节点

#### 否决理由

| 问题 | 说明 |
|------|------|
| 评估者自身不可靠 | LLM 评估 LLM 的输出，陷入"谁来监督监督者"的无限递归。当前用人工审核终结这个链条是正确的 |
| 延迟和成本翻倍 | 每加一次 LLM 评估调用增加 2-5 秒延迟，在金融业务场景下用户等待时间是核心体验指标 |
| 评估标准难以定义 | "基金画像是否正确"、"客群匹配是否合理"这类判断需要业务专业知识，LLM Evaluator 不具备 |
| 增加回环复杂度 | 在已缺乏断路器的情况下再增加评估回环，加剧死循环风险 |

#### 真正的问题

人工审核定位是"建立共识"而非"质量评估"，但审核者专业性参差不齐。架构中**缺少一个质量守门员角色**，但该角色不应以独立 LLM Agent 节点的形式存在。

### 3.2 替代方案：评估能力内嵌到 Executor（已达成共识）

**原则：能用规则解决的不用 LLM，该让人决定的不用 LLM 替代人。**

#### 第一层：Executor 输出结构化

要求 Executor 的 LLM 输出包含自检信息：

```python
class StepOutput(BaseModel):
    reasoning: str          # 推理过程
    conclusion: str         # 核心结论
    data_completeness: bool # 任务所需数据是否完整获取
    tools_all_succeeded: bool  # 所有工具调用是否成功
    confidence: float       # 对结论的置信度 (0-1)
    risk_flags: list[str]   # 潜在风险点（数据异常、条件模糊等）
```

这不是让 LLM 评估自己，而是**要求 LLM 暴露不确定性**。

#### 第二层：规则校验（确定性、零 LLM 成本）

在 Executor 内部、返回结果之前，用确定性规则校验：

| 规则 | 触发条件 | 结果 |
|------|----------|------|
| 预期工具未调用 | `expected_tools` 与 `tools_called` 有差集 | 不通过，自动重试 |
| 置信度过低 | `confidence < 0.6` | 不通过，自动重试 |
| 数据不完整 | `data_completeness = false` | 不通过，自动重试 |
| 存在风险标记 | `risk_flags` 非空 | 动态升级为需审核 |

#### 第三层：不通过时 Executor 内重试，不回 Dispatcher

```
executor 内部: 执行 → 规则校验 → 不通过 → 将失败原因注入 messages → 重试 (max 1次)
```

不增加节点、不增加回环复杂度。

#### 第四层：增强人工审核体验

改造前审核者看到的：
```
步骤描述：获取基金画像
执行结论：该基金为混合型基金，近一年收益率12.3%...
```

改造后审核者看到的：
```
步骤描述：获取基金画像
执行结论：该基金为混合型基金，近一年收益率12.3%...

⚠️ AI 提示：
  - 数据完整性：✅ 完整
  - 置信度：0.85
  - 风险提示：近3月数据缺失，使用近6月数据替代
```

**效果**：AI 不替人做判断，但帮人标记该判断的地方，降低对审核者专业性的依赖。

---

## 四、待优化项（非紧急）

| 编号 | 优化项 | 说明 | 优先级 |
|------|--------|------|--------|
| O-1 | LLM 实例创建统一 | 各节点独立创建 ChatOpenAI，temperature 不统一，应抽取 `llm_factory.py` | 中 |
| O-2 | builder.py 显式定义边 | 当前路由完全依赖 `Command(goto=...)`，无法利用 LangGraph 图可视化 | 低 |
| O-3 | normal → responder 冗余跳转 | normal_node 已生成完整回答，responder 仅透传，增加无意义延迟 | 中 |
| O-4 | 结论提取改为 Prompt 内嵌 | `_extract_conclusion` 额外 LLM 调用可通过要求 Executor 输出时自带结论段来消除 | 中 |
| O-5 | `_execute_step_with_agent` 返回类型标注 | 实际返回 `tuple[StepResult, list, str]`，但签名标注为 `StepResult` | 低 |

---

## 五、修复与优化的执行优先级

```
紧急修复（影响系统稳定性）：
  1. 断路器：AgentState 增加 iteration_count，Dispatcher 限制最大回环次数
  2. plan=[] 语义修复：Planner 异常时 plan=None + error，Dispatcher 增加 error 判断

重要改进（影响系统可靠性）：
  3. _execute_step_default 权限收紧
  4. Executor 输出结构化 + 规则校验（本文第三章方案）
  5. 人工审核体验增强（risk_flags 暴露给审核者）

优化项（影响代码质量）：
  6. messages 瘦身（调度日志不写 messages）
  7. LLM 实例创建统一
  8. 结论提取改为 Prompt 内嵌
```

---

## 六、设计原则备忘

以下原则在本次架构评审中被明确提出并达成共识，指导后续所有演进决策：

1. **能用规则解决的不用 LLM**——确定性校验优于 LLM 评估
2. **该让人决定的不用 LLM 替代人**——人工审核 = 建立共识，不可被 AI 取代
3. **评估能力要有，但不以独立 Agent 节点的形式存在**——内嵌到执行流程，不增加回环
4. **LLM 不擅长自评质量，但擅长标记不确定性**——要求暴露 risk_flags 和 confidence
5. **不增加节点，不增加回环**——在当前断路器缺失的前提下，任何新增回环都是风险

---

## 七、Tool 全生命周期管理（2026-04-07 补充）

本章记录 Tool 从注册到被 LLM 调用的完整链路设计决策，以及本次对话中已确认的三项优化。

### 7.1 Tool 全链路数据流

```
Bus Kernel DB (tool_cards 表)
        │
        ▼
BusKernelClient ── 两阶段 API ──
├─ POST /tool/available  → 轻量摘要 (Phase 1)
└─ POST /tool/detail     → 完整卡片 (Phase 2)
        │
        ▼
ToolRegistry ── 两阶段懒加载 ──
├─ load(token)     → _user_tool_summaries 缓存 (摘要，1x/token/session)
└─ get_tool(name)  → _user_tools 缓存 (StructuredTool，按需创建)
        │
        ▼
ToolFactory (create_dynamic_tool) ── 三步创建 ──
├─ tool_parameters → Pydantic Model (args_schema)
├─ url_path + method → HTTP executor (自动注入 Token)
└─ 组装 StructuredTool.from_function()
        │
        ▼
AgentConfig ── 桥接 Agent 与 Tool ──
├─ raw_bound_tools: ["tool_a", "tool_b"]
├─ get_tools(token) → 调 ToolRegistry 获取实例
└─ build_execution_system_message() → 角色定义 (不含工具描述)
        │
        ▼
plan_task_execute_node ── 两步使用 ──
├─ llm.bind_tools(tools)  → API 层结构化注册
└─ _execute_with_tool_loop → ReAct 循环 (最多 8 轮)
```

### 7.2 两阶段懒加载的适用场景评估（已确认）

| 消费方 | 使用的阶段 | 实际价值 |
|--------|-----------|---------|
| Planner | 仅 Phase 1 (摘要) | **有效** — 只需知道"有哪些工具、干什么用"做规划，不创建工具实例 |
| Executor | Phase 1 + Phase 2 | **防御性冗余** — 摘要层权限预检有防御价值，但不是性能优化 |

**结论**：两阶段设计对 Planner 场景有实际收益，对 Executor 场景主要价值在权限前置校验。整体保留，不做改动。

### 7.3 已确认的三项优化

#### 优化 1：移除 system message 中的冗余工具描述

**问题**：`build_execution_system_message()` 在 system message 中以文本形式列出 `## 可用工具`，同时 `llm.bind_tools(tools)` 在 API 层面注册了完整的工具 JSON Schema。两者信息重复，浪费 token。

**决策**：工具信息由 `bind_tools()` 独立承担。`build_execution_system_message()` 仅保留 `system_prompt` + `negative_prompt`。

**变更文件**：`agent_registry.py` — `build_execution_system_message()`

#### 优化 2：ReAct 循环增加综合引导

**问题**：`_execute_with_tool_loop` 最多 8 轮工具循环，轮次耗尽时取 `messages[-1].content` 作为最终输出，可能是原始 ToolMessage 而非 LLM 的综合分析。

**决策**：分两层引导。

| 引导时机 | 注入内容 |
|----------|---------|
| 倒数第二轮结束 | "你即将用尽工具调用轮次，请综合所有结果给出结论" |
| 轮次耗尽 (for-else) | "不要再调工具，直接给结论"，再做一次收尾 LLM 调用 |

**变更文件**：`plan_task_execute_node.py` — `_execute_with_tool_loop()`

#### 优化 3：工具调用失败分层引导

**问题**：HTTP 工具的所有错误（200/500/401/404）在 factory 层被 catch 并以 JSON 字符串返回，不抛异常。对 `_execute_with_tool_loop` 来说，500 业务错误和 200 正常返回走同一条路径，LLM 无法区分"应该改参数重试"还是"这个工具不可用"。

**决策**：两层配合。

**Factory 层**：HTTP 错误返回新增 `tool_error_type` 分类字段：

| `tool_error_type` | 触发条件 | 语义 |
|-------------------|---------|------|
| `"business"` | 5xx | 业务错误，参数有误/数据不存在，LLM 可修正参数重试 |
| `"auth"` | 401/403 | 权限不足，不可通过修改参数解决 |
| `"system"` | 404/405 等 | 协议级错误，不可重试 |
| `"network"` | 超时/DNS/连接失败 | 网络异常，不可重试 |

**ReAct 循环层**：每轮工具调用后解析 `tool_error_type`，按三类注入差异化引导：

| 错误类型 | 引导策略 |
|----------|---------|
| 业务错误 (可修正) | "分析错误详情，修正参数后重新调用" |
| 系统错误 (不可重试) | "放弃该工具，换用其他工具或基于已有数据给结论" |
| 工具异常 (不可重试) | "工具内部故障，勿重试，换用其他工具" |

**变更文件**：
- `factory.py` — `create_http_executor()` 错误返回增加 `tool_error_type`
- `plan_task_execute_node.py` — 新增 `_parse_tool_error_type()` + `_build_failure_guidance()`

### 7.4 本章设计原则

1. **工具信息单一信源**——`bind_tools()` 是 LLM 获取工具定义的唯一通道，不在 prompt 中重复
2. **错误分层，引导分层**——业务错误引导修正，系统错误引导放弃，不做无差别"请重试"
3. **factory 层不吞错误语义**——通过 `tool_error_type` 将错误分类透传给上层，上层按需处理
4. **循环要有收口**——轮次耗尽时主动引导 LLM 综合结论，不依赖 `messages[-1]` 兜底

---

*文档版本: v1.1*
*v1.0: 架构评审对话提炼 (2026-04-01)*
*v1.1: 补充 Tool 全生命周期管理共识 (2026-04-07)*
