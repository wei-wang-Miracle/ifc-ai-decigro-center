"""
知识库文档管理路由
负责文档的上传、列表查询、删除、Chunk 预览等 CRUD 操作
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from raglite import Document, insert_documents

from ..rag_config import get_raglite_config
from ..config import get_settings
from ..models import (
    ApiResponse,
    DocumentVO,
    ChunkVO,
    DocumentStatus,
)
from ..service.document_service import (
    create_document_record,
    list_documents,
    get_document_by_id,
    delete_document_record,
    get_chunks_by_doc_id,
    update_document_status,
    delete_chunks_by_doc_id,
)

router = APIRouter(prefix="/knowledge", tags=["知识库管理"])


async def _process_document_async(
    doc_id: str,
    file_path: str,
    doc_type: str,
    biz_tags: list[str],
):
    """
    后台异步任务：执行文档的解析、切块、向量化并写入数据库
    
    流程：PARSING -> EMBEDDING -> SUCCESS / FAILED
    """
    try:
        # 第一步：更新状态为解析中
        await update_document_status(doc_id, DocumentStatus.PARSING)

        config = get_raglite_config()

        # 第二步：构建 RAGLite Document 对象，附带元数据
        # 这些元数据将被存入 Chunk 的 metadata 字段，供后续搜索过滤
        document = Document.from_path(
            Path(file_path),
            # 【关键】把我们的 doc_id 作为 RAGLite Document 的主键 id 传入。
            # 若不传 id，RAGLite 会自动用文件内容哈希作为主键，
            # 导致删除时 WHERE document_id = our_doc_id 无法命中任何数据！
            id=doc_id,
            # RAGLite 支持任意 keyword 元数据，会被存入搜索索引
            doc_type=doc_type,
            biz_tags=",".join(biz_tags),
        )

        # 第三步：更新状态为向量化中
        await update_document_status(doc_id, DocumentStatus.EMBEDDING)

        # 第四步：RAGLite 全自动完成：
        #   - 格式转换（PDF/Word -> Markdown）
        #   - 最优语义切块（通过二进制整数规划，非粗暴按字数截断）
        #   - 带上下文标题的多向量嵌入（Late Chunking）
        #   - 写入 PostgreSQL pgvector 索引
        insert_documents([document], config=config)

        # 第五步：成功，更新状态
        await update_document_status(doc_id, DocumentStatus.SUCCESS)

    except Exception as e:
        # 任何异常都标记为 FAILED，并记录错误信息
        await update_document_status(doc_id, DocumentStatus.FAILED, error_msg=str(e))
        raise


@router.post("/upload", response_model=ApiResponse[DocumentVO])
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="上传的文档文件（PDF / Word / Markdown 等）"),
    doc_type: str = Form(..., description="文档分类，如：研报、名词释义、制度规范"),
    biz_tags: str = Form("", description="业务标签，多个以英文逗号分隔"),
    publish_date: Optional[str] = Form(None, description="文档发布日期，格式：YYYY-MM-DD"),
):
    """
    上传文档到知识库。

    文档将被异步处理（解析 -> 切块 -> 向量化），状态从 PENDING 更新至 SUCCESS 或 FAILED。
    可通过 GET /knowledge/list 查询处理进度。
    """
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名，避免冲突
    doc_id = str(uuid.uuid4()).replace("-", "")
    suffix = Path(file.filename).suffix
    saved_path = upload_dir / f"{doc_id}{suffix}"

    # 保存原始文件到本地临时目录
    try:
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {e}")

    # 解析标签
    tags_list = [t.strip() for t in biz_tags.split(",") if t.strip()]

    # 在数据库中创建记录（状态: PENDING）
    doc_vo = await create_document_record(
        doc_id=doc_id,
        file_name=file.filename,
        file_path=str(saved_path),
        doc_type=doc_type,
        biz_tags=tags_list,
        publish_date=publish_date,
    )

    # 将繁重的解析任务放入后台，立即返回给前端
    background_tasks.add_task(
        _process_document_async,
        doc_id=doc_id,
        file_path=str(saved_path),
        doc_type=doc_type,
        biz_tags=tags_list,
    )

    return ApiResponse(data=doc_vo, message="文件已上传，正在后台处理中...")


@router.get("/list", response_model=ApiResponse[list[DocumentVO]])
async def list_knowledge_documents(
    doc_type: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    size: int = 20,
):
    """
    分页查询知识库文档列表，支持按文档类型、关键字筛选。
    返回数据包含文档的向量化状态（PENDING / PARSING / EMBEDDING / SUCCESS / FAILED）。
    """
    result = await list_documents(doc_type=doc_type, keyword=keyword, page=page, size=size)
    return ApiResponse(data=result)


@router.get("/{doc_id}", response_model=ApiResponse[DocumentVO])
async def get_document_detail(doc_id: str):
    """获取单个文档的详情，包含元数据和当前处理状态。"""
    doc = await get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return ApiResponse(data=doc)


@router.delete("/{doc_id}", response_model=ApiResponse[None])
async def delete_document(doc_id: str):
    """
    删除文档记录及其所有 Chunk。
    
    警告：此操作会从 PostgreSQL / pgvector 向量索引中物理删除该文档的所有切块数据，不可恢复！
    """
    doc = await get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 第一步：删除向量索引中此文档的所有 Chunks（防止幽灵数据）
    await delete_chunks_by_doc_id(doc_id)

    # 第二步：删除本地文件（如果存在）
    if doc.file_path and Path(doc.file_path).exists():
        os.remove(doc.file_path)

    # 第三步：删除数据库记录
    await delete_document_record(doc_id)

    return ApiResponse(message="文档已删除")


@router.get("/{doc_id}/chunks", response_model=ApiResponse[list[ChunkVO]])
async def preview_document_chunks(doc_id: str):
    """
    预览文档被切分后的 Chunk 详情列表。
    
    用途：管理员可以通过此接口验证文档的切块质量，判断语义边界是否合理，
    并在发现 OCR 错误时使用 PUT /{doc_id}/chunks/{chunk_id} 进行人工修正。
    """
    doc = await get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    chunks = await get_chunks_by_doc_id(doc_id)
    return ApiResponse(data=chunks)


@router.put("/{doc_id}/chunks/{chunk_id}", response_model=ApiResponse[ChunkVO])
async def update_chunk_content(
    doc_id: str,
    chunk_id: str,
    content: str = Form(..., description="修正后的 Chunk 文本内容"),
):
    """
    人工修正某个 Chunk 的文本内容并重新向量化。
    
    适用场景：PDF OCR 识别错误导致向量质量差，导致 RAG 持续找不到相关片段时，
    管理员可以手动修正文本，触发重新 Embedding。
    """
    from ..service.document_service import update_chunk_and_reembed
    updated = await update_chunk_and_reembed(doc_id, chunk_id, content)
    if not updated:
        raise HTTPException(status_code=404, detail="Chunk 不存在")
    return ApiResponse(data=updated, message="Chunk 已修正并重新向量化")


@router.post("/{doc_id}/reprocess", response_model=ApiResponse[None])
async def reprocess_document(doc_id: str, background_tasks: BackgroundTasks):
    """
    重新处理文档（重新切块、重新向量化）。
    
    适用场景：文档处理失败后的手动重试，或 Embedding 模型切换后的批量重建。
    """
    doc = await get_document_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 清除旧的 Chunk 数据
    await delete_chunks_by_doc_id(doc_id)
    await update_document_status(doc_id, DocumentStatus.PENDING)

    background_tasks.add_task(
        _process_document_async,
        doc_id=doc_id,
        file_path=doc.file_path,
        doc_type=doc.doc_type,
        biz_tags=doc.biz_tags or [],
    )

    return ApiResponse(message="已重新开始处理文档...")
