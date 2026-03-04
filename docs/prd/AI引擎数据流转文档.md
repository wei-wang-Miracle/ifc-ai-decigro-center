# AI 引擎全流程数据流转文档

## 一、架构概述

AI 引擎采用 **LangGraph StateGraph** 实现的**共享黑板（Blackboard）架构**，所有图节点共享同一个 `AgentState` 实例，通过读取和写入黑板数据实现节点间协作。

### 1.1 架构模式对比

| 模式 | 特点 | 本系统 |
|------|------|--------|
| **Workflow 模式** | 上一节点输出作为下一节点输入，串行流水线 | ❌ |
| **共享黑板模式** | 所有参与者读写同一数据空间，支持任意节点间通信 | ✅ |

### 1.2 系统架构图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         AgentState (共享黑板)                                 │
│  ┌────────┬────────┬────────┬─────────────┬─────────────────┬──────────────┐ │
│  │ query  │ intent │  plan  │ step_results│ review_feedback │    error     │ │
│  └───┬────┴───┬────┴───┬────┴──────┬──────┴────────┬────────┴───────┬──────┘ │
│      │        │        │           │               │                │        │
│  ┌───┴────┬───┴────┬───┴────┬──────┴────┬──────────┴─────┬──────────┴─────┐  │
│  │ token  │ taskId │ traceId│ curPlanner│  curExecutor   │  review_status │  │
│  └────────┴────────┴────────┴───────────┴────────────────┴────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
        │         │         │          │              │            │
   ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌────▼────┐ ┌───────▼────────┐ ┌─▼────────┐
   │ intent │ │dispatch│ │planner│ │executor │ │feedback_handler│ │responder │
   │_recog. │ │ _node  │ │_node │ │  _node  │ │     _node      │ │  _node   │
   └────────┘ └────────┘ └──────┘ └─────────┘ └────────────────┘ └──────────┘
```

---

## 二、共享黑板数据结构（AgentState）

### 2.1 核心数据字段

| 字段名 | 类型 | 说明 | 生命周期 |
|--------|------|------|----------|
| `query` | `str` | 用户原始输入 | 请求开始时写入，全程只读 |
| `intent` | `IntentObject` | 意图识别结果 | intent_recognition 写入，后续节点读取 |
| `plan` | `list[PlanStep]` | 任务执行计划 | planner 写入，executor 逐步消费 |
| `step_results` | `list[StepResult]` | 步骤执行结果 | executor 追加写入，后续步骤读取 |
| `review_feedback` | `str` | 用户审核反馈 | human_review 写入，executor/planner 读取 |
| `error` | `str` | 全局错误信息 | 任意节点写入，responder 读取 |

### 2.2 控制流数据字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `current_step_index` | `int` | 当前执行步骤索引 |
| `current_planner` | `str` | 当前 Planner Agent 名称 |
| `current_executor` | `str` | 当前 Executor Agent 名称 |
| `require_review` | `bool` | 是否需要人工审核 |
| `review_status` | `ReviewStatus` | 审核状态（PENDING/APPROVED/REJECTED） |

### 2.3 追踪与认证字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `task_id` | `str` | 任务标识符 |
| `trace_id` | `str` | 链路追踪 ID |
| `token` | `str` | 用户认证 Token |
| `node_traces` | `list[dict]` | 节点执行追踪记录 |

---

## 三、图节点数据流转详情

### 3.1 intent_recognition_node（意图识别节点）

**职责**：解析用户输入，识别意图类型

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `query` | 获取用户原始输入 |
| 读取 | `token` | 获取可用工具/Agent 列表 |
| 写入 | `intent` | 写入意图识别结果 |
| 写入 | `messages` | 追加用户消息 |

**数据流**：
```
query → LLM 意图识别 → intent (IntentObject)
                     ├── intent_type: TASK/QUESTION/CHAT/CLARIFY/...
                     ├── confidence: 0.0-1.0
                     └── entities: {...}
```

---

### 3.2 dispatcher_node（调度中心节点）

**职责**：根据当前状态决定路由，选择 Planner/Executor

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `intent` | 判断意图类型 |
| 读取 | `plan` | 检查是否已有计划 |
| 读取 | `step_results` | 生成审核提示信息 |
| 读取 | `require_review` | 判断是否需要审核 |
| 读取 | `review_status` | 判断审核状态 |
| 读取 | `review_feedback` | 检查是否有用户反馈 |
| 写入 | `current_planner` | 选择的 Planner Agent |
| 写入 | `current_executor` | 选择的 Executor Agent |

**路由决策逻辑**：
```
if require_review:
    → review
elif intent is None:
    → intent_recognition
elif intent_type in [END, INVALID]:
    → __end__
elif plan is None:
    → planner
elif current_index >= len(plan):
    → responder
elif current_step.requires_review and not approved:
    → review
else:
    → executor
```

---

### 3.3 planner_node（规划节点）

**职责**：将用户需求拆解为可执行的步骤计划

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `query` | 获取用户原始需求 |
| 读取 | `step_results` | 构建上下文（之前执行结果） |
| 读取 | `review_feedback` | 构建上下文（用户反馈） |
| 读取 | `current_planner` | 使用指定的 Planner Agent |
| 写入 | `plan` | 生成的任务计划 |
| 写入 | `plan_reasoning` | 规划思路说明 |
| 写入 | `current_step_index` | 重置为 0 |

**数据流**：
```
query + step_results + review_feedback
    ↓
┌─────────────────────────────────────┐
│  LLM Planner (with_structured_output)│
└─────────────────────────────────────┘
    ↓
plan: [
  PlanStep(step_id="1", description="...", assigned_agent="...", expected_tools=[...]),
  PlanStep(step_id="2", description="...", dependencies=["1"], ...),
  ...
]
```

---

### 3.4 plan_task_execute_node（执行节点）

**职责**：执行当前计划步骤，调用 Agent 和工具

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `plan` | 获取当前步骤 |
| 读取 | `current_step_index` | 确定执行哪个步骤 |
| 读取 | `query` | 用户原始需求（上下文） |
| 读取 | `step_results` | **共享黑板核心：之前步骤的产出** |
| 读取 | `review_feedback` | 用户修改意见 |
| 读取 | `current_executor` | 使用指定的 Executor Agent |
| 写入 | `step_results` | 追加当前步骤结果 |
| 写入 | `current_step_index` | 推进到下一步 |
| 写入 | `require_review` | 是否触发审核 |

**共享黑板机制（核心）**：
```
执行 Step N 时，Prompt 结构：

## 当前任务
{step.description}

## 用户原始需求
{query}

## 之前步骤的执行结果（重要参考）    ← 共享黑板数据注入
- 步骤 1: 成功
  输出: {step_results[0].output}
- 步骤 2: 成功
  输出: {step_results[1].output}
...

## 用户修改意见（如有）
{review_feedback}

请充分利用上述步骤的产出信息来完成当前任务。
```

---

### 3.5 human_review_node（人工审核节点）

**职责**：处理需要人工审核的敏感操作

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `review_status` | 判断用户决定 |
| 读取 | `step_results` | 获取待审核的执行结果 |
| 读取 | `plan` | 获取当前步骤描述 |
| 读取 | `review_feedback` | 获取用户反馈 |
| 写入 | `require_review` | 清除审核标记 |
| 写入 | `review_status` | 更新审核状态 |

**审核流程**：
```
interrupt_before=["review"]
    ↓
用户决策 → handle_review_decision()
    ├── approve → review_status = APPROVED → dispatcher → executor
    └── reject  → review_status = REJECTED → feedback_handler
```

---

### 3.6 feedback_handler_node（反馈处理节点）

**职责**：处理用户驳回后的反馈，决定重新规划或调整执行

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `review_feedback` | 获取用户反馈内容 |
| 读取 | `review_status` | 确认是驳回状态 |
| 写入 | `plan` | 清空计划（若需重新规划） |
| 写入 | `review_feedback` | 保留反馈供后续节点使用 |
| 写入 | `review_status` | 清除审核状态 |

**决策逻辑**：
```
if "重新规划" in review_feedback:
    plan = None                    # 清空计划
    → dispatcher → planner         # 重新规划
else:
    保留 plan 和 review_feedback
    → dispatcher → executor        # 携带反馈重新执行当前步骤
```

---

### 3.7 responder_node（响应汇总节点）

**职责**：汇总所有执行结果，生成最终回答

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `step_results` | 获取所有步骤执行结果 |
| 读取 | `intent` | 判断特殊意图 |
| 读取 | `query` | 用户原始问题 |
| 读取 | `error` | 获取错误信息 |
| 写入 | `messages` | 最终回答 |

**汇总逻辑**：
```
step_results + query + error
    ↓
┌─────────────────────────┐
│  LLM 汇总生成最终回答    │
└─────────────────────────┘
    ↓
最终回答（Markdown 格式）
```

---

### 3.8 normal_node（普通对话节点）

**职责**：处理简单需求（闲聊、简单问答）

| 操作 | 数据字段 | 说明 |
|------|----------|------|
| 读取 | `query` | 用户输入 |
| 读取 | `token` | 获取 public 工具 |
| 读取 | `intent` | 判断意图类型 |
| 写入 | `messages` | 对话回复 |

---

## 四、关键数据传递链路

### 4.1 step_results 传递链（多步执行上下文共享）

```
┌─────────────┐    step_results: []
│  executor   │ ─────────────────────┐
│  (step 1)   │                      │
└──────┬──────┘                      ▼
       │ append          ┌──────────────────────┐
       │                 │  step_results: [     │
       ▼                 │    StepResult(1)     │
┌─────────────┐          │  ]                   │
│  executor   │ ◄────────┴──────────────────────┘
│  (step 2)   │   读取 step_results 注入 Prompt
└──────┬──────┘
       │ append
       ▼
┌─────────────┐    step_results: [StepResult(1), StepResult(2)]
│  responder  │ ◄──────────────────────────────────────────────
│             │   汇总所有结果生成最终回答
└─────────────┘
```

### 4.2 review_feedback 传递链（人机协同）

```
┌─────────────┐
│ human_review│
│  (用户驳回) │
└──────┬──────┘
       │ review_feedback = "请用中文回复"
       ▼
┌─────────────┐
│  feedback   │
│  _handler   │
└──────┬──────┘
       │ 分析反馈类型
       ├─────────────────────────────────────┐
       ▼                                     ▼
┌─────────────┐                       ┌─────────────┐
│  planner    │                       │  executor   │
│ (重新规划)   │                       │ (调整执行)   │
└─────────────┘                       └─────────────┘
  读取 review_feedback                   读取 review_feedback
  生成新计划                              携带反馈重新执行
```

### 4.3 plan 传递链（任务编排）

```
┌─────────────┐
│  planner    │
│             │
└──────┬──────┘
       │ plan = [Step1, Step2, Step3]
       ▼
┌─────────────┐    current_step_index = 0
│ dispatcher  │ ───────────────────────────┐
└──────┬──────┘                            │
       │ 选择 executor                      │
       ▼                                   │
┌─────────────┐                            │
│  executor   │  执行 plan[0]               │
│  (step 1)   │                            │
└──────┬──────┘                            │
       │ current_step_index = 1            │
       ▼                                   │
┌─────────────┐                            │
│ dispatcher  │ ◄──────────────────────────┘
└──────┬──────┘   循环直到 index >= len(plan)
       │
       ▼
┌─────────────┐
│  responder  │  任务完成，汇总响应
└─────────────┘
```

---

## 五、数据流转状态机

```
                    ┌──────────────────────────────────────────────────────┐
                    │                    START                             │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────────────┐
                    │            intent_recognition_node                   │
                    │  读取: query, token                                  │
                    │  写入: intent                                        │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      ▼                      │
                    │   ┌─────────────────────────────────────┐   │
                    │   │          dispatcher_node            │   │
                    │   │  读取: intent, plan, step_results,  │   │
                    │   │        review_status, review_feedback│   │
                    │   │  写入: current_planner, current_executor│
                    │   └──────────────────┬──────────────────┘   │
                    │                      │                      │
          ┌─────────┴────────┬─────────────┼─────────────┬────────┴─────────┐
          │                  │             │             │                  │
          ▼                  ▼             ▼             ▼                  ▼
┌─────────────────┐  ┌──────────────┐ ┌─────────┐ ┌─────────────┐  ┌────────────┐
│  planner_node   │  │executor_node │ │ review  │ │  responder  │  │   normal   │
│                 │  │              │ │  _node  │ │   _node     │  │   _node    │
│ 读取:           │  │ 读取:        │ │         │ │             │  │            │
│  query          │  │  query       │ │ 读取:   │ │ 读取:       │  │ 读取:      │
│  step_results   │  │  step_results│ │ review  │ │ step_results│  │  query     │
│  review_feedback│  │  review_feedb│ │ _status │ │  intent     │  │  intent    │
│                 │  │  plan        │ │ step    │ │  error      │  │            │
│ 写入:           │  │              │ │ _results│ │             │  │ 写入:      │
│  plan           │  │ 写入:        │ │         │ │ 写入:       │  │  messages  │
│  plan_reasoning │  │  step_results│ │ 写入:   │ │  messages   │  │            │
└────────┬────────┘  │  step_index  │ │ review  │ └──────┬──────┘  └─────┬──────┘
         │           └──────┬───────┘ │ _status │        │               │
         │                  │         └────┬────┘        │               │
         │                  │              │             │               │
         └──────────────────┴──────────────┴─────────────┴───────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────────────┐
                    │                     END                              │
                    └──────────────────────────────────────────────────────┘
```

---

## 六、总结

### 6.1 共享黑板模式优势

1. **上下文连贯性**：step_results 在多步执行间传递，后续步骤可充分利用前序产出
2. **人机协同灵活**：review_feedback 可传递到 planner/executor，支持重新规划或调整执行
3. **错误可追溯**：error 字段统一收集，responder 可生成友好错误提示
4. **审计完整性**：node_traces 记录全链路执行过程

### 6.2 关键数据利用矩阵

| 数据 | 写入节点 | 读取节点 | 用途 |
|------|----------|----------|------|
| query | 初始化 | 全部节点 | 用户原始需求 |
| intent | intent_recognition | dispatcher, responder, normal | 路由决策 |
| plan | planner | dispatcher, executor | 任务编排 |
| step_results | executor | executor, planner, responder, dispatcher | **多步执行上下文共享** |
| review_feedback | human_review | executor, planner, feedback_handler | **人机协同反馈传递** |
| error | 任意节点 | responder | 错误信息汇总 |

---

*文档版本: v1.0*  
*更新日期: 2026-03-04*  
*维护者: AI Engine Team*
