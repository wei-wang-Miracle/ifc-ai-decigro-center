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