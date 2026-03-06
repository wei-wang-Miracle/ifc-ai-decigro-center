"""
AI 引擎主应用入口
FastAPI 应用配置和启动
"""

import sys
# 强制 stdout/stderr 无缓冲，确保 print 日志在重定向时实时写入文件
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import router as workflow_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    功能: 应用生命周期管理

    启动时:
    - 初始化 PostgreSQL 连接池
    - 初始化 AsyncPostgresSaver（短期记忆 checkpointer）
    - 初始化 AsyncPostgresStore（长期记忆 Store）+ 注入 LongTermMemoryManager
    - 编译持久化 workflow，挂载到 app.state

    关闭时:
    - 关闭连接池，清理资源
    """
    print("[AI Engine] 正在启动...")

    settings = get_settings()
    print(f"[AI Engine] LLM Model: {settings.llm_model}")

    # ── 初始化 PostgreSQL 连接池 ──────────────────────────────────
    from psycopg_pool import AsyncConnectionPool
    from .graph import create_workflow_graph_async

    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=2,
        max_size=10,
        open=False,
    )
    await pool.open()
    app.state.pg_pool = pool
    print("[AI Engine] PostgreSQL 连接池已初始化")

    # ── 编译持久化 workflow（同时初始化 checkpointer + Store）────
    app.state.workflow = await create_workflow_graph_async(pool)
    print("[AI Engine] 持久化 Workflow 已就绪（AsyncPostgresSaver + AsyncPostgresStore）")

    print("[AI Engine] 启动完成!")

    yield  # 应用运行中

    # ── 关闭时清理 ────────────────────────────────────────────────
    print("[AI Engine] 正在关闭...")

    await app.state.pg_pool.close()
    print("[AI Engine] PostgreSQL 连接池已关闭")

    from .api.bus_kernel_client import get_bus_kernel_client
    try:
        get_bus_kernel_client().close()
        print("[AI Engine] BusKernel 客户端已关闭")
    except Exception:
        pass

    print("[AI Engine] 已关闭")


def create_app() -> FastAPI:
    """
    功能: 创建 FastAPI 应用实例
    参数: 无
    返回: 配置完成的 FastAPI 实例
    """
    settings = get_settings()
    
    app = FastAPI(
        title="AI Engine",
        description="多智能体编排引擎 (Multi-Agent Orchestration Engine)",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )
    
    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制来源
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(workflow_router)

    # 全局异常捕捉
    import traceback
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        print(f"[GlobalError] {exc}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"内部服务器错误: {str(exc)}",
                "traceback": traceback.format_exc()
            }
        )
    
    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": "AI Engine",
            "version": "0.1.0",
            "description": "多智能体编排引擎",
            "docs": "/docs",
        }
    
    # 健康检查
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    
    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "ai_engine.main:app",
        host=settings.ai_engine_host,
        port=settings.ai_engine_port,
        reload=settings.ai_engine_debug,
    )
