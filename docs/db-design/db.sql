-- =================================================================
-- IFC AI Decigro Center - Database DDL
-- 维护原则: 以 Java Entity 类为单一信源，本文件与实体类保持同步
-- 数据库: PostgreSQL
-- =================================================================

-- =================================================================
-- 系统模块 (sys_*)
-- =================================================================

-- -----------------------------------------------------------------
-- 部门表 (sys_dept)
-- 对应实体: SysDept extends BaseEntity
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_dept (
    dept_id     BIGSERIAL       NOT NULL,
    parent_id   BIGINT,
    dept_name   VARCHAR(100)    NOT NULL,
    created_time TIMESTAMP      DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_time TIMESTAMP      DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_sys_dept PRIMARY KEY (dept_id)
);
COMMENT ON TABLE  sys_dept             IS '部门表，定义职能边界与工作流上下文';
COMMENT ON COLUMN sys_dept.dept_id     IS '部门主键 ID（自增）';
COMMENT ON COLUMN sys_dept.parent_id   IS '父部门 ID，顶级部门为 NULL';
COMMENT ON COLUMN sys_dept.dept_name   IS '部门名称';
COMMENT ON COLUMN sys_dept.created_time IS '创建时间';
COMMENT ON COLUMN sys_dept.updated_time IS '最后更新时间';

-- -----------------------------------------------------------------
-- 角色表 (sys_role)
-- 对应实体: SysRole extends BaseEntity
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_role (
    role_id      BIGSERIAL       NOT NULL,
    role_name    VARCHAR(100)    NOT NULL,
    role_desc    VARCHAR(255),
    agent_list   JSONB           DEFAULT '[]'::jsonb,
    is_enabled   BOOLEAN         DEFAULT true,
    created_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_sys_role PRIMARY KEY (role_id)
);
COMMENT ON TABLE  sys_role             IS '角色表，定义基础权限与工具集模板';
COMMENT ON COLUMN sys_role.role_id     IS '角色主键 ID（自增）';
COMMENT ON COLUMN sys_role.role_name   IS '角色显示名称';
COMMENT ON COLUMN sys_role.role_desc   IS '角色描述';
COMMENT ON COLUMN sys_role.agent_list  IS '角色可用智能体列表（JSONB），对应 PRD 智能体分配';
COMMENT ON COLUMN sys_role.is_enabled  IS '是否启用（true=启用，false=禁用）';

-- -----------------------------------------------------------------
-- 用户表 (sys_user)
-- 对应实体: SysUser extends BaseEntity
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_user (
    id           BIGSERIAL       NOT NULL,
    username     VARCHAR(64)     NOT NULL,
    password     VARCHAR(255)    NOT NULL,
    password_v   VARCHAR(32),
    nick_name    VARCHAR(100),
    gender       INTEGER,
    email        VARCHAR(128),
    phone        VARCHAR(32),
    avatar_path  VARCHAR(512),
    dept_id      BIGINT,
    role_id      BIGINT,
    is_enabled   BOOLEAN         DEFAULT true,
    created_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_sys_user     PRIMARY KEY (id),
    CONSTRAINT uq_sys_user_name UNIQUE (username)
);
COMMENT ON TABLE  sys_user              IS '用户表，系统核心，承载记忆与当前职能';
COMMENT ON COLUMN sys_user.id           IS '用户主键 ID（自增）';
COMMENT ON COLUMN sys_user.username     IS '用户名，全局唯一';
COMMENT ON COLUMN sys_user.password     IS '加密密码（对称加密）';
COMMENT ON COLUMN sys_user.password_v   IS '密码版本号，用于密码轮换';
COMMENT ON COLUMN sys_user.nick_name    IS '昵称';
COMMENT ON COLUMN sys_user.gender       IS '性别（1=男，2=女，0=未知）';
COMMENT ON COLUMN sys_user.email        IS '邮箱';
COMMENT ON COLUMN sys_user.phone        IS '手机号';
COMMENT ON COLUMN sys_user.avatar_path  IS '头像路径';
COMMENT ON COLUMN sys_user.dept_id      IS '所属部门 ID，关联 sys_dept.dept_id';
COMMENT ON COLUMN sys_user.role_id      IS '所属角色 ID，关联 sys_role.role_id';
COMMENT ON COLUMN sys_user.is_enabled   IS '账户状态（true=启用，false=禁用）';

CREATE INDEX IF NOT EXISTS idx_sys_user_dept ON sys_user(dept_id);
CREATE INDEX IF NOT EXISTS idx_sys_user_role ON sys_user(role_id);

-- -----------------------------------------------------------------
-- 租户表 (sys_tenant)
-- 对应实体: SysTenant extends BaseEntity
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_tenant (
    tenant_code  VARCHAR(32)     NOT NULL,
    tenant_name  VARCHAR(128)    NOT NULL,
    agent_list   JSONB           DEFAULT '[]'::jsonb,
    is_enabled   BOOLEAN         DEFAULT true,
    created_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_sys_tenant PRIMARY KEY (tenant_code)
);
COMMENT ON TABLE  sys_tenant              IS '租户表，管理物理边界与系统接入源';
COMMENT ON COLUMN sys_tenant.tenant_code  IS '租户唯一编码（主键），如 HEYI';
COMMENT ON COLUMN sys_tenant.tenant_name  IS '租户名称';
COMMENT ON COLUMN sys_tenant.agent_list   IS '租户绑定的智能体列表（JSONB）';
COMMENT ON COLUMN sys_tenant.is_enabled   IS '是否启用（true=启用，false=禁用）';

-- -----------------------------------------------------------------
-- 用户登录日志表 (sys_login_log)
-- 对应实体: SysLoginLog extends BaseEntity
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sys_login_log (
    token_sign   VARCHAR(256)    NOT NULL,
    username     VARCHAR(64)     NOT NULL,
    ip_address   VARCHAR(64),
    login_time   TIMESTAMP,
    tenant_code  VARCHAR(32),
    is_enabled   BOOLEAN         DEFAULT true,
    created_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_time TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_sys_login_log PRIMARY KEY (token_sign)
);
COMMENT ON TABLE  sys_login_log             IS '用户登录日志表';
COMMENT ON COLUMN sys_login_log.token_sign  IS 'Token 签名（主键）';
COMMENT ON COLUMN sys_login_log.username    IS '登录用户名';
COMMENT ON COLUMN sys_login_log.ip_address  IS '登录 IP 地址';
COMMENT ON COLUMN sys_login_log.login_time  IS '登录时间';
COMMENT ON COLUMN sys_login_log.tenant_code IS '租户编码，用于多租户日志隔离';
COMMENT ON COLUMN sys_login_log.is_enabled  IS '登录状态（true=有效，false=已踢下线）';

CREATE INDEX IF NOT EXISTS idx_login_log_user   ON sys_login_log(username);
CREATE INDEX IF NOT EXISTS idx_login_log_tenant ON sys_login_log(tenant_code);

-- =================================================================
-- MAS 智能体模块 (agent_cards / tool_cards)
-- =================================================================

-- -----------------------------------------------------------------
-- 工具卡片表 (tool_cards)
-- 对应实体: ToolCard
-- 设计理念: AI-First Schema，语义优先，自愈契约，少样本增强
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tool_cards (
    -- 1. Identity & Intent
    tool_name        VARCHAR(128)    NOT NULL,
    tool_alias       VARCHAR(128),
    tool_description TEXT            NOT NULL,
    tool_tags        JSONB           DEFAULT '[]'::jsonb,
    tool_version     VARCHAR(32)     DEFAULT '1.0.0',
    tool_privileges  VARCHAR(32)     DEFAULT 'public',
    -- 2. Protocol
    tool_protocol    VARCHAR(32)     NOT NULL,
    url_path         VARCHAR(512),
    tool_method      VARCHAR(16)     DEFAULT 'POST',
    tool_headers     JSONB           DEFAULT NULL,
    reference_target VARCHAR(128),
    -- 3. Parameters
    tool_parameters  JSONB           NOT NULL DEFAULT '[]'::jsonb,
    output_schema    JSONB           NOT NULL DEFAULT '[]'::jsonb,
    -- 4. Few-Shot Examples
    input_examples   TEXT            DEFAULT '',
    output_examples  TEXT            DEFAULT '',
    -- 5. Meta
    is_online        BOOLEAN         DEFAULT false,
    create_time      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP NOT NULL,
    update_time      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    manager_by       VARCHAR(64),
    CONSTRAINT pk_tool_cards PRIMARY KEY (tool_name)
);
COMMENT ON TABLE  tool_cards                  IS 'MAS 工具注册表，存储 Tool Card 定义';
COMMENT ON COLUMN tool_cards.tool_name        IS '工具唯一标识（主键），建议 snake_case，如 get_weather_data';
COMMENT ON COLUMN tool_cards.tool_alias       IS '工具别名，用于前端展示，可为空';
COMMENT ON COLUMN tool_cards.tool_description IS '核心 Prompt：包含 Action, Trigger, Constraint';
COMMENT ON COLUMN tool_cards.tool_tags        IS '标签列表（JSONB），用于分类检索，如 ["finance","external_api"]';
COMMENT ON COLUMN tool_cards.tool_version     IS '工具版本号，默认 1.0.0';
COMMENT ON COLUMN tool_cards.tool_privileges  IS '权限级别：public（公开）/ protected（需授权）';
COMMENT ON COLUMN tool_cards.tool_protocol    IS '调用协议：http / reference';
COMMENT ON COLUMN tool_cards.url_path         IS 'HTTP URL 路径，protocol=http 时必填';
COMMENT ON COLUMN tool_cards.tool_method      IS 'HTTP 请求方法：GET/POST/PUT/DELETE，默认 POST';
COMMENT ON COLUMN tool_cards.tool_headers     IS '自定义请求头（JSONB），X-Auth-Token 由系统自动注入';
COMMENT ON COLUMN tool_cards.reference_target IS '内部引用目标，protocol=reference 时必填';
COMMENT ON COLUMN tool_cards.tool_parameters  IS '入参定义列表（JSONB），结构：[{param_name,param_type,param_description,param_required,param_example}]';
COMMENT ON COLUMN tool_cards.output_schema    IS '出参定义列表（JSONB），结构与 tool_parameters 一致';
COMMENT ON COLUMN tool_cards.input_examples   IS 'Few-Shot Input：用于告诉 Agent 用户可能会怎么问';
COMMENT ON COLUMN tool_cards.output_examples  IS 'Few-Shot Output：用于告诉 Agent 工具会怎么回';
COMMENT ON COLUMN tool_cards.is_online        IS '是否上线（true=对 Agent 可见，false=草稿）';
COMMENT ON COLUMN tool_cards.manager_by       IS '工具管理/创建人';

-- -----------------------------------------------------------------
-- 智能体卡片表 (agent_cards)
-- 对应实体: AgentCard
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_cards (
    -- 1. Identity & Registry
    agent_name          VARCHAR(100)    NOT NULL,
    agent_alias         VARCHAR(100),
    agent_description   TEXT            NOT NULL,
    agent_tags          JSONB           DEFAULT '[]'::jsonb,
    agent_type          VARCHAR(32)     DEFAULT 'EXECUTOR',
    -- 2. Core Config
    system_prompt       TEXT            NOT NULL,
    negative_prompt     TEXT,
    bound_tools         JSONB           DEFAULT '[]'::jsonb,
    bound_agents        JSONB           DEFAULT '[]'::jsonb,
    reasoning_framework VARCHAR(50),
    -- 3. Meta
    agent_version       VARCHAR(20)     DEFAULT '1.0.0',
    is_online           BOOLEAN         DEFAULT true,
    require_review      BOOLEAN         DEFAULT false,
    human_review_config JSONB           DEFAULT NULL,
    manager_by          VARCHAR(100),
    create_time         TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    update_time         TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_agent_cards PRIMARY KEY (agent_name)
);
COMMENT ON TABLE  agent_cards                     IS 'MAS Agent 注册与配置表';
COMMENT ON COLUMN agent_cards.agent_name          IS '唯一标识（主键），建议 snake_case';
COMMENT ON COLUMN agent_cards.agent_alias         IS '智能体别名/展示名称';
COMMENT ON COLUMN agent_cards.agent_description   IS '给 Planner 看的路由描述，用于语义匹配';
COMMENT ON COLUMN agent_cards.agent_tags          IS '标签列表（JSONB），如 ["finance","external_api"]';
COMMENT ON COLUMN agent_cards.agent_type          IS '智能体类型：PLANNER / EXECUTOR';
COMMENT ON COLUMN agent_cards.system_prompt       IS 'Agent 的系统提示词（灵魂）';
COMMENT ON COLUMN agent_cards.negative_prompt     IS '负向提示词（行为边界）';
COMMENT ON COLUMN agent_cards.bound_tools         IS '工具绑定：NULL=全部工具, []=无工具, [names]=白名单';
COMMENT ON COLUMN agent_cards.bound_agents        IS 'PLANNER 绑定的 EXECUTOR 列表（JSONB）';
COMMENT ON COLUMN agent_cards.reasoning_framework IS '推理框架：NULL=系统默认, 否则如 ReAct / PlanSolve';
COMMENT ON COLUMN agent_cards.agent_version       IS '版本号，默认 1.0.0';
COMMENT ON COLUMN agent_cards.is_online           IS '上线状态，支持灰度发布或熔断';
COMMENT ON COLUMN agent_cards.require_review      IS '是否需要人工审核任务计划（true=需要）';
COMMENT ON COLUMN agent_cards.human_review_config IS '人工审核配置（JSONB），含 review_dimensions / review_instruction / summary_prompt';
COMMENT ON COLUMN agent_cards.manager_by          IS '责任人/团队';

-- =================================================================
-- AI 对话模块 (ai_chat_*)
-- =================================================================

-- -----------------------------------------------------------------
-- AI 聊天会话表 (ai_chat_session)
-- 对应服务: AiChatServiceImpl
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_chat_session (
    session_id    VARCHAR(64)     NOT NULL,
    user_id       VARCHAR(64)     NOT NULL,
    session_title VARCHAR(200)    DEFAULT '新会话',
    create_time   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    update_time   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ai_chat_session PRIMARY KEY (session_id)
);
CREATE INDEX IF NOT EXISTS idx_session_user ON ai_chat_session(user_id, update_time DESC);
COMMENT ON TABLE  ai_chat_session               IS 'AI 聊天会话表';
COMMENT ON COLUMN ai_chat_session.session_id    IS '会话唯一标识';
COMMENT ON COLUMN ai_chat_session.user_id       IS '所属用户标识';
COMMENT ON COLUMN ai_chat_session.session_title IS '会话标题，可由首条消息自动生成';

-- -----------------------------------------------------------------
-- AI 聊天消息表 (ai_chat_message)
-- 对应服务: AiChatServiceImpl
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_chat_message (
    id            BIGSERIAL       NOT NULL,
    session_id    VARCHAR(64)     NOT NULL,
    task_id       VARCHAR(64),
    trace_id      VARCHAR(64),
    role          VARCHAR(16)     NOT NULL,
    content       TEXT            NOT NULL,
    thought_log   TEXT,
    agent_log     TEXT,
    review_detail TEXT,
    create_time   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ai_chat_message PRIMARY KEY (id),
    CONSTRAINT fk_message_session FOREIGN KEY (session_id)
        REFERENCES ai_chat_session(session_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_message_session ON ai_chat_message(session_id, create_time ASC);
CREATE INDEX IF NOT EXISTS idx_message_trace   ON ai_chat_message(trace_id);
COMMENT ON TABLE  ai_chat_message               IS 'AI 聊天消息表';
COMMENT ON COLUMN ai_chat_message.task_id       IS '任务标识，一个 plan 执行期间共享';
COMMENT ON COLUMN ai_chat_message.trace_id      IS '链路追踪 ID，用于审计和问题排查';
COMMENT ON COLUMN ai_chat_message.role          IS '消息角色：user / assistant';
COMMENT ON COLUMN ai_chat_message.thought_log   IS '思考过程（JSON 字符串）';
COMMENT ON COLUMN ai_chat_message.agent_log     IS '智能体动作/日志（JSON 字符串）';
COMMENT ON COLUMN ai_chat_message.review_detail IS '人工审核详情（JSON 字符串）';

-- -----------------------------------------------------------------
-- AI 全链路审计宽表 (ai_chat_trace_index)
-- 对应实体: AiChatTraceIndex
-- 核心价值: 快速筛选、异常发现、宏观透视
-- 分表策略: 按 create_time 进行 Range Partition（月度或季度）
-- -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_chat_trace_index (
    -- 1. 链路指纹
    trace_id            VARCHAR(64)     NOT NULL,
    session_id          VARCHAR(64)     NOT NULL,
    task_id             VARCHAR(64),
    user_id             VARCHAR(64)     NOT NULL,
    dept_id             VARCHAR(64),
    tenant_code         VARCHAR(32),
    -- 2. 智能体画像
    agent_name          VARCHAR(64),
    agent_version       VARCHAR(32),
    model_provider      VARCHAR(32),
    user_feedback       SMALLINT        DEFAULT 0,
    -- 3. 摘要与透视
    user_intent         VARCHAR(200),
    user_trace_query    VARCHAR(500),
    ai_trace_response   VARCHAR(500),
    execution_path      JSONB           DEFAULT '[]'::jsonb,
    tools_used          JSONB           DEFAULT '[]'::jsonb,
    -- 4. 状态与合规
    status              VARCHAR(20)     NOT NULL DEFAULT 'RUNNING',
    failure_reason      VARCHAR(255),
    -- 5. 效能账本
    trace_latency_ms    INTEGER,
    trace_total_tokens  INTEGER,
    trace_input_tokens  INTEGER,
    trace_output_tokens INTEGER,
    -- 6. 时序
    create_time         TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    update_time         TIMESTAMPTZ     DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_ai_chat_trace PRIMARY KEY (trace_id)
);
-- 核心索引
CREATE INDEX IF NOT EXISTS idx_chat_trace_time       ON ai_chat_trace_index (create_time DESC);
CREATE INDEX IF NOT EXISTS idx_chat_trace_user       ON ai_chat_trace_index (user_id, create_time DESC);
CREATE INDEX IF NOT EXISTS idx_chat_trace_tenant_dept ON ai_chat_trace_index (tenant_code, dept_id);
CREATE INDEX IF NOT EXISTS idx_chat_trace_status     ON ai_chat_trace_index (status);
CREATE INDEX IF NOT EXISTS idx_chat_trace_tools      ON ai_chat_trace_index USING GIN (tools_used);

COMMENT ON TABLE  ai_chat_trace_index                  IS 'AI 全链路审计宽表，PG 索引承担 90% 日常查询';
COMMENT ON COLUMN ai_chat_trace_index.trace_id         IS '全局唯一请求 ID，与 ES _id 一一对应';
COMMENT ON COLUMN ai_chat_trace_index.session_id       IS '所属会话 ID';
COMMENT ON COLUMN ai_chat_trace_index.task_id          IS '异步任务 ID（可空）';
COMMENT ON COLUMN ai_chat_trace_index.user_id          IS '用户 ID';
COMMENT ON COLUMN ai_chat_trace_index.dept_id          IS '部门 ID';
COMMENT ON COLUMN ai_chat_trace_index.tenant_code      IS '多租户隔离字段';
COMMENT ON COLUMN ai_chat_trace_index.agent_name       IS '入口 Agent 名称';
COMMENT ON COLUMN ai_chat_trace_index.agent_version    IS 'Agent 版本号';
COMMENT ON COLUMN ai_chat_trace_index.model_provider   IS '模型底座，如 gpt-4-turbo';
COMMENT ON COLUMN ai_chat_trace_index.user_feedback    IS '用户反馈：1=好评, 0=无, -1=差评';
COMMENT ON COLUMN ai_chat_trace_index.user_intent      IS '用户意图（意图识别节点提供）';
COMMENT ON COLUMN ai_chat_trace_index.user_trace_query IS '用户本次提问（前 500 字符截断）';
COMMENT ON COLUMN ai_chat_trace_index.ai_trace_response IS 'AI 本次回复（前 500 字符截断）';
COMMENT ON COLUMN ai_chat_trace_index.execution_path   IS '执行路径，经过的节点 agent_name 列表（JSONB）';
COMMENT ON COLUMN ai_chat_trace_index.tools_used       IS '本次使用的工具列表（JSONB），GIN 索引支持包含查询';
COMMENT ON COLUMN ai_chat_trace_index.status           IS '执行状态：SUCCESS / FAILED / RUNNING / INTERRUPTED';
COMMENT ON COLUMN ai_chat_trace_index.failure_reason   IS '简短失败原因（长堆栈存 ES）';
COMMENT ON COLUMN ai_chat_trace_index.trace_latency_ms IS 'Trace 总耗时（毫秒）';
COMMENT ON COLUMN ai_chat_trace_index.trace_total_tokens IS 'Trace 总 Token 消耗';
COMMENT ON COLUMN ai_chat_trace_index.trace_input_tokens IS 'Trace 提示词 Token 数';
COMMENT ON COLUMN ai_chat_trace_index.trace_output_tokens IS 'Trace 输出 Token 数';
