# AI RAG 知识库微服务

基于 [RAGLite](https://github.com/superlinear-ai/raglite) 的智能知识库管理与检索服务。

## 核心功能

- **智能分块**: 不同于传统的固定长度切块，使用二进制整数规划进行最优语义切分。
- **上下文增强**: 自动为每个 Chunk 提取所在章节标题及上下文信息，解决“断章取义”问题。
- **混合检索**: 集成向量语义搜索 (pgvector) 与关键词搜索 (BM25)，并使用 RRF 算法进行结果融合。
- **管理后台**: 提供文档上传、状态追踪、Chunk 预览以及人工干预修正功能。

## 快速启动

### 准备工作

1. 确保已安装 **Python 3.12+**。
2. 确保 PostgreSQL 已启用 **pgvector** 扩展。
3. 拥有 Moonshot (Kimi) 或 OpenAI 的 API Key。

### 安装步骤

```bash
# 进入目录
cd ai-rag

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install --upgrade pip
pip install -e .
pip install raglite[pandoc] # 用于支持 Word/PDF 解析
```

### 配置环境变量

将 `.env.example` 复制为 `.env` 并根据实际情况修改数据库地址和 API Key。

### 运行服务

```bash
python -m ai_rag.main
```

服务默认运行在 `http://localhost:8002`。可以通过 `http://localhost:8002/docs` 查看 Swagger 文档。

---

## 开发规范

- **元数据对齐**: 文档的 `doc_id` 需与 `knowledge_documents` 表保持一致。
- **异常处理**: 任何文档解析失败需将错误堆栈写入 `knowledge_documents` 表的 `error_msg` 字段供前端展示。
