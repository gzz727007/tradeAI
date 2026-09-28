"""
TradeAI 统一数据库模块 (SQLAlchemy 关系型事务引擎)
支持 SQLite (WAL并发事务模式) 与 PostgreSQL 无缝切换。
"""

from db.session import Base, engine, SessionLocal, get_db, get_db_context
from db.models import Strategy, BacktestRecord, Account, Position, TradeOrder, AgentReportRecord
from db.init_db import init_db

__all__ = [
    "Base",
    "engine",
    "SessionLocal",
    "get_db",
    "get_db_context",
    "Strategy",
    "BacktestRecord",
    "Account",
    "Position",
    "TradeOrder",
    "AgentReportRecord",
    "init_db",
]
