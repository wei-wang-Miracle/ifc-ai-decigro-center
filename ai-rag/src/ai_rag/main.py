"""
ai-rag 微服务主入口
FastAPI 应用初始化，挂载所有路由，暴露知识库管理和检索 API
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api.documents import router as document_router
from .api.search import router as search_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - 启动时：确保上传目录存在，预热 RAGLite 配置（建立 pgvector 索引如果不存在）
    - 关闭时：执行清理操作
    """
    settings = get_settings()

    # 确保文件上传目录存在
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"[ai-rag] 文件上传目录: {upload_dir}")

    # 预热 RAGLite 配置（触发 pgvector 表的自动创建）
    try:
        from .rag_config import get_raglite_config
        config = get_raglite_config()
        logger.info(f"[ai-rag] RAGLite 初始化成功，数据库: {config.db_url[:40]}...")
    except Exception as e:
        logger.warning(f"[ai-rag] RAGLite 预热失败（非致命），稍后请求时再尝试: {e}")

    yield

    logger.info("[ai-rag] 服务关闭中...")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    settings = get_settings()

    app = FastAPI(
        title="AI RAG 知识库微服务",
        description="基于 RAGLite 的智能知识库管理与检索服务，支持文档上传、语义切块、向量化和混合检索",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 跨域配置（与 bus-kernel 和前端同域通信）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制为具体的前端域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(document_router, prefix="/api/rag")
    app.include_router(search_router, prefix="/api/rag")

    @app.get("/health")
    async def health_check():
        """健康检查端点，供 Docker / K8s 探活使用"""
        return {"status": "ok", "service": "ai-rag"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "ai_rag.main:app",
        host=settings.ai_rag_host,
        port=settings.ai_rag_port,
        reload=True,
        log_level="info",
    )
