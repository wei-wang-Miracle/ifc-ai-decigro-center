# IFC AI DeciGro Center (AI智能决策增长中心)

IFC AI DeciGro Center 是一个基于 **Multi-Agent 系统设计思想** 构建的智能决策与增长平台。本项目旨在通过 AI 赋能业务，打造一个集感知、决策、执行于一体的闭环自动化系统，实现业务增长与效率提升。

系统采用前后端分离的现代化微服务架构，由 **AI 引擎**、**业务内核** 和 **前端交互** 三大核心模块组成。

## 🏗 系统架构 (Architecture)

系统遵循 **“大脑-躯干-界面”** 的仿生设计理念：

- **🧠 [AI Engine](./ai-engine/README.md)**: **系统大脑**。基于 Python 生态构建，负责复杂的逻辑推理、意图识别、Agent 编排（LangGraph）以及决策制定。它是智能的源头。
- **⚙️ [Bus Kernel](./bus-kernel/README.md)**: **系统躯干**。基于 Java Spring Boot 构建，它是连接 AI 与真实业务世界的桥梁。
  - **Context Provider**: 为 AI 提供结构化的业务上下文数据。
  - **Tools Provider**: 将业务能力封装为 AI 可调用的工具（Tools）。
  - **Gatekeeper**: 负责权限校验、安全审计和租户隔离。
- **💻 [DeciGro FE](./decigro-fe/README.md)**: **系统界面**。基于 Vue 3 构建，提供直观的人机交互界面，支持 AI 对话、工作台操作及系统管理。

## 📂 模块详情 (Modules)

### 1. AI Engine (智能引擎)

> _核心职责：推理、决策、编排_

- **技术栈**: Python 3.12+, FastAPI, LangChain, LangGraph, Pydantic, uv
- **设计模式**: Plan and Execute, COT (Chain of Thought), ReAct
- **功能**:
  - 基于 Multi-Agent 的任务编排。
  - 记忆管理与工作流控制。
  - LLM 交互与结构化输出。

### 2. Bus Kernel (业务内核)

> _核心职责：上下文提供、工具执行、安全管控_

- **技术栈**: Java 17, Spring Boot 3.2+, Mybatis-Flex, PostgreSQL, Redis
- **核心理念**:
  - **降低认知负载**: 将复杂的业务数据转化为结构化语义信息提供给 Agent。
  - **提升执行确定性**: 标准化 API 接口，确保 Function Calling 准确执行。
  - **安全与审计**: 严格的租户权限控制与全链路执行日志。

### 3. DeciGro FE (前端交互)

> _核心职责：用户交互、管理配置、可视化_

- **技术栈**: Node.js 20+, Vue 3, TypeScript, Vite, TailwindCSS, Element Plus
- **功能**:
  - **管理后台**: 租户、会话、工具及审计日志管理。
  - **交互终端**: 智能对话框、业务工作台、数据报表 (Echarts)。

## 🚀 快速开始 (Getting Started)

### 环境要求 (Prerequisites)

- **Java**: JDK 17+
- **Node.js**: v20.0+
- **Python**: 3.12+
- **Database**: PostgreSQL 17+, Redis 7.0+

### 项目初始化 (Installation)

_(项目尚处于初始化阶段，请参考各子模块 README 进行配置)_

---

_Copyright © 2026 IFC AI DeciGro Center Team._
