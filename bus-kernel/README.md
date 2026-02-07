# 业务内核

## 核心理念:Context Provider（上下文提供者） + Tools Provider（工具提供者）

以服务于 AI Agent 为第一核心原则。
作为 AI 的“统一数据网关” 和 “统一执行器”，在信息获取时执行语义层职责，通过 API View 暴露数据和含义，提供AI友好的数据结构和数据提供，将数据包装成业务语义；在执行动作时，负责工具层职责，通过 API View 暴露工具和限制，为AI提供做什么？怎么用？为什么用不了？预校验服务。

## 主要职责

1. 降低 AI 获取信息的认知负载,通过结构化方式，将业务信息输出给Agent
2. 提升 AI 执行动作的确定性，通过结构化交互，保证Agent Function Calling的有效执行
3. 限制 AI 信息获取和数据处理权限，通过租户和会话管理，将AI工具调用和数据处理限制在权限范围内
4. 审计 AI 执行动作和产出结果，通过执行日志和各类监控，保证AI执行的透明性和可追溯性
5. 提供 管理功能，包括租户管理、会话管理、工具管理、审计管理等

## 技术要求

| 技术                  | 版本    | 用途             |
| --------------------- | ------- | ---------------- |
| **Java**              | JDK 17  | Java开发         |
| **hutool**            | 5.8.25+ | 工具类库         |
| **springdoc-openapi** | 2.5.0+  | API文档生成      |
| **mybatis-flex**      | 1.11.0+ | ORM框架          |
| **spring-boot**       | 3.2.0+  | Spring Boot 框架 |
| **fastjson2**         | 2.0.48+ | JSON处理         |
| **caffeine**          | 3.2.0+  | 缓存框架         |
| **HikariCP**          | 5.0.0+  | 数据库连接池     |
| **postgresql**        | 17+     | 数据库           |
| **redis**             | 7.0+    | 缓存、消息队列   |
| **slf4j**             | 2.0.48+ | 日志处理         |

### 工具使用管理拦截

_面向对象：所有用户_

1. tools共分为2级，第一级 是`PUBLIC`,也就是大家都能用，第二级是`PROTECTED`，受保护的，只有指定的人用。
2. 级别会维护在 Tools Card,也就是工具管理表中，而谁可以使用哪些工具，会维护在用户表中
3. PROTECTED tool 会跟角色和用户进行绑定，也就是用户可以使用哪些工具，会维护在用户表中和角色表中，用户可以使用的工具 = PUBLIC + 角色TOOL_LIST + 用户TOOL_LIST

Tool Gatekeeper:

- 用户通过Agent进行访问时，Agent仅可以使用用户可以使用的工具（包含工具获取和使用拦截）

### Tool Card (参考 Claude Skill 设计思想)

"AI-friendly Tool Card"，本质上是一份给 LLM 看的“自述文件”。它不仅要符合编程规范（Schema），更要符合语言模型的认知逻辑（Semantics）。

#### 1. 身份与意图 (Identity & Intent) —— 解决“AI 调用谁？”

- **tool_name** (唯一标识)
  要求: 语义清晰，建议用 `snake_case`，如 `get_weather_data`。
- **tool_description** (核心 Prompt)
  要素: 必须包含 **Action (做什么)**、**Trigger (什么时候用)** 和 **Constraint (限制条件)**。
  示例: "Retrieves current weather. Use when user asks for temperature. Input strictly city name."
- **tool_tags** (标签)
  用途: 用于检索或权限分组，格式为 JSON 数组，如 `['finance', 'external_api']`。
- **tool_version** (版本号)
  默认 `1.0.0`，用于追踪工具迭代。
- **tool_privileges** (权限等级)
  枚举值：`public` (公开)、`protected` (受保护)。

#### 2. 调用协议 (Protocol) —— 解决“怎么调用？”

- **tool_protocol** (协议类型)
  - `http`: 通过 REST API 调用工具，需提供 `url_path`。
  - `reference`: 引用本地实体执行，需提供 `reference_target`（如实体表名）。
- **url_path / reference_target**
  具体的调用路径或引用目标。

#### 3. 参数定义 (Parameters) —— 解决“传什么？”

- **tool_parameters** (入参定义)
  结构: `[{ "param_name": "city", "param_type": "string", "param_description": "...", "param_required": true, "param_example": "Beijing" }]`
  **Prompt 思想**: 字段描述 (param_description) 应当包含如何从用户输入中提取该值的逻辑。
- **output_schema** (出参定义)
  结构与入参一致，定义工具返回的数据结构（如返回字段、类型及含义），帮助 Agent 理解如何解析结果。

#### 4. 少样本增强 (Few-Shot Examples) —— 解决“模型认知”

- **input_examples** (Few-Shot Input)
  用于告诉 Agent 用户可能会怎么问，辅助模型进行 Intent Detection 和 Slot Filling。
- **output_examples** (Few-Shot Output)
  工具预期返回的数据结构示例，帮助 Agent 建立正确的结果处理逻辑。

#### 5. 元数据 (Meta Information)

- **is_online**: 布尔值，标识工具是否处于激活上线状态。
- **manager_by**: 维护责任人。
- **create_time / update_time**: 生命周期追踪。

## 接口文档

项目集成了 `springdoc-openapi`，自动生成符合 OpenAPI 3 规范的接口文档。

### 访问地址

- **Swagger UI**: [http://localhost:8080/swagger-ui.html](http://localhost:8080/swagger-ui.html)
- **OpenAPI JSON**: [http://localhost:8080/v3/api-docs](http://localhost:8080/v3/api-docs)

### 主要功能

1. **自动化**: 无需手动维护文档，随着代码更新自动同步。
2. **交互式**: 可以在浏览器直接测试接口。
3. **标准化**: 生成标准的 OpenAPI 3.0 定义文件。
