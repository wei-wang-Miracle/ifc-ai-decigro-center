# ⚙️ Bus Kernel — 业务内核

> **系统躯干 + 守门员**：只 "做"，不 "想"。负责注册中心、权限守门、工具执行、数据服务、审计存储。

## 概述

Bus Kernel 是 NexusGraph 系统的 **"躯干和守门员"** —— 它是连接 AI 大脑与真实业务世界的桥梁。

以 **服务于 AI Agent 为第一核心原则**，Bus Kernel 承担三重角色：

| 角色                 | 隐喻            | 职责                                           |
| -------------------- | --------------- | ---------------------------------------------- |
| **Context Provider** | 📖 图书馆管理员 | 为 AI 提供结构化的业务上下文数据               |
| **Tools Provider**   | 🔧 工具管家     | 将业务能力封装为 AI 可调用的工具（Tool Cards） |
| **Gatekeeper**       | 🛡️ 安全守卫     | 权限校验、Token 认证、租户隔离、全链路审计     |

### 核心原则

- **降低 AI 获取信息的认知负载**：通过结构化方式，将业务数据转化为 AI 友好的语义信息
- **提升 AI 执行动作的确定性**：标准化 API 接口，确保 Function Calling 精准执行
- **限制 AI 的权限边界**：基于用户角色的工具白名单，不同用户看到不同能力集
- **审计 AI 的全部行为**：PG 宽表 + ES 快照，实现全链路可追踪

---

## 技术栈

| 技术                  | 版本    | 用途         |
| --------------------- | ------- | ------------ |
| **Java**              | JDK 17  | 编程语言     |
| **Spring Boot**       | 3.2.2+  | 核心框架     |
| **MyBatis-Flex**      | 1.9.3+  | ORM 框架     |
| **PostgreSQL**        | 17+     | 核心数据存储 |
| **Redis**             | 7.0+    | Token 缓存   |
| **Elasticsearch**     | 8.x     | 审计详情存储 |
| **Hutool**            | 5.8.26+ | 工具类库     |
| **FastJSON2**         | 2.0.43+ | JSON 处理    |
| **SpringDoc OpenAPI** | 2.5.0+  | API 文档生成 |
| **Lombok**            | Latest  | 简化代码     |

---

## 功能模块

### 1. 📋 注册中心 (Registry Center) — 核心模块

> 工具即能力，注册中心是能力的目录和守门员。

#### Tool Card — 工具能力注册

**Tool Card** 是一份给 LLM 看的"自述文件"。它不仅符合编程规范（Schema），更符合语言模型的认知逻辑（Semantics）。

##### Tool Card 数据结构

| 字段分类       | 字段名             | 说明                                            |
| -------------- | ------------------ | ----------------------------------------------- |
| **身份与意图** | `tool_name`        | 唯一标识（PK），`snake_case` 格式               |
|                | `tool_description` | 核心 Prompt：做什么 + 何时用 + 约束条件         |
|                | `tool_tags`        | JSONB，用于检索或权限分组                       |
| **调用协议**   | `tool_protocol`    | `http`（REST API）或 `reference`（本地引用）    |
|                | `url_path`         | HTTP 工具的 API 端点路径                        |
|                | `reference_target` | 本地引用类的目标标识                            |
| **参数定义**   | `tool_parameters`  | JSONB 入参定义（名称、类型、描述、是否必填）    |
|                | `output_schema`    | JSONB 出参定义，帮助 Agent 解析结果             |
| **少样本增强** | `input_examples`   | JSONB，辅助 Intent Detection 和 Slot Filling    |
|                | `output_examples`  | JSONB，帮助 Agent 建立结果处理逻辑              |
| **权限控制**   | `tool_privileges`  | `public`（所有用户可用）/ `protected`（需授权） |
| **生命周期**   | `is_online`        | 上线状态开关，下线后 Agent 不可见               |
|                | `manager_by`       | 责任人                                          |

##### Tool Card API

| 端点                       | 方法     | 说明                                     | 调用方        |
| -------------------------- | -------- | ---------------------------------------- | ------------- |
| `/tool/page`               | GET      | 分页查询工具列表（支持关键字、标签筛选） | 前端管理      |
| `/tool/detail/{toolName}`  | GET      | 获取工具详情                             | 前端管理      |
| `/tool/save`               | POST     | 新增/更新工具                            | 前端管理      |
| `/tool/remove/{toolName}`  | DELETE   | 删除工具                                 | 前端管理      |
| `/tool/online/{toolName}`  | PUT      | 工具上线                                 | 前端管理      |
| `/tool/offline/{toolName}` | PUT      | 工具下线                                 | 前端管理      |
| `/tool/check-name`         | GET      | 检查工具名称可用性                       | 前端表单校验  |
| **`/tool/available`**      | **POST** | **获取当前用户可用工具列表（摘要）**     | **AI Engine** |
| **`/tool/detail`**         | **POST** | **获取工具详情（含参数定义）**           | **AI Engine** |

> `/tool/available` 返回的是 **摘要信息**（ToolCardSummaryVO），仅包含名称、描述和标签，符合渐进式加载思想。

##### 工具权限模型

```
用户可用工具 = PUBLIC 工具 ∪ 角色绑定工具 ∪ 用户单独绑定工具

过滤规则: is_online = true AND (public OR 用户角色授权 OR 用户个人授权)
```

- `PUBLIC`：所有登录用户可用
- `PROTECTED`：需在角色表（`sys_role.tool_list`）或用户表（`sys_user.tool_list`）中显式授权

---

#### Agent Card — 智能体身份注册

**Agent Card** 是 AI Agent 的"身份证"和"核心配置单"。它定义了 Agent 是谁、能做什么、以及如何思考。

##### Agent Card 数据结构

| 字段分类       | 字段名                | 说明                              |
| -------------- | --------------------- | --------------------------------- |
| **身份与形象** | `agent_name`          | 唯一标识（PK），`snake_case` 格式 |
|                | `agent_alias`         | 显示名称，如 "金牌客服小助手"     |
|                | `agent_description`   | 职责描述，用于展示和检索          |
|                | `agent_tags`          | JSONB，能力标签                   |
| **核心大脑**   | `system_prompt`       | 系统提示词（核心指令集）          |
|                | `negative_prompt`     | 负向提示词（不应做什么）          |
|                | `reasoning_framework` | 推理框架：`ReAct` / `PlanSolve`   |
| **能力边界**   | `bound_tools`         | JSONB 工具绑定白名单              |
| **元数据**     | `agent_version`       | 版本号                            |
|                | `is_online`           | 上线状态                          |
|                | `manager_by`          | 负责人                            |

##### 工具绑定规则

```
bound_tools = NULL       → 使用所有 Public 工具（通用 Agent）
bound_tools = []         → 不使用任何工具（纯对话模式）
bound_tools = ["a","b"]  → 仅使用指定工具（专项 Agent）
```

##### Agent Card API

| 端点                         | 方法     | 说明                             | 调用方        |
| ---------------------------- | -------- | -------------------------------- | ------------- |
| `/agent/page`                | GET      | 分页查询智能体列表               | 前端管理      |
| `/agent/detail/{agentName}`  | GET      | 获取智能体详情                   | 前端管理      |
| `/agent/save`                | POST     | 新增/更新智能体                  | 前端管理      |
| `/agent/remove/{agentName}`  | DELETE   | 删除智能体                       | 前端管理      |
| `/agent/online/{agentName}`  | PUT      | 智能体上线                       | 前端管理      |
| `/agent/offline/{agentName}` | PUT      | 智能体下线                       | 前端管理      |
| `/agent/check-name`          | GET      | 检查名称可用性                   | 前端表单校验  |
| `/agent/available-tools`     | GET      | 获取可绑定工具列表               | 前端配置      |
| **`/agent/available`**       | **POST** | **获取可用智能体列表（摘要）**   | **AI Engine** |
| **`/agent/detail`**          | **POST** | **获取智能体详情（含提示词等）** | **AI Engine** |

---

### 2. 💬 AI 聊天会话管理

提供完整的会话生命周期管理（CRUD）：

| 端点                                     | 方法   | 说明                   |
| ---------------------------------------- | ------ | ---------------------- |
| `/ai/chat/sessions`                      | GET    | 获取当前用户的会话列表 |
| `/ai/chat/sessions`                      | POST   | 创建新会话             |
| `/ai/chat/sessions/{sessionId}`          | PUT    | 更新会话标题           |
| `/ai/chat/sessions/{sessionId}`          | DELETE | 删除会话               |
| `/ai/chat/sessions/{sessionId}/messages` | GET    | 获取会话历史消息       |
| `/ai/chat/messages`                      | POST   | 保存消息记录           |

所有接口需携带 `X-Auth-Token` 请求头，实现用户级数据隔离。

---

### 3. 📊 全链路审计监控

**双存储架构**：PG 宽表（列表查询） + ES 快照（详情钻取）

| 端点                      | 方法     | 说明                             | 数据源             |
| ------------------------- | -------- | -------------------------------- | ------------------ |
| `/trace/page`             | GET      | 审计列表分页查询（多维度筛选）   | PostgreSQL         |
| `/trace/detail/{traceId}` | GET      | 审计详情查询（完整执行堆栈）     | Elasticsearch      |
| **`/trace/save`**         | **POST** | **保存审计数据（PG + ES 双写）** | **AI Engine 调用** |

##### PG 宽表字段 (`ai_chat_trace_index`)

```
trace_id / session_id / task_id / user_id / dept_id / tenant_code
agent_name / agent_version / model_provider
user_intent / user_trace_query / ai_trace_response
execution_path[] / tools_used[]
status (SUCCESS/FAILED) / failure_reason
trace_latency_ms / trace_total_tokens
user_feedback (-1/0/1)
```

##### ES 快照结构

```json
{
  "trace_id": "...",
  "graph_nodes": [
    {
      "node_name": "intent_recognition",
      "latency_ms": 1200,
      "status": "SUCCESS",
      "agent_snapshots": [
        {
          "agent_name": "...",
          "system_prompt": "...",
          "tools_snapshot": [
            {
              "tool_name": "get_all_customer_tags",
              "input_args": {},
              "output_result": "...",
              "latency_ms": 300
            }
          ]
        }
      ]
    }
  ]
}
```

---

### 4. 🏷 客户标签管理

| 端点                             | 方法     | 说明                            |
| -------------------------------- | -------- | ------------------------------- |
| `/tag/page`                      | GET      | 分页查询标签                    |
| `/tag/detail/{tagField}`         | GET      | 获取标签详情                    |
| `/tag/save`                      | POST     | 新增/更新标签                   |
| `/tag/remove/{tagField}`         | DELETE   | 删除标签（级联删除枚举值）      |
| `/tag/migrate`                   | POST     | 批量迁移分类下的标签            |
| **`/tag/get_all_customer_tags`** | **POST** | **获取所有标签（AI 工具端点）** |

关联模块：

- **CustomerTagCategory**：标签分类管理（树形结构）
- **CustomerTagEnum**：标签枚举值管理

---

### 5. 👥 系统管理

| 模块         | Controller             | 功能                                    |
| ------------ | ---------------------- | --------------------------------------- |
| **认证**     | `AuthController`       | 登录（RSA 加密）、登出、Token 管理      |
| **用户管理** | `SysUserController`    | 用户 CRUD、角色分配、密码重置、头像上传 |
| **角色管理** | `SysRoleController`    | 角色 CRUD、控制工具 (`tool_list`)       |
| **部门管理** | `SysDeptController`    | 组织架构管理                            |
| **租户管理** | `SysTenantController`  | 多租户支持                              |
| **在线用户** | `OnlineUserController` | 实时监控、强制下线                      |
| **Token**    | `TokenController`      | Token 校验、续签                        |

---

### 6. 🛡️ 安全体系

| 组件                       | 位置                  | 功能                                 |
| -------------------------- | --------------------- | ------------------------------------ |
| **TokenProvider**          | `common/auth/`        | Token 生成、验证、解析（Redis 存储） |
| **AuthInterceptor**        | `common/interceptor/` | 请求拦截、Token 校验、用户上下文注入 |
| **UserContext**            | `common/context/`     | 线程级用户信息（ThreadLocal）        |
| **RSA 加密**               | `common/crypto/`      | 密码传输非对称加密                   |
| **RequestLogFilter**       | `common/filter/`      | 全链路请求日志（URL、参数、耗时）    |
| **GlobalExceptionHandler** | `common/handler/`     | 统一异常处理                         |

---

## 目录结构

```
bus-kernel/
├── pom.xml                     # Maven 项目配置
├── README.md                   # 本文档
├── src/main/
│   ├── java/com/ifc/decigro/buskernel/
│   │   ├── BusKernelApplication.java   # Spring Boot 启动类
│   │   │
│   │   ├── controller/                 # REST API 层
│   │   │   ├── ToolCardController.java      # 工具注册中心 API
│   │   │   ├── AgentCardController.java     # 智能体注册中心 API
│   │   │   ├── AiChatController.java        # AI 会话管理 API
│   │   │   ├── AiChatTraceController.java   # 审计监控 API
│   │   │   ├── CustomerTagController.java   # 客户标签 API
│   │   │   ├── CustomerTagCategoryController.java  # 标签分类 API
│   │   │   ├── CustomerTagEnumController.java      # 标签枚举 API
│   │   │   ├── AuthController.java          # 认证 API
│   │   │   ├── SysUserController.java       # 用户管理 API
│   │   │   ├── SysRoleController.java       # 角色管理 API
│   │   │   ├── SysDeptController.java       # 部门管理 API
│   │   │   ├── SysTenantController.java     # 租户管理 API
│   │   │   ├── OnlineUserController.java    # 在线用户 API
│   │   │   └── TokenController.java         # Token 管理 API
│   │   │
│   │   ├── service/                    # 业务逻辑层
│   │   │   ├── ToolCardService.java         # 工具管理服务
│   │   │   ├── AgentCardService.java        # 智能体管理服务
│   │   │   ├── AiChatTraceIndexService.java # 审计存储服务
│   │   │   ├── CustomerTagService.java      # 标签管理服务
│   │   │   ├── SysUserService.java          # 用户管理服务
│   │   │   └── impl/                        # 服务实现类
│   │   │
│   │   ├── entity/                     # 数据实体
│   │   │   ├── ToolCard.java                # 工具卡片实体
│   │   │   ├── AgentCard.java               # 智能体卡片实体
│   │   │   ├── AiChatTraceIndex.java        # 审计索引实体
│   │   │   ├── CustomerTag.java             # 客户标签实体
│   │   │   ├── SysUser.java / SysRole.java  # 系统实体
│   │   │   ├── dto/                         # 请求 DTO
│   │   │   └── vo/                          # 响应 VO
│   │   │
│   │   ├── mapper/                     # MyBatis-Flex 数据访问层
│   │   │
│   │   ├── common/                     # 通用组件
│   │   │   ├── api/Result.java              # 统一响应包装
│   │   │   ├── auth/TokenProvider.java      # Token 管理
│   │   │   ├── context/UserContext.java     # 用户上下文
│   │   │   ├── crypto/                      # RSA 加密
│   │   │   ├── filter/RequestLogFilter.java # 请求日志过滤器
│   │   │   ├── interceptor/                 # 认证拦截器
│   │   │   ├── handler/                     # 异常处理器
│   │   │   └── annotation/                  # 自定义注解
│   │   │
│   │   ├── config/                     # 配置类
│   │   └── dto/                        # 公共 DTO
│   │
│   └── resources/
│       └── application.yml             # 应用配置
```

---

## 接口文档

项目集成了 `springdoc-openapi`，自动生成符合 OpenAPI 3 规范的接口文档。

### 访问地址（Context Path: `/api/dg`）

- **Swagger UI**: [http://localhost:8080/api/dg/swagger-ui.html](http://localhost:8080/api/dg/swagger-ui.html)
- **OpenAPI JSON**: [http://localhost:8080/api/dg/v3/api-docs](http://localhost:8080/api/dg/v3/api-docs)

---

## 快速开始

### 1. 数据库初始化

```bash
# 创建数据库
createdb -U postgres decigro

# 初始化系统表和基础数据
psql -U postgres -d decigro -f scripts/init.sql

# 初始化业务表（Tool Card, Agent Card, 标签等）
psql -U postgres -d decigro -f docs/db-design/db.sql
```

### 2. 配置修改

编辑 `src/main/resources/application.yml`：

- 数据库连接信息
- Redis 连接信息
- ES 连接信息（可选）

### 3. 编译运行

```bash
mvn clean package -DskipTests
java -jar target/bus-kernel-*.jar
```

### 4. 验证

```bash
# 健康检查
curl http://localhost:8080/api/dg/actuator/health

# 登录获取 Token
curl -X POST http://localhost:8080/api/dg/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'
```
