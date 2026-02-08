-- =================================================================
-- 1. 标签分类表 (customer_tag_category)
-- 原表: T_LABEL_CATEGORY
-- =================================================================
CREATE TABLE IF NOT EXISTS customer_tag_category (
    id BIGINT NOT NULL,
    -- 主键ID (原ID)
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    -- 原CREATE_DATE
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- 原UPDATE_DATE
    name VARCHAR(50) NOT NULL,
    -- 分类名称
    parent_id BIGINT DEFAULT 0,
    -- 上级分类ID
    sort_index INTEGER DEFAULT 1 NOT NULL,
    -- 排序
    CONSTRAINT pk_customer_tag_category PRIMARY KEY (id)
);
COMMENT ON TABLE customer_tag_category IS '标签分类表 (原T_LABEL_CATEGORY)';
COMMENT ON COLUMN customer_tag_category.id IS '主键ID，手动维护或序列生成';
COMMENT ON COLUMN customer_tag_category.name IS '分类名称';
COMMENT ON COLUMN customer_tag_category.parent_id IS '上级分类ID，一级分类设为0';
COMMENT ON COLUMN customer_tag_category.create_time IS '创建时间';
COMMENT ON COLUMN customer_tag_category.update_time IS '最后更新时间';
-- =================================================================
-- 2. 客户标签表 (customer_tag)
-- 原表: T_LABEL
-- 变更: 主键改为 tag_field, 新增 tag_table, desc
-- =================================================================
CREATE TABLE IF NOT EXISTS customer_tag (
    tag_field VARCHAR(64) NOT NULL,
    -- 主键, 字段名 (原FIELD, 现作为主键)
    tag_table VARCHAR(64) NOT NULL,
    -- 标签来源表名
    tag_name VARCHAR(200) NOT NULL,
    -- 标签中文名称 (原NAME)
    tag_desc TEXT,
    -- 维护口径/描述 (desc是关键字，需加引号)
    value_type VARCHAR(20) NOT NULL,
    -- 值类型: string, number, enum, date, array
    category_id BIGINT NOT NULL,
    -- 关联分类ID
    remark VARCHAR(255),
    -- 备注 (保留原REMARK)
    sort_index INTEGER DEFAULT 0 NOT NULL,
    -- 排序
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_customer_tag PRIMARY KEY (tag_field)
);
-- 创建外键索引通常建议加上，用于优化关联查询
CREATE INDEX idx_customer_tag_category ON customer_tag(category_id);
COMMENT ON TABLE customer_tag IS '客户标签定义表 (原T_LABEL)';
COMMENT ON COLUMN customer_tag.tag_field IS '主键，标签字段英文名，用于SQL拼接';
COMMENT ON COLUMN customer_tag.tag_table IS '标签对应的来源表名';
COMMENT ON COLUMN customer_tag.tag_name IS '标签中文名称';
COMMENT ON COLUMN customer_tag.tag_desc IS '标签维护口径/详细描述';
COMMENT ON COLUMN customer_tag.value_type IS '值类型：string, number, enum, date, array';
COMMENT ON COLUMN customer_tag.category_id IS '标签分类ID，关联 customer_tag_category.id';
COMMENT ON COLUMN customer_tag.create_time IS '创建时间';
COMMENT ON COLUMN customer_tag.update_time IS '最后更新时间';
-- =================================================================
-- 3. 标签枚举值表 (customer_tag_enum)
-- 原表: T_LABEL_ENUM_VALUE
-- 适配: 关联字段由 ID(number) 变更为 tag_field(varchar)
-- =================================================================
CREATE TABLE IF NOT EXISTS customer_tag_enum (
    id BIGINT NOT NULL,
    -- 主键ID (建议使用序列)
    tag_field VARCHAR(64) NOT NULL,
    -- [变更] 关联 customer_tag 的 tag_field
    enum_code VARCHAR(100),
    -- 枚举值代码 (SQL拼接用)
    enum_name VARCHAR(100),
    -- 枚举展示名称
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_customer_tag_enum PRIMARY KEY (id)
);
COMMENT ON TABLE customer_tag_enum IS '标签枚举值可选表 (原T_LABEL_ENUM_VALUE)';
COMMENT ON COLUMN customer_tag_enum.tag_field IS '关联 customer_tag 的字段名';
COMMENT ON COLUMN customer_tag_enum.enum_code IS '枚举值代码';
COMMENT ON COLUMN customer_tag_enum.enum_name IS '枚举展示名称';
COMMENT ON COLUMN customer_tag_enum.create_time IS '创建时间';
COMMENT ON COLUMN customer_tag_enum.update_time IS '最后更新时间';
-- ----------------------------
-- Table structure for tool_cards
-- ----------------------------
CREATE TABLE tool_cards (
    -- 1. Identity & Intent (身份与意图)
    tool_name VARCHAR(128) NOT NULL,
    -- 主键，唯一标识，建议 snake_case，如 'get_weather_data'
    tool_description TEXT NOT NULL,
    -- 核心 Prompt：包含 Action, Trigger, Constraint。
    -- Ex: "Retrieves weather. Use when user asks for temperature. Input strictly city name."
    tool_tags JSONB DEFAULT '[]'::jsonb,
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
    -- 出参定义（结构与 tool_parameters 一致）
    -- 结构: [{ "param_name": "temperature", "param_type": "number", "param_description": "温度值", "param_required": true, "param_example": 25 }]
    output_schema JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- 4. Few-Shot Examples (少样本增强) - 改为 TEXT 类型，可填入任意文本含 JSON
    -- 输入示例：用于补充用户视角的 Prompt 或参数示例
    input_examples TEXT DEFAULT '',
    -- 输出示例：工具预期返回的数据结构示例，帮助 Agent 理解 schema
    output_examples TEXT DEFAULT '',
    is_online BOOLEAN DEFAULT false,
    -- 5. Meta Information (元数据)
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    -- 原CREATE_DATE
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    manager_by VARCHAR(64),
    -- 创建人 ID 或 Name
    -- 约束
    CONSTRAINT pk_tool_cards PRIMARY KEY (tool_name)
);
-- ----------------------------
-- Comments (AI 辅助理解数据库结构)
-- ----------------------------
COMMENT ON TABLE tool_cards IS 'MAS 工具注册表，存储 Tool Card 定义';
COMMENT ON COLUMN tool_cards.tool_parameters IS '参数列表数组，每个元素包含 name, type, description, required, example';
COMMENT ON COLUMN tool_cards.input_examples IS 'Few-Shot Input: 用于告诉 Agent 用户可能会怎么问';
COMMENT ON COLUMN tool_cards.output_examples IS 'Few-Shot Output: 用于告诉 Agent 工具会怎么回';
-- 启用必要的扩展（如果需要更复杂的文本搜索，可选）
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE agent_cards (
    -- 1. 身份与注册中心 (Identity & Registry)
    -- 这是一个语义化的 ID，作为主键，方便代码中直接引用 (e.g. agent_cards['data_cleaner'])
    agent_name VARCHAR(100) PRIMARY KEY,
    -- 核心路由描述，给 Manager/Planner 做语义匹配用
    agent_description TEXT NOT NULL,
    -- 标签：使用 PostgreSQL 原生数组类型，支持 GIN 索引加速检索
    -- 对应需求: ['finance', 'external_api']
    agent_tags TEXT [] DEFAULT '{}',
    -- 2. 内核配置 (Core Configuration)
    -- System Prompt: Agent 的灵魂
    system_prompt TEXT NOT NULL,
    -- Negative Prompt: 行为边界
    negative_prompt TEXT,
    -- 工具绑定：
    -- NULL: 表示默认继承用户当前会话可用的所有工具 (All Access)
    -- Empty Array '{}': 表示不使用任何工具 (Pure Chat)
    -- Array ['tool_a']: 仅允许使用指定工具 (Allowlist)
    bound_tools TEXT [],
    -- 推理框架：NULL 则使用系统默认 (e.g. Direct/CoT)，否则指定如 'ReAct'
    reasoning_framework VARCHAR(50),
    -- 3. 元数据 (Meta Information)
    -- 生命周期与管理字段
    agent_version VARCHAR(20) DEFAULT '1.0.0',
    is_online BOOLEAN DEFAULT true,
    -- 上下线状态，方便灰度发布或熔断
    manager_by VARCHAR(100),
    -- 责任人/团队
    create_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
-- 添加字段注释 (Data Dictionary)
COMMENT ON TABLE agent_cards IS 'Agent 注册与配置表';
COMMENT ON COLUMN agent_cards.agent_name IS '唯一标识 (ID)，建议 snake_case';
COMMENT ON COLUMN agent_cards.agent_description IS '给 Planner 看的路由描述';
COMMENT ON COLUMN agent_cards.bound_tools IS 'NULL=全部工具, {}=无工具, [names]=指定工具';