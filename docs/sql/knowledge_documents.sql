-- ============================================================
-- RAG 知识库管理表 - ai-rag 微服务的元数据存储
-- 注意: RAGLite 的向量表（documents/chunks/chunk_embeddings）由 RAGLite 自动创建
--       此表为我们自建的元数据管理表，用于前端展示和状态跟踪
-- ============================================================
-- 确保 pgvector 扩展已安装（由 RAGLite 自动初始化，此处为保险起见）
CREATE EXTENSION IF NOT EXISTS vector;
-- 知识库文档管理主表
CREATE TABLE IF NOT EXISTS knowledge_documents (
    -- ============ 主键 ============
    doc_id VARCHAR(64) PRIMARY KEY,
    -- 文档唯一ID（与RAGLite documents.id对齐）
    -- ============ 文件信息 ============
    file_name VARCHAR(512) NOT NULL,
    -- 原始文件名
    file_path VARCHAR(1024),
    -- 本地/OSS文件路径
    -- ============ 业务元数据（与Chunk索引中的元数据字段保持一致！） ============
    doc_type VARCHAR(64) NOT NULL,
    -- 文档分类: 研报/制度规范/名词释义 等
    biz_tags JSONB DEFAULT '[]',
    -- 业务标签数组: ["A股","大盘"]
    publish_date DATE,
    -- 文档发布时间（用于时间过滤）
    -- ============ 处理状态 ============
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    -- 状态: PENDING/PARSING/EMBEDDING/SUCCESS/FAILED
    error_msg TEXT,
    -- 失败时的错误信息
    chunk_count INTEGER DEFAULT 0,
    -- 处理成功后的分块数量
    -- ============ 元数据 ============
    tenant_code VARCHAR(64),
    -- 租户隔离（可选）
    created_by VARCHAR(128),
    -- 上传人
    create_time TIMESTAMP NOT NULL DEFAULT NOW(),
    update_time TIMESTAMP NOT NULL DEFAULT NOW()
);
-- 索引：用于前端列表查询加速
CREATE INDEX IF NOT EXISTS idx_kd_doc_type ON knowledge_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_kd_status ON knowledge_documents(status);
CREATE INDEX IF NOT EXISTS idx_kd_create_time ON knowledge_documents(create_time DESC);
-- GIN 索引：加速 JSONB 字段的包含查询（如搜索包含某基金代码的文档）
CREATE INDEX IF NOT EXISTS idx_kd_biz_tags ON knowledge_documents USING GIN(biz_tags);
-- 注释
COMMENT ON TABLE knowledge_documents IS 'AI RAG 知识库文档管理表，跟踪文档处理状态和业务元数据';
COMMENT ON COLUMN knowledge_documents.doc_id IS '与 RAGLite documents 表的 id 字段保持一致';
COMMENT ON COLUMN knowledge_documents.status IS 'PENDING 等待|PARSING 解析中|EMBEDDING 向量化中|SUCCESS 完成|FAILED 失败';