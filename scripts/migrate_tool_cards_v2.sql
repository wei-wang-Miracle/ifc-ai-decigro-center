-- ============================================================
-- Migration: tool_cards 新增 tool_method / tool_headers 字段
-- 版本: v2 (2026-03)
-- 说明: 支持工具卡片配置 HTTP 请求方法和自定义请求头
--       适用于已存在 tool_cards 表的环境（增量执行）
-- ============================================================

-- 1. 扩大 url_path 长度（原 VARCHAR(128) 不足以存完整 URL）
ALTER TABLE tool_cards
    ALTER COLUMN url_path TYPE VARCHAR(512);

-- 2. 新增 tool_method 字段（HTTP 请求方法）
ALTER TABLE tool_cards
    ADD COLUMN IF NOT EXISTS tool_method VARCHAR(16) DEFAULT 'POST';

-- 3. 新增 tool_headers 字段（自定义请求头，JSONB）
ALTER TABLE tool_cards
    ADD COLUMN IF NOT EXISTS tool_headers JSONB DEFAULT NULL;

-- 4. 补充字段注释
COMMENT ON COLUMN tool_cards.url_path IS 'HTTP URL，支持相对路径（/api/v1/xxx）或完整 URL（https://...）';
COMMENT ON COLUMN tool_cards.tool_method IS 'HTTP 请求方法：GET/POST/PUT/DELETE，默认 POST，仅 protocol=http 时有效';
COMMENT ON COLUMN tool_cards.tool_headers IS '自定义请求头，JSONB 格式 {"Key":"Value"}，X-Auth-Token 由系统自动注入无需配置';

-- 5. 为已有记录回填默认值（protocol=http 的记录默认 POST）
UPDATE tool_cards
SET tool_method = 'POST'
WHERE tool_method IS NULL
  AND tool_protocol = 'http';
