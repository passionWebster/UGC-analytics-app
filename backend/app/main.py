# 应用启动入口文件
"""
FastAPI 应用主入口
整合所有路由和中间件，启动应用服务
"""
import time
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_database
from .config import settings
from .logger import app_logger
from .nlp_worker_pool import start_nlp_worker_pool, stop_nlp_worker_pool
from .routers import auth, analytics, ai, crawler, admin, user_space
from .scheduler import create_scheduler


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Bilibili 番剧数据分析平台 - 统一的 FastAPI 后端服务",
    docs_url="/api/docs",  # Swagger UI 文档地址
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────────────────────
# HTTP 请求日志中间件：记录每条请求的时间、路径、方法、耗时与状态码
# ──────────────────────────────────────────────────────────────────────────────
@app.middleware("http")
async def http(request: Request, call_next):
    """拦截所有 HTTP 请求，统一记录访问日志"""
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency = (time.perf_counter() - start_time) * 1000  # 单位：毫秒
        app_logger.info(
            "{method} {path} | status={status} | latency={latency:.1f}ms",
            method=request.method,
            path=request.url.path,
            status=500,
            latency=latency,
        )
        # 重新抛出异常，让全局异常处理器生成统一的 500 响应
        raise
    else:
        latency = (time.perf_counter() - start_time) * 1000  # 单位：毫秒
        app_logger.info(
            "{method} {path} | status={status} | latency={latency:.1f}ms",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency=latency,
        )
        return response
# ──────────────────────────────────────────────────────────────────────────────
# 全局异常处理器：捕获未处理异常，返回标准 JSON 错误响应
# ──────────────────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获全局未处理异常，返回统一格式的 JSON 错误信息"""
    app_logger.exception(
        "未处理的异常 [{method} {path}]: {exc}",
        method=request.method,
        path=request.url.path,
        exc=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": "服务器内部错误，请稍后重试", "data": None},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """统一处理 HTTPException，避免前端拿到不一致错误结构。"""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    app_logger.warning(
        "HTTPException [{method} {path}] status={status} detail={detail}",
        method=request.method,
        path=request.url.path,
        status=exc.status_code,
        detail=detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": detail, "detail": detail, "data": None},
    )

# 注册路由
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(analytics.proxy_router)
app.include_router(ai.router)
app.include_router(crawler.router)
app.include_router(admin.router)
app.include_router(user_space.router)


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    # 关闭 uvicorn 默认 access 日志，避免与自定义中间件日志重复输出
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.disabled = True

    app_logger.info("=" * 60)
    app_logger.info("🚀 {} v{}", settings.app_name, settings.app_version)
    app_logger.info("=" * 60)

    # 初始化数据库
    init_database()

    # 启动定时任务调度器（AsyncIOScheduler）
    scheduler = create_scheduler()
    scheduler.start()
    # 将 scheduler 挂载到 app.state，以便 shutdown 时停止
    app.state.scheduler = scheduler
    app_logger.info("⏰ 定时任务已启动：每 1 小时刷新剧集在线人数；每月 1 日 2:00 生成月度快照")
    start_nlp_worker_pool()

    app_logger.info("✅ 服务器启动成功")
    app_logger.info("📖 API 文档: http://{}:{}/api/docs", settings.host, settings.port)
    app_logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        app_logger.info("⏰ 定时任务已停止")
    stop_nlp_worker_pool()


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/api/docs",
    }


@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
