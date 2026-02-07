# PRD: MAS 智能体注册中心 (Agent Registry) & Agent Card 管理后台

**核心设计哲学**：如果说 Tool Card 是 API 文档，那么 Agent Card 就是 **“数字员工档案”**。我们需要管理不仅仅是配置参数，更是 Agent 的 **“人设 (Persona)”**、**“大脑 (Cognition)”** 和 **“职权 (Permission)”**。

## 1. 项目背景与目标

- **背景**: 在 Multi-Agent System (MAS) 中，Agent 是任务的执行主体。随着业务复杂度提升，我们需要管理不同职责（如“客户画像分析师”、“代码审计员”）的 Agent 集群。
- **目标**: 建立一套 **"Digital Workforce" (数字员工)** 管理体系。
- **对于 Planner**: 能快速检索到最适合的 Agent 来分发任务（路由能力）。
- **对于 Runtime**: 能毫秒级加载 Agent 的系统提示词、工具集和记忆配置（执行能力）。
- **对于 Manager**: 通过可视化的“工牌”形式，直观管理虚拟团队。

## 2. 核心设计理念：Persona-First Schema

- **拟人化定义**: 强制要求录入 `Role` (角色名) 和 `Slogan` (行为准则)，赋予 Agent 独特的性格，减少机器味，提升交互体验。
- **认知封装**: 将 System Prompt 视为 Agent 的“灵魂”，将 Tools 视为 Agent 的“技能”。
- **可视化隐喻**: 界面设计严格遵循 **“实体工牌 (Physical Badge)”** 的隐喻，让管理者感觉自己在管理真实的员工。

## 3. 核心功能需求 (Functional Requirements)

### 3.1 智能体管理 (Agent Management - CRUD)

#### 3.1.1 创建/编辑 Agent (Digital Onboarding)

后台需提供“入职登记表”式的编辑器：

- **身份与人设 (Identity)**:
- `agent_name`: 唯一标识 (Snake Case, e.g., `user_profiler`).
- `agent_role`: 自然语言职称 (e.g., "客户画像分析师").
- `agent_avatar`: **强制要求像素风 (Pixel Art)** 头像上传或生成，保持视觉统一。
- `agent_slogan`: 一句简短的格言，用于强化人设 (e.g., "允许中场休息，拒绝止步不前").
- `agent_description`: 给 Router/Planner 看的路由描述 (e.g., "擅长从非结构化对话中提取用户标签和偏好").

- **大脑配置 (Cognition - System Prompt)**:
- **System Prompt**: 核心指令集。支持变量插入（如 `{{user_context}}`）。
- **Negative Prompt**: 行为禁区 (e.g., "严禁编造用户信息").
- **Reasoning Framework**: 选择推理模式 (e.g., `ReAct`, `COT`, `Direct`).

- **技能挂载 (Capabilities)**:
- **Bound Tools**: 从《工具注册中心》选择绑定的 Tool ID 列表。
- **Knowledge Base**: 绑定特定的知识库 ID (RAG Scope).

### 3.2 智能体广场 (Agent Roster)

- **展示形式**: 网格化的 **“工牌墙”**。
- **状态可视化**: 工牌上的指示灯显示 Agent 的运行状态 (Idle, Busy, Offline).

## 4. 数据模型设计 (Data Model - PostgreSQL)

```sql
-- ----------------------------
-- Table structure for agent_cards
-- ----------------------------
CREATE TABLE agent_cards (
    id BIGINT NOT NULL,

    -- 1. Identity (数字身份)
    agent_name VARCHAR(128) NOT NULL UNIQUE,
    -- 唯一ID，如 'marketing_copywriter'

    agent_role VARCHAR(64) NOT NULL,
    -- 职称，如 '文案策划专家'

    agent_avatar TEXT,
    -- 头像 URL，建议存储 Base64 或 OSS 路径，前端渲染为像素风

    agent_slogan VARCHAR(128),
    -- 个性签名，如 '用文字打动人心'

    agent_description TEXT NOT NULL,
    -- 路由描述：给上级 Agent 或 Router 看的，用于任务分发

    -- 2. Cognition (认知内核)
    system_prompt TEXT NOT NULL,
    -- 核心人设指令 (System Message)

    negative_prompt TEXT,
    -- 负向约束

    reasoning_config JSONB DEFAULT '{"framework": "ReAct", "temperature": 0.7}'::jsonb,
    -- 推理配置

    -- 3. Capabilities (能力挂载)
    -- 存储 tool_cards 表中的 tool_name 列表
    bound_tools JSONB DEFAULT '[]'::jsonb,
    -- 示例: ["web_search", "calc_tax"]

    agent_tags TEXT[] DEFAULT '{}',
    -- 标签，如 ['marketing', 'writing']

    -- 4. Meta & Status
    is_online BOOLEAN DEFAULT false,
    -- 上下线状态

    manager_by VARCHAR(64),
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE agent_cards IS 'MAS 智能体注册表，存储 Agent 定义';
COMMENT ON COLUMN agent_cards.bound_tools IS '绑定的工具列表，关联 tool_cards.tool_name';

```

---

## 5. 前端风格设计：The "ID Badge" Aesthetic

参考你上传的图片，我们将 UI 风格定义为 **"Neo-Retro Corporate" (新复古企业风)**。

### 5.1 视觉核心隐喻：实体工牌 (Physical Badge)

在列表页或详情预览时，Agent 不再展示为普通的 Table Row，而是展示为一张张悬挂的工牌。

- **工牌结构 (The Card Structure)**:
- **挂绳 (Lanyard)**: 顶部必须有一个视觉上的“挂绳接口”或“穿孔”，暗示这是可佩戴的实体。
- **黑带 (Black Header)**: 姓名区域使用纯黑背景 + 反白文字，高对比度，位于卡片上部。
- **圆角 (Rounding)**: 卡片整体采用大圆角 (Radius 12px-16px)，模拟塑料材质。
- **阴影 (Drop Shadow)**: 使用弥散阴影，营造卡片悬浮在桌面上的层次感。

### 5.2 像素化与排版 (Pixel & Typography)

- **像素头像 (Pixel Avatar)**:
- 所有 Agent 的头像必须通过算法处理或人工上传为 **Bit/Pixel Art** 风格。
- _Rationale_: 像素风传达了“这是数字生命”的隐喻，同时与黑色粗线条形成复古科技感。
- 头像需放置在卡片正中央，留白充足。

- **字体层级**:
- **Name (黑底白字)**: 使用粗壮的无衬线字体，字号大，紧凑。
- **Role (职称)**: 使用 **Bold** 字体，黑色，清晰有力。
- **Slogan (格言)**: 使用 **Serif (衬线体)** 或细体，灰色，营造一种“座右铭”的优雅感。

- **底部标识**:
- 左下角：系统 Logo (如 KIMI/MAS)。
- 右下角：操作按钮 (如 "角色说明" / "配置")，采用胶囊型黑色按钮，反白文字。

### 5.3 交互动效 (Interactions)

- **Flip (翻转)**:
- 点击工牌右下角的“角色说明”按钮，工牌执行 **3D 翻转** 动画。
- **背面 (Back Side)**: 显示 System Prompt 的摘要、绑定的工具图标列表、以及性能指标（如平均响应时间）。

- **Swing (晃动)**:
- 当鼠标 Hover 到工牌上时，工牌模拟物理重力，产生轻微的 **左右钟摆晃动**，仿佛挂在绳子上。

### 5.4 编辑器布局 (The "Personnel File")

点击工牌进入编辑模式时，不使用弹窗，而是展开一个 **“员工档案袋 (Personnel File)”** 风格的界面：

- **左侧 (Profile)**: 实时预览工牌样式。
- **右侧 (Form)**:
- **基本信息**: 填写姓名、职称、上传头像。
- **认知配置 (System Prompt)**: 提供带有语法高亮的 Prompt 编辑器。
- **工具箱 (Toolbox)**: 提供一个可搜索的 Tool 列表（来自 Tool Registry），支持拖拽将工具“放入” Agent 的能力槽。
