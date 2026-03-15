# main.py
"""
FastAPI 应用主入口
整合所有路由和中间件，启动应用服务
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .database import init_database, engine
from .config import settings
from .routers import auth, analytics, ai, crawler


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Bilibili 番剧数据分析平台 - 统一的 FastAPI 后端服务",
    docs_url="/api/docs",  # Swagger UI 文档地址
    redoc_url="/api/redoc"  # ReDoc 文档地址
)

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(ai.router)
app.include_router(crawler.router)


def _run_update_online_viewers():
    """在独立的数据库会话中刷新所有剧集在线人数"""
    from sqlmodel import Session
    from .scraper import BilibiliBangumiCrawler
    with Session(engine) as session:
        crawler_instance = BilibiliBangumiCrawler(session)
        crawler_instance.update_online_viewers_for_all_episodes()


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print("=" * 60)
    print(f"🚀 {settings.app_name} v{settings.app_version}")
    print("=" * 60)
    
    # 初始化数据库
    init_database()

    # 启动定时任务：每 4 小时刷新一次所有剧集在线人数
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_update_online_viewers,
        trigger='interval',
        hours=4,
        id='update_online_viewers_job',
        replace_existing=True,
    )
    scheduler.start()
    # 将 scheduler 挂载到 app.state，以便 shutdown 时停止
    app.state.scheduler = scheduler
    print("⏰ 定时任务已启动：每 4 小时刷新剧集在线人数")
    
    print(f"✅ 服务器启动成功")
    print(f"📖 API 文档: http://{settings.host}:{settings.port}/api/docs")
    print(f"📖 ReDoc 文档: http://{settings.host}:{settings.port}/api/redoc")
    print("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏰ 定时任务已停止")


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/api/docs",
        "redoc": "/api/redoc"
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
