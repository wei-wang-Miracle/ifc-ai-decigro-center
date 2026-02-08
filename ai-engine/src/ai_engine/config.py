import os
from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# 定位项目根目录 (ai-engine/)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """
    功能: AI 引擎核心配置类
    参数: 从 .env 文件或环境变量自动加载
    返回: Settings 单例实例
    """
    
    # ========================================
    # 数据库配置
    # ========================================
    database_url: str = "postgresql://postgres:password@localhost:5432/decigro"
    
    # ========================================
    # LLM 配置
    # ========================================
    llm_provider: Literal["openai", "azure"] = "openai"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    
    # Azure OpenAI 专用配置
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment: str = ""
    
    # ========================================
    # Bus Kernel 配置
    # ========================================
    bus_kernel_base_url: str = "http://localhost:8080/api/dg"
    
    # ========================================
    # 服务配置
    # ========================================
    ai_engine_host: str = "0.0.0.0"
    ai_engine_port: int = 8001
    ai_engine_debug: bool = True
    
    # 配置来源：自动寻找项目根目录下的 .env
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
