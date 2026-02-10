# 产品需求文档 (PRD)：AI 全链路审计监控

| 项目名称     | AI 全链路审计监控 (AI-ATM)                   |
| ------------ | -------------------------------------------- |
| **版本号**   | V1.0                                         |
| **文档状态** | Draft                                        |
| **核心架构** | **List Source:** PostgreSQL (Rich Index)<br> |

<br>**Detail Source:** Elasticsearch (Full Payload) |
| **目标用户** | 审计员、研发工程师、产品经理、合规专员 |

---

## 1. 项目背景与目标

为了满足企业级 AI 应用的**可审计性**与**可追溯性**需求，我们需要构建一个可视化监控台。该平台不仅要能宏观统计 token 消耗与响应延迟，更核心的能力是**“案发现场还原”**——即通过 Trace ID 快速定位，并以时间轴形式重现“用户提问 -> 思维链(CoT) -> 工具调用 -> 最终回复”的全过程。

PG 宽表 (ai_chat_trace_index)：承担 90% 的日常查询、筛选、统计需求，确保存储成本低、查询速度快。

ES 文档 (ai_chat_trace_index_snapshot)：承担 10% 的深度溯源需求，记录完整的思维链、工具出入参和上下文。

---

## 2. 总体流程图

用户在列表页通过 PostgreSQL 的索引字段进行筛选，点击单条记录后，通过 `trace_id` 去 Elasticsearch 拉取完整的对话 Payload 和执行堆栈进行渲染。
数据库准备：
PostgreSQL 和 ES 均部署在本地，ES当前没有密码，注意PUT初始化索引时，需要指定字段的类型，否则默认都是text类型，无法进行范围查询和精确查询。

---

## 2.1 数据库设计

数据库设计理念：
我们将字段分为四个维度，以满足不同角色的审计需求：

1. **链路指纹 (Identity)**：谁在什么时候发起了什么？（基础审计）
2. **执行画像 (Profile)**：任务有多复杂？用了什么工具？（技术审计）
3. **效能账本 (Economics)**：花了多少钱？耗了多少时？（财务/性能审计）
4. **内容摘要 (Content Shadow)**：大概聊了什么？有没有风险？（合规审计）

### 2.1.1 数据模型设计：

**数据源：** PostgreSQL (`ai_chat_trace_index` 表)
**核心价值：** 快速筛选、异常发现、宏观透视。

```sql
-- 表名：ai_chat_trace_index
-- 分表策略建议：按 create_time 进行 Range Partition（月度或季度），以应对海量数据。

CREATE TABLE ai_chat_trace_index (
    -- === 1. 链路指纹 (Identity) ===
    trace_id        VARCHAR(64) PRIMARY KEY,      -- 全局唯一请求ID (与 ES _id 对应)
    session_id      VARCHAR(64) NOT NULL,         -- 会话ID
    task_id         VARCHAR(64),                  -- 异步任务ID (可空)
    user_id         VARCHAR(64) NOT NULL,         -- 用户ID
    dept_id         VARCHAR(64),                  -- 部门ID
    tenant_code     VARCHAR(32),                  -- 多租户隔离字段

    -- === 2. 智能体画像 (Agent Profile) ===
    agent_name      VARCHAR(64) NOT NULL,         -- 入口 Agent 名称
    agent_version   VARCHAR(32),                  -- Agent 版本号
    model_provider  VARCHAR(32),                  -- 模型底座 (e.g., "gpt-4-turbo")
    user_feedback   SMALLINT DEFAULT 0,           -- 用户反馈 (e.g., 1, 0, -1)

    -- === 3. 摘要与透视 (Summary & Insight) ===
    -- 关键：使用 JSONB 存储标签，利用 GIN 索引加速“包含”查询
    user_intent     VARCHAR(200),                  -- 用户意图 意图识别节点提供
    user_trace_query VARCHAR(500),                -- 用户本次请求的提问信息 (前200字符)，超出部分自动截断
    ai_trace_response VARCHAR(500),               -- AI 本次回复的内容 (前200字符)超出部分自动截断
    execution_path   JSONB DEFAULT '[]'           -- 之前经过的节点agent_name列表
    tools_used       JSONB DEFAULT '[]',           -- 本次agent使用的工具名称tool_name列表

    -- === 4. 状态与合规 (Status & Compliance) ===
    status          VARCHAR(20) NOT NULL,         -- SUCCESS, FAILED, RUNNING, INTERRUPTED
    failure_reason  VARCHAR(255),                 -- 简短的失败原因 (长堆栈存 ES)

    -- === 5. 效能账本 (Metrics) ===
    trace_latency_ms INT,                         -- trace 总耗时
    trace_total_tokens     INT,                         -- trace 总 Token 消耗
    trace_input_tokens     INT,                         -- trace 提示词 Token
    trace_output_tokens    INT,                         -- trace 输出 Token

    -- === 6. 时序 (Timing) ===
    create_time       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    update_time       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- ==========================================
-- ⚡️ 核心索引设计 (Performance Boosters)
-- ==========================================

-- 1. 基础列表查询 (最常用的默认视图)
-- 场景：用户打开控制台，默认看最近的记录
CREATE INDEX idx_chat_trace_time ON ai_chat_trace_index (create_time DESC);

-- 2. 用户维度的历史查询
-- 场景：查看 "张三" 过去所有的对话
CREATE INDEX idx_chat_trace_user ON ai_chat_trace_index (user_id, create_time DESC);

-- 3. 部门/租户级审计 (B端多租户必备)
CREATE INDEX idx_chat_trace_tenant_dept ON ai_chat_trace_index (tenant_code, dept_id);
```

### ES Document (Detail)

ES中需要存储详细信息 index:ai_chat_trace_index_snapshot

```json
{
  "trace_id": "tr_20240210_8888",
  "session_id": "sess_user_007",
  "task_id": "task_1234567890",
  "user_id": "u_zhangsan",
  "dept_id": "dept_001",
  "start_time": "2024-02-10T10:30:00.000Z",
  "graph_nodes": [
    {
      "node_name": "intent_recognition",
      "start_time": "2024-02-10T10:30:00.000Z",
      "status": "SUCCESS",
      "agent_snapshots": [
        {
          "agent_name": "FinancialBot",
          "agent_version": "v2.5.1",
          "model_config": {
            "provider": "openai",
            "model_name": "gpt-4-turbo",
            "temperature": 0.5,
            "top_p": 0.9,
            "max_tokens": 4096
          },
          "system_prompt": "你是一个金融助手。在回答股价问题时，必须先使用工具查询实时数据，严禁编造。",
          "status": "PENDING/IN_PROGRESS/COMPLETED",
          "latency_ms": 800,
          "tools_snapshot": [
            {
              "tool_name": "stock_api_search",
              "tool_type": "HTTP",
              "start_time": "2024-02-10T10:30:01.000Z",
              "latency_ms": 800,
              "status": "SUCCESS",
              "input_args": "{\"symbol\": \"TSLA\"}",
              "output_result": "{\"price\": 195.50, \"currency\": \"USD\"}"
            }
          ]
        }
      ]
    }
  ]
}
```

## 3. 功能模块详解

### 3.1 模块一：全链路追踪列表 (Trace List)

**数据源：** PostgreSQL `ai_chat_trace_index`
**核心价值：** 利用 PG 的索引能力，提供秒级的多维度筛选。

#### 3.1.1 筛选区 (Filter Bar)

对应 SQL 中的索引字段，支持以下组合查询：

| 筛选字段      | 控件类型        | 对应数据库字段           | 逻辑说明                                       |
| ------------- | --------------- | ------------------------ | ---------------------------------------------- |
| **时间范围**  | DateRangePicker | `create_time`            | 默认近 24 小时，精确到秒                       |
| **Trace ID**  | Input           | `trace_id`               | 精确匹配                                       |
| **用户 ID**   | Input           | `user_id`                | 精确匹配                                       |
| **部门/租户** | Select          | `dept_id`, `tenant_code` | 级联选择 (B端场景)                             |
| **Agent名称** | Select/Search   | `agent_name`             | 下拉选择                                       |
| **执行状态**  | Multi-Select    | `status`                 | SUCCESS, FAILED, RUNNING                       |
| **包含工具**  | Search          | `tools_used` (JSONB)     | 输入工具名 (e.g., "search")，利用 GIN 索引查询 |
| **用户反馈**  | Select          | `user_feedback`          | 好评(1), 差评(-1), 无(0)                       |

#### 3.1.2 列表展示区 (Data Grid)

每一行代表一次完整的对话交互，字段映射如下：

1. **链路标识 (Identity)**

- 展示 `Trace ID` (前8位 + 复制按钮)。
- 展示 `User ID` / `Dept ID`。
- 展示 `create_time` (格式：MM-dd HH:mm:ss)。

2. **摘要透视 (Summary)**

- **Intent:** 展示 `user_intent` 标签 (如：`咨询`, `代码生成`)。
- **Q&A Snippet:**
- **Q:** 展示 `user_trace_query` (限制显示 50 字，hover 显示 PG 中的 500 字摘要)。
- **A:** 展示 `ai_trace_response` (同上)。

3. **技术画像 (Tech Profile)**

- **Agent:** 展示 `agent_name` (v`agent_version`)。
- **Path:** 解析 `execution_path` JSONB，展示为简单的面包屑导航 (e.g., `Planner > Search > Writer`)。
- **Tools:** 解析 `tools_used` JSONB，展示为图标/Tag 集合 (e.g., `🔍 Google`, `🐍 Python`)。

4. **效能指标 (Metrics)**

- **Latency:** 展示 `trace_latency_ms`。
- 规则：< 3s 绿色, 3-10s 黄色, > 10s 红色。

- **Tokens:** 展示 `trace_total_tokens` (Input/Output)。

5. **状态与反馈**

- **Status:** 状态徽章 (SUCCESS=绿, FAILED=红)。
- **Feedback:** 如果 `user_feedback` != 0，显示 👍 或 👎 图标。

6. **操作**

- **[查看详情]** 按钮 -> 抽屉友好展示ES中的详细信息。

---

## 4. 非功能性需求 (NFR)

1. **大文本性能 (Performance):**

- 对于 ES 中超过 1MB 的 Payload，接口不应一次性返回，建议拆分为 `GET /.../payload` 懒加载，防止前端卡死。
- 代码高亮组件（如 Monaco Editor 或 Prism.js）需开启 Virtual Scrolling。

2. **延迟 (Latency):**

- 列表页查询 (PG) 响应需 < 500ms。
- 详情页查询 (ES) 响应需 < 1s。
