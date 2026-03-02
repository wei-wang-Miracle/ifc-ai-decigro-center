"""
ai-rag 服务数据模型定义
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Optional, TypeVar
from pydantic import BaseModel, Field, field_validator
import re

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
    """
    知识库检索请求（已加入严格的 Pydantic 校验，校验失败时返回 422 + 明确错误原因）

    字段说明：
    - query: 语义查询词，必须是自然语言描述，2~500 字符（必填）
    - doc_type: 文档分类过滤，最长 50 字符（选填）
    - top_k: 返回最相关片段数量，范围 1~10，默认 5
    """

    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="[必填] 语义查询词，必须是自然语言描述，长度 2~500 字符。"
                    "不得传入 SQL、JSON 代码或纯关键词列表。"
    )

    doc_type: Optional[str] = Field(
        default=None,
        max_length=50,
        description="[选填] 文档分类过滤，仅接受已录入知识库的分类值（如'研报'、'规则文档'）。"
                    "传入未知分类值时检索结果将为空，省略则不限制分类。"
    )


    exact_keyword: Optional[str] = Field(
        default=None,
        description="[选填] 关键词精确匹配，要求在文档内容中必须包含此词。"
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="[选填] 返回最相关的文档片段数量，默认 5，范围 1~10。"
                    "超过 10 会显著增加响应延迟，强制拒绝。"
    )

    @field_validator("query")
    @classmethod
    def validate_query_not_code(cls, v: str) -> str:
        """
        功能: 校验 query 不是 SQL 或代码片段，而是自然语言描述。
        参数: v - 待校验的查询字符串
        返回: 校验通过后的字符串
        """
        # 检测明显的 SQL 关键词（大小写不敏感）
        sql_keywords = ["SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP ", "CREATE ", "ALTER "]
        normalized = v.upper()
        for kw in sql_keywords:
            if kw in normalized:
                raise ValueError(
                    f"[AI调用错误] query 字段不得包含 SQL 关键词（如 {kw.strip()}）。"
                    "请将 query 改为自然语言语义描述，例如：'沪深300指数增强策略的风险控制方法'。"
                )
        return v




class SearchResult(BaseModel):
    """单条检索结果"""
    content: str          # 检索到的文本内容（已扩展上下文）
    doc_id: str           # 来源文档 ID
    doc_name: str         # 来源文档文件名
    doc_type: str         # 文档分类
    score: float          # 相关性得分
    chunk_count: int      # 此结果包含的 Chunk 数量（上下文扩展后）

