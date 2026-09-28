"""
数据库连接与会话管理器 (Database Session Manager)
默认采用 SQLite + WAL (Write-Ahead Logging) 高并发读写分离事务引擎，
支持无缝切换至 PostgreSQL 生产集群。
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from config.config import settings

db_url = settings.DATABASE_URL

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 创建通用 SQLAlchemy 引擎
engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
    pool_pre_ping=True
)

# 针对 SQLite 自动开启企业级 WAL (预写日志) 模式与外键约束
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI 依赖注入会话生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context():
    """上下文管理器 (用于后台任务或独立模块)"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
