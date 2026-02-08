# 多智能体 AI 引擎产品需求文档 (PRD)

| 项目         | 内容                                              |
| ------------ | ------------------------------------------------- |
| **文档名称** | 多智能体规划与执行引擎 PRD                        |
| **版本号**   | v1.0.0                                            |
| **架构模式** | Plan-and-Execute / Human-in-the-loop / 辐射型调度 |
| **核心技术** | LangGraph, LangChain, FastAPI, PostgreSQL         |

---

## 1. 产品概述 (Executive Summary)

本项目旨在构建一个企业级的 **多智能体编排引擎 (Multi-Agent Orchestration Engine)**。系统采用 **辐射型 (Hub-and-Spoke)** 架构，以调度中心 (Dispatcher) 为核心，结合 **Plan-and-Execute** 范式，实现复杂任务的自动化处理。

系统的核心差异化在于其 **动态注册机制**：

1. **Agent 动态加载**：通过数据库 (`agent_cards`) 定义 Agent 的人设、权限和推理模式，而非硬编码。
2. **Tool 动态绑定**：通过数据库 (`tool_cards`) 定义工具的参数结构和协议，支持热插拔。
3. **人机协同**：内置人工审核节点，支持敏感操作的“中断-恢复”机制。

---

## 2. 系统架构 (System Architecture)

### 2.1 核心节点流程图 (Mermaid)

基于 LangGraph 的状态机流转逻辑：

```mermaid
graph TD
    START([开始]) --> intent_recognition_node["Intent Recognition Node<br/>(意图识别)"]

    intent_recognition_node --> |识别成功| dispatcher_node["Dispatcher Node<br/>(调度中心)"]
    intent_recognition_node --> |无效/结束| END1([结束])

    dispatcher_node --> |1. 需要规划| planner_node["Planner Node<br/>(任务规划)"]
    dispatcher_node --> |2. 执行子任务| plan_task_execute_node["Plan Task Execute Node<br/>(执行节点)"]
    dispatcher_node --> |3. 重新理解| intent_recognition_node
    dispatcher_node --> |4. 全部完成| END2([结束])

    planner_node --> |生成/更新计划| dispatcher_node

    plan_task_execute_node --> |敏感操作/触发阈值| human_review_node["Human Review Node<br/>(人工审核)"]
    plan_task_execute_node --> |自动执行完成| dispatcher_node

    human_review_node --> |APPROVE (通过)| dispatcher_node
    human_review_node --> |REJECT (驳回)| feedback_handler_node["Feedback Handler Node<br/>(反馈处理)"]

    feedback_handler_node --> |修正指令| dispatcher_node

    style dispatcher_node fill:#ff9800,stroke:#e65100,stroke-width:3px
    style intent_recognition_node fill:#2196f3,stroke:#0d47a1,stroke-width:2px
    style human_review_node fill:#9c27b0,stroke:#4a148c,stroke-width:2px

```

### 2.2 架构特点

- **辐射型架构 (Hub-and-Spoke)**：`Dispatcher` 维持全局状态，所有节点执行完毕后必须通过 Dispatcher 决策下一步。
- **状态持久化 (Checkpointing)**：使用 LangGraph 的 `MemorySaver` (Postgres checkpointer) 保存每一步的 State，支持系统重启后继续执行，以及人工审核时的状态暂停。

---

## 3. 功能模块详解 (Functional Requirements)

### 3.1 注册中心模块 (Registry Module)

系统启动或运行时，需从数据库加载配置。

#### A. 工具注册 (Tool Registry)

- **数据源**：`tool_cards` 表。
- **功能逻辑**：
- 读取 `tool_parameters` (JSONB) 并动态转换为 Pydantic 模型或 OpenAI Function Schema。
- 根据 `tool_protocol` ('http' 或 'reference') 生成对应的执行器。如果为 'http'，自动构建 API 请求。
- **Few-Shot 注入**：将 `input_examples` 和 `output_examples` 注入到 Prompt 中，增强模型对工具调用的理解。

- **权限控制**：根据 `tool_privileges` 字段（public/protected），在绑定 Agent 时进行校验。

#### B. 智能体注册 (Agent Registry)

- **数据源**：`agent_cards` 表。
- **功能逻辑**：
- 根据 `agent_name` 唯一标识 Agent。
- **工具绑定**：解析 `bound_tools` 数组，从 Tool Registry 中获取对应的工具对象，绑定到该 Agent 的 LangChain 实例上。
- **人设构建**：组合 `system_prompt`、`negative_prompt` 以及工具描述，构建完整的 System Message。

### 3.2 核心节点逻辑 (Core Nodes)

#### Node 1: 意图识别 (Intent Recognition)

- **输入**：用户原始 Query。
- **职责**：
- 判断用户意图是否明确。
- 提取关键上下文信息。

- **输出**：结构化意图对象 (IntentObject)，包含意图类别和置信度。

#### Node 2: 调度中心 (Dispatcher Node)

- **输入**：当前全局状态 (State)。
- **职责**：
- **路由决策**：
- 若无计划，路由至 `Planner`。
- 若有计划且有未完成任务，路由至 `Plan Task Execute`。
- 若任务完成，路由至 `END`。

- **Agent 选择**：根据任务描述，在 `agent_cards` 中通过 `agent_description` 和 `agent_tags` 进行语义匹配，选择最合适的 Agent 执行。

#### Node 3: 规划节点 (Planner Node)

- **输入**：用户需求 + 历史对话。
- **职责**：
- 将复杂目标拆解为有序步骤 list `[Step 1, Step 2, Step 3...]`。
- 支持动态调整：如果之前的执行失败，Planner 需根据错误信息调整后续计划。

#### Node 4: 执行节点 (Plan Task Execute Node)

- **输入**：当前的具体步骤 (Current Step)。
- **核心逻辑**：

1. Dispatcher 指定了当前步骤的执行 Agent (例如 `fund_product_expert`)。
2. 系统从 Registry 加载该 Agent 的 System Prompt 和 Tools。
3. Agent 执行推理 (Reasoning) 和工具调用 (Function Calling)。
4. **安全拦截**：如果在执行过程中触发了敏感工具（`tool_cards.tool_privileges = 'protected'`），或者 Agent 自身的 Output 包含敏感词，设置标记 `require_review = True`。

#### Node 5: 人工审核 (Human Review Node)

- **机制**：利用 LangGraph `interrupt_before=["human_review_node"]`。
- **交互**：系统在此处挂起 (Suspend)，生成一个 `review_id` 等待 API 调用。
- **API 动作**：
- **APPROVE**: 更新状态，允许数据流向 Dispatcher，继续执行。
- **REJECT**: 附带修改意见，流向 Feedback Handler。

#### Node 6: 反馈处理 (Feedback Handler Node)

- **输入**：人工驳回意见。
- **职责**：将人工意见转化为系统指令，更新 `Memory`，并强制 Dispatcher 指挥 Planner 重新规划或让 Agent 重试。

---

## 4. 数据模型设计 (Database Schema)

基于用户提供的 SQL，核心字段映射逻辑如下：

### 4.1 Tool Cards (`tool_cards`)

用于定义 Function Calling 的结构。

| 字段名            | 类型    | 用途                                                                |
| ----------------- | ------- | ------------------------------------------------------------------- |
| `tool_name`       | VARCHAR | 函数名，LLM 调用时的标识符                                          |
| `tool_parameters` | JSONB   | **关键**：动态转换为 Pydantic/JSON Schema 供 LLM 理解参数           |
| `url_path`        | VARCHAR | 当 `tool_protocol`='http' 时，Generic Tool 执行器将向此路径发送请求 |
| `tool_privileges` | VARCHAR | 假如为 'protected'，执行器在调用前会强制路由到 Human Review Node    |

### 4.2 Agent Cards (`agent_cards`)

用于定义具体的执行者（Persona）。

| 字段名              | 类型    | 用途                                                            |
| ------------------- | ------- | --------------------------------------------------------------- |
| `agent_name`        | VARCHAR | ID，Dispatcher 根据此 ID 加载配置                               |
| `agent_description` | TEXT    | **路由依据**：Planner/Dispatcher 使用语义相似度匹配此字段来选人 |
| `bound_tools`       | TEXT[]  | 关联 `tool_cards.tool_name`，决定该 Agent 能用什么工具          |
| `system_prompt`     | TEXT    | 定义 Agent 的核心行为准则                                       |

---

## 5. 技术栈与环境 (Technical Stack)

| 组件           | 版本要求           | 实现细节                                                 |
| -------------- | ------------------ | -------------------------------------------------------- |
| **Python**     | 3.12+              | 利用最新的类型提示特性                                   |
| **Web 框架**   | FastAPI 0.115+     | 提供 `/chat`, `/agent/register`, `/workflow/resume` 接口 |
| **Agent 框架** | LangChain 1.2+     | 基础 LLM 抽象，Tool 转换工具                             |
| **编排引擎**   | LangGraph 1.0+     | 实现 StateGraph, Checkpointer (Postgres), Interrupts     |
| **包管理**     | uv                 | 高速依赖安装                                             |
| **数据验证**   | Pydantic 2.9+      | 解析 JSONB Schema，构建动态 Model                        |
| **配置管理**   | python-dotenv 1.0+ | 管理 LLM API Keys, DB URL                                |

---

## 6. 接口设计草案 (API Design)

### 6.1 发起任务

- **Endpoint**: `POST /api/v1/workflow/chat`
- **Payload**:

```json
{
  "query": "帮我写一份关于易方达蓝筹的营销文案，并检查是否合规",
  "user_id": "u123",
  "session_id": "s_abc_123"
}
```

- **Response**: 返回 `thread_id` 和初始流式响应。

### 6.2 获取待审核任务

- **Endpoint**: `GET /api/v1/workflow/pending_reviews`
- **Response**: 返回当前卡在 `human_review_node` 的任务列表及上下文。

### 6.3 提交人工审核结果

- **Endpoint**: `POST /api/v1/workflow/review/{thread_id}`
- **Payload**:

```json
{
  "action": "approve", // 或 "reject"
  "feedback": "文案中关于收益的描述太夸张，请修改" // 仅 reject 时需要
}
```

---

## 7. 开发实施路线 (Implementation Roadmap)

1. **Phase 1: 基础设施 (Day 1-2)**

- 搭建 PostgreSQL 环境，运行提供的 SQL 初始化表。
- 使用 `uv` 初始化 Python 3.12 项目，安装 FastAPI, LangGraph。
- 编写 `DatabaseManager` 类，实现对 cards 表的 CRUD 读取。

2. **Phase 2: 动态注册机制 (Day 3-4)**

- 实现 `ToolFactory`：将 `tool_parameters` JSON 转换为 LangChain `StructuredTool`。
- 实现 `AgentFactory`：根据 Agent Card 组装 Runnable (Prompt | LLM | Tools)。

3. **Phase 3: LangGraph 编排 (Day 5-7)**

- 定义 `AgentState` (TypedDict)。
- 实现 `dispatcher`, `planner`, `executor` 函数。
- 构建 Graph 连线，配置 Checkpointer。

4. **Phase 4: 人机交互与测试 (Day 8-9)**

- 实现 `human_review_node` 的中断逻辑。
- 开发 FastAPI 接口对接 Graph。
- 测试：模拟“写文案 -> 触发合规审核 -> 人工驳回 -> 重写”的闭环。
