# 智能体多级记忆系统实现文档

> 版本：1.0 | 对应分支：workflow-0215 | 最后更新：2026-03-06

---

## 目录

1. [架构概览](#架构概览)
2. [技术组件](#技术组件)
3. [启动流程](#启动流程)
4. [请求处理流程](#请求处理流程)
5. [后台 Reflection 流程](#后台-reflection-流程)
6. [典型场景](#典型场景)
7. [数据流转](#数据流转)
8. [配置参考](#配置参考)
9. [关键设计决策](#关键设计决策)

---

## 架构概览

系统实现 CoALA 三层记忆架构，每层由独立组件负责，职责不重叠：

```
┌─────────────────────────────────────────────────────────┐
│  工作记忆（Working Memory）                               │
│  AgentState — 单次请求内所有节点共享的运行时状态            │
│  生命周期：单次 workflow.invoke() 调用                     │
└─────────────────────────────┬───────────────────────────┘
                              │ 请求结束后由 checkpointer 持久化
┌─────────────────────────────▼───────────────────────────┐
│  短期记忆（Short-Term Memory）                            │
│  AsyncPostgresSaver — 按 thread_id=session_id 存 messages│
│  ContextManager — 从 messages 构建压缩摘要视图             │
│  生命周期：会话级，支持跨重启恢复                           │
└─────────────────────────────┬───────────────────────────┘
                              │ 任务完成后后台 Reflection 写入
┌─────────────────────────────▼───────────────────────────┐
│  长期记忆（Long-Term Memory）                             │
│  AsyncPostgresStore — 按 user_id namespace 持久化         │
│  LongTermMemoryManager — Profile + Experience 管理        │
│  生命周期：用户级，跨会话永久保存                           │
└─────────────────────────────────────────────────────────┘
```

### 核心组件映射

| 层级 | 存储后端 | 管理器 | Namespace/Key |
|------|---------|--------|---------------|
| 短期记忆 | `AsyncPostgresSaver` | `ContextManager` | `thread_id = session_id` |
| 长期记忆（语义） | `AsyncPostgresStore` | `LongTermMemoryManager` | `("users", user_id, "semantic")` → `"_profile"` |
| 长期记忆（情景） | `AsyncPostgresStore` | `LongTermMemoryManager` | `("users", user_id, "episodic")` → `experience_id` |

---

## 技术组件

### 1. ContextManager（短期记忆压缩视图层）

**文件**：`ai-engine/src/ai_engine/context/manager.py`

**定位**：不存储对话历史（由 checkpointer 负责），只提供"压缩摘要视图"供节点注入 Prompt。

**核心方法**：

```python
class ContextManager:
    # 实体追踪（轻量缓存，session_id -> dict）
    def update_entities(self, session_id: str, entities: dict) -> None
    def get_entities(self, session_id: str) -> dict

    # 上下文窗口构建（只读，从外部传入 messages）
    def build_context_window(
        self,
        session_id: str,
        messages: list[BaseMessage],  # 来自 checkpointer，非内部存储
        current_query: str = "",
        step_results: list = None,
    ) -> ContextWindow

    # 消息修剪（超 10 轮时折叠早期消息）
    async def prune_messages_if_needed(
        self, messages: list[BaseMessage]
    ) -> list[BaseMessage]

    # 任务记忆构建（供 Reflection 使用）
    def build_task_memory(
        self, task_id, turn_id, query, step_results, final_response
    ) -> TaskMemory
```

**消息修剪策略**：
- 阈值：超过 10 轮（HumanMessage 数量）触发
- 保留：最近 6 轮 Human/AI 消息
- 折叠：早期消息调用 LLM 压缩为 `SystemMessage("[早期对话摘要]\n...")`
- 返回：处理后的 messages 列表（调用方通过 State 写回 checkpointer）

---

### 2. LongTermMemoryManager（长期记忆管理器）

**文件**：`ai-engine/src/ai_engine/context/long_term.py`

**定位**：基于 `AsyncPostgresStore`，管理跨会话的用户事实（语义记忆）和成功任务经验（情景记忆）。

**存储类型**：

| 类型 | 模式 | 更新方式 | 读取方式 |
|------|------|---------|---------|
| `SemanticProfile` | Profile（单文档） | JSON Patch 增量合并 | 直接加载全量 |
| `EpisodicExperience` | Collection（多文档） | 追加写入 | 语义检索 Top-K |

**核心方法**：

```python
class LongTermMemoryManager:
    def set_store(self, store) -> None              # lifespan 注入 Store 实例

    # 热路径读取（无 LLM，只做 Store 查询）
    async def retrieve_long_term_context(
        self, user_id: str, query: str
    ) -> str                                        # 返回可注入 Prompt 的文本块

    # 后台写入（非阻塞，create_task）
    def trigger_reflection_async(
        self, user_id, task_id, query, step_results, final_response
    ) -> None                                       # 不阻塞，所有失败静默记录

    # 管理接口（主动遗忘）
    async def delete_episodic_experience(self, user_id, experience_id) -> None
    async def clear_semantic_profile(self, user_id) -> None
```

**Reflection 流程**：
1. 构建任务轨迹文本（步骤结果 + 最终响应）
2. 加载当前 `SemanticProfile`（传给 LLM 防止覆写已有信息）
3. 调用 LLM（`temperature=0.0`），要求严格 JSON 输出
4. 解析 JSON，判断 `has_new_facts` / `has_valuable_experience`
5. 有新事实 → `_apply_semantic_patch()`（按领域子文档合并）
6. 有优质经验 → `_append_episodic_experience()`（追加新文档）
7. 任何步骤失败 → `logger.warning()`，不向上层抛出

**Reflection 输出 JSON 结构**：

```json
{
  "has_new_facts": true,
  "semantic_patch": {
    "basic_info": {"role": "基金经理"},
    "work_prefs": {},
    "domain_facts": {"preferred_style": "价值型"}
  },
  "has_valuable_experience": true,
  "experience": {
    "task_summary": "为恒生科技ETF生成销售方案",
    "intent_type": "task",
    "key_entities": {"fund_code": "513130"},
    "execution_trace": "步骤1: 获取基金信息 → 步骤2: 匹配客群 → 步骤3: 生成方案",
    "outcome": "成功生成针对C4积极型客群的销售话术，涵盖3个核心卖点"
  }
}
```

---

### 3. 数据模型

**文件**：`ai-engine/src/ai_engine/context/models.py`

```python
@dataclass
class SemanticProfile:
    user_id: str
    basic_info: dict[str, Any]    # 基本信息：角色、偏好等
    work_prefs: dict[str, Any]    # 工作偏好：风格、习惯等
    domain_facts: dict[str, Any]  # 领域事实：基金偏好、客群认知等
    updated_at: datetime

    def to_prompt_text(self) -> str   # 序列化为 Prompt 文本

@dataclass
class EpisodicExperience:
    experience_id: str              # UUID hex[:16]，Store key
    user_id: str
    task_summary: str               # 任务描述（≤100字）
    intent_type: str                # 意图类型
    key_entities: dict[str, Any]    # 关键实体
    execution_trace: str            # 执行轨迹压缩（≤300字）
    outcome: str                    # 最终结论（≤200字）
    created_at: datetime

    def to_prompt_text(self) -> str   # 序列化为 few-shot 样例文本
```

---

### 4. AgentState 新增字段

**文件**：`ai-engine/src/ai_engine/graph/state.py`

```python
class AgentState(BaseModel):
    # ...原有字段...

    # 上下文管理：由 ContextManager 在请求开始时注入，节点直接读取使用
    context_turns_summary: str = ""          # 近期对话摘要
    context_entities_summary: str = ""       # 关键实体摘要
    context_task_memory_summary: str = ""    # 历史任务记忆摘要
    long_term_context: str = ""              # 长期记忆检索结果（跨会话）

    # 审计追踪
    node_traces: list[dict] = []
```

`long_term_context` 由 `intent_recognition_node` 检索后通过 Command update 写入，供后续节点在需要时读取。

---

### 5. Workflow 编译器

**文件**：`ai-engine/src/ai_engine/graph/builder.py`

```python
# 生产入口（lifespan 调用）
async def create_workflow_graph_async(pool: AsyncConnectionPool) -> object:
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()    # 幂等建表

    store = AsyncPostgresStore(pool)
    await store.setup()            # 幂等建表

    ltm = get_long_term_memory_manager()
    ltm.set_store(store)           # 注入 Store 单例

    return _build_workflow(checkpointer)

# 测试/开发入口
def create_workflow_graph(checkpointer=None) -> object:
    return _build_workflow(checkpointer or MemorySaver())
```

两个入口共享 `_build_workflow(checkpointer)` 内部函数，保证节点注册一致性。

---

## 启动流程

```
uvicorn ai_engine.main:app
         │
         ▼
lifespan() 启动阶段
         │
         ├─ 1. AsyncConnectionPool(conninfo=DATABASE_URL, min=2, max=10)
         │      └─ await pool.open()
         │         挂载到 app.state.pg_pool
         │
         └─ 2. create_workflow_graph_async(pool)
                │
                ├─ AsyncPostgresSaver(pool).setup()
                │   建表：checkpoints, checkpoint_writes, checkpoint_migrations
                │
                ├─ AsyncPostgresStore(pool).setup()
                │   建表：store（LangGraph Store 标准表）
                │
                ├─ get_long_term_memory_manager().set_store(store)
                │   注入 Store 单例，LTM 此后可用
                │
                └─ _build_workflow(checkpointer) → compiled workflow
                    挂载到 app.state.workflow
```

**关键点**：整个生命周期只有一个 `workflow` 实例，所有请求共享（checkpointer 内部按 `thread_id` 隔离数据）。

---

## 请求处理流程

以 `/chat/stream` 端点为例（`api/routes.py`）：

```
POST /chat/stream {session_id, user_id, query, token}
         │
         ▼
routes.py: start_workflow_stream()
         │
         ├─ 1. 从 app.state.workflow 获取单例 workflow
         │
         ├─ 2. session_config = {"configurable": {"thread_id": session_id}}
         │      注意：thread_id = session_id（不含 task_id，保证跨轮次连续性）
         │
         ├─ 3. snapshot = workflow.get_state(session_config)
         │      existing_messages = snapshot.values.get("messages", [])
         │      从 checkpointer 恢复本 session 的历史 messages
         │
         ├─ 4. ctx_mgr.build_context_window(session_id, existing_messages, query)
         │      构建压缩摘要视图（ContextWindow）
         │
         ├─ 5. create_initial_state(query, user_id, session_id, ...)
         │      注入 context_turns_summary / context_entities_summary 等字段
         │
         └─ 6. workflow.astream(initial_state, session_config, stream_mode="values")
                │
                ▼
         intent_recognition_node
                │
                ├─ A. ltm.retrieve_long_term_context(user_id, query)
                │      └─ 加载 SemanticProfile + 语义检索 EpisodicExperience Top-3
                │         格式化为 Prompt 文本块
                │
                ├─ B. 构建意图识别 Prompt（含 long_term_ctx + context_window）
                │
                ├─ C. LLM 调用 → IntentObject
                │
                └─ D. Command update: intent + long_term_context + (可能的) messages 修剪
                         │
                         ▼
                dispatcher_node → planner_node → executor → responder_node
                                                                    │
                                                                    ├─ 生成最终回复
                                                                    ├─ ctx_mgr.update_entities()
                                                                    └─ ltm.trigger_reflection_async()
                                                                         └─ asyncio.create_task (后台，不阻塞)
```

**`thread_id` 统一规则**：
- 旧实现：`f"{session_id}_{task_id}"`（每次任务创建新线程，丢失历史）
- 新实现：`thread_id = session_id`（同一会话所有轮次共享一个 checkpoint 线程）

---

## 后台 Reflection 流程

Reflection 在 `responder_node` 结束后、响应返回用户前触发，完全在后台运行：

```
responder_node 生成最终回复
         │
         ├─ ctx_mgr.update_entities(session_id, entities)   # 更新实体缓存
         │
         └─ ltm.trigger_reflection_async(user_id, task_id, query, step_results, summary)
                │
                └─ asyncio.create_task(_run_reflection(...))  ← 立即返回，不阻塞
                          │
                          ▼ （后台异步执行，约 1-3 秒）
                   _run_reflection()
                          │
                          ├─ 1. 构建步骤摘要文本
                          │
                          ├─ 2. _load_current_profile_dict(user_id)
                          │      AsyncPostgresStore.aget(("users", uid, "semantic"), "_profile")
                          │
                          ├─ 3. ChatOpenAI(temperature=0.0).ainvoke([SystemMessage, HumanMessage])
                          │      → 严格 JSON 输出
                          │
                          ├─ 4. json.loads(raw)（剥离 ```json 代码块）
                          │
                          ├─ 5a. has_new_facts=true → _apply_semantic_patch()
                          │       ├─ 加载当前 Profile
                          │       ├─ 按领域子文档 dict.update() 合并
                          │       └─ AsyncPostgresStore.aput(("users", uid, "semantic"), "_profile", data)
                          │
                          └─ 5b. has_valuable_experience=true → _append_episodic_experience()
                                  ├─ 创建 EpisodicExperience(experience_id=uuid4.hex[:16])
                                  └─ AsyncPostgresStore.aput(("users", uid, "episodic"), exp_id, data)
```

**失败处理**：每个步骤均有独立 try/except，失败时 `logger.warning()` 后继续，不影响已返回给用户的响应。

**触发条件**：仅当 `step_results` 非空时触发（即仅 TASK 场景，CHAT 场景不触发）。

---

## 典型场景

### 场景 A：用户首次对话

```
用户 U001，首次发送消息，无任何历史记录

1. routes.py: get_state() → snapshot.values = {}，existing_messages = []
2. build_context_window([], "...") → ContextWindow（全部字段为空）
3. intent_recognition_node:
   - ltm.retrieve_long_term_context("U001", query)
     → _load_semantic_profile_text: Store.aget → None → 返回 ""
     → _search_episodic_experiences: Store.asearch → [] → 返回 ""
     → 最终 long_term_ctx = ""
   - _build_context_summary 中 long_term_ctx 段不输出
4. workflow 正常执行，回复用户
5. responder_node: trigger_reflection_async（若 TASK 场景）
   → 后台创建首条 SemanticProfile / EpisodicExperience
```

### 场景 B：同一会话多轮对话

```
用户 U001，session_id=S001，第 3 轮对话

1. routes.py: get_state({"thread_id": "S001"})
   → existing_messages = [H1, A1, H2, A2]（2轮历史）

2. build_context_window(session_id="S001", messages=[H1,A1,H2,A2], query=Q3)
   → _build_turns_summary_from_messages: 格式化最近 2 轮对话摘要
   → merged_entities: 缓存实体 + Q3 中提取的实体

3. initial_state.context_turns_summary = "用户：Q1\n助手：A1\n用户：Q2\n助手：A2"

4. workflow 执行，checkpointer 自动将 Q3/A3 追加到 messages
   （thread_id="S001" 下持久化）
```

### 场景 C：跨会话长期记忆注入

```
用户 U001，上周曾完成一次基金分析任务（session_id=S001）
本周新开会话（session_id=S002），发起相关查询

1. get_state({"thread_id": "S002"}) → 无历史消息（新会话）
2. intent_recognition_node:
   - ltm.retrieve_long_term_context("U001", "帮我分析一下恒生科技ETF")
     → SemanticProfile: "基本信息: {'role': '基金经理'}\n领域事实: {'preferred_style': '价值型'}"
     → EpisodicExperience Top-1: "[经验 a3b2c1d0] 为恒生科技ETF生成销售方案\n
        涉及实体: {'fund_code': '513130'}\n执行路径: ...\n执行结论: ..."
   - Prompt 中增加 "### 用户长期记忆（事实与经验）" 段落

3. 意图识别 LLM 拥有用户历史背景，识别更准确
4. long_term_context 写入 AgentState，后续节点可直接读取
```

### 场景 D：超过 10 轮消息修剪

```
用户在 session_id=S001 下已完成 12 轮对话

1. routes.py 恢复 existing_messages = [H1,A1,...,H12,A12]（24条）
2. build_context_window 中 _build_turns_summary_from_messages 只取最近 10 对

3. intent_recognition_node 处理时，若判断需要修剪：
   ctx_mgr.prune_messages_if_needed(state.messages)
   → 轮次计数 = 12 > 10，触发修剪
   → 保留最近 6 轮（H7~H12, A7~A12）
   → 早期 H1~H6, A1~A6 → LLM 压缩为 SystemMessage("早期对话摘要\n...")
   → 返回 [SystemMessage, H7,A7,...,H12,A12]

4. 通过 Command update 将修剪后 messages 写回 checkpointer
   (下次请求恢复时已是修剪后的版本)
```

---

## 数据流转

### 完整数据流图

```
用户请求
   │
   ▼
[routes.py]
   ├─ checkpointer.get_state(session_id)
   │      ↓ 恢复
   │   existing_messages[]
   │      ↓ 输入
   ├─ ContextManager.build_context_window()
   │      ↓ 输出
   │   ContextWindow{turns_summary, entities_summary}
   │      ↓ 注入
   ├─ create_initial_state()
   │      ↓ 生成
   │   AgentState{query, context_turns_summary, context_entities_summary, ...}
   │
   ▼
[intent_recognition_node]
   ├─ LongTermMemoryManager.retrieve_long_term_context(user_id, query)
   │      ├─ Store.aget(("users", uid, "semantic"), "_profile") → SemanticProfile text
   │      └─ Store.asearch(("users", uid, "episodic"), query, limit=3) → EpisodicExperience text
   │      ↓ 返回
   │   long_term_ctx: str
   │      ↓ 拼入 Prompt
   ├─ LLM(intent_prompt + long_term_ctx + context_window)
   │      ↓ 输出
   │   IntentObject{intent_type, entities, ...}
   │      ↓ Command update
   │   State.intent, State.long_term_context
   │
   ▼
[dispatcher → planner → executor]
   ├─ 读取 State.long_term_context（可选，供 Planner 参考）
   ├─ 读取 State.context_turns_summary, context_entities_summary
   └─ 写入 State.plan, step_results
   │
   ▼
[responder_node]
   ├─ 生成最终 summary 回复用户
   ├─ ContextManager.update_entities(session_id, entities)
   │      └─ 更新 in-memory 实体缓存
   └─ LongTermMemoryManager.trigger_reflection_async(...)
          └─ asyncio.create_task(_run_reflection)
                 │（后台异步，约 1-3 秒）
                 ├─ LLM 分析任务轨迹
                 ├─ Store.aput(("users", uid, "semantic"), "_profile", {...})  ← 更新语义记忆
                 └─ Store.aput(("users", uid, "episodic"), exp_id, {...})      ← 追加情景记忆
   │
   ▼
[checkpointer 自动持久化]
   └─ 将本轮 HumanMessage + AIMessage 追加到 thread_id=session_id 的 checkpoint
```

### 各组件数据存储位置

| 数据 | 存储位置 | Key | 读取时机 |
|------|---------|-----|---------|
| 对话消息（messages） | PostgreSQL（checkpointer 表） | `thread_id=session_id` | 每次请求开始时恢复 |
| 实体缓存（tracked_entities） | 进程内存（ContextManager._entity_cache） | `session_id` | 每次请求 build_context_window |
| 用户事实（SemanticProfile） | PostgreSQL（Store 表） | `("users", uid, "semantic")._profile` | 每次请求 intent_node 检索 |
| 用户经验（EpisodicExperience） | PostgreSQL（Store 表） | `("users", uid, "episodic").{exp_id}` | 每次请求 intent_node 语义检索 |
| 工作状态（AgentState 其余字段） | 进程内存（LangGraph 运行时） | 仅单次请求内有效 | — |

---

## 配置参考

### 关键参数（`context/manager.py`）

```python
_MAX_TURNS_IN_WINDOW = 10      # 超过此轮次触发消息修剪
_MAX_STEP_OUTPUT_LEN = 300     # 每个步骤输出的最大保留字符数
_MAX_TURN_RESPONSE_LEN = 400   # 每轮响应的最大保留字符数
_MAX_TASK_SUMMARY_LEN = 500    # 任务最终摘要的最大保留字符数
```

修剪保留策略：保留最近 6 轮（`keep_rounds = 6`），更早的折叠为 `SystemMessage`。

### 关键参数（`context/long_term.py`）

```python
_TOP_K_EPISODIC = 3            # 情景记忆检索 Top-K 数量
# Reflection 截断限制（在 _REFLECTION_HUMAN prompt 中定义）
# execution_trace ≤ 300字，outcome ≤ 200字
```

### 依赖包

```toml
# pyproject.toml 新增
"langgraph-checkpoint-postgres>=2.0.0"  # AsyncPostgresSaver + AsyncPostgresStore
"psycopg[binary]>=3.2.1"               # PostgreSQL 异步驱动
"psycopg-pool>=3.2.1"                  # 连接池
```

---

## 关键设计决策

### 1. ContextManager 保留为"压缩视图层"而非废弃

对话历史持久化完全交给 checkpointer，ContextManager 不再存储 `messages`，只负责：
- 接收 checkpointer 恢复的 messages → 构建摘要文本
- 维护轻量的 in-memory 实体缓存（`session_id → entities`）
- 提供消息修剪能力（超阈值时折叠早期消息）

**好处**：消除双写，checkpointer 是唯一真实来源。

### 2. thread_id = session_id（不含 task_id）

旧实现使用 `f"{session_id}_{task_id}"` 导致每次新任务创建新 checkpoint 线程，历史消息丢失。新实现统一使用 `session_id` 作为 thread_id，所有轮次的消息在同一线程下持续追加。

### 3. 长期记忆写入完全异步（双轨更新）

- **热路径**（checkpointer）：同步写入，阻塞请求，确保对话历史可靠持久化
- **冷路径**（Reflection）：`asyncio.create_task` 在后台运行，任何失败不影响已返回的响应

用户感受到的延迟只有 checkpointer 写入（< 100ms），Reflection（约 1-3 秒）对用户透明。

### 4. SemanticProfile 按领域子文档拆分

将用户事实拆分为 `basic_info`、`work_prefs`、`domain_facts` 三个子文档，Reflection 只更新有变化的子文档（`dict.update` 合并），避免 LLM 生成整体 Profile 时因字段过多导致格式崩溃或覆写已有信息。

### 5. EpisodicExperience 使用 Collection 模式

每条经验独立存储（key = `experience_id`），支持：
- 按 query 语义检索 Top-K（避免加载所有经验）
- 主动遗忘单条记录（`delete_episodic_experience`）
- 数量无上限，不影响上下文窗口大小

### 6. 单例 Workflow 共享连接池

`app.state.workflow` 在 lifespan 中初始化一次，所有请求共享。checkpointer 内部使用传入的 `pool`（`AsyncConnectionPool`），连接池自动管理并发连接复用，无需每请求重建 workflow。
