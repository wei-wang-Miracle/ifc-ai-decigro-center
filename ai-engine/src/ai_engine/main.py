"""
AI 引擎主应用入口
FastAPI 应用配置和启动
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api import router as workflow_router
from .registry import get_tool_registry, get_agent_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    功能: 应用生命周期管理
    参数: app - FastAPI 应用实例
    返回: 异步上下文管理器
    
    启动时:
    - 初始化配置
    - 加载工具注册中心
    - 加载 Agent 注册中心
    
    关闭时:
    - 清理资源
    """
    # 启动时初始化
    print("[AI Engine] 正在启动...")
    
    settings = get_settings()
    print(f"[AI Engine] LLM Model: {settings.llm_model}")
    
    # 预加载逻辑已移除，因为现在采用基于 Token 的动态注册
    print("[AI Engine] 启动完成! (等待首个用户请求触发动态注册)")
    
    print("[AI Engine] 启动完成!")
    
    yield  # 应用运行中
    
    # 关闭时清理
    print("[AI Engine] 正在关闭...")
    
    # 关闭 BusKernel 客户端
    from .api.bus_kernel_client import get_bus_kernel_client
    try:
        client = get_bus_kernel_client()
        client.close()
        print("[AI Engine] BusKernel 客户端已关闭")
    except:
        pass

    # 关闭数据库连接池
    from .db import get_db_manager
    try:
        db = get_db_manager()
        db.close()
        print("[AI Engine] 数据库连接已关闭")
    except:
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
