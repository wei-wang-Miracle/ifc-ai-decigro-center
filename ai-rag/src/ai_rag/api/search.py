"""
知识库检索路由
暴露给 bus-kernel 调用的语义检索接口（支持混合检索 + 元数据过滤）
"""
from typing import Optional

from fastapi import APIRouter
from raglite import hybrid_search, retrieve_chunk_spans, rerank_chunks, retrieve_chunks

from ..rag_config import get_raglite_config
from ..models import ApiResponse, SearchRequest, SearchResult

router = APIRouter(prefix="/knowledge", tags=["知识库检索"])


@router.post("/search", response_model=ApiResponse[list[SearchResult]])
async def search_knowledge(req: SearchRequest):
    """
    高级知识库混合检索接口（供 bus-kernel ToolCard 和 ai-engine 调用）

    实现：
    1. 硬过滤（Pre-filter）：先用元数据（doc_type, related_codes）缩小候选集
    2. 混合召回（Hybrid Search）：向量语义搜索 + BM25 关键词搜索，RRF 融合排序
    3. 上下文扩展：将命中的 Chunk 扩展至其邻居，解决语义在块边界被截断的问题
    4. 重排序（可选）：FlashRank 精排，取 top_k 结果

    参数说明：
    - query: 语义查询主词（必填）
    - doc_type: 文档分类过滤（选填，如 '研报'）
    - must_match_code: 精确匹配基金代码（选填，如 '000001'）
    - top_k: 返回数量（默认 5）
    """
    config = get_raglite_config()

    # 第一步：构建元数据过滤条件（RAGLite metadata_filter 格式）
    metadata_filter = {}
    if req.doc_type:
        metadata_filter["doc_type"] = req.doc_type
    if req.must_match_code:
        # 因为 related_codes 存储为逗号分隔字符串，用 LIKE 匹配
        metadata_filter["related_codes__icontains"] = req.must_match_code

    # 第二步：执行混合检索（向量 + BM25 双路，RRF 融合打分）
    chunk_ids, _ = hybrid_search(
        query=req.query,
        num_results=req.top_k * 4,  # 多召回一些，供后续重排
        metadata_filter=metadata_filter if metadata_filter else None,
        config=config,
    )

    if not chunk_ids:
        return ApiResponse(data=[], message="未找到相关文档片段")

    # 第三步：获取 Chunk 实体
    chunks = retrieve_chunks(chunk_ids, config=config)

    # 第四步：重排序，选取最相关的 top_k 个
    reranked = rerank_chunks(req.query, chunks, config=config)
    top_chunks = reranked[: req.top_k]

    # 第五步：扩展 Chunk 上下文（取前后相邻的块，防止语义被截断）
    chunk_spans = retrieve_chunk_spans(top_chunks, config=config)

    # 第六步：构建返回结果
    results = []
    for span in chunk_spans:
        results.append(
            SearchResult(
                content=span.text,
                doc_id=str(span.document.id) if span.document else "",
                doc_name=span.document.filename if span.document else "",
                doc_type=span.document.metadata.get("doc_type", "") if span.document else "",
                score=1.0,  # RAGLite span 未直接暴露得分，默认为1
                chunk_count=len(span.chunks),
            )
        )

    return ApiResponse(data=results)
