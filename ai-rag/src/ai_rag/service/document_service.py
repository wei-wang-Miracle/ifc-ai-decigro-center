"""
文档管理 Service 层
封装数据库的 CRUD 操作，底层使用 asyncpg 或 psycopg3 直连 PostgreSQL
（RAGLite 已管理好向量表，这里管理自建的 knowledge_documents 元数据表）
"""
import json
from datetime import datetime
from typing import Optional

import asyncpg  # 使用异步驱动，保证 FastAPI 性能

from ..models import DocumentVO, DocumentStatus, ChunkVO
from ..config import get_settings


async def _get_conn() -> asyncpg.Connection:
    """获取数据库连接（生产环境应使用连接池 asyncpg.Pool）"""
    settings = get_settings()
    # 将 psycopg 风格的连接字符串转为 asyncpg 格式
    url = settings.database_url.replace("postgresql://", "")
    return await asyncpg.connect(f"postgresql://{url}")


async def create_document_record(
    doc_id: str,
    file_name: str,
    file_path: str,
    doc_type: str,
    biz_tags: list[str],
    publish_date: Optional[str],
) -> DocumentVO:
    """在元数据表中创建文档记录，状态初始化为 PENDING"""
    conn = await _get_conn()
    
    # 转换日期格式：asyncpg 插入 DATE 类型列时需要 datetime.date 对象，不能直接传字符串
    pub_date_obj = None
    if publish_date:
        try:
            pub_date_obj = datetime.strptime(publish_date, "%Y-%m-%d").date()
        except ValueError:
            # 如果日期格式非法，设为 None
            pass

    try:
        await conn.execute(
            """
            INSERT INTO knowledge_documents
                (doc_id, file_name, file_path, doc_type, biz_tags, publish_date, status, create_time, update_time)
            VALUES ($1, $2, $3, $4, $5, $6, 'PENDING', NOW(), NOW())
            """,
            doc_id,
            file_name,
            file_path,
            doc_type,
            json.dumps(biz_tags),
            pub_date_obj,
        )
    finally:
        await conn.close()

    return DocumentVO(
        doc_id=doc_id,
        file_name=file_name,
        file_path=file_path,
        doc_type=doc_type,
        biz_tags=biz_tags,
        publish_date=publish_date,
        status=DocumentStatus.PENDING,
    )


async def list_documents(
    doc_type: Optional[str],
    keyword: Optional[str],
    page: int,
    size: int,
) -> list[DocumentVO]:
    """分页查询文档列表"""
    conn = await _get_conn()
    try:
        conditions = ["1=1"]
        params = []
        idx = 1

        if doc_type:
            conditions.append(f"doc_type = ${idx}")
            params.append(doc_type)
            idx += 1

        if keyword:
            conditions.append(f"file_name ILIKE ${idx}")
            params.append(f"%{keyword}%")
            idx += 1

        where = " AND ".join(conditions)
        offset = (page - 1) * size

        rows = await conn.fetch(
            f"""
            SELECT doc_id, file_name, file_path, doc_type, biz_tags,
                   publish_date, status, error_msg, chunk_count,
                   to_char(create_time, 'YYYY-MM-DD HH24:MI:SS') AS create_time,
                   to_char(update_time, 'YYYY-MM-DD HH24:MI:SS') AS update_time
            FROM knowledge_documents
            WHERE {where}
            ORDER BY create_time DESC
            LIMIT {size} OFFSET {offset}
            """,
            *params,
        )
    finally:
        await conn.close()

    return [_row_to_document_vo(r) for r in rows]


async def get_document_by_id(doc_id: str) -> Optional[DocumentVO]:
    """根据 ID 获取单个文档"""
    conn = await _get_conn()
    try:
        row = await conn.fetchrow(
            """
            SELECT doc_id, file_name, file_path, doc_type, biz_tags,
                   publish_date, status, error_msg, chunk_count,
                   to_char(create_time, 'YYYY-MM-DD HH24:MI:SS') AS create_time,
                   to_char(update_time, 'YYYY-MM-DD HH24:MI:SS') AS update_time
            FROM knowledge_documents
            WHERE doc_id = $1
            """,
            doc_id,
        )
    finally:
        await conn.close()

    return _row_to_document_vo(row) if row else None


async def delete_document_record(doc_id: str):
    """删除文档记录"""
    conn = await _get_conn()
    try:
        await conn.execute("DELETE FROM knowledge_documents WHERE doc_id = $1", doc_id)
    finally:
        await conn.close()


async def update_document_status(
    doc_id: str,
    status: DocumentStatus,
    error_msg: Optional[str] = None,
):
    """更新文档处理状态"""
    conn = await _get_conn()
    try:
        await conn.execute(
            """
            UPDATE knowledge_documents
            SET status = $1, error_msg = $2, update_time = NOW()
            WHERE doc_id = $3
            """,
            status.value,
            error_msg,
            doc_id,
        )
    finally:
        await conn.close()


async def delete_chunks_by_doc_id(doc_id: str):
    """
    从 RAGLite 的 chunk 表中删除指定文档的所有 Chunk。
    RAGLite 实际表名均为单数：document / chunk / chunk_embedding
    上传时已通过 id=doc_id 保证主键对齐，此处直接使用 doc_id 操作。
    """
    conn = await _get_conn()
    try:
        # 第一步：删除向量数据（外键依赖 chunk 表，需先删除）
        await conn.execute(
            "DELETE FROM chunk_embedding WHERE chunk_id IN (SELECT id FROM chunk WHERE document_id = $1)",
            doc_id,
        )
        # 第二步：删除切块记录
        await conn.execute("DELETE FROM chunk WHERE document_id = $1", doc_id)
        # 第三步：删除 RAGLite 内部的 document 记录
        await conn.execute("DELETE FROM document WHERE id = $1", doc_id)
        # 第四步：同步更新元数据表 chunk_count
        await conn.execute(
            "UPDATE knowledge_documents SET chunk_count = 0, update_time = NOW() WHERE doc_id = $1",
            doc_id,
        )
    finally:
        await conn.close()


async def get_chunks_by_doc_id(doc_id: str) -> list[ChunkVO]:
    """获取文档的切块列表（用于管理员预览验证切块质量）。"""
    conn = await _get_conn()
    try:
        # RAGLite 的切块表名为 'chunk'（单数），文本字段为 'body'（非 'text'）
        rows = await conn.fetch(
            """
            SELECT id, document_id, index, body, headings
            FROM chunk
            WHERE document_id = $1
            ORDER BY index ASC
            """,
            doc_id,
        )
    finally:
        await conn.close()

    return [
        ChunkVO(
            chunk_id=str(r["id"]),
            doc_id=doc_id,
            chunk_index=r["index"],
            content=r["body"],  # RAGLite 存储切块文本的字段名为 'body'
            title_path=r["headings"].split("\n") if r["headings"] else [],
        )
        for r in rows
    ]


async def update_chunk_and_reembed(
    doc_id: str, chunk_id: str, new_content: str
) -> Optional[ChunkVO]:
    """
    修正 Chunk 文本内容，并重新计算向量（用于修正 OCR 错误）
    """
    from raglite import RAGLiteConfig
    from ..rag_config import get_raglite_config
    import numpy as np

    conn = await _get_conn()
    try:
        # 第一步：更新切块文本（RAGLite 表名为 'chunk'，文本字段为 'body'）
        row = await conn.fetchrow(
            "UPDATE chunk SET body = $1 WHERE id = $2 AND document_id = $3 RETURNING *",
            new_content,
            chunk_id,
            doc_id,
        )
        if not row:
            return None

        # 第二步：重新向量化（调用 RAGLite 的 embedder）
        config = get_raglite_config()
        # 直接用 litellm 调用 embedding API
        from litellm import embedding as litellm_embedding
        import os
        from ..config import get_settings
        
        settings = get_settings()
        # 设置 Embedding API 认证信息（LiteLLM openai provider 读取以下环境变量）
        os.environ["OPENAI_API_KEY"] = settings.embedding_api_key
        os.environ["OPENAI_BASE_URL"] = settings.embedding_api_base
        
        response = litellm_embedding(model=config.embedder, input=[new_content])
        new_vector = response.data[0]["embedding"]

        # 第三步：更新向量数据（RAGLite 向量表名为 'chunk_embedding'，无复数 's'）
        await conn.execute(
            "UPDATE chunk_embedding SET embedding = $1 WHERE chunk_id = $2",
            str(new_vector),
            chunk_id,
        )

    finally:
        await conn.close()

    return ChunkVO(
        chunk_id=chunk_id,
        doc_id=doc_id,
        chunk_index=row["index"],
        content=new_content,
        title_path=row["headings"].split("\n") if row["headings"] else [],
    )


def _row_to_document_vo(row) -> DocumentVO:
    """将数据库行转换为 DocumentVO"""
    # 确保日期字段转换为字符串，避免 Pydantic 校验错误
    pub_date = row["publish_date"]
    if hasattr(pub_date, "isoformat"):
        pub_date = pub_date.isoformat()
    elif pub_date is not None:
        pub_date = str(pub_date)

    return DocumentVO(
        doc_id=row["doc_id"],
        file_name=row["file_name"],
        file_path=row["file_path"],
        doc_type=row["doc_type"],
        biz_tags=json.loads(row["biz_tags"]) if row["biz_tags"] else [],
        publish_date=pub_date,
        status=DocumentStatus(row["status"]),
        error_msg=row.get("error_msg"),
        chunk_count=row.get("chunk_count", 0),
        create_time=row.get("create_time"),
        update_time=row.get("update_time"),
    )
