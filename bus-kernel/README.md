# 业务内核 (Bus Kernel)

## 核心理念: Context Provider（上下文提供者） + Tools Provider（工具提供者）

以服务于 AI Agent 为第一核心原则。
作为 AI 的“统一数据网关” 和 “统一执行器”，在信息获取时执行语义层职责，通过 API View 暴露数据和含义，提供AI友好的数据结构和数据提供，将数据包装成业务语义；在执行动作时，负责工具层职责，通过 API View 暴露工具和限制，为AI提供做什么？怎么用？为什么用不了？预校验服务。

## 主要职责

1. **降低 AI 获取信息的认知负载**: 通过结构化方式，将业务信息输出给Agent。
2. **提升 AI 执行动作的确定性**: 通过结构化交互，保证Agent Function Calling的有效执行。
3. **限制 AI 信息获取和数据处理权限**: 通过租户和会话管理，将AI工具调用和数据处理限制在权限范围内。
4. **审计 AI 执行动作和产出结果**: 通过执行日志和各类监控，保证AI执行的透明性和可追溯性。
5. **提供 业务管理功能**: 包括租户管理、用户管理、Agent管理、工具管理、标签管理等。

## 功能模块

### 1. 系统管理 (System Management)

- **用户管理**: 用户增删改查、角色分配、密码重置。
- **角色管理**: 角色定义、权限分配（菜单权限、数据权限）。
- **部门管理**: 组织架构管理。
- **租户管理**: 多租户支持。
- **在线用户**: 实时监控在线用户状态。

### 2. Agent 管理 (Agent Management)

- **Agent Card**: 定义 Agent 的身份、能力和配置。

### 3. 工具管理 (Tool Management)

- **Tool Card**: 定义工具的元数据、参数、调用协议及权限。
- **权限控制**: 基于角色和用户的工具访问控制（Public/Protected）。

### 4. 客户标签管理 (Customer Tag Management)

- **标签类目**: 标签的分类管理。
- **标签定义**: 具体标签的定义与管理。
- **标签枚举**: 标签值的枚举管理。

### 5. 安全与监控

- **请求日志**: 全链路请求日志记录（RequestLogFilter）。
- **RSA 加密**: 敏感信息（如密码）传输采用 RSA 非对称加密。

## 技术栈 (Technology Stack)

| 技术                  | 版本    | 用途           |
| --------------------- | ------- | -------------- |
| **Java**              | JDK 17  | Java开发       |
| **Spring Boot**       | 3.2.2+  | 核心框架       |
| **MyBatis-Flex**      | 1.9.3+  | ORM框架        |
| **PostgreSQL**        | 17+     | 数据库         |
| **Redis**             | 7.0+    | 缓存、消息队列 |
| **Hutool**            | 5.8.26+ | 工具类库       |
| **FastJSON2**         | 2.0.43+ | JSON处理       |
| **SpringDoc OpenAPI** | 2.5.0+  | API文档生成    |
| **Lombok**            | Latest  | 简化代码       |
| **HikariCP**          | Default | 数据库连接池   |
| **Slf4j**             | Default | 日志处理       |

### Agent Card (参考 Character Card 设计思想)

"Agent Card" 是 AI Agent 的“身份身份证”和“核心配置单”。它定义了 Agent 是谁、能做什么、以及如何思考。

#### 1. 身份与形象 (Identity & Profile) —— 解决“我是谁？”

- **agent_name** (唯一标识): Agent 的系统级唯一 ID，建议使用 `snake_case`，如 `customer_service_bot`。
- **agent_alias** (显示名称): Agent 的对外昵称，如 "金牌客服小助手"。
- **agent_description** (人设描述): 简短描述 Agent 的职责和角色，用于展示和初步检索。
- **agent_tags** (能力标签): 用于对 Agent 进行分类和检索，如 `['customer_support', 'nlp']`。

#### 2. 核心大脑 (Core Brain) —— 解决“怎么思考？”

- **system_prompt** (系统提示词): Agent 的核心指令集，定义了其行为准则、语气风格和任务边界。
- **negative_prompt** (负向提示词): 明确 Agent **不应该** 做什么或说什么。
- **reasoning_framework** (推理框架): 定义 Agent 的思考模式，如 `ReAct`, `PlanSolve` 等。

#### 3. 能力边界 (Capabilities) —— 解决“能用什么？”

- **bound_tools** (绑定工具): 定义该 Agent 可以调用的工具白名单。
  - `NULL`: 可使用所有 Public 工具。
  - `[]`: 不可使用任何工具。
  - `["tool_a", "tool_b"]`: 仅可使用列表中的工具。

#### 4. 元数据 (Meta Information)

- **agent_version**: 版本号，用于迭代管理。
- **is_online**: 上线状态控制。
- **manager_by**: 负责人。

### 工具使用管理拦截

_面向对象：所有用户_

1. Tools 共分为2级：
   - `PUBLIC`: 公开工具，所有用户可用。
   - `PROTECTED`: 受保护工具，需特定权限。
2. 级别维护在 **Tool Card** (工具管理表) 中。
3. 用户可使用的工具 = `PUBLIC` + `角色绑定的工具` + `用户单独绑定的工具`。

**Tool Gatekeeper**:

- 用户通过 Agent 访问时，Agent 仅可调用当前用户有权限使用的工具。

### Tool Card (参考 Claude Skill 设计思想)

"AI-friendly Tool Card"，本质上是一份给 LLM 看的“自述文件”。它不仅要符合编程规范（Schema），更要符合语言模型的认知逻辑（Semantics）。

#### 1. 身份与意图 (Identity & Intent)

- **tool_name**: 唯一标识，建议 `snake_case`。
- **tool_description**: 核心 Prompt，包含 Action, Trigger, Constraint。
- **tool_tags**: 用于检索或权限分组。

#### 2. 调用协议 (Protocol)

- **tool_protocol**: `http` (REST API) 或 `reference` (本地引用)。
- **url_path / reference_target**: 调用地址或目标。

#### 3. 参数定义 (Parameters)

- **tool_parameters**: 入参定义，描述如何从用户输入提取值。
- **output_schema**: 出参定义，帮助 Agent 解析结果。

#### 4. 少样本增强 (Few-Shot Examples)

- **input_examples**: 辅助 Intent Detection 和 Slot Filling。
- **output_examples**: 帮助 Agent 建立结果处理逻辑。

#### 5. 元数据 (Meta Information)

- **is_online**: 上线状态。
- **manager_by**: 责任人。

## 接口文档

项目集成了 `springdoc-openapi`，自动生成符合 OpenAPI 3 规范的接口文档。

### 访问地址 (Context Path: `/api/dg`)

- **Swagger UI**: [http://localhost:8080/api/dg/swagger-ui.html](http://localhost:8080/api/dg/swagger-ui.html)
- **OpenAPI JSON**: [http://localhost:8080/api/dg/v3/api-docs](http://localhost:8080/api/dg/v3/api-docs)

### 主要功能

1. **自动化**: 代码更新自动同步文档。
2. **交互式**: 浏览器直接测试接口。
3. **标准化**: 标准 OpenAPI 3.0 定义。
