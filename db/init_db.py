"""
数据库自动建表、增量无损平滑迁移与快照热备份器 (Database Auto-migration & Hot-Backup)
系统每次启动时自动执行：
1. [安全快照热备份]: 在任何变更前，对 SQLite 数据库进行热备份 (SQLite Online Backup)，保留最近 15 份快照；
2. [增量平滑迁移]: 动态比对 ORM 模型与数据库物理表，若发现新版代码定义了新字段 (如 version, tags 等)，
   自动执行无损 ALTER TABLE ... ADD COLUMN，绝不丢失已有数据，无需手动写 SQL；
3. [新表自动创建]: 自动建立新增数据表 (DDL, 如 agent_report_records)；
4. [冷启动历史迁移]: 若初次部署，自动从旧版 JSON 中将已有策略与流水迁入关系型数据库。
"""

import os
import json
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from sqlalchemy import inspect, text

from config.config import settings
from db.session import Base, engine, SessionLocal
from db.models import Strategy, BacktestRecord, Account, Position, TradeOrder, AgentReportRecord

def auto_backup_database():
    """
    启动或迁移前自动快照备份 SQLite 数据库。
    采用 SQLite 原生在线备份 API (安全热备份，防锁表)。
    最多滚动保留最近 15 份快照。
    """
    try:
        db_file = Path(settings.DATA_DIR) / "trade_ai.db"
        if not db_file.exists() or db_file.stat().st_size == 0:
            return

        backup_dir = Path(settings.DATA_DIR) / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"trade_ai_auto_{timestamp}.db"

        # SQLite 原生在线热备份
        src_conn = sqlite3.connect(str(db_file))
        dst_conn = sqlite3.connect(str(backup_path))
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()

        print(f"[DB-BACKUP] 自动热备份数据库快照成功: backups/{backup_path.name}")

        # 滚动清理：最多保留 15 个最新快照
        backups = sorted(backup_dir.glob("trade_ai_auto_*.db"), key=lambda f: f.stat().st_mtime, reverse=True)
        for old_b in backups[15:]:
            try:
                old_b.unlink()
            except Exception:
                pass
    except Exception as e:
        print(f"[DB-BACKUP-WARN] 自动备份数据库提示: {e}")

def auto_migrate_schema(engine, Base):
    """
    轻量级增量无损平滑迁移器：
    对比 SQLAlchemy ORM Model 定义与数据库现有物理表结构，
    若发现新版代码定义了新列，自动无损执行 ALTER TABLE ... ADD COLUMN ...。
    """
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        with engine.connect() as conn:
            for table_name, table in Base.metadata.tables.items():
                if table_name in existing_tables:
                    existing_cols = {col["name"]: col for col in inspector.get_columns(table_name)}
                    for col in table.columns:
                        if col.name not in existing_cols:
                            col_type = col.type.compile(engine.dialect)
                            default_clause = ""
                            if col.default is not None:
                                arg = getattr(col.default, 'arg', None)
                                if arg is not None and not callable(arg):
                                    if isinstance(arg, str):
                                        default_clause = f" DEFAULT '{arg}'"
                                    elif isinstance(arg, (int, float)):
                                        default_clause = f" DEFAULT {arg}"
                                    elif isinstance(arg, bool):
                                        default_clause = f" DEFAULT {1 if arg else 0}"

                            sql = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default_clause}"
                            try:
                                conn.execute(text(sql))
                                conn.commit()
                                print(f"[AUTO-MIGRATE] 成功为表 '{table_name}' 平滑增量添加字段 '{col.name}' ({col_type})")
                            except Exception as e:
                                print(f"[AUTO-MIGRATE-WARN] 表 '{table_name}' 添加字段 '{col.name}' 提示: {e}")
    except Exception as e:
        print(f"[AUTO-MIGRATE-ERROR] 检查或增量迁移数据表异常: {e}")

def init_db():
    # 1. 优先执行快照热备份
    auto_backup_database()

    # 2. 创建所有新数据表 (DDL)
    Base.metadata.create_all(bind=engine)

    # 3. 增量平滑迁移已存在表的新增字段 (ALTER TABLE)
    auto_migrate_schema(engine, Base)

    session = SessionLocal()
    try:
        # 4. 检查并迁移旧版策略档案 (strategies)
        strat_count = session.query(Strategy).count()
        if strat_count == 0:
            pool_json_file = settings.DATA_DIR / "strategies_pool.json"
            if pool_json_file.exists():
                try:
                    with open(pool_json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    strategies_map = data.get("strategies", {})
                    for s_id, s in strategies_map.items():
                        new_strat = Strategy(
                            id=s_id,
                            name=s.get("name", s_id),
                            category=s.get("category", "用户自定义"),
                            description=s.get("description", ""),
                            params_json=json.dumps(s.get("params", {}), ensure_ascii=False),
                            version=1
                        )
                        session.add(new_strat)
                    session.commit()
                    print(f"[INFO] 成功从 strategies_pool.json 迁移 {len(strategies_map)} 个策略至数据库！")
                except Exception as e:
                    session.rollback()
                    print(f"[WARN] 从 strategies_pool.json 迁移策略失败: {e}")

        # 5. 检查并迁移账户与持仓记录 (accounts, positions, trade_orders)
        account_count = session.query(Account).count()
        if account_count == 0:
            ledger_json_file = settings.DATA_DIR / "accounts_ledger.json"
            if ledger_json_file.exists():
                try:
                    with open(ledger_json_file, "r", encoding="utf-8") as f:
                        ledger_data = json.load(f)
                    accounts_map = ledger_data.get("accounts", {})
                    for acc_id, acc in accounts_map.items():
                        new_acc = Account(
                            id=acc_id,
                            name=acc.get("account_name", acc_id),
                            account_type=acc.get("account_type", "PAPER"),
                            associated_strategy=acc.get("associated_strategy", ""),
                            initial_capital=float(acc.get("initial_capital", 100000.0)),
                            available_cash=float(acc.get("available_cash", 100000.0)),
                            total_asset=float(acc.get("total_assets", acc.get("available_cash", 100000.0))),
                            status="ACTIVE",
                            nav_history_json=json.dumps(acc.get("nav_history", []), ensure_ascii=False)
                        )
                        session.add(new_acc)
                        session.flush()

                        # 迁移持仓
                        for symbol, pos in acc.get("positions", {}).items():
                            p_obj = Position(
                                account_id=acc_id,
                                symbol=symbol,
                                name=pos.get("bond_name", symbol),
                                amount=int(pos.get("amount", 0)),
                                avg_price=float(pos.get("avg_price", 0.0)),
                                current_price=float(pos.get("current_price", pos.get("avg_price", 0.0))),
                                market_value=float(pos.get("market_value", 0.0)),
                                profit_rate=float(pos.get("profit_rate", 0.0)),
                                buy_date=pos.get("buy_date", "")
                            )
                            session.add(p_obj)

                        # 迁移历史流水
                        for idx, t in enumerate(acc.get("history_trades", [])):
                            trade_time_str = t.get("trade_time", "")
                            try:
                                t_dt = datetime.strptime(trade_time_str, "%Y-%m-%d %H:%M:%S")
                            except Exception:
                                t_dt = datetime.now()

                            trade_id = f"tr_{acc_id}_{int(t_dt.timestamp())}_{idx}"
                            t_obj = TradeOrder(
                                id=trade_id,
                                account_id=acc_id,
                                symbol=t.get("bond_code", ""),
                                name=t.get("bond_name", ""),
                                action=t.get("action", "BUY"),
                                price=float(t.get("price", 0.0)),
                                amount=int(t.get("amount", 0)),
                                fee=float(t.get("fee", 0.0)),
                                reason=t.get("reason", ""),
                                trade_time=t_dt
                            )
                            session.add(t_obj)

                    session.commit()
                    print(f"[INFO] 成功从 accounts_ledger.json 迁移 {len(accounts_map)} 个账户与持仓流水至数据库！")
                except Exception as e:
                    session.rollback()
                    print(f"[WARN] 从 accounts_ledger.json 迁移账户失败: {e}")

    finally:
        session.close()

if __name__ == "__main__":
    init_db()
