"""
多账号实盘记账与模拟盘持久化引擎 (Trading Ledger Engine)
基于 SQLAlchemy 关系型事务数据库实现，支持 SQLite WAL 模式与 PostgreSQL。
支持多账号管理 (按策略划分不同账号)、持仓成本计算、真实市价每日结算与严格调仓审计流水。
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

from config.config import settings
from db.session import SessionLocal
from db.models import Account, Position, TradeOrder
from db.init_db import init_db

class TradingLedger:
    def __init__(self):
        # 确保数据库表已初始化
        init_db()

    def get_accounts(self, account_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取账号列表 (可按 PAPER 或 REAL 过滤)"""
        session = SessionLocal()
        try:
            query = session.query(Account)
            if account_type:
                query = query.filter(Account.account_type == account_type.upper())
            accounts = query.order_by(Account.created_at.asc()).all()
            return [acc.to_dict() for acc in accounts]
        finally:
            session.close()

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取单账号详情"""
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            return acc.to_dict() if acc else None
        finally:
            session.close()

    def create_account(self, account_id: str, name: str = "", strategy: str = "", account_type: str = "PAPER", initial_capital: float = 100000.0, **kwargs) -> bool:
        """新建账号 (ACID事务)"""
        act_name = name or kwargs.get("account_name", account_id)
        act_strategy = strategy or kwargs.get("associated_strategy", "")
        session = SessionLocal()
        try:
            existing = session.query(Account).filter(Account.id == account_id).first()
            if existing:
                return False
            today_str = datetime.now().strftime("%Y-%m-%d")
            nav_init = json.dumps([{"date": today_str, "total_assets": float(initial_capital), "nav": 1.0, "benchmark_nav": 1.0, "portfolio_return": 0.0, "benchmark_return": 0.0, "excess_return": 0.0}], ensure_ascii=False)
            new_acc = Account(
                id=account_id,
                name=act_name,
                account_type=account_type.upper(),
                associated_strategy=act_strategy,
                initial_capital=float(initial_capital),
                available_cash=float(initial_capital),
                total_asset=float(initial_capital),
                status="RUNNING" if account_type.upper() == "PAPER" else "ACTIVE",
                nav_history_json=nav_init,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            session.add(new_acc)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_buy(self, account_id: str, bond_code: str, bond_name: str, price: float, amount: int, reason: str = "") -> bool:
        """
        记录买入成交 (1手 = 10张)
        严格保证资金扣减、持仓更新、流水入库在单个原子事务中完成！
        """
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return False

            cost = price * amount
            # 扣除手续费 (万0.5, 忽略最低收费)
            fee = max(cost * settings.COMMISSION_RATE, 0.1)
            total_cost = cost + fee

            if acc.available_cash < total_cost:
                print(f"[WARN] 账号 {account_id} 现金不足: 需 {total_cost:.2f}元，现有 {acc.available_cash:.2f}元")
                return False

            # 1. 扣减可用资金
            acc.available_cash -= total_cost
            acc.updated_at = datetime.now()

            # 2. 更新或新建持仓明细
            pos = session.query(Position).filter(
                Position.account_id == account_id,
                Position.symbol == bond_code
            ).first()

            if pos:
                total_amount = pos.amount + amount
                total_money = (pos.avg_price * pos.amount) + cost
                pos.avg_price = round(total_money / total_amount, 3)
                pos.amount = total_amount
                pos.current_price = price
                pos.market_value = round(price * total_amount, 2)
                pos.profit_rate = round((price / pos.avg_price - 1.0) * 100, 2)
                pos.updated_at = datetime.now()
            else:
                pos = Position(
                    account_id=account_id,
                    symbol=bond_code,
                    name=bond_name,
                    amount=amount,
                    avg_price=round(price, 3),
                    current_price=price,
                    market_value=round(price * amount, 2),
                    profit_rate=0.0,
                    buy_date=datetime.now().strftime("%Y-%m-%d"),
                    updated_at=datetime.now()
                )
                session.add(pos)

            # 3. 记录买入流水
            t_dt = datetime.now()
            trade_id = f"tr_{account_id}_{int(t_dt.timestamp())}_{bond_code}_BUY"
            trade = TradeOrder(
                id=trade_id,
                account_id=account_id,
                symbol=bond_code,
                name=bond_name,
                action="BUY",
                price=price,
                amount=amount,
                fee=round(fee, 2),
                reason=reason,
                trade_time=t_dt
            )
            session.add(trade)

            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_sell(self, account_id: str, bond_code: str, price: float, amount: int, reason: str = "") -> bool:
        """
        记录卖出成交
        严格保证持仓扣减、资金回流、流水入库在单个原子事务中完成！
        """
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return False

            pos = session.query(Position).filter(
                Position.account_id == account_id,
                Position.symbol == bond_code
            ).first()

            if not pos or pos.amount < amount:
                print(f"[WARN] 账号 {account_id} 持仓不足: 标的 {bond_code} 尝试卖出 {amount} 张，现有 {pos.amount if pos else 0} 张")
                return False

            proceeds = price * amount
            fee = max(proceeds * settings.COMMISSION_RATE, 0.1)
            net_proceeds = proceeds - fee

            # 1. 资金到账
            acc.available_cash += net_proceeds
            acc.updated_at = datetime.now()

            bond_name = pos.name

            # 2. 扣减持仓 (若清仓则彻底删除记录)
            pos.amount -= amount
            if pos.amount <= 0:
                session.delete(pos)
            else:
                pos.current_price = price
                pos.market_value = round(price * pos.amount, 2)
                pos.profit_rate = round((price / pos.avg_price - 1.0) * 100, 2)
                pos.updated_at = datetime.now()

            # 3. 记录卖出流水
            t_dt = datetime.now()
            trade_id = f"tr_{account_id}_{int(t_dt.timestamp())}_{bond_code}_SELL"
            trade = TradeOrder(
                id=trade_id,
                account_id=account_id,
                symbol=bond_code,
                name=bond_name,
                action="SELL",
                price=price,
                amount=amount,
                fee=round(fee, 2),
                reason=reason,
                trade_time=t_dt
            )
            session.add(trade)

            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_account_status(self, account_id: str, status: str) -> bool:
        """更新账户运行状态 (ACTIVE/RUNNING, PAUSED, ENDED, IDLE)"""
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return False
            acc.status = status.upper()
            acc.updated_at = datetime.now()
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def reset_account(self, account_id: str) -> bool:
        """重置模拟账户 (清空持仓、流水与净值历史，资金复原为初始金额)"""
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return False

            session.query(Position).filter(Position.account_id == account_id).delete()
            session.query(TradeOrder).filter(TradeOrder.account_id == account_id).delete()

            today_str = datetime.now().strftime("%Y-%m-%d")
            acc.available_cash = acc.initial_capital
            acc.total_asset = acc.initial_capital
            acc.status = "IDLE"
            acc.nav_history_json = json.dumps([{
                "date": today_str,
                "total_assets": acc.initial_capital,
                "nav": 1.0,
                "benchmark_nav": 1.0,
                "portfolio_return": 0.0,
                "benchmark_return": 0.0,
                "excess_return": 0.0
            }], ensure_ascii=False)
            acc.updated_at = datetime.now()

            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_account(self, account_id: str) -> bool:
        """注销并删除账户及其持仓与交易记录"""
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return False
            session.delete(acc)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _resolve_strategy(self, strategy_ident: str) -> Any:
        """智能匹配并实例化策略引擎"""
        from core.strategy_manager import StrategyManager
        from strategies.configurable_strategy import ConfigurableCBStrategy

        sm = StrategyManager()
        all_strats = sm.get_all_strategies()
        ident_lower = (strategy_ident or "").strip().lower()

        for s in all_strats:
            if s.get("id", "").lower() == ident_lower or s.get("name", "").lower() == ident_lower:
                return ConfigurableCBStrategy(s)

        for s in all_strats:
            s_name = s.get("name", "").lower()
            if ident_lower and (ident_lower in s_name or s_name in ident_lower):
                return ConfigurableCBStrategy(s)

        if "小盘" in strategy_ident or "动量" in strategy_ident or "弹性" in strategy_ident:
            return ConfigurableCBStrategy({
                "id": "strat_small_cap",
                "name": strategy_ident or "小盘高弹性进取",
                "params": {"min_price": 95, "max_price": 145, "max_scale": 5.0, "top_n": 10, "sort_by": "remaining_scale", "sort_ascending": True}
            })
        elif "ytm" in ident_lower or "高息" in strategy_ident or "防守" in strategy_ident:
            return ConfigurableCBStrategy({
                "id": "strat_high_ytm",
                "name": strategy_ident or "高YTM防守反击",
                "params": {"min_price": 85, "max_price": 120, "top_n": 10, "sort_by": "ytm", "sort_ascending": False}
            })
        elif "ai" in ident_lower or "增强" in strategy_ident:
            return ConfigurableCBStrategy({
                "id": "strat_ai_enhanced",
                "name": strategy_ident or "AI多智能体增强型",
                "params": {"min_price": 90, "max_price": 130, "max_scale": 8.0, "double_low_weight": 1.0, "top_n": 10}
            })
        else:
            return ConfigurableCBStrategy({
                "id": "strat_classic_double_low",
                "name": strategy_ident or "经典双低轮动",
                "params": {"min_price": 90, "max_price": 135, "max_premium": 60, "double_low_weight": 1.0, "top_n": 10, "sort_by": "double_low", "sort_ascending": True}
            })

    def seed_paper_account_history(self, account_id: str, lookback_days: int = 60) -> Dict[str, Any]:
        """
        基于真实数据湖运行近 N 个交易日的历史切片回测，
        为模拟账户预演补齐前向赛马的历史对比净值曲线与初始持仓！
        """
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return {"success": False, "message": "账户不存在"}

            strat = self._resolve_strategy(acc.associated_strategy)
            init_cap = acc.initial_capital
        finally:
            session.close()

        from core.data_lake.cb_lake import CBDataLake
        from core.backtest_engine import CBBacktestEngine

        lake = CBDataLake()
        daily_df = lake.load_daily()
        if daily_df.empty:
            return {"success": False, "message": "数据湖未初始化"}

        all_dates = sorted(daily_df["trade_date"].unique().tolist())
        if len(all_dates) < lookback_days:
            lookback_dates = all_dates
        else:
            lookback_dates = all_dates[-lookback_days:]

        s_date = lookback_dates[0].replace("-", "")
        e_date = lookback_dates[-1].replace("-", "")

        engine = CBBacktestEngine([strat], benchmark_symbol="sh000832", start_date=s_date, end_date=e_date, initial_capital=init_cap)
        nav_df, metrics_summary, _ = engine.run()

        if nav_df.empty or strat.name not in nav_df.columns:
            return {"success": False, "message": "回测生成曲线为空"}

        bench_col = "中证转债基准" if "中证转债基准" in nav_df.columns else nav_df.columns[0]
        strat_col = strat.name

        nav_history = []
        for d, row in nav_df.iterrows():
            s_nav = round(float(row[strat_col]), 4)
            b_nav = round(float(row[bench_col]), 4)
            tot_assets = round(init_cap * s_nav, 2)
            p_ret = round((s_nav - 1.0) * 100, 2)
            b_ret = round((b_nav - 1.0) * 100, 2)
            nav_history.append({
                "date": str(d)[:10],
                "total_assets": tot_assets,
                "nav": s_nav,
                "benchmark_nav": b_nav,
                "portfolio_return": p_ret,
                "benchmark_return": b_ret,
                "excess_return": round(p_ret - b_ret, 2)
            })

        latest_day = lookback_dates[-1]
        day_quotes = daily_df[daily_df["trade_date"] == latest_day].copy()
        basic_df = lake.load_basic()
        name_map = dict(zip(basic_df["symbol"], basic_df["name"])) if not basic_df.empty else {}
        day_quotes["bond_name"] = day_quotes["symbol"].map(name_map).fillna(day_quotes["symbol"])
        day_quotes["price"] = day_quotes["close"]
        day_quotes["bond_code"] = day_quotes["symbol"]

        target_df = strat.select_portfolio(latest_day, day_quotes)

        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return {"success": False, "message": "账户不存在"}

            session.query(Position).filter(Position.account_id == account_id).delete()
            session.query(TradeOrder).filter(TradeOrder.account_id == account_id).delete()

            latest_nav = nav_history[-1]["nav"]
            latest_total_assets = round(init_cap * latest_nav, 2)

            allocated_cash = 0.0
            if not target_df.empty:
                target_count = len(target_df)
                per_bond_val = (latest_total_assets * 0.95) / max(target_count, 1)

                for rank, (_, row) in enumerate(target_df.iterrows(), 1):
                    code = str(row["bond_code"])
                    name = str(row["bond_name"])
                    price = float(row["price"])
                    amount = int((per_bond_val / price) // 10 * 10)
                    if amount < 10:
                        amount = 10
                    mkt_val = round(price * amount, 2)
                    allocated_cash += mkt_val

                    pos = Position(
                        account_id=account_id,
                        symbol=code,
                        name=name,
                        amount=amount,
                        avg_price=price,
                        current_price=price,
                        market_value=mkt_val,
                        profit_rate=0.0,
                        buy_date=latest_day,
                        updated_at=datetime.now()
                    )
                    session.add(pos)

                    trade = TradeOrder(
                        id=f"tr_{account_id}_{latest_day.replace('-', '')}_{code}_BUY",
                        account_id=account_id,
                        symbol=code,
                        name=name,
                        action="BUY",
                        price=price,
                        amount=amount,
                        fee=round(mkt_val * settings.COMMISSION_RATE, 2),
                        reason=f"【{strat.name}】前向赛马建仓入选第{rank}名",
                        trade_time=datetime.strptime(f"{latest_day} 09:30:00", "%Y-%m-%d %H:%M:%S")
                    )
                    session.add(trade)

            avail_cash = max(0.0, round(latest_total_assets - allocated_cash, 2))
            acc.available_cash = avail_cash
            acc.total_asset = latest_total_assets
            acc.status = "RUNNING"
            acc.nav_history_json = json.dumps(nav_history, ensure_ascii=False)
            acc.updated_at = datetime.now()

            session.commit()
            return {
                "success": True,
                "account_id": account_id,
                "trading_days": len(nav_history),
                "latest_nav": latest_nav,
                "latest_assets": latest_total_assets,
                "metrics": metrics_summary.get(strat.name, {})
            }
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def trigger_paper_rebalance(self, account_id: str) -> Dict[str, Any]:
        """
        立即执行今日策略选券模拟调仓 (Paper Trading Instant Rebalance)
        1. 运行绑定策略的选券逻辑
        2. 自动清仓调出标的
        3. 自动建仓调入新选标的
        4. 结算资金与净值，生成审计订单流水
        """
        session = SessionLocal()
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            if not acc:
                return {"success": False, "message": f"账户 {account_id} 不存在"}
            if acc.status == "ENDED":
                return {"success": False, "message": f"账户 {account_id} 已归档结束，请先重置或重启"}

            strat_name = acc.associated_strategy
            if acc.status in ["IDLE", "PAUSED"]:
                acc.status = "RUNNING"
                session.commit()
        finally:
            session.close()

        from core.data_fetcher import CBDataFetcher
        from core.data_lake.cb_lake import CBDataLake

        # 获取最新行情数据
        quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=True)
        if quotes_df.empty or "price" not in quotes_df.columns:
            lake = CBDataLake()
            daily_all = lake.load_daily()
            if not daily_all.empty:
                max_d = daily_all["trade_date"].max()
                quotes_df = daily_all[daily_all["trade_date"] == max_d].copy()
                basic_df = lake.load_basic()
                name_map = dict(zip(basic_df["symbol"], basic_df["name"])) if not basic_df.empty else {}
                quotes_df["bond_name"] = quotes_df["symbol"].map(name_map).fillna(quotes_df["symbol"])
                quotes_df["price"] = quotes_df["close"]
                quotes_df["bond_code"] = quotes_df["symbol"]

        if quotes_df.empty:
            return {"success": False, "message": "无法获取行情数据，调仓中止"}

        strat = self._resolve_strategy(strat_name)
        today_str = datetime.now().strftime("%Y-%m-%d")
        selected_df = strat.select_portfolio(today_str, quotes_df)

        if selected_df.empty:
            return {"success": False, "message": "策略选券池为空，无需调仓"}

        target_symbols = [str(c) for c in selected_df["bond_code"].tolist()]
        target_names = dict(zip([str(c) for c in selected_df["bond_code"]], selected_df["bond_name"]))

        price_map = {}
        for _, row in quotes_df.iterrows():
            code = str(row.get("bond_code", row.get("symbol", "")))
            if code:
                price_map[code] = float(row.get("price", row.get("close", 100.0)))

        # 1. 查找持仓并卖出不在选券池中的标的
        session = SessionLocal()
        sells_to_do = []
        try:
            positions = session.query(Position).filter(Position.account_id == account_id).all()
            for p in positions:
                if p.symbol not in target_symbols:
                    p_price = price_map.get(p.symbol, p.avg_price)
                    sells_to_do.append({
                        "symbol": p.symbol,
                        "name": p.name,
                        "price": p_price,
                        "amount": p.amount,
                        "reason": f"【{strat.name}】轮动调出：移出精选标的池"
                    })
        finally:
            session.close()

        for s in sells_to_do:
            self.record_sell(account_id, s["symbol"], s["price"], s["amount"], reason=s["reason"])

        # 2. 重新统计可用资产并按策略配置买入新标的
        session = SessionLocal()
        buys_done = []
        try:
            acc = session.query(Account).filter(Account.id == account_id).first()
            current_positions = session.query(Position).filter(Position.account_id == account_id).all()
            cur_pos_map = {p.symbol: p for p in current_positions}

            total_assets = acc.available_cash
            for p in current_positions:
                total_assets += p.amount * price_map.get(p.symbol, p.avg_price)

            target_count = len(target_symbols)
            target_per_bond = (total_assets * 0.95) / max(target_count, 1)

            for rank, sym in enumerate(target_symbols, 1):
                if sym in cur_pos_map:
                    continue  # 已持有

                cur_p = price_map.get(sym, 100.0)
                bond_name = target_names.get(sym, sym)
                # 计算手(1手10张)
                target_amount = int((target_per_bond / cur_p) // 10 * 10)
                if target_amount < 10:
                    target_amount = 10

                needed_cash = target_amount * cur_p
                if acc.available_cash < needed_cash and acc.available_cash >= (10 * cur_p):
                    target_amount = int((acc.available_cash * 0.9 / cur_p) // 10 * 10)

                if target_amount >= 10 and acc.available_cash >= (target_amount * cur_p):
                    buy_reason = f"【{strat.name}】调仓买入：选券综合评分第{rank}名"
                    ok = self.record_buy(account_id, sym, bond_name, cur_p, target_amount, reason=buy_reason)
                    if ok:
                        buys_done.append({
                            "symbol": sym,
                            "name": bond_name,
                            "price": cur_p,
                            "amount": target_amount,
                            "reason": buy_reason
                        })
                        acc = session.query(Account).filter(Account.id == account_id).first()
        finally:
            session.close()

        # 3. 刷新估值
        self.update_daily_valuation(quotes_df)

        return {
            "success": True,
            "account_id": account_id,
            "strategy": strat.name,
            "rebalanced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sold_count": len(sells_to_do),
            "bought_count": len(buys_done),
            "sells": sells_to_do,
            "buys": buys_done
        }

    def get_account_nav_history(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取账户净值历史曲线、对比基准与量化核心KPI指标"""
        acc_dict = self.get_account(account_id)
        if not acc_dict:
            return None

        nav_history = acc_dict.get("nav_history", [])

        # 如果曲线点数少于等于 2 点，且是模拟盘，自动预演补齐近 60 天真实历史轨迹
        if len(nav_history) <= 2 and acc_dict.get("account_type") == "PAPER":
            try:
                self.seed_paper_account_history(account_id, lookback_days=60)
                acc_dict = self.get_account(account_id)
                nav_history = acc_dict.get("nav_history", [])
            except Exception as e:
                print(f"[WARN] 自动预演轨迹失败: {e}")

        import pandas as pd
        from core.metrics import QuantMetrics

        metrics = {
            "total_return": 0.0,
            "benchmark_return": 0.0,
            "excess_return": 0.0,
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "total_trades": len(acc_dict.get("history_trades", [])),
            "rebalance_count": len([t for t in acc_dict.get("history_trades", []) if t.get("action") == "BUY"]),
            "trading_days": len(nav_history)
        }

        if len(nav_history) >= 2:
            nav_series = pd.Series([item.get("nav", 1.0) for item in nav_history])
            perf = QuantMetrics.calculate_performance(nav_series)
            latest_point = nav_history[-1]

            p_ret = round((latest_point.get("nav", 1.0) - 1.0) * 100, 2)
            b_ret = round((latest_point.get("benchmark_nav", 1.0) - 1.0) * 100, 2)
            metrics["total_return"] = p_ret
            metrics["benchmark_return"] = b_ret
            metrics["excess_return"] = round(p_ret - b_ret, 2)
            metrics["annual_return"] = perf.get("cagr", 0.0)
            metrics["max_drawdown"] = perf.get("max_drawdown", 0.0)
            metrics["sharpe_ratio"] = perf.get("sharpe_ratio", 0.0)

            daily_changes = nav_series.pct_change().dropna()
            if len(daily_changes) > 0:
                win_days = (daily_changes > 0).sum()
                metrics["win_rate"] = round(float(win_days / len(daily_changes)) * 100, 1)

        return {
            "account": {
                "account_id": acc_dict["account_id"],
                "account_name": acc_dict["account_name"],
                "account_type": acc_dict["account_type"],
                "associated_strategy": acc_dict["associated_strategy"],
                "initial_capital": acc_dict["initial_capital"],
                "available_cash": acc_dict["available_cash"],
                "total_asset": acc_dict["total_asset"],
                "status": acc_dict["status"],
                "created_at": acc_dict["created_at"]
            },
            "curve_data": nav_history,
            "metrics": metrics,
            "positions": list(acc_dict.get("positions", {}).values()),
            "history_trades": acc_dict.get("history_trades", [])
        }

    def update_daily_valuation(self, quotes_df: pd.DataFrame) -> Dict[str, Any]:
        """每日收盘用真实市场价格在数据库事务中刷新所有账号的持仓市值与净值"""
        price_map = {}
        for _, row in quotes_df.iterrows():
            code = str(row.get("bond_code", row.get("symbol", "")))
            if code:
                price_map[code] = float(row.get("price", row.get("close", 100.0)))

        today_str = datetime.now().strftime("%Y-%m-%d")
        summary = {}

        session = SessionLocal()
        try:
            accounts = session.query(Account).all()
            for acc in accounts:
                market_value = 0.0
                for pos in acc.positions:
                    cur_price = price_map.get(pos.symbol, pos.avg_price)
                    pos.current_price = cur_price
                    pos.market_value = round(cur_price * pos.amount, 2)
                    pos.profit_rate = round((cur_price / pos.avg_price - 1.0) * 100, 2) if pos.avg_price > 0 else 0.0
                    pos.updated_at = datetime.now()
                    market_value += pos.market_value

                total_assets = round(acc.available_cash + market_value, 2)
                acc.total_asset = total_assets
                acc.updated_at = datetime.now()

                init_cap = acc.initial_capital
                nav = round(total_assets / init_cap, 4) if init_cap > 0 else 1.0

                # 更新净值时序记录
                nav_list = []
                if acc.nav_history_json:
                    try:
                        nav_list = json.loads(acc.nav_history_json)
                    except Exception:
                        nav_list = []

                bench_nav = 1.0
                if nav_list:
                    bench_nav = nav_list[-1].get("benchmark_nav", 1.0)

                point_data = {
                    "date": today_str,
                    "total_assets": total_assets,
                    "nav": nav,
                    "benchmark_nav": bench_nav,
                    "portfolio_return": round((nav - 1.0) * 100, 2),
                    "benchmark_return": round((bench_nav - 1.0) * 100, 2),
                    "excess_return": round((nav - bench_nav) * 100, 2)
                }

                if nav_list and nav_list[-1].get("date") == today_str:
                    nav_list[-1].update(point_data)
                else:
                    nav_list.append(point_data)

                acc.nav_history_json = json.dumps(nav_list, ensure_ascii=False)

                summary[acc.id] = {
                    "account_name": acc.name,
                    "total_assets": total_assets,
                    "cash": acc.available_cash,
                    "market_value": market_value,
                    "nav": nav,
                    "total_profit_pct": round((nav - 1.0) * 100, 2)
                }

            session.commit()
            return summary
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

ledger = TradingLedger()

