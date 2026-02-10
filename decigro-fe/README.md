# 💻 DeciGro FE — 前端管理界面

> **系统界面**：只 "看" 和 "传"，不 "算"。负责数据展示、用户交互和配置管理。

## 概述

DeciGro FE 是 NexusGraph 系统的 **用户交互界面** —— 它为管理员和业务用户提供直观的操作界面，涵盖 AI 智能对话、工具/Agent 管理、标签管理、审计监控和系统管理全功能。

---

## 技术栈

| 技术             | 版本 | 用途        |
| ---------------- | ---- | ----------- |
| **Vue**          | 3.5+ | 前端框架    |
| **TypeScript**   | 5.6+ | 类型安全    |
| **Vite**         | 6.0+ | 构建工具    |
| **Element Plus** | 2.9+ | UI 组件库   |
| **Pinia**        | 2.3+ | 状态管理    |
| **Vue Router**   | 4.5+ | 路由管理    |
| **Axios**        | 1.7+ | HTTP 客户端 |

---

## 功能模块

### 🤖 AI 智能对话 (`/chat/index`)

对话式 AI 交互界面，类 ChatGPT 体验：

- **多会话管理**：创建、切换、删除、重命名会话
- **实时对话**：与 AI Engine 的工作流直接交互
- **消息持久化**：消息自动保存到 Bus Kernel
- **Task 追踪**：每条 AI 回复关联 `task_id` 和 `trace_id`

### 🔧 工具管理 (`/tool/list`)

注册中心的工具管理后台：

- **工具卡片列表**：卡片式展示，支持关键字和标签筛选
- **可视化编辑**：表单式编辑 Tool Card 全部字段
- **参数定义**：可视化配置入参 (`tool_parameters`) 和出参 (`output_schema`)
- **少样本配置**：配置输入/输出示例，增强 LLM 理解
- **Schema 预览**：实时预览 OpenAI Function Calling 格式的 Schema
- **上下线控制**：一键上线/下线，即时生效
- **名称校验**：实时检查 `tool_name` 唯一性

### 🧠 智能体管理 (`/agent/list`)

注册中心的 Agent 管理后台：

- **Agent 卡片列表**：展示 Agent 及其状态
- **全面配置**：编辑名称、别名、描述、系统提示词、负向提示词
- **工具绑定**：从可用工具列表中选择绑定工具
- **推理框架选择**：支持 ReAct、PlanSolve 等推理框架
- **版本管理**：Agent 版本标记

### 🏷 标签管理 (`/tag/list`)

客户标签主数据管理：

- **分类树**：左侧分类树形结构导航
- **标签列表**：右侧分页表格，支持分类筛选和关键字搜索
- **标签编辑**：标签名称、字段名、数据类型等
- **枚举值管理**：关联枚举值的 CRUD
- **批量迁移**：支持跨分类批量迁移标签

### 📊 审计监控 (`/audit/list`)

AI 全链路审计追踪界面：

- **审计列表**：分页展示，支持多维度筛选
  - Trace ID / Task ID / User ID 精确匹配
  - Agent 名称、执行状态、工具名称筛选
  - 时间范围筛选
  - 用户反馈筛选
- **审计详情抽屉**：展示完整执行堆栈
  - Graph 节点执行时间线
  - Agent 快照：使用的提示词和工具
  - 工具调用详情：入参、出参、耗时

### 🔐 系统管理 (`/system/*`)

| 页面         | 路由               | 功能                            |
| ------------ | ------------------ | ------------------------------- |
| **用户管理** | `/system/user`     | 用户 CRUD、角色分配、工具白名单 |
| **角色管理** | `/system/role`     | 角色 CRUD、工具权限配置         |
| **部门管理** | `/system/dept`     | 组织架构树形管理                |
| **租户管理** | `/system/tenant`   | 多租户启用/禁用                 |
| **在线用户** | `/system/online`   | 实时在线用户监控、强制下线      |
| **个人信息** | `/system/profile`  | 个人资料修改、头像上传          |
| **修改密码** | `/system/password` | 密码修改                        |

---

## 路由结构

```
/login                  # 登录页
/                       # 主布局 (Layout)
├── /system/user        # 用户管理
├── /system/role        # 角色管理
├── /system/dept        # 部门管理
├── /system/tenant      # 租户管理
├── /system/online      # 在线用户
├── /system/profile     # 个人信息
├── /system/password    # 修改密码
├── /tag/list           # 标签管理
├── /tool/list          # 工具管理
├── /agent/list         # 智能体管理
├── /chat/index         # AI 智能对话
└── /audit/list         # 审计监控
```

---

## 目录结构

```
decigro-fe/
├── package.json               # 项目配置与依赖
├── vite.config.ts             # Vite 构建配置（含代理设置）
├── tsconfig.json              # TypeScript 配置
├── README.md                  # 本文档
├── index.html                 # HTML 入口
├── public/                    # 静态资源
│
├── src/
│   ├── main.ts                # 应用入口
│   ├── App.vue                # 根组件
│   │
│   ├── router/                # 路由配置
│   │   └── index.ts           # 路由定义 + 全局导航守卫
│   │
│   ├── stores/                # Pinia 状态管理
│   │   └── user.ts            # 用户状态（Token、用户信息）
│   │
│   ├── layout/                # 全局布局
│   │   └── index.vue          # 侧边栏 + 顶栏 + 内容区
│   │
│   ├── views/                 # 页面视图
│   │   ├── login/             # 登录页
│   │   │   └── index.vue
│   │   ├── chat/              # AI 智能对话
│   │   │   └── index.vue
│   │   ├── tool/              # 工具管理
│   │   │   └── index.vue
│   │   ├── agent/             # 智能体管理
│   │   │   └── index.vue
│   │   ├── tag/               # 标签管理
│   │   │   └── index.vue
│   │   ├── audit/             # 审计监控
│   │   │   ├── index.vue      # 审计列表
│   │   │   └── DetailDrawer.vue  # 审计详情抽屉
│   │   └── system/            # 系统管理
│   │       ├── user/          # 用户管理
│   │       ├── role/          # 角色管理
│   │       ├── dept/          # 部门管理
│   │       ├── tenant/        # 租户管理
│   │       ├── online/        # 在线用户
│   │       └── profile/       # 个人信息 + 修改密码
│   │
│   ├── api/                   # API 请求封装
│   ├── utils/                 # 工具类
│   └── assets/                # 静态资源
```

---

## 开发代理配置

`vite.config.ts` 中配置了 API 代理，将请求转发到对应的后端服务：

| 前端路径前缀 | 代理目标                | 后端服务   |
| ------------ | ----------------------- | ---------- |
| `/api/dg`    | `http://127.0.0.1:8080` | Bus Kernel |
| `/api/v1`    | `http://127.0.0.1:8001` | AI Engine  |

> ⚠️ 注意：代理目标使用 `127.0.0.1` 而非 `localhost`，避免 IPv6 解析问题。

---

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 开发模式

```bash
npm run dev
```

### 3. 构建生产包

```bash
npm run build
```

### 4. 访问

- **开发地址**: [http://localhost:5173](http://localhost:5173)
- **默认账号**: `admin` / `admin`

---

## 认证机制

前端采用 **Token 认证**：

1. 用户在登录页输入用户名和密码（密码经 RSA 公钥加密）
2. 调用 `POST /api/dg/auth/login` 获取 Token
3. Token 存储在 Pinia Store 中
4. 后续所有 API 请求自动携带 `X-Auth-Token` 请求头
5. 全局导航守卫：未登录用户自动跳转到登录页
