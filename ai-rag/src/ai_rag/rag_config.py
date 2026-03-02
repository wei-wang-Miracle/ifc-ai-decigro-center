"""
RAGLite 核心配置与初始化
统一封装 RAGLiteConfig 的创建，确保全局使用一致的数据库和模型
"""
import os
from functools import lru_cache

import litellm
from raglite import RAGLiteConfig
from .config import get_settings


@lru_cache
def get_raglite_config() -> RAGLiteConfig:
    """
    功能: 获取全局 RAGLiteConfig 单例
    参数: 无
    返回: RAGLiteConfig 实例
    
    注意事项:
    - database_url 必须指向已安装 pgvector 扩展的 PostgreSQL 数据库
    - embedder 的维度一旦确定，切换时需要清空向量索引
    - self_query=True 允许 LLM 自动从用户查询中提取元数据过滤条件
    """
    settings = get_settings()
    
    # ----------------------------------------------------------------
    # LLM 认证：Moonshot/Kimi
    # LiteLLM 的 moonshot provider 原生读取 MOONSHOT_API_KEY
    # 无需手动设置 base_url，LiteLLM 内置了 https://api.moonshot.cn/v1
    # ----------------------------------------------------------------
    os.environ["MOONSHOT_API_KEY"] = settings.moonshot_api_key

    # ----------------------------------------------------------------
    # Embedding 认证：SiliconFlow（OpenAI 兼容接口）
    # RAGLite 调用 litellm.embedding("openai/<model>", ...)
    # LiteLLM 的 openai provider 路由逻辑（litellm/main.py L4810-L4828）读取：
    #   api_key  <- OPENAI_API_KEY
    #   api_base <- OPENAI_BASE_URL 或 OPENAI_API_BASE（优先前者）
    # 两者用独立字段设置，与 MOONSHOT_API_KEY 完全隔离，互不覆盖
    # ----------------------------------------------------------------
    os.environ["OPENAI_API_KEY"] = settings.embedding_api_key
    os.environ["OPENAI_BASE_URL"] = settings.embedding_api_base

    # ----------------------------------------------------------------
    # 预注册 Embedding 模型元信息到 LiteLLM
    # 原因：RAGLite 的 get_embedding_dim() 调用 litellm.get_model_info() 获取向量维度
    #       对未知模型（不在 LiteLLM 内置列表）会直接抛 Exception，而非走 fallback
    # BAAI/bge-m3 维度为 1024，远小于 pgvector HNSW halfvec 限制Ｈ4000维）
    # ----------------------------------------------------------------
    _embedding_model_info = {
        "max_tokens": 8192,          # bge-m3 最大输入 token 数
        "max_input_tokens": 8192,
        "max_output_tokens": None,
        "input_cost_per_token": 0.0,
        "output_cost_per_token": 0.0,
        "output_vector_size": 1024,  # bge-m3 输出维度（远小于 pgvector HNSW 4000维限制）
        "litellm_provider": "openai",
        "mode": "embedding",
    }
    litellm.register_model(
        {
            # 同时注册两个 key，确保 LiteLLM 按 combined_model_name 或 split_model 查找都能命中
            "openai/BAAI/bge-m3": _embedding_model_info,
            "BAAI/bge-m3": _embedding_model_info,
        }
    )
    
    return RAGLiteConfig(
        # 数据库：使用项目已有的 PostgreSQL（需要 pgvector 扩展）
        db_url=settings.database_url,
        
        # 生成模型：格式 moonshot/<model_name>，供 RAG 自主决策是否检索
        llm=settings.llm_model,
        
        # 向量化模型：格式 openai/<model_name>，路由至 SiliconFlow API
        # 注意：一旦文档入库后不应随意更换 embedder，否则需要重新向量化
        embedder=settings.embedder_model,
    )
