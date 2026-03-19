# database.py
"""
数据库连接和会话管理
使用 SQLite 作为数据存储，提供数据库引擎和会话工厂
"""
import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from typing import Generator


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
    print(f"✅ 数据库已初始化: {DATABASE_PATH}")


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
    print("🚀 正在初始化数据库...")
    create_db_and_tables()
    print(f"📁 数据库位置: {DATABASE_PATH}")


if __name__ == "__main__":
    # 测试数据库连接
    init_database()
