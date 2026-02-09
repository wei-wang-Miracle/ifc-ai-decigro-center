# 权限系统 PRD

| 文档版本     | V1.0       |
| ------------ | ---------- |
| **最后更新** | 2026-02-06 |

## 1. 项目背景与目标

### 1.1 背景

AI DeciGro Center 是一个基于 Multi-Agent 的决策增长平台。系统由 AI 引擎（大脑）、业务内核（躯干）和前端（界面）组成。
为了确保 AI 在执行任务时既能充分利用用户历史上下文（Cognitive Context），又能严格遵守当前的职能边界（Functional Context），我们需要设计一套 **AI 友好型、轻量级、支持多租户（SaaS）** 的权限系统。

### 1.2 核心目标

1. **一切为了 AI 服务**：权限系统不仅控制人，更要控制 Agent。Agent 的权限必须动态继承自操作用户。
2. **轻量级鉴权**：摒弃复杂的鉴权中心（如 OAuth2/JWT 复杂流程），采用“签名式长效令牌”机制，便于外部系统集成。
3. **动静分离**：用户的“身份记忆”（历史）与“职能权限”（当前）解耦，支持用户转岗后保留记忆但变更权限。
4. **SaaS 隔离**：实现基于租户（Company）的物理/逻辑隔离，并支持“一键熔断”。

---

## 2. 核心概念定义

| 概念              | 定义                                                                                         | 示例                                | AI 系统中的作用                                                         |
| ----------------- | -------------------------------------------------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------------------- |
| **Tenant (租户)** | Tenant_Code唯一标识导向，数据隔离的物理边界，对应“公司”或“组织”,本系统主要标记访问来源系统。 | HEYI                                | 计算Token使用量，统计服务信息。                                         |
| **User (用户)**   | UserName唯一标识导向，唯一的身份标识，贯穿用户生命周期。                                     | WangWei_1                           | **记忆锚点**。AI 通过此 ID 检索历史对话和偏好，不论用户此时在哪个部门。 |
| **Dept (部门)**   | 用户当前的部门，标记用户当前职能，协助用户保留使用习惯的前提下快速切换工作内容。             | 合规管理部, 数字运营中心            | **权限边界**。决定当前部门的工具调用权限。                              |
| **Token (令牌)**  | 携带当前职能信息的签名字符串，基于用户信息的加密字符串。                                     | `BDFJLSFHJSLK21414LBLHASLAGH`       | **Agent 的工牌**。Agent 执行工具时必须携带，Bus Kernel 据此放行或拦截。 |
| **Role (角色)**   | 粗粒度的权限集合。基于枚举                                                                   | `ADMIN` (管理员), `USER` (普通员工) | 决定前端菜单显隐和工具调用的基础门槛。                                  |

---

## 3. 系统架构与流程

### 3.1 令牌设计 (The Badge)

采用自包含信息的签名 Token，无需查库即可完成基础校验。

- **原始信息**：
  `Prefix_TenantCode_DeptId_UserName_Timestamp`
- **示例**：
  `sk_v1_ifc001_299_u8829_1740012345`
- **生成规则**：
- 由 Bus Kernel 使用 `System_Secret` 进行 HMAC-SHA256 签名对原始信息加密之后返回，放置到header里。
- 支持外部系统通过算法自行生成（如果有 Secret），实现无缝集成。

### 3.2 交互流程 (The Flow)

1. **登录/切换身份**：

- 用户登录 -> 前端加密传输请求Bus Kernel -> Bus Kernel 解密之后验证账号密码（密码在数据库内加密保存，支持解密） -> 读取 `sys_user` 当前的 `相关用户信息` -> **生成携带部门信息的 Token** -> 放置到Header里，并返回前端。

2. **AI 对话 (认知层)**：

- 前端携带 Token 请求 AI Engine。
- AI Engine 解析 Token 中的 `UserName` -> 从向量库检索该用户的**历史记忆**（跨部门、跨时间）。

3. **工具执行 (职能层)**：

- AI Engine 决定调用工具（如 `query_codebase`）。
- AI Engine 将用户的 Token 透传给 Bus Kernel 的 Tools API。
- **Bus Kernel **： ① 拦截用户信息进行解析缓存，并验证有效性。 ② 获取可用工具时，根据信息过滤可用工具 ③ 进行工具使用时，使用不同的用户权限

---

## 4. 功能需求 (Functional Requirements)

### 4.1 租户管理 (Tenant Management)

_面向对象：平台超级管理员_

- **租户生命周期管理**：
- 创建/编辑租户信息（TenantCode、名称）, `TENANT_CODE`、`TENANT_NAME`
- **一键熔断**：设置状态为 `ENABLED`。Bus Kernel 拦截器需立即拒绝该 `TENANT_CODE` 下的所有请求。

### 4.2 角色管理 (Role Management)

_面向对象：平台超级管理员_

- **角色生命周期管理**：
- 创建/编辑角色信息（角色名称、角色描述、 角色可以使用的工具）， `ROLE_ID`、`ROLE_NAME`、`ROLE_DESC`、`TOOL_LIST`
- **一键熔断**：设置状态为 `ENABLED`。Bus Kernel 拦截器需立即拒绝该 `ROLE` 下的所有请求。
- 支持基于角色的工具分配`TOOL_LIST`,TOOL_LIST 是 基于tool_name的JSON Array

### 4.3 用户管理 (User Management)

_面向对象：平台超级管理员_

- **用户档案管理**：
- 创建用户，不需要分配 `TENANT_CODE`, `TENANT_CODE`仅作为令牌处理和统计记录
- _关键字段_：`USERNAME`、`PASSWORD`、`PASSWORD_V`、 `NICK_NAME`、 `GENDER`、`EMAIL`、`PHONE`、`AVATAR_PATH`、 `DEPT_ID`、`ROLE_ID`、`TOOL_LIST`、`ENABLED`
- **动态职能调整**：
- 设置/更新用户信息,支持重置密码，PASSWORD必须加密存储，并且直指解密
- 支持基于用户的工具分配`TOOL_LIST`，TOOL_LIST 是 基于tool_name的JSON Array
- _注意_：更新此信息后，用户下次登录/刷新 Token 时生效，不影响历史数据。

### 4.4 用户监控 (User Monitor)

_面向对象：平台超级管理员_

- 查看和管理用户登录状态，一键下线、在线用户监控，必须要知道谁在用，以及在干什么

### 4.5 认证与授权内核 (Bus Kernel Core)

_面向对象：所有用户_

- **Token 生成器**：实现上述 Token 格式的生成逻辑。
- **统一拦截器 (Interceptor)**：
- **解析**：从 Header 提取 Token，解析出信息。
- **链路追踪**：将上述信息注入 `MDC`。
- **MyBatis-Flex 租户隔离**：根据解析出的 `TENANT_CODE` 自动配置 DB 隔离策略。

---

## 5. 数据模型设计 (ERD 简述)

基于 PostgreSQL，采用 MyBatis-Flex 规范。
基于您提供的《AI DeciGro Center 权限系统 PRD》，以下是 **5. 数据模型设计 (Data Model Design)** 章节。

该设计基于 **PostgreSQL** 数据库，并严格适配 **MyBatis-Flex** 的多租户与乐观锁特性。

---

## 5. 数据模型设计 (ERD)

### 5.1 设计原则

1. **JSONB 灵活授权**：利用 PostgreSQL 的 `jsonb` 类型存储 `tool_list`，避免传统 RBAC 复杂的中间表（User-Tool, Role-Tool），实现 AI Agent 的轻量级鉴权。
2. **SaaS 隔离策略**：核心业务表（如日志、部门）包含 `tenant_code` 以支持 MyBatis-Flex 的多租户拦截；用户表设计为平台级或弱绑定，以支持“跨租户记忆”的愿景。
3. **可逆加密存储**：密码字段适配 PRD 要求的“支持解密”，预留加密算法所需的结构。

---

### 5.2 数据表详情

#### 1. 租户表 (`sys_tenant`)

_管理物理边界与系统接入源。_

| 字段名           | 类型         | 必填 | 说明                                | MyBatis-Flex 注解/逻辑                                      |
| ---------------- | ------------ | ---- | ----------------------------------- | ----------------------------------------------------------- |
| **tenant_code**  | VARCHAR(32)  | Y    | **唯一租户编码** 主键 ID(如 `HEYI`) | 核心隔离字段                                                |
| **tenant_name**  | VARCHAR(100) | Y    | 租户名称                            |                                                             |
| **is_enabled**   | boolean      | Y    | 是否有效                            | 用于 PRD 4.1 一键熔断                                       |
| **created_time** | TIMESTAMP    | Y    | 创建时间                            | `@Column(onInsertValue = "now()")`                          |
| **updated_time** | TIMESTAMP    | Y    | 更新时间                            | `@Column(onInsertValue = "now()", onUpdateValue = "now()")` |

#### 2. 角色表 (`sys_role`)

_定义基础权限与工具集模板。_

| 字段名         | 类型         | 必填 | 说明                                                     | MyBatis-Flex 注解/逻辑    |
| -------------- | ------------ | ---- | -------------------------------------------------------- | ------------------------- |
| **role_id**    | BIGINT       | Y    | 主键 ID                                                  | `@Id` ,对应 PRD `ROLE_ID` |
| **role_name**  | VARCHAR(50)  | Y    | 角色显示名称                                             |                           |
| **role_desc**  | VARCHAR(255) | N    | 描述 ，可空                                              |                           |
| **tool_list**  | **JSONB**    | N    | **工具列表** `["codebase_query", "email_sender"]`， 可空 | 对应 PRD 工具分配         |
| **is_enabled** | boolean      | Y    | 是否有效                                                 | 用于 PRD 4.2 一键熔断     |

#### 3. 用户表 (`sys_user`)

_系统的核心，承载记忆与当前职能。_

| 字段名           | 类型         | 必填 | 说明                               | MyBatis-Flex 注解/逻辑                                      |
| ---------------- | ------------ | ---- | ---------------------------------- | ----------------------------------------------------------- |
| **id**           | BIGINT       | Y    | 主键 ID                            | `@Id`                                                       |
| **username**     | VARCHAR(64)  | Y    | **用户名** (全局唯一)              | 对应 PRD `UserName`                                         |
| **password**     | VARCHAR(255) | Y    | **加密密码** (Symmetric Encrypted) | 对应 PRD 可逆加密需求                                       |
| **password_v**   | VARCHAR(64)  | N    | 密码版本                           |                                                             |
| **nick_name**    | VARCHAR(64)  | N    | 昵称                               |                                                             |
| **gender**       | INT          | N    | 性别 可空                          |                                                             |
| **email**        | VARCHAR(100) | N    | 邮箱 ， 可空                       |                                                             |
| **phone**        | VARCHAR(20)  | N    | 电话 ， 可空                       |                                                             |
| **avatar_path**  | VARCHAR(255) | N    | 头像路径 ， 可空                   |                                                             |
| **dept_id**      | BIGINT       | N    | **当前部门 ID**                    | 关联 `sys_dept`                                             |
| **role_id**      | BIGINT       | N    | **当前角色 ID**                    | 关联 `sys_role`                                             |
| **tool_list**    | **JSONB**    | N    | **个性化工具** (覆盖角色配置)      | JSON 数组                                                   |
| **is_enabled**   | boolean      | Y    | 账户状态 (1:启用, 0:禁用)          |                                                             |
| **created_time** | TIMESTAMP    | Y    | 创建时间                           | `@Column(onInsertValue = "now()")`                          |
| **updated_time** | TIMESTAMP    | Y    | 更新时间                           | `@Column(onInsertValue = "now()", onUpdateValue = "now()")` |

#### 4. 部门表 (`sys_dept`)

_定义职能边界与工作流上下文。_

| 字段名           | 类型        | 必填 | 说明      | MyBatis-Flex 注解/逻辑                                      |
| ---------------- | ----------- | ---- | --------- | ----------------------------------------------------------- |
| **dept_id**      | BIGINT      | Y    | 主键 ID   | `@Id`                                                       |
| **parent_id**    | BIGINT      | N    | 父部门 ID | 树形结构支持                                                |
| **dept_name**    | VARCHAR(64) | Y    | 部门名称  |                                                             |
| **created_time** | TIMESTAMP   | Y    | 创建时间  | `@Column(onInsertValue = "now()")`                          |
| **updated_time** | TIMESTAMP   | Y    | 更新时间  | `@Column(onInsertValue = "now()", onUpdateValue = "now()")` |

#### 5. 用户登录日志表 (`sys_login_log`)

_满足 4.4 监控需求。_

| 字段名           | 类型        | 必填 | 说明                              |
| ---------------- | ----------- | ---- | --------------------------------- | ----------------------------------------------------------- |
| **token_sign**   | VARCHAR(64) | Y    | Token 签名 (主键)                 |
| **username**     | VARCHAR(64) | Y    | 用户名                            |
| **ip_address**   | VARCHAR(50) | N    | 登录 IP                           |
| **login_time**   | TIMESTAMP   | Y    | 登录时间                          |
| **is_enabled**   | boolean     | Y    | 登录状态 (1:启用, 0:禁用)，踢下线 |
| **created_time** | TIMESTAMP   | Y    | 创建时间                          | `@Column(onInsertValue = "now()")`                          |
| **updated_time** | TIMESTAMP   | Y    | 更新时间                          | `@Column(onInsertValue = "now()", onUpdateValue = "now()")` |

---

### 5.4 关键逻辑映射

1. **Token 生成逻辑数据源**：

- `Prefix`: 硬编码配置。
- `TenantCode`: 获取 `sys_dept.tenant_code` ，调用方传入
- `DeptId`: 取自 `sys_user.dept_id`。
- `UserName`: 取自 `sys_user.username`。
- `Timestamp`: 当前系统时间。

2. **工具鉴权逻辑 (Tool Auth)**：

- 当 Agent 请求调用工具时，Bus Kernel 按以下优先级获取可用工具列表：

1. `sys_user.tool_list` (如果不为空)。
2. `sys_role.tool_list` (作为兜底)。

- 通过 PostgreSQL 的 JSONB 操作符可高效查询，例如：`sys_user.tool_list ? 'codebase_query'`。

3. **一键熔断逻辑 (Circuit Breaker)**：

- 拦截器中查询 `sys_tenant` 或 `sys_role`。
- 若 `status == 0`，直接抛出 `PermissionDeniedException`，不进入后续 AI 流程。

## 6. 非功能需求 (NFR)

1. **性能 (Performance)**：

- Bus Kernel 的 Token 解析与验签必须在内存中完成（<1ms），严禁在拦截器层查库（除非缓存未命中）。
- 租户状态、角色权限表应缓存在 Redis 或本地 Caffeine 中。

2. **安全性 (Security)**：

- `System_Secret` 必须严格保密，建议通过环境变量注入，通过定期轮换 Secret 实现 Token 批量失效。
- 跨租户数据访问必须在 ORM 层面（MyBatis-Flex）做强制物理隔离。

3. **初始化**：
   初始化一个可以正常登录的admin用户

---

## 7. 开发分工建议

- **Bus Kernel (Java)**：
- 实现 Token 生成与验签工具类 (`TokenProvider`)。
- 实现 `AuthInterceptor` 和 MyBatis-Flex 的 `TenantFactory`。
- **AI Engine (Python)**：
- 在 LangGraph 的 `State` 中增加 `auth_token` ，`query_user`字段。
- 修改所有 `ToolNode`，确保发起 HTTP 请求时自动携带 Header 中的 Token。
- 更新 System Prompt 模板，能够读取 User Info 并注入 Context。
- **DeciGro FE (Vue)**：
- 实现登录逻辑，存储 Token 到 Pinia/LocalStorage。
- 在所有 Axios 请求中自动附加 `X-Auth-Token`。
- 根据 User Role 简单控制侧边栏菜单的显示。
