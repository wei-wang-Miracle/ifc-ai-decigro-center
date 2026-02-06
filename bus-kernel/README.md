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

### Tool Card (参考Claude Skill 设计思想)

"AI-friendly Tool Card"，本质上是一份给 LLM 看的“自述文件”。它不仅要符合编程规范（Schema），更要符合语言模型的认知逻辑（Semantics）。

1. 身份与意图 (Identity & Intent) —— 解决“AI 调用谁？”

- tool_name(唯一标识)
  要求: 语义清晰，建议用 snake_case，如 get_weather_data 而不是 func_01。
- tool_description(工具描述)
  要素: 必须包含 "做什么" (Action)、"什么时候用" (Trigger) 和 "局限性" (Constraint)。
  AI 友好写法: 不要写 "API to get weather"，要写 "Retrieves current weather conditions for a specific location. Use this tool when the user asks about temperature, rain, or forecast."

2. 调用协议 Or 引用执行 —— 解决“怎么调用？“

- use_protocol: "http" | "reference"
  - http: 使用 HTTP 协议调用工具
  - reference: 引用执行，即在当前对话中直接执行工具
- parameters (JSON Schema)
  - 字段名
  - 数据类型
  - 是否必传
  - Field Description (关键语义):重点: 字段描述比字段名更重要。
    示例: 对于字段 query，不要只写 "The query string"，要写 "The search keyword extracted from user's prompt, optimized for a search engine (e.g., remove stop words)." —— 这实际上是在把 Prompt Engineering 内嵌到工具定义中。
  - Enumerations (枚举约束):
    如果参数只有固定几个值（如 ["metric", "imperial"]），必须显式列出，防止 AI 产生幻觉（比如编造一个 "scientific" 单位）。
- parameter_examples (JSON Array): Few Shot少样本提示，让模型更好的理解如何请求

3. 结果预期 (Outcome & Feedback) —— 解决“能够得到什么？”

- Output Schema (返回结构):
  告诉 AI 返回的是一段文本、一个 JSON 还是一个图片 URL。这决定了 Agent 拿到结果后是直接输出给用户，还是需要进行下一轮处理。

- Error Handling (异常契约):
  定义当工具调用失败时，会返回什么？（是返回 null 还是具体的 error_message）。
  AI 友好策略: 错误信息应当是“可自愈的”。例如返回 "Error: Date format invalid, please use YYYY-MM-DD"，这样 Agent 可以在下一轮自动修正参数重试。
