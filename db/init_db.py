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
from db.models import Strategy, BacktestRecord, Account, Position, TradeOrder, AgentReportRecord, AgentDefinition, MeetingChamber

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

        # 4. 初始化预置智能体人才库与议事厅 (Agent Talent Pool & Chambers)
        seed_default_agents_and_chambers(session)

    finally:
        session.close()

def seed_default_agents_and_chambers(session):
    """预置默认智能体与经典议事空间 (圆桌投研 + 多空法庭)"""
    try:
        # 1. 预置智能体定义
        default_agents = [
            {
                "id": "cb_credit",
                "name": "首席信用风控官",
                "avatar": "🛡️",
                "target_asset": "cb",
                "role_type": "veto",
                "description": "穿透审查发债公司基本面、债务违约与退市风险，拥有一票否决权 (VETO)",
                "model_provider": "auto",
                "model_name": "",
                "system_prompt": "你是可转债投研委员会的【首席信用风控官】。你的职责是极度严谨地排查发债公司是否存在退市风险警示(*ST/ST)、大股东高比例质押爆仓、债券信用评级降级或违约暴雷隐患。对高危标的拥有神圣的一票否决权。",
                "user_prompt_template": "标的: {bond_name} ({bond_code}), 正股: {stock_name}, 现价: {price}元, 评级: {rating}。请评估是否存在信用违约或退市风险，给出审查结论 (PASS/WARN/VETO) 与详细论证理由。",
                "is_builtin": True,
                "sort_order": 1
            },
            {
                "id": "cb_equity",
                "name": "正股动量分析师",
                "avatar": "🚀",
                "target_asset": "cb",
                "role_type": "score",
                "description": "扫描正股均线趋势与所处题材风口（算力/自主可控等），输出正股弹性进攻评分 (0~100)",
                "model_provider": "auto",
                "model_name": "",
                "system_prompt": "你是可转债投研委员会的【正股动量分析师】。你的职责是从进攻视角评估转债正股的技术面均线多头排列、所处热门行业题材风口与短期资金关注度，输出进攻弹性评分 (0-100)。",
                "user_prompt_template": "标的: {bond_name} ({bond_code}), 正股: {stock_name}, 转债溢价率: {premium_rate}%。请分析正股所属题材与进攻动量，给出 0-100 弹性评分与催化逻辑。",
                "is_builtin": True,
                "sort_order": 2
            },
            {
                "id": "cb_clause",
                "name": "条款博弈专家",
                "avatar": "♟️",
                "target_asset": "cb",
                "role_type": "review",
                "description": "深度推演大股东下修博弈意愿与强赎风险不对称赔率空间",
                "model_provider": "auto",
                "model_name": "",
                "system_prompt": "你是可转债投研委员会的【条款博弈专家】。你的职责是评估转债特有条款价值：下修到底概率、强赎砸盘风险（价格是否临近130元强赎触发线）、大股东转股诉求与不对称赔率空间。",
                "user_prompt_template": "标的: {bond_name} ({bond_code}), 现价: {price}元, 溢价率: {premium_rate}%, 规模: {remaining_scale}亿。请推演下修博弈空间与强赎风险，给出深入博弈结论。",
                "is_builtin": True,
                "sort_order": 3
            },
            {
                "id": "bear_prosecutor",
                "name": "做空公诉人 · 浑水质询官",
                "avatar": "🔴",
                "target_asset": "universal",
                "role_type": "prosecutor",
                "description": "坚定的做空主义者，专挑造假破绽、估值泡沫、质押暴雷与诱多陷阱，千方百计论证买入会亏损",
                "model_provider": "auto",
                "model_name": "",
                "system_prompt": "你是金融多空对抗法庭上的【激进空头公诉人】（做空机构视角）。你的天职是怀疑一切，专挑标的的致命弱点：财务造假疑点、应收账款恶化、高估值泡沫、大股东暗中减持或高质押、技术面诱多顶背离。你的目标是向法庭提供有力的做空指控，千方百计证明买入此标的将带来巨大亏损！",
                "user_prompt_template": "标的: {bond_name} ({bond_code}), 现价: {price}元, 溢价率/估值: {premium_rate}%。请作为空方公诉人，针对此标的列出最致命的 3 大做空控诉证据，坚决主张驳回建仓。",
                "is_builtin": True,
                "sort_order": 4
            },
            {
                "id": "bull_defender",
                "name": "多头辩护人 · 价值辩护律师",
                "avatar": "🟢",
                "target_asset": "universal",
                "role_type": "defender",
                "description": "坚定的买方多头代表，挖掘硬核护城河、周期反转催化剂、业绩预期差与非对称暴利机会",
                "model_provider": "auto",
                "model_name": "",
                "system_prompt": "你是金融多空对抗法庭上的【执着多头辩护人】（顶尖买方价值投资者视角）。面对空方公诉人的残酷指控，你要据理力争，找出标的核心护城河、产业周期反转催化剂、未被市场充分认知的预期差以及不对称的高盈亏比。你的目标是向法官证明此标的具有不可错过的阿尔法超额收益潜力！",
                "user_prompt_template": "标的: {bond_name} ({bond_code}), 现价: {price}元, 溢价率/估值: {premium_rate}%。针对做空风险，请给出最强有力的反驳辩词，阐述支撑其上涨的 3 大不可替代核心逻辑与非对称高赔率优势。",
                "is_builtin": True,
                "sort_order": 5
            },
            {
                "id": "court_judge",
                "name": "首席大法官 · 独立合议庭",
                "avatar": "⚖️",
                "target_asset": "universal",
                "role_type": "judge",
                "description": "兼听多空控辩双方所有质询论据，秉持客观中立，下达建仓许可或驳回判决令，并量刑建议仓位权重",
                "model_provider": "auto",
                "model_name": "",
                "system_prompt": "你是金融多空裁决法庭的【主审首席大法官】（首席投资官 CIO / PM 仲裁视角）。你已听取了【空头公诉人】的严厉控诉与【多头辩护人】的抗辩理由。你必须秉持绝对客观与冷酷的资本准则，审查双方证据链的可信度，最终敲槌下达《金融合议裁决书》：裁定罪名是否成立（驳回建仓 / 疑罪从无轻仓观察 / 控方证据不足准予重仓配置），并给出具体判决执行权重与防守止损线。",
                "user_prompt_template": "标的: {bond_name} ({bond_code})。请主审大法官敲槌宣判！输出最终判决结果 (REJECT 驳回 / WATCH 观望 / ACQUIT_BUY 准予建仓)、推荐配置权重与核心量刑判词。",
                "is_builtin": True,
                "sort_order": 6
            }
        ]

        for a in default_agents:
            existing = session.query(AgentDefinition).filter(AgentDefinition.id == a["id"]).first()
            if not existing:
                agent_obj = AgentDefinition(
                    id=a["id"],
                    name=a["name"],
                    avatar=a["avatar"],
                    target_asset=a["target_asset"],
                    role_type=a["role_type"],
                    description=a["description"],
                    model_provider=a["model_provider"],
                    model_name=a["model_name"],
                    system_prompt=a["system_prompt"],
                    user_prompt_template=a["user_prompt_template"],
                    is_builtin=a["is_builtin"],
                    is_active=True,
                    sort_order=a["sort_order"]
                )
                session.add(agent_obj)

        # 2. 预置议事空间 (Meeting Chambers)
        default_chambers = [
            {
                "id": "chamber_cb_roundtable",
                "name": "🏛️ 可转债多智能体投研圆桌",
                "chamber_type": "ROUNDTABLE",
                "target_asset": "cb",
                "description": "经典可转债多维度研判：信用一票否决 + 正股动量弹性 + 条款下修博弈 + 投资总监PM量化终审",
                "icon": "🏛️",
                "agent_ids": ["cb_credit", "cb_equity", "cb_clause"],
                "sort_order": 1
            },
            {
                "id": "chamber_adversarial_court",
                "name": "⚖️ 金融多空对抗裁决法庭",
                "chamber_type": "COURTROOM",
                "target_asset": "universal",
                "description": "高确定性残酷多空交锋：做空公诉人挑刺指控 vs 多头律师护城河辩护 vs 主审大法官敲槌裁决",
                "icon": "⚖️",
                "agent_ids": ["bear_prosecutor", "bull_defender", "court_judge"],
                "sort_order": 2
            }
        ]

        for c in default_chambers:
            existing_c = session.query(MeetingChamber).filter(MeetingChamber.id == c["id"]).first()
            if not existing_c:
                chamber_obj = MeetingChamber(
                    id=c["id"],
                    name=c["name"],
                    chamber_type=c["chamber_type"],
                    target_asset=c["target_asset"],
                    description=c["description"],
                    icon=c["icon"],
                    agent_ids_json=json.dumps(c["agent_ids"], ensure_ascii=False),
                    is_active=True,
                    sort_order=c["sort_order"]
                )
                session.add(chamber_obj)

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[WARN] 初始化预置智能体与议事厅失败: {e}")

if __name__ == "__main__":
    init_db()
