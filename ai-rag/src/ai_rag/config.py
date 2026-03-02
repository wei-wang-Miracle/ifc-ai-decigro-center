"""
ai-rag 配置管理
基于 Pydantic Settings，从 .env 文件或环境变量自动加载
"""
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# 定位项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """
    功能: AI RAG 服务核心配置类
    参数: 从 .env 文件或环境变量自动加载
    返回: Settings 单例实例
    """

    # ========================================
    # 数据库配置
    # ========================================
    database_url: str = "postgresql://postgres:123456@localhost:5432/decigro"

    # ========================================
    # LLM 与 Embedding 配置（供 RAGLite 使用）
    # ========================================
    # LLM 配置（Moonshot/Kimi）
    # 格式：moonshot/<model_name>，LiteLLM 会自动读取 MOONSHOT_API_KEY，无需手动指定 base_url
    moonshot_api_key: str = "sk-pymikPWePlXQaHmMQXJwWCk6s2N5HxpVniegkrm9n46DnDF5"
    llm_model: str = "moonshot/moonshot-v1-8k"

    # Embedding 模型配置 (SiliconFlow)
    # 注意：LiteLLM 调用 OpenAI 兼容接口时必须添加 openai/ 前缀，否则无法正确路由
    # LiteLLM 对应环境变量：OPENAI_API_KEY 和 OPENAI_BASE_URL
    # 使用 BAAI/bge-m3（1024维）而非 Qwen3-Embedding-8B（4096维）
    # 原因：pgvector 的 HNSW 索引对 halfvec 类型最多支持4000维，4096维超出限制
    embedding_api_key: str = "sk-xedqcwptfervigxqrqenjubzihjnygquzouwtknnxvmnghgl"
    embedding_api_base: str = "https://api.siliconflow.cn/v1"
    embedder_model: str = "openai/BAAI/bge-m3"

    # ========================================
    # 服务配置
    # ========================================
    ai_rag_host: str = "0.0.0.0"
    ai_rag_port: int = 8002

    # ========================================
    # 文件存储
    # ========================================
    upload_dir: str = "/tmp/ai_rag_uploads"

    # ========================================
    # Bus Kernel
    # ========================================
    bus_kernel_base_url: str = "http://localhost:8080/api/dg"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    功能: 获取配置单例（使用缓存避免重复加载）
    参数: 无
    返回: Settings 实例
    """
    return Settings()
