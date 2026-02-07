# PRD: MAS 工具注册中心 (Tool Registry) & Tool Card 管理后台

核心设计哲学参考 **Claude Skill / OpenAI Function Calling**，但在数据结构上更进一步，强制要求录入“AI 友好”的元数据，以降低 Agent 调用时的幻觉率，提高参数填充的准确性。

## 项目背景与目标

- **背景**: 在 Multi-Agent System (MAS) 中，Tool 是 Agent 的核心能力延伸。为了让 Agent 准确调度工具，需要一个中心化的注册管理平台。
- **目标**: 建立一套 "AI-Friendly" 的工具注册中心，不仅管理工具的生命周期，更核心的是管理**工具的认知语义**，确保 LLM 能精准理解 `Identity` (我是谁)、`Intent` (我能干什么) 和 `Protocol` (怎么用我)。

## 1. 核心设计理念：AI-First Schema

本系统的核心不仅仅是 CRUD，而是**Prompt Engineering as Code**。

- **语义优先**: 字段设计强制要求包含 "Context" (语境) 和 "Constraint" (约束)，而不仅仅是数据类型。
- **自愈契约**: 错误处理机制必须包含 "Recovery Hint" (恢复提示)，以便 Agent 自动重试。
- **少样本增强**: 强制录入 `Few-Shot Examples`，在 Agent 调用时动态注入 Prompt，提升准确率。
- **生命周期管理**：支持工具的版本控制、上下架管理。
- **标准化录入**：提供严格的 Schema 校验，确保录入的工具定义符合 LLM 的认知逻辑。

## 2. 核心功能需求 (Functional Requirements)

### 2.1 工具管理 (Tool Management - CRUD)

#### 2.1.1 创建/编辑工具 (Create/Update)

后台需提供表单或 JSON 编辑器，支持以下字段的录入与校验：

- **基本信息 (Identity)**:
- `tool_name`: 校验 Snake Case (e.g., `calculate_tax`).
- `tool_description`: 强制建议包含 Trigger (何时用), Action (做什么), Constraint (限制).
- `tool_tags`: 标签数组，可为空，用于选择增强，或者工具检索 (e.g., `["finance", "search"]`).

- **协议控制 (Protocol)**: tool_protocol 枚举值：http、reference
- **HTTP 模式**: 需录入 URLpath

- **参数定义 (Parameters - JSON Schema)**:tool_parameters
- 核心逻辑：利用 JSON Schema 标准定义入参。
  最终入库是JSON Array格式，每个JSON对象代表一个入参，入参对象包含以下字段： param_name、param_type、param_description、param_required、param_example

- **Few-Shot 样本 (Examples)**:
- 入参示例：`input_examples` (JSON )
- 出参示例：`output_examples` (JSON)

## 3. 数据模型设计 (Data Model - PostgreSQL)

本模型设计采用了 **PostgreSQL + JSONB**。为了适应 AI 的灵活性，我们将结构化的元数据（如 Name, Protocol）与半结构化的描述数据（Parameters, Examples）结合存储。

### 3.1 DDL Script (SQL)

```sql

-- ----------------------------
-- Table structure for tool_cards
-- ----------------------------
CREATE TABLE tool_cards (
    id BIGINT NOT NULL,

    -- 1. Identity & Intent (身份与意图)
    tool_name VARCHAR(128) NOT NULL,
    -- 唯一标识，建议 snake_case，如 'get_weather_data'

    tool_description TEXT NOT NULL,
    -- 核心 Prompt：包含 Action, Trigger, Constraint。
    -- Ex: "Retrieves weather. Use when user asks for temperature. Input strictly city name."

    tool_tags TEXT[] DEFAULT '{}',
    -- 标签，用于检索或权限分组，如 ['finance', 'external_api']

    tool_version VARCHAR(32) DEFAULT '1.0.0',
    -- 版本号
    tool_privileges VARCHAR(32) DEFAULT 'public',
    -- 权限枚举：public、protected

    -- 2. Protocol (调用协议)
    tool_protocol VARCHAR(32) NOT NULL,
    -- 协议枚举：http、reference

    url_path VARCHAR(128),
    -- 当 protocol='http' 时必填，例如 '/api/v1/weather'
    -- 基础 Host 通常在 MAS 环境变量中配置，此处仅存 Path，也可存完整 URL
    reference_target VARCHAR(128),
    -- 当 protocol='reference' 时必填，例如 'tool_cards'

    -- 3. Parameters (参数定义)
    -- 存储为一个 JSON Array，符合前端表单结构，便于编辑
    -- 结构: [{ "param_name": "city", "param_type": "string", "param_description": "...", "param_required": true, "param_example": "Beijing" }]
    tool_parameters JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- 4. Few-Shot Examples (少样本增强)
    -- 输入示例：用户视角的 Prompt 或 参数 JSON
    -- 结构: ["Check weather in Tokyo", "What is the price of AAPL?"]
    -- 或者更结构化: [{"scenario": "Normal query", "content": "..."}]
    input_examples JSONB DEFAULT '[]'::jsonb,

    -- 输出示例：工具预期返回的数据结构示例，帮助 Agent 理解 schema
    -- 结构: [{"temperature": 25, "unit": "celsius"}]
    output_examples JSONB DEFAULT '[]'::jsonb,
    is_online BOOLEAN DEFAULT false,

    -- 5. Meta Information (元数据)
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    -- 原CREATE_DATE
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    manager_by VARCHAR(64), -- 创建人 ID 或 Name

    -- 约束
    CONSTRAINT uq_tool_name UNIQUE (tool_name)
);
-- ----------------------------
-- Comments (AI 辅助理解数据库结构)
-- ----------------------------
COMMENT ON TABLE tool_cards IS 'MAS 工具注册表，存储 Tool Card 定义';
COMMENT ON COLUMN tool_cards.tool_parameters IS '参数列表数组，每个元素包含 name, type, description, required, example';
COMMENT ON COLUMN tool_cards.input_examples IS 'Few-Shot Input: 用于告诉 Agent 用户可能会怎么问';
COMMENT ON COLUMN tool_cards.output_examples IS 'Few-Shot Output: 用于告诉 Agent 工具会怎么回';

```

### 3.2 关键字段 JSON 结构示例

#### `tool_parameters` (存储结构)

这是后台编辑时的数据结构，**注意**：在提供给 LLM 时，需要在运行时（Runtime）转换为 OpenAI 标准的 JSON Schema `properties` 格式。

```json
[
  {
    "param_name": "city",
    "param_type": "string",
    "param_description": "The target city name for weather query. Must be in English.",
    "param_required": true,
    "param_example": "Shanghai"
  },
  {
    "param_name": "days",
    "param_type": "integer",
    "param_description": "Number of forecast days. Max 7.",
    "param_required": false,
    "param_example": 3
  }
]
```

---

## 4. 功能建设列表 (Feature List)

### 4.1 管理侧功能 (Admin Console)

#### 工具管理管理

1. **工具列表 (Tool List)**:

- 展示工具名称、描述、版本、Protocol、在线状态、标签。
- 支持按标签、名称搜索。
- 展示形式：交互式卡片，极简风格，点击卡片进行查看和编辑
- FontAwesome - 提供通用的视觉隐喻（如云朵、数据库、图片图标）。

2. **工具编辑器 工具的CRUD (Tool Editor / Wizard)**:

- **基本信息录入**: 表单校验 `tool_name` (Snake Case 正则校验 `^[a-z0-9_]+$`)，后端需要进行唯一性校验
- **参数配置器**: 动态增删改参数行（Name, Type, Description, Required, Example）。
- **协议切换**: 选择 HTTP 显式输入 `url_path`，选择 Reference 输入 `reference_target`。
- **JSON 预览**: 实时预览转换后的 OpenAI Function Schema，方便开发者核对。

3. **生命周期控制**:

- 上线 (Publish): 状态流转 is_online=true
- 下线 (Deprecate): is_online=false

## 5.前端风格设计

# UI/UX 设计规范：MAS Registry "Light Cockpit"

本设计文档旨在定义 MAS 工具注册中心的视觉语言。
**核心隐喻**：**精密仪器仪表盘 (Precision Instrument Panel)**。
**设计原则**：摒弃传统 Web 表单的松散感，构建高密度、高响应、模块化的“操作舱”。

---

## 1. 核心理念 (Core Philosophy)

- **Precision (精确)**：像素级对齐，严格的网格系统，数据展示零歧义。
- **Structured (结构化)**：模块化布局，信息层级通过框线而非留白区分。
- **Immersive (沉浸)**：减少页面跳转，利用侧边栏、模态框和折叠面板保持上下文。
- **Retro-Logic (复古逻辑)**：在现代高清界面中融入**像素 (Pixel)** 元素，隐喻“底层逻辑”和“数字基石”。

---

## 2. 布局与框架 (Layout & Framework)

### 2.1 模块化网格 (Bento Grid System)

- **布局逻辑**：采用 **Bento (便当盒)** 网格布局。每个功能区（列表、预览、日志）都是独立的“容器单元”。
- **边框工程**：
- 放弃大面积阴影，使用**实线边框**定义区域。
- **高对比度**：在亮色模式下，使用深灰/黑色细线 (1px) 勾勒轮廓，营造工程蓝图感。
- **R角处理**：小圆角 (2px - 4px) 或直角，拒绝大圆角，保持硬朗的工业风。

### 2.2 仪表盘式密度 (Cockpit Density)

- **紧凑排版**：减少组件间的 Padding。信息密度应高于消费级 App，接近 IDE（集成开发环境）。
- **固定视口**：主操作界面应尽量适配一屏显示，减少整页滚动，内容区域内部滚动。

---

## 3. 组件设计 (Component Design)

### 3.1 交互式卡片 (The Tool Card)

- **实体感**：卡片不应像“浮在纸上”，而应像“嵌入在卡槽中”。使用内阴影或加粗边框来体现嵌入感。
- **状态指示灯**：卡片右上角使用 **像素化 (Pixelated)** 的方块点阵来表示状态 (Online/Draft/Error)。
- _Example_: 一个 3x3 的像素格，而非一个平滑的圆点。

- **微交互**：Hover 时，卡片边框加粗或出现“扫描线”效果，提供明确的选中反馈。

### 3.2 像素化图标与装饰 (Pixel Elements)

- **功能性图标**：所有的系统图标（如保存、删除、API、链接）使用 **16-bit 像素风格**。这不仅是装饰，更强化“这是机器指令”的语义。
- **装饰性角标**：容器的四角可添加像素化的“准星”或“支架”装饰，增强取景器 (Viewfinder) 的视觉感。
- **进度条/加载器**：使用块状进度条（Block Progress Bar），而非平滑的线性进度条。

### 3.3 输入控件 (Input Slots)

- **Slot Metaphor**：输入框不是简单的下划线，而是封闭的矩形“插槽”。
- **Monospace Input**：所有输入内容（尤其是 Key, Name, Config）默认使用等宽字体。

---

## 4. 排版与字体 (Typography)

### 4.1 混合字体策略

- **UI 标题 (Heading)**：使用粗壮的无衬线字体 (如 Inter, Roboto)，强调结构。
- **数据与代码 (Data/Code)**：**JetBrains Mono** 或 **Fira Code**。所有参数、JSON、返回值必须使用等宽字体。
- **元数据标签 (Pixel Touch)**：极少量的 Label（如 `VER 1.0`, `HTTP`, `GET`）使用 **像素字体 (Pixel Font)**，作为视觉点缀，模拟电子显示屏效果。

### 4.2 文本处理

- **高对比度**：正文使用纯黑或极深灰，拒绝浅灰字。确保在任何光照下清晰可读。
- **截断处理**：长文本（如 Description）优先使用折叠/展开，而非省略号，保证信息可获取性。

---

## 5. 可视化反馈 (Visual Feedback)

### 5.1 JSON 结构可视化

- **连接线**：当可视化参数层级时，使用**折线 (Orthogonal Lines)** 而非贝塞尔曲线。保持电路图般的硬朗感。
- **树状图**：节点使用矩形框，连接点使用像素块。

### 5.2 幻觉检测反馈

- 当系统检测到模糊语义时，不使用柔和的警告色，而是使用**故障艺术 (Glitch) 效果**或**像素化抖动**来提示开发者“此处逻辑不清晰”。
