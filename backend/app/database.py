# database.py
"""
数据库连接和会话管理
使用 SQLite 作为数据存储，提供数据库引擎和会话工厂
"""
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event, text as sa_text
from sqlalchemy.pool import StaticPool
from typing import Generator
from loguru import logger

# 数据库文件路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(DATABASE_DIR, "bilibili.db")

# 确保数据目录存在
os.makedirs(DATABASE_DIR, exist_ok=True)

# SQLite 连接字符串
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# 创建数据库引擎
# check_same_thread=False: 允许多线程访问（仅用于 SQLite）
# poolclass=StaticPool: 使用静态连接池（适合 SQLite）
engine = create_engine(
    DATABASE_URL,
    echo=False,  # 设置为 True 可以看到 SQL 日志
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    """
    开启 SQLite WAL 模式，支持读写并发，避免多线程下的数据库锁冲突。
    WAL 模式允许爬虫写入时，其他请求仍能正常读取，消除 'database is locked' 错误。
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")      # 开启 WAL 模式，支持读写并发
        cursor.execute("PRAGMA synchronous=NORMAL")    # 平衡性能与安全
        cursor.execute("PRAGMA busy_timeout=5000")     # 等待锁的超时时间设为 5000 毫秒
    finally:
        cursor.close()


def create_db_and_tables():
    """
    创建所有数据库表
    在应用启动时调用
    """
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()
    logger.success(f"✅ 数据库已初始化")  # 使用 success 级别，控制台会显示绿色


# 新增列的 DDL 定义：(列名, SQLite 类型)
_NEW_ANIME_COLUMNS: list = [
    ("total_coins", "INTEGER"),
    ("total_danmakus", "INTEGER"),
    ("total_likes", "INTEGER"),
    ("total_reply", "INTEGER"),
    ("total_share", "INTEGER"),
    ("rating_count", "INTEGER"),
    ("is_finish", "INTEGER"),
    ("copyright", "VARCHAR(20)"),
    ("areas_raw", "JSON"),
]

# 用户表新增列
_NEW_USER_COLUMNS: list = [
    ("is_admin", "BOOLEAN DEFAULT 0"),
    ("is_active", "BOOLEAN DEFAULT 1"),
]

# 爬虫日志表新增列
_NEW_CRAWL_LOG_COLUMNS: list = [
    ("total_scraped", "INTEGER"),
    ("cleaned_filtered", "INTEGER"),
    ("final_inserted", "INTEGER"),
    ("failed_reason", "VARCHAR(1000)"),
    ("duration", "REAL"),
]


def _add_missing_columns():
    """
    对已存在的 anime 表执行增量列迁移：只添加尚未存在的列，不影响现有数据。
    SQLite 不支持 ALTER TABLE … ADD COLUMN IF NOT EXISTS 语法，因此先用
    PRAGMA table_info 查询已有列，再逐一添加缺失列。
    若 anime 表尚不存在（首次启动），直接返回，由 create_all 负责建表。
    """
    with engine.connect() as conn:
        # 先检查表是否存在，避免对不存在的表执行 ALTER TABLE
        table_exists_rows = conn.execute(
            sa_text("SELECT name FROM sqlite_master WHERE type='table' AND name='anime'")
        ).fetchall()
        if not table_exists_rows:
            return  # 首次启动：表尚未由 create_all 创建，直接跳过

        existing = {
            row[1]
            for row in conn.execute(sa_text("PRAGMA table_info(anime)"))
        }

        for col_name, col_type in _NEW_ANIME_COLUMNS:
            if col_name not in existing:
                try:
                    conn.execute(
                        sa_text(f"ALTER TABLE anime ADD COLUMN {col_name} {col_type} DEFAULT NULL")
                    )
                    conn.commit()
                    logger.info(f"  ✅ 迁移：已向 anime 表添加列 {col_name}")
                except Exception as exc:
                    logger.warning(f"  ⚠️ 添加列 {col_name} 失败: {exc}")

        # 用户表增量列迁移
        user_existing = {
            row[1]
            for row in conn.execute(sa_text("PRAGMA table_info(users)"))
        }
        for col_name, col_type in _NEW_USER_COLUMNS:
            if col_name not in user_existing:
                try:
                    conn.execute(
                        sa_text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    )
                    conn.commit()
                    logger.info(f"  ✅ 迁移：已向 users 表添加列 {col_name}")
                except Exception as exc:
                    logger.warning(f"  ⚠️ 向 users 表添加列 {col_name} 失败: {exc}")

        # 爬虫日志表增量列迁移
        crawl_log_existing = {
            row[1]
            for row in conn.execute(sa_text("PRAGMA table_info(crawl_logs)"))
        }
        for col_name, col_type in _NEW_CRAWL_LOG_COLUMNS:
            if col_name not in crawl_log_existing:
                try:
                    conn.execute(
                        sa_text(f"ALTER TABLE crawl_logs ADD COLUMN {col_name} {col_type}")
                    )
                    conn.commit()
                    logger.info(f"  ✅ 迁移：已向 crawl_logs 表添加列 {col_name}")
                except Exception as exc:
                    logger.warning(f"  ⚠️ 向 crawl_logs 表添加列 {col_name} 失败: {exc}")


def get_session() -> Generator[Session, None, None]:
    """
    获取数据库会话
    用于依赖注入，自动管理会话的创建和关闭
    
    使用示例:
        @app.get("/items")
        def read_items(session: Session = Depends(get_session)):
            items = session.exec(select(Item)).all()
            return items
    """
    with Session(engine) as session:
        yield session


def init_database():
    """
    初始化数据库
    创建所有表结构
    """
    logger.info("🚀 正在初始化数据库...")
    create_db_and_tables()


if __name__ == "__main__":
    # 测试数据库连接
    init_database()
