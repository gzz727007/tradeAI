"""
TradeAI 数据资产管理与版本升级灾备工具 (Data Asset Management & Disaster Recovery CLI)
用于系统升级、数据无损保留、便携式备份与跨机器迁移：

常用命令：
  # 1. 查看当前数据资产全貌 (数据库体量、策略、回测、账户与行情数据湖)
  python scripts/manage_data.py status

  # 2. 一键快照热备份 (升级代码前强烈推荐执行)
  python scripts/manage_data.py backup --tag "before_v2_upgrade"

  # 3. 从快照安全回滚还原
  python scripts/manage_data.py restore data/backups/trade_ai_snapshot_XXXX.db

  # 4. 全量导出为人类可读的便携式 JSON (可跨平台/跨机器导入)
  python scripts/manage_data.py export-json --out data/export_backup.json

  # 5. 从便携式 JSON 恢复或合并数据
  python scripts/manage_data.py import-json data/export_backup.json
"""

import sys
import os
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

# 自动定位项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Windows 控制台 UTF-8 编码兼容
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config.config import settings
from db.session import SessionLocal, engine
from db.models import Strategy, BacktestRecord, Account, Position, TradeOrder, AgentReportRecord
from db.init_db import init_db

def cmd_status():
    """查看数据资产全貌"""
    print("\n" + "=" * 60)
    print("📊 TradeAI 数据资产与持久化状态看板")
    print("=" * 60)

    db_path = Path(settings.DATA_DIR) / "trade_ai.db"
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"📁 核心关系数据库: {db_path} ({size_kb:.1f} KB)")
        try:
            with SessionLocal() as session:
                strat_cnt = session.query(Strategy).count()
                bt_cnt = session.query(BacktestRecord).count()
                acc_cnt = session.query(Account).count()
                pos_cnt = session.query(Position).count()
                order_cnt = session.query(TradeOrder).count()
                rpt_cnt = session.query(AgentReportRecord).count()

                print(f"  ├── 🎯 量化策略档案: {strat_cnt} 个")
                print(f"  ├── 📈 历史回测归档: {bt_cnt} 条")
                print(f"  ├── 💼 模拟/实盘账户: {acc_cnt} 个 (持仓标的: {pos_cnt} 只, 调仓流水: {order_cnt} 笔)")
                print(f"  └── 🤖 投研会诊纪要: {rpt_cnt} 份")
        except Exception as e:
            print(f"  └── [WARN] 读取数据库表统计失败: {e}")
    else:
        print(f"⚠️ 核心关系数据库尚未建立: {db_path}")

    # 数据湖统计
    print("\n📦 行情数据湖 (Parquet Data Lake):")
    lake_dirs = ["cb", "stock", "etf", "us_stock", "index"]
    total_lake_bytes = 0
    total_files = 0
    for d in lake_dirs:
        dir_path = Path(settings.DATA_DIR) / d
        if dir_path.exists():
            files = list(dir_path.rglob("*.parquet"))
            d_bytes = sum(f.stat().st_size for f in files)
            total_lake_bytes += d_bytes
            total_files += len(files)
            print(f"  ├── [{d.upper()}] {len(files)} 个文件, 共 {d_bytes / (1024*1024):.2f} MB")
    print(f"  └── 行情总计: {total_files} 个文件, {total_lake_bytes / (1024*1024):.2f} MB")

    # 快照备份统计
    backup_dir = Path(settings.DATA_DIR) / "backups"
    if backup_dir.exists():
        backups = sorted(backup_dir.glob("*.db"), key=lambda f: f.stat().st_mtime, reverse=True)
        print(f"\n🛡️ 历史快照热备份 ({len(backups)} 份):")
        for b in backups[:5]:
            mtime = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  ├── {b.name} ({b.stat().st_size / 1024:.1f} KB, 时间: {mtime})")
        if len(backups) > 5:
            print(f"  └── ... (共 {len(backups)} 份快照)")
    print("=" * 60 + "\n")

def cmd_backup(tag: str = ""):
    """热备份 SQLite 数据库及便携式 JSON"""
    db_file = Path(settings.DATA_DIR) / "trade_ai.db"
    if not db_file.exists():
        print(f"[ERROR] 数据库文件不存在: {db_file}")
        return

    backup_dir = Path(settings.DATA_DIR) / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    db_backup_path = backup_dir / f"trade_ai_snapshot_{timestamp}{suffix}.db"
    json_backup_path = backup_dir / f"trade_ai_snapshot_{timestamp}{suffix}.json"

    # 1. SQLite 原生在线热备份
    try:
        src = sqlite3.connect(str(db_file))
        dst = sqlite3.connect(str(db_backup_path))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        print(f"✅ [1/2] 数据库快照创建成功: {db_backup_path}")
    except Exception as e:
        print(f"❌ 数据库快照备份失败: {e}")
        return

    # 2. 导出伴随式便携 JSON
    try:
        data = _dump_all_to_dict()
        with open(json_backup_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ [2/2] 便携式 JSON 导出成功: {json_backup_path}")
        print(f"\n🎉 备份完成！升级代码前随时可使用以下命令回滚:\n   python scripts/manage_data.py restore \"{db_backup_path}\"\n")
    except Exception as e:
        print(f"⚠️ 便携 JSON 伴随备份提示: {e}")

def cmd_restore(backup_file_str: str):
    """从快照安全恢复数据库"""
    backup_path = Path(backup_file_str)
    if not backup_path.exists():
        print(f"❌ 快照文件不存在: {backup_path}")
        return

    target_db = Path(settings.DATA_DIR) / "trade_ai.db"

    # 先对当前可能损坏或待替换的数据库做一个紧急安全留存
    if target_db.exists():
        emergency_file = target_db.parent / f"trade_ai_emergency_before_restore_{int(datetime.now().timestamp())}.db"
        try:
            import shutil
            shutil.copy2(target_db, emergency_file)
            print(f"🛡️ 当前数据库已紧急安全暂存至: {emergency_file.name}")
        except Exception as e:
            print(f"⚠️ 紧急留存提示: {e}")

    try:
        # SQLite 安全热恢复
        src = sqlite3.connect(str(backup_path))
        dst = sqlite3.connect(str(target_db))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        print(f"✅ 成功从快照恢复数据库: {backup_path.name}")
        cmd_status()
    except Exception as e:
        print(f"❌ 恢复数据库失败: {e}")

def _dump_all_to_dict():
    """将数据库全部核心业务表导出为结构化字典"""
    with SessionLocal() as session:
        strategies = [s.to_dict() for s in session.query(Strategy).all()]
        backtests = [b.to_dict(include_curve=True) for b in session.query(BacktestRecord).all()]
        accounts = [a.to_dict() for a in session.query(Account).all()]
        reports = [r.to_dict() for r in session.query(AgentReportRecord).all()]

        return {
            "version": "2.0.0",
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategies": strategies,
            "backtests": backtests,
            "accounts": accounts,
            "agent_reports": reports
        }

def cmd_export_json(out_file_str: str = ""):
    """全量导出为结构化 JSON"""
    out_path = Path(out_file_str) if out_file_str else (Path(settings.DATA_DIR) / "export_all_data.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = _dump_all_to_dict()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已成功导出全部业务数据至便携文件: {out_path}")
    print(f"   (包含 {len(data['strategies'])} 个策略, {len(data['backtests'])} 条回测, {len(data['accounts'])} 个账户)")

def cmd_import_json(in_file_str: str):
    """从便携式 JSON 导入并还原数据库"""
    in_path = Path(in_file_str)
    if not in_path.exists():
        print(f"❌ 导入文件不存在: {in_path}")
        return

    with open(in_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    init_db()  # 确保表结构与增量字段就绪

    with SessionLocal() as session:
        # 1. 导入策略
        strat_imported = 0
        for s in data.get("strategies", []):
            s_id = s.get("id")
            if not s_id:
                continue
            rec = session.query(Strategy).filter(Strategy.id == s_id).first()
            params_str = json.dumps(s.get("params", {}), ensure_ascii=False)
            if rec:
                rec.name = s.get("name", rec.name)
                rec.category = s.get("category", rec.category)
                rec.description = s.get("description", rec.description)
                rec.params_json = params_str
                rec.version = s.get("version", 1)
            else:
                rec = Strategy(
                    id=s_id,
                    name=s.get("name", s_id),
                    category=s.get("category", "用户自定义"),
                    description=s.get("description", ""),
                    params_json=params_str,
                    version=s.get("version", 1)
                )
                session.add(rec)
            strat_imported += 1

        # 2. 导入回测
        bt_imported = 0
        for b in data.get("backtests", []):
            b_id = b.get("id")
            if not b_id:
                continue
            rec = session.query(BacktestRecord).filter(BacktestRecord.id == b_id).first()
            if not rec:
                rec = BacktestRecord(
                    id=b_id,
                    strategy_id=b.get("strategy_id"),
                    strategy_name=b.get("strategy_name", ""),
                    start_date=b.get("start_date", ""),
                    end_date=b.get("end_date", ""),
                    rebalance_freq=b.get("rebalance_freq", 5),
                    mode=b.get("mode", "real"),
                    total_return=float(b.get("total_return", 0.0)),
                    annual_return=float(b.get("annual_return", 0.0)),
                    max_drawdown=float(b.get("max_drawdown", 0.0)),
                    sharpe_ratio=float(b.get("sharpe_ratio", 0.0)),
                    win_rate=float(b.get("win_rate", 0.0)),
                    benchmark_return=float(b.get("benchmark_return", 0.0)),
                    metrics_json=json.dumps(b.get("metrics", {}), ensure_ascii=False),
                    curve_data_json=json.dumps(b.get("curve_data", {}), ensure_ascii=False)
                )
                session.add(rec)
                bt_imported += 1

        # 3. 导入账户
        acc_imported = 0
        for a in data.get("accounts", []):
            a_id = a.get("account_id") or a.get("id")
            if not a_id:
                continue
            rec = session.query(Account).filter(Account.id == a_id).first()
            if not rec:
                rec = Account(
                    id=a_id,
                    name=a.get("account_name", a_id),
                    account_type=a.get("account_type", "PAPER"),
                    associated_strategy=a.get("associated_strategy", ""),
                    initial_capital=float(a.get("initial_capital", 100000.0)),
                    available_cash=float(a.get("available_cash", 100000.0)),
                    total_asset=float(a.get("total_asset", a.get("available_cash", 100000.0))),
                    status=a.get("status", "ACTIVE"),
                    nav_history_json=json.dumps(a.get("nav_history", []), ensure_ascii=False)
                )
                session.add(rec)
                session.flush()

                for sym, p in a.get("positions", {}).items():
                    pos_obj = Position(
                        account_id=a_id,
                        symbol=sym,
                        name=p.get("bond_name", sym),
                        amount=int(p.get("amount", 0)),
                        avg_price=float(p.get("avg_price", 0.0)),
                        current_price=float(p.get("current_price", p.get("avg_price", 0.0))),
                        market_value=float(p.get("market_value", 0.0)),
                        profit_rate=float(p.get("profit_rate", 0.0)),
                        buy_date=p.get("buy_date", "")
                    )
                    session.add(pos_obj)

                for idx, t in enumerate(a.get("history_trades", [])):
                    trade_time_str = t.get("trade_time", "")
                    try:
                        t_dt = datetime.strptime(trade_time_str, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        t_dt = datetime.now()
                    t_id = t.get("order_id") or f"tr_{a_id}_{int(t_dt.timestamp())}_{idx}"
                    order_obj = TradeOrder(
                        id=t_id,
                        account_id=a_id,
                        symbol=t.get("bond_code", ""),
                        name=t.get("bond_name", ""),
                        action=t.get("action", "BUY"),
                        price=float(t.get("price", 0.0)),
                        amount=int(t.get("amount", 0)),
                        fee=float(t.get("fee", 0.0)),
                        reason=t.get("reason", ""),
                        trade_time=t_dt
                    )
                    session.add(order_obj)
                acc_imported += 1

        session.commit()
        print(f"🎉 导入完成！成功同步: {strat_imported} 个策略, {bt_imported} 条新增回测, {acc_imported} 个账户")

def main():
    parser = argparse.ArgumentParser(description="TradeAI 数据资产与灾备管理工具")
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    subparsers.add_parser("status", help="查看当前数据资产与备份状态")

    backup_parser = subparsers.add_parser("backup", help="创建数据库快照热备份")
    backup_parser.add_argument("--tag", type=str, default="", help="备份标签备注")

    restore_parser = subparsers.add_parser("restore", help="从快照安全回滚数据库")
    restore_parser.add_argument("file", type=str, help="快照文件路径 (.db)")

    export_parser = subparsers.add_parser("export-json", help="导出全部数据为便携 JSON")
    export_parser.add_argument("--out", type=str, default="", help="输出文件路径")

    import_parser = subparsers.add_parser("import-json", help="从便携 JSON 恢复或合并数据")
    import_parser.add_argument("file", type=str, help="待导入的 JSON 文件路径")

    args = parser.parse_args()

    if args.command == "status" or not args.command:
        cmd_status()
    elif args.command == "backup":
        cmd_backup(tag=args.tag)
    elif args.command == "restore":
        cmd_restore(args.file)
    elif args.command == "export-json":
        cmd_export_json(args.out)
    elif args.command == "import-json":
        cmd_import_json(args.file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
