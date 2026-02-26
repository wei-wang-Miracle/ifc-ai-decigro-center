-- ========================================
-- MAS 智能体注册表 (Agent Registry) - V2
-- 功能: 存储 Agent "数字员工" 的元数据定义 (Updated Schema)
-- ========================================
DROP TABLE IF EXISTS agent_cards;
CREATE TABLE agent_cards (
    -- 1. 身份 (Identity)
    agent_name VARCHAR(100) PRIMARY KEY,
    -- 建议仍用 varchar 作为主键，索引效率最高
    -- 2. 注册中心信息 (Registry Info - JSONB for Tags)
    agent_description TEXT NOT NULL,
    agent_alias TEXT NOT NULL,
    -- 使用 JSONB 存储标签
    -- 结构示例: '["finance", "external_api"]'
    agent_tags JSONB DEFAULT '[]'::jsonb,
    -- 智能体类型 (PLANNER, EXECUTOR)
    agent_type VARCHAR(32) DEFAULT 'EXECUTOR',
    -- 3. 内核配置 (Core Config - JSONB for Tools)
    system_prompt TEXT NOT NULL,
    negative_prompt TEXT,
    -- 使用 JSONB 存储工具绑定
    -- 逻辑定义:
    --   NULL (SQL NULL): 表示 "默认全量" (Use all available tools)
    --   '[]' (JSON Empty List): 表示 "纯对话模式" (No tools)
    --   '["search", "calculator"]': 表示 "白名单模式" (Allowlist)
    bound_tools JSONB,
    -- PLANNER 绑定的 EXECUTOR 列表
    bound_agents JSONB DEFAULT '[]'::jsonb,
    reasoning_framework VARCHAR(50),
    -- e.g. 'ReAct', 'PlanSolve'
    -- 4. 元数据 (Meta Data)
    agent_version VARCHAR(50) DEFAULT '1.0.0',
    is_online BOOLEAN DEFAULT true,
    require_review BOOLEAN DEFAULT false,
    manager_by VARCHAR(100),
    -- 审计时间
    create_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE agent_cards IS 'MAS 智能体注册表，存储 Agent 定义';
COMMENT ON COLUMN agent_cards.agent_name IS 'Agent 唯一标识 (主键)';
COMMENT ON COLUMN agent_cards.agent_alias IS 'Agent 别名/名称';
COMMENT ON COLUMN agent_cards.agent_description IS 'Agent 描述';
COMMENT ON COLUMN agent_cards.agent_tags IS '标签列表 (JSONB)';
COMMENT ON COLUMN agent_cards.agent_type IS '智能体类型 (PLANNER, EXECUTOR)';
COMMENT ON COLUMN agent_cards.bound_tools IS '绑定工具 (JSONB): NULL表示全量, []表示无工具, 列表表示白名单';
COMMENT ON COLUMN agent_cards.bound_agents IS '绑定的执行智能体 (JSONB)';
COMMENT ON COLUMN agent_cards.reasoning_framework IS '推理框架 (ReAct, PlanSolve等)';