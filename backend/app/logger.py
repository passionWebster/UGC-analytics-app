# 日志模块实现文件
"""
统一日志配置模块

基于 Loguru 提供全项目的日志管理，包括：
- 标准应用日志（输出到控制台 + 文件）
- 爬虫专属日志（独立绑定，隔离爬虫日志与 Web 服务日志）
"""
import sys
from pathlib import Path
from loguru import logger

# ──────────────────────────────────────────────────────────────────────────────
# 日志目录：固定在项目根目录下的 logs/，与进程工作目录无关
# __file__ = backend/app/logger.py  →  parents[2] = 项目根目录
# ──────────────────────────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# 移除 Loguru 默认 Handler，统一重新配置
# ──────────────────────────────────────────────────────────────────────────────
logger.remove()

# ──────────────────────────────────────────────────────────────────────────────
# Handler 1：控制台输出（标准应用日志，级别 INFO 及以上）
# ──────────────────────────────────────────────────────────────────────────────
logger.add(
    sys.stdout,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    colorize=True,
)

# ──────────────────────────────────────────────────────────────────────────────
# Handler 2：应用日志文件（轮转，保留 7 天）
# ──────────────────────────────────────────────────────────────────────────────
logger.add(
    _LOG_DIR / "app.log",
    level="INFO",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} - "
        "{message}"
    ),
    rotation="10 MB",   # 单文件超过 10 MB 时轮转
    retention="7 days", # 保留最近 7 天的日志文件
    compression="zip",  # 旧日志压缩为 zip
    encoding="utf-8",
    filter=lambda record: record["extra"].get("module") != "scraper",
)

# ──────────────────────────────────────────────────────────────────────────────
# Handler 3：爬虫专属日志文件（独立文件，便于运维查看爬取状态）
# ──────────────────────────────────────────────────────────────────────────────
logger.add(
    _LOG_DIR / "scraper.log",
    level="DEBUG",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "[SCRAPER] "
        "{message}"
    ),
    rotation="20 MB",
    retention="14 days",
    compression="zip",
    encoding="utf-8",
    filter=lambda record: record["extra"].get("module") == "scraper",
)

# ──────────────────────────────────────────────────────────────────────────────
# 对外暴露的 Logger 实例
# ──────────────────────────────────────────────────────────────────────────────

# 标准应用 logger（用于 FastAPI 路由、Service 层等）
app_logger = logger.bind()

# 爬虫专属 logger，所有调用均携带 module="scraper" 标识，
# 与标准应用日志路由到不同的输出通道
scraper_logger = logger.bind(module="scraper")
