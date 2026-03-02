"""
ai-rag 服务数据模型定义
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class DocumentStatus(str, Enum):
    """文档处理状态枚举"""
    PENDING = "PENDING"       # 等待处理
    PARSING = "PARSING"       # 文档解析中（PDF/Word -> Markdown）
    EMBEDDING = "EMBEDDING"   # 向量化切块中
    SUCCESS = "SUCCESS"       # 处理成功
    FAILED = "FAILED"         # 处理失败


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应包装，与 bus-kernel 的 Result<T> 格式对齐"""
    code: int = 200
    message: str = "操作成功"
    data: Optional[T] = None


class DocumentVO(BaseModel):
    """文档信息视图对象"""
    doc_id: str
    file_name: str
    file_path: Optional[str] = None
    doc_type: str
    related_codes: list[str] = []
    biz_tags: list[str] = []
    publish_date: Optional[str] = None
    status: DocumentStatus = DocumentStatus.PENDING
    error_msg: Optional[str] = None
    chunk_count: int = 0
    create_time: Optional[str] = None
    update_time: Optional[str] = None


class ChunkVO(BaseModel):
    """文档切块视图对象，用于管理员预览切块质量"""
    chunk_id: str
    doc_id: str
    chunk_index: int
    content: str
    title_path: list[str] = []   # 所属章节路径，如 ["第一章", "风险提示"]
    has_embedding: bool = True


class SearchRequest(BaseModel):
    """知识库检索请求"""
    query: str                         # 语义查询词（必填）
    doc_type: Optional[str] = None     # 文档分类过滤（选填）
    must_match_code: Optional[str] = None  # 精确匹配业务代码（选填，如基金代码）
    exact_keyword: Optional[str] = None    # 关键词精确匹配（选填）
    top_k: int = 5                     # 返回最相关的片段数量


class SearchResult(BaseModel):
    """单条检索结果"""
    content: str          # 检索到的文本内容（已扩展上下文）
    doc_id: str           # 来源文档 ID
    doc_name: str         # 来源文档文件名
    doc_type: str         # 文档分类
    score: float          # 相关性得分
    chunk_count: int      # 此结果包含的 Chunk 数量（上下文扩展后）
