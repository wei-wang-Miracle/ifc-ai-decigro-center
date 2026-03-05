# 上下文工程技术文档

> **模块路径**: `ai-engine/src/ai_engine/context/`
> **适用版本**: ai-engine v0.3+
> **关联场景**: 基金销售方案生成（多轮对话 + 跨轮次任务记忆）

---

## 一、为什么需要上下文工程

### 1.1 问题背景

LangGraph 的 `AgentState` 原生支持 `messages` 字段作为对话历史，但这是一个 **无界限的消息追加器**：

- 每轮对话追加原始 `HumanMessage` 和 `AIMessage`，长度无上限
- Token 消耗随轮次线性增长，多轮后 Prompt 超窗口
- 不区分"闲聊"与"任务执行结论"，所有内容混在一起
- 没有实体追踪，意图识别节点无法知道用户上一轮说的"它"指的是哪支基金

### 1.2 设计目标

| 目标 | 实现方式 |
|------|---------|
| 跨轮次记忆：让下一轮能"记得"上一轮做了什么 | `SessionContext` 持久化任务记忆 |
| Token 可控：历史不随轮次无限膨胀 | 滑动窗口 + 文本压缩截断 |
| 实体追踪：基金代码等关键信息自动穿透对话 | 正则提取 + `tracked_entities` 字典 |
| 避免重复工具调用：第二轮同基金任务复用第一轮数据 | `TaskMemory` 步骤输出注入执行器 |
| 节点解耦：各节点无需自行管理历史 | 入口统一注入 `AgentState` |

---

## 二、技术架构

### 2.1 模块结构

```
ai-engine/src/ai_engine/
├── context/
│   ├── __init__.py          # 对外暴露 ContextManager, get_context_manager
│   ├── models.py            # 数据模型：ConversationTurn, TaskMemory, SessionContext, ContextWindow
│   └── manager.py           # 核心逻辑：ContextManager 单例
│
└── graph/
    ├── state.py             # AgentState：新增 3 个 context_* 字段
    ├── nodes/
    │   ├── intent_recognition_node.py   # 读：context_turns/entities/task_memory → Prompt
    │   ├── plan_task_execute_node.py    # 读：context_task_memory → 执行器 Prompt
    │   └── responder_node.py            # 写：record_turn() + build_task_memory()
    └── ...
api/
└── routes.py                # 注入：每次新请求前 build_context_window() → create_initial_state()
```

### 2.2 数据模型层级

```
ContextManager (全局单例, asyncio.Lock 保护)
  └── _sessions: dict[session_id, SessionContext]
        └── SessionContext
              ├── turns: list[ConversationTurn]     # 滑动窗口，最近 10 轮
              ├── task_memories: list[TaskMemory]   # 滑动窗口，最近 5 次 TASK
              └── tracked_entities: dict            # 跨轮次实体（如 fund_code）
                    └── ConversationTurn
                          ├── turn_id, query, rewritten_query
                          ├── response (截断至 400 字)
                          ├── intent_type (task/chat/end)
                          └── entities: dict
                    └── TaskMemory
                          ├── task_id, turn_id
                          ├── entities: dict           # 从 query 和步骤输出提取
                          ├── step_outputs: dict       # step_id → 截断输出 (≤300 字)
                          └── final_output_summary     # 截断至 500 字
```

---

## 三、核心技术实现

### 3.1 ContextManager

**位置**: [context/manager.py](../ai-engine/src/ai_engine/context/manager.py)

单例模式，持有所有会话的上下文状态。所有写操作通过 `asyncio.Lock` 保证并发安全。

```python
class ContextManager:
    def __init__(self):
        self._sessions: dict[str, SessionContext] = {}
        self._lock = asyncio.Lock()
```

**全局常量（Token 预算控制）**：

```python
_MAX_TURNS = 10              # 对话历史保留最近 N 轮
_MAX_TASK_MEMORIES = 5       # 任务记忆保留最近 M 次
_MAX_STEP_OUTPUT_LEN = 300   # 每个步骤输出的最大字符数
_MAX_TURN_RESPONSE_LEN = 400 # 每轮响应的最大字符数
_MAX_TASK_SUMMARY_LEN = 500  # 任务最终摘要的最大字符数
```

**核心方法**：

| 方法 | 性质 | 用途 |
|------|------|------|
| `build_context_window(session_id, current_query)` | 只读 | 构建注入 Prompt 的上下文快照 |
| `record_turn(session_id, ...)` | 异步写 | 每轮结束后更新会话状态 |
| `build_task_memory(task_id, ...)` | 纯函数 | 从步骤结果构建压缩任务记忆 |
| `clear_session(session_id)` | 写 | 清除会话（测试/重置用） |

### 3.2 实体提取

**位置**: [context/manager.py:32-57](../ai-engine/src/ai_engine/context/manager.py)

当前支持两种来源的实体提取：

```python
# 从用户 query 提取（请求开始时）
_FUND_CODE_RE = re.compile(r'\b(\d{6})\b')   # 6 位基金代码

def _extract_entities_from_query(query: str) -> dict:
    fund_codes = _FUND_CODE_RE.findall(query)
    if fund_codes:
        entities["fund_code"] = fund_codes[0]   # 主基金代码
        if len(fund_codes) > 1:
            entities["fund_codes"] = fund_codes  # 多基金列表

# 从步骤输出提取（任务完成时）
def _extract_entities_from_step_outputs(step_outputs: dict) -> dict:
    all_text = " ".join(step_outputs.values())
    fund_codes = _FUND_CODE_RE.findall(all_text)
    if fund_codes:
        entities["fund_codes_mentioned"] = list(set(fund_codes))
```

提取的实体写入 `SessionContext.tracked_entities`，在 `_build_entities_summary()` 中序列化为可读文本注入 Prompt。

### 3.3 上下文窗口构建

**位置**: [context/manager.py:105-145](../ai-engine/src/ai_engine/context/manager.py)

`build_context_window()` 是**只读操作**，无副作用，可安全地在请求入口调用：

```python
def build_context_window(
    self,
    session_id: str,
    current_query: str = "",
    step_results: list = None,      # 当前任务已完成步骤（黑板）
    relevant_task_ids: list[str] = None,
) -> ContextWindow:
    window.recent_turns_summary       = self._build_turns_summary(session)
    window.tracked_entities_summary   = self._build_entities_summary(session, current_query)
    window.relevant_task_memory_summary = self._build_task_memory_summary(session, current_query)
    window.current_task_step_context  = self._build_step_context(step_results)  # 黑板
    return window
```

**任务记忆相关性过滤**（避免不相关历史噪音）：

```python
# 当前 query 提到基金代码时，只返回涉及该基金的历史任务记忆
current_fund = current_entities.get("fund_code", "")
if current_fund:
    relevant = [m for m in memories
                if m.entities.get("fund_code") == current_fund
                or current_fund in str(m.entities.get("fund_codes_mentioned", []))]
```

### 3.4 ContextWindow 数据模型

**位置**: [context/models.py:70-119](../ai-engine/src/ai_engine/context/models.py)

```python
@dataclass
class ContextWindow:
    recent_turns_summary: str = ""          # 注入意图识别节点
    tracked_entities_summary: str = ""      # 注入意图识别 + 执行节点
    relevant_task_memory_summary: str = ""  # 注入执行节点（避免重复工具调用）
    current_task_step_context: str = ""     # 注入执行节点（步骤间黑板）

    def to_prompt_block(self, sections: list[str] = None) -> str:
        """按需序列化为可注入 Prompt 的 Markdown 文本块"""
```

---

## 四、数据流转

### 4.1 完整请求生命周期

```
┌──────────────────────────────────────────────────────────┐
│  请求入口 routes.py / start_workflow_stream              │
│                                                          │
│  ctx_mgr = get_context_manager()                        │
│  ctx_window = ctx_mgr.build_context_window(             │
│      session_id, current_query                          │  ← 只读，无副作用
│  )                                                       │
│  _initial_state = create_initial_state(                 │
│      ...,                                               │
│      context_turns_summary    = ctx_window.recent_...  │
│      context_entities_summary = ctx_window.tracked_... │  ← 注入 AgentState
│      context_task_memory_summary = ctx_window.task_... │
│  )                                                       │
└───────────────────┬──────────────────────────────────────┘
                    │ AgentState 携带 context_* 字段
                    ▼
┌──────────────────────────────────────────────────────────┐
│  intent_recognition_node                                 │
│                                                          │
│  context_summary = _build_context_summary(state)        │
│    ├── state.context_turns_summary    → "### 近期对话"   │  ← 读 AgentState
│    ├── state.context_entities_summary → "### 关键实体"   │
│    └── state.context_task_memory_summary → "### 历史结论"│
│                                                          │
│  prompt = INTENT_RECOGNITION_PROMPT.format(             │
│      context_summary=context_summary, ...               │  ← 注入 LLM Prompt
│  )                                                       │
│  result = LLM(prompt) → IntentResult                   │
│                                                          │
│  → 路由到 dispatcher → executor                         │
└───────────────────┬──────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────┐
│  plan_task_execute_node (_execute_step_with_agent)       │
│                                                          │
│  task_memory_summary = state.context_task_memory_summary│  ← 读 AgentState
│                                                          │
│  if task_memory_summary:                                │
│      execution_prompt_parts.append(                     │
│          "## 历史相关任务结论（可直接参考）\n..."         │  ← 注入执行器 Prompt
│      )                                                   │
│                                                          │
│  # 步骤完成后结果写入 state.step_results（黑板）         │
└───────────────────┬──────────────────────────────────────┘
                    │ state.step_results（当次任务内共享）
                    ▼
┌──────────────────────────────────────────────────────────┐
│  responder_node                                          │
│                                                          │
│  summary = LLM 汇总(step_results)                      │
│                                                          │
│  task_memory = ctx_mgr.build_task_memory(               │
│      task_id, query, step_results, summary              │  ← 构建任务记忆
│  )                                                       │
│                                                          │
│  asyncio.create_task(                                   │  ← 异步写，不阻塞响应
│      ctx_mgr.record_turn(                               │
│          session_id, user_id, turn_id,                  │
│          query, rewritten_query, summary,               │  ← 写入 ContextManager
│          intent_type, entities, task_memory             │
│      )                                                   │
│  )                                                       │
└──────────────────────────────────────────────────────────┘
                    │ ContextManager 持久化
                    │ SessionContext.turns 追加
                    │ SessionContext.task_memories 追加
                    │ tracked_entities 更新
                    ▼
              下一次请求 → routes.py → build_context_window() → 闭环
```

### 4.2 跨轮次数据流转细节

**第 N 轮 → 写入**:
```
responder_node
  ├── record_turn() ──写──→ SessionContext.turns[N]
  │     ├── query = "生成 513130 的销售方案"
  │     ├── rewritten_query = "生成恒生科技ETF(513130)完整销售方案"
  │     ├── response = "## 恒生科技ETF销售方案\n..."
  │     ├── intent_type = "task"
  │     └── entities = {"rewritten_query": "...", "original_query": "..."}
  │
  └── build_task_memory() ──写──→ SessionContext.task_memories[N]
        ├── entities = {"fund_code": "513130", "fund_codes_mentioned": ["513130"]}
        ├── step_outputs = {
        │     "1": "恒生科技ETF，规模8.9亿，费率0.5%，近一年涨32%...",
        │     "2": "匹配到C4积极型+港股偏好客群，共120人...",
        │     "3": "销售方案已生成，话术15条，推送时间建议周三..."
        │   }
        └── final_output_summary = "## 恒生科技ETF销售方案\n..."
```

**第 N+1 轮 → 读取**:
```
routes.py build_context_window("S001", "帮我看看这个基金的客群")
  │
  ├── _build_turns_summary()
  │     └── "[10:23][task] 用户：生成 513130 的销售方案\n         助手：## 恒生科技ETF销售方案..."
  │
  ├── _build_entities_summary(current_query="帮我看看这个基金的客群")
  │     └── "当前会话中识别到的关键实体：\n- 基金代码: 513130"
  │
  └── _build_task_memory_summary(current_query=...)
        └── "[任务 task_abc... @ 10:23]\n  涉及实体: fund_code=513130\n  步骤1结果: ...\n  最终结论: ..."

→ create_initial_state(context_entities_summary="...基金代码: 513130...")
→ intent_recognition_node 用上下文将"这个基金"解析为 513130
```

---

## 五、场景模拟

### 场景：基金销售方案多轮对话

#### 第 1 轮 — 新会话，无历史

```
用户: "帮我生成 513130 的销售方案"

routes.py:
  ctx_mgr.build_context_window("session_001", "帮我生成 513130 的销售方案")
  → ContextWindow (全空，session_001 是新会话)
  → create_initial_state(context_turns_summary="", ...)

intent_recognition_node:
  context_summary = "无历史对话上下文"
  LLM 识别：intent_type=TASK, rewritten_query="生成恒生科技ETF(513130)完整销售方案"

plan_task_execute_node:
  task_memory_summary = ""  → 无历史提示，正常调用工具
  步骤1: 调用 get_fund_info("513130") → 返回基金详情
  步骤2: 调用 match_customer_group(profile) → 匹配客群
  步骤3: 调用 generate_sales_plan(fund, groups) → 生成方案

responder_node:
  summary = "## 恒生科技ETF销售方案\n..."
  build_task_memory(step_results) → TaskMemory{fund_code:"513130", step_outputs:{...}}
  record_turn() → 写入 session_001

ContextManager 状态（session_001）:
  turns[0] = {query:"帮我生成...", response:"## 恒生科技...", intent:"task"}
  task_memories[0] = {fund_code:"513130", step_outputs:{1:..., 2:..., 3:...}}
  tracked_entities = {"fund_code": "513130"}
```

#### 第 2 轮 — 指代消歧 + 跨轮次记忆

```
用户: "帮我看看这个基金的客群情况"（"这个基金"指 513130，未明说）

routes.py:
  ctx_mgr.build_context_window("session_001", "帮我看看这个基金的客群情况")
  → recent_turns_summary:
      "[10:23][task] 用户：帮我生成 513130 的销售方案
               助手：## 恒生科技ETF销售方案..."
  → tracked_entities_summary:
      "当前会话中识别到的关键实体：
       - 基金代码: 513130"
  → relevant_task_memory_summary:
      "[任务 task_abc... @ 10:23]
        涉及实体: fund_code=513130
        步骤1结果: 恒生科技ETF，规模8.9亿，费率0.5%...
        步骤2结果: 匹配到C4积极型+港股偏好客群，共120人...
        最终结论: ## 恒生科技ETF销售方案..."

intent_recognition_node:
  context_summary 包含 "基金代码: 513130"
  LLM 识别：
    rewritten_query = "查看513130恒生科技ETF的匹配客群详情"  ← 自动消歧
    intent_type = TASK

plan_task_execute_node:
  task_memory_summary 包含：
    "步骤2结果: 匹配到C4积极型+港股偏好客群，共120人..."
  LLM 判断：客群数据已在历史记忆中
  → 跳过 match_customer_group 工具调用，直接引用历史结果
  → Token 节省，延迟降低
```

#### 第 3 轮 — 明确结束

```
用户: "谢谢，没有其他问题了"

intent_recognition_node:
  LLM 识别：intent_type = END
  goto = "__end__"  ← 直接结束，不经过 dispatcher

（本轮不产生 step_results，responder_node 透传上游 normal_node 的回复）
record_turn() 写入：{intent_type:"end", response:"好的，再见！"}
```

### 场景：Token 预算效果对比

| | 无上下文管理 | 有上下文管理 |
|--|------------|------------|
| 第5轮 messages 长度 | 原始对话 × 5 轮累积 | 最近 10 轮压缩摘要 |
| 实体识别准确率 | 依赖 LLM 记忆，多轮后退化 | 结构化 tracked_entities，稳定 |
| 重复工具调用 | 每轮独立执行相同工具 | TaskMemory 复用历史步骤结果 |
| Prompt 大小（第5轮） | ~8000 tokens | ~2000 tokens（摘要压缩后） |

---

## 六、扩展设计说明

### 6.1 为何选择纯内存实现

当前选择内存存储（非 Redis/数据库）基于以下权衡：

- **部署简单**：无外部依赖，单进程即可完整运行
- **延迟极低**：内存读写 < 1ms，不增加请求链路延迟
- **适配阶段**：上下文模块初期验证阶段，功能优先于持久化

**生产演进路径**：可将 `_sessions` 替换为 Redis Hash 结构，`record_turn` 和 `build_context_window` 的接口签名不变，节点代码无需修改。

### 6.2 实体扩展

当前只提取基金代码（6位数字），扩展方式：

```python
# 在 manager.py 中添加新正则
_ISIN_RE = re.compile(r'\b[A-Z]{2}\d{10}\b')        # ISIN 证券编码
_ACCOUNT_ID_RE = re.compile(r'\b账户[：:]?\s*(\w+)\b')  # 账户编号

def _extract_entities_from_query(query: str) -> dict:
    # 新增提取逻辑
    isin_codes = _ISIN_RE.findall(query)
    if isin_codes:
        entities["isin"] = isin_codes[0]
```

### 6.3 当前限制

- **进程重启丢失**：纯内存实现，服务重启后所有会话上下文清空
- **单进程绑定**：多实例部署时不同实例无法共享上下文（需改为外部存储）
- **任务记忆相关性依赖正则**：只能按实体（基金代码）过滤历史，复杂语义相关性需接入向量检索
- **实体类型有限**：目前只支持 6 位基金代码，其他业务实体需手动扩展正则

---

## 七、关键文件索引

| 文件 | 职责 |
|------|------|
| [context/models.py](../ai-engine/src/ai_engine/context/models.py) | 数据模型定义（ConversationTurn, TaskMemory, SessionContext, ContextWindow） |
| [context/manager.py](../ai-engine/src/ai_engine/context/manager.py) | ContextManager 核心逻辑 + 全局单例 |
| [graph/state.py](../ai-engine/src/ai_engine/graph/state.py) | AgentState 中的 `context_*` 字段定义 |
| [api/routes.py](../ai-engine/src/ai_engine/api/routes.py) | 请求入口：`build_context_window` → `create_initial_state` |
| [graph/nodes/intent_recognition_node.py](../ai-engine/src/ai_engine/graph/nodes/intent_recognition_node.py) | 消费 `context_*` 字段，构建意图识别上下文摘要 |
| [graph/nodes/plan_task_execute_node.py](../ai-engine/src/ai_engine/graph/nodes/plan_task_execute_node.py) | 消费 `context_task_memory_summary`，注入执行器 Prompt |
| [graph/nodes/responder_node.py](../ai-engine/src/ai_engine/graph/nodes/responder_node.py) | 写入：`record_turn()` + `build_task_memory()` |
