"""
多策略并行回测引擎 (Backtest Engine)
支持双引擎架构：
1. 真实历史个券截面切片与撮合引擎 (Point-in-Time Cross-Sectional Backtest) - 100% 真实历史个券数据与调仓撮合驱动
2. 因子特征推演引擎 (Factor-based Simulation) - 快速毫秒级风格试算
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

from config.config import settings
from core.data_fetcher import CBDataFetcher
from core.data_lake.cb_lake import CBDataLake
from core.metrics import QuantMetrics
from strategies.base import BaseCBStrategy

class CBBacktestEngine:
    def __init__(
        self,
        strategies: List[BaseCBStrategy],
        benchmark_symbol: str = "sh000832",
        start_date: str = "20230101",
        end_date: str = None,
        initial_capital: float = 100000.0,
        rebalance_interval_days: int = 5,  # 默认每周调仓一次
        commission_rate: float = settings.COMMISSION_RATE,
        slippage_rate: float = settings.SLIPPAGE_RATE,
        mode: str = "auto"  # 'auto', 'real', 'fast'
    ):
        self.strategies = strategies
        self.benchmark_symbol = benchmark_symbol
        self.start_date = start_date.replace("-", "").replace("/", "")
        self.end_date = (end_date or datetime.now().strftime("%Y%m%d")).replace("-", "").replace("/", "")
        self.initial_capital = initial_capital
        self.rebalance_interval_days = max(1, rebalance_interval_days)
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.mode = mode

    def run(self) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]], pd.DataFrame]:
        """
        执行多策略并行回测
        :return: (nav_df: 净值走势表, metrics_summary: 各策略指标字典, drawdown_df: 回撤走势表)
        """
        # 1. 尝试使用真实个券数据湖进行真实截面回测
        if self.mode in ["auto", "real"]:
            res = self._run_point_in_time_backtest()
            if res is not None:
                return res
            print("⚠️ 真实个券历史数据不足，auto/real 模式降级执行因子特征模拟 (指标带 is_simulated=True 标记)")

        # 2. 备用或快速推演引擎
        return self._run_factor_simulation()

    def _run_point_in_time_backtest(self) -> Optional[Tuple[pd.DataFrame, Dict[str, Dict[str, Any]], pd.DataFrame]]:
        """
        100% 真实历史个券截面切片与投资组合模拟回测
        """
        cb_lake = CBDataLake()
        s_date = f"{self.start_date[:4]}-{self.start_date[4:6]}-{self.start_date[6:]}"
        e_date = f"{self.end_date[:4]}-{self.end_date[4:6]}-{self.end_date[6:]}"
        
        # 读取本地可转债历史日线全量表
        daily_df = cb_lake.load_daily(start_date=s_date, end_date=e_date)
        if daily_df.empty or daily_df["trade_date"].nunique() < 10:
            return None
            
        print(f"🔬 启动【真实历史个券截面回测】: 覆盖 {daily_df['trade_date'].nunique()} 个交易日, {daily_df['symbol'].nunique()} 只转债")
        
        # 补充基本信息
        basic_df = cb_lake.load_basic()
        name_map = dict(zip(basic_df["symbol"], basic_df["name"])) if not basic_df.empty else {}
        
        # 标准化字段映射
        if "price" not in daily_df.columns and "close" in daily_df.columns:
            daily_df["price"] = daily_df["close"]
        if "bond_code" not in daily_df.columns and "symbol" in daily_df.columns:
            daily_df["bond_code"] = daily_df["symbol"]
        if "bond_name" not in daily_df.columns:
            daily_df["bond_name"] = daily_df["bond_code"].map(name_map).fillna(daily_df["bond_code"])

        # 提取排序交易日历
        trade_dates = sorted(daily_df["trade_date"].unique().tolist())
        
        # 获取基准指数行情并对齐日期
        bench_df = CBDataFetcher.get_index_history(
            symbol=self.benchmark_symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        bench_map = {}
        if not bench_df.empty:
            bench_df["date_str"] = bench_df["date"].astype(str).str[:10]
            bench_map = dict(zip(bench_df["date_str"], bench_df["close"]))
            
        # 构造基准净值序列
        bench_nav = []
        first_bench = None
        for d in trade_dates:
            val = bench_map.get(d)
            if val is not None and first_bench is None:
                first_bench = val
            if first_bench and val:
                bench_nav.append(round(val / first_bench, 4))
            else:
                bench_nav.append(1.0 if not bench_nav else bench_nav[-1])
                
        nav_dict: Dict[str, List[float]] = {
            "中证转债基准": bench_nav
        }
        
        # 预先按交易日对 daily_df 进行索引分组，极大提升切片速度
        grouped_by_date = {d: group for d, group in daily_df.groupby("trade_date")}
        
        # 逐一运行各参战策略的真实撮合
        for strat in self.strategies:
            strat_mode = getattr(strat, "strategy_mode", "ROTATION")

            if strat_mode == "EVENT_PRICE":
                # =========================================================
                # 现代事件驱动与价格点回测分支 (Event-Driven Backtest)
                # =========================================================
                from strategies.context import StrategyContext
                context = StrategyContext(
                    initial_capital=self.initial_capital,
                    commission_rate=self.commission_rate,
                    slippage_rate=self.slippage_rate
                )
                strat.on_start(context)
                strat_nav_series = []

                for t_idx, current_date in enumerate(trade_dates):
                    day_quotes = grouped_by_date.get(current_date, pd.DataFrame())
                    if day_quotes.empty:
                        strat_nav_series.append(strat_nav_series[-1] if strat_nav_series else 1.0)
                        continue

                    price_map = dict(zip(day_quotes["symbol"], day_quotes["price"]))
                    context.current_date = current_date

                    # 驱动策略 on_bar (价格点随时买卖与追踪止盈)
                    strat.on_bar(context, day_quotes)

                    # 停牌/摘牌持仓巡检: 连续 3 日无行情按最后市价强制平仓 (强赎/退市离场)
                    context.force_liquidate_stale(price_map)

                    # 当日收盘盯市估值
                    end_total_assets = context.get_total_assets(price_map)
                    nav = end_total_assets / self.initial_capital
                    strat_nav_series.append(round(float(nav), 4))

                    strat.on_day_close(context)

                nav_dict[strat.name] = strat_nav_series
                continue

            # =========================================================
            # 经典截面轮动回测分支 (Periodic Rotation)
            # 撮合规则：T 日收盘生成选券信号，T+1 个交易日按当日行情撮合成交，
            # 规避"用当日收盘价选券又用同一价格成交"的前视偏差 (Look-ahead Bias)。
            # =========================================================
            cash = float(self.initial_capital)
            positions: Dict[str, Dict[str, Any]] = {}  # {symbol: {"amount": int, "avg_price": float}}
            strat_nav_series = []
            # 待执行的调仓信号: {"target_symbols": set, "weight_map": dict}
            pending_signal: Optional[Dict[str, Any]] = None

            for t_idx, current_date in enumerate(trade_dates):
                day_quotes = grouped_by_date.get(current_date, pd.DataFrame())
                if day_quotes.empty:
                    strat_nav_series.append(strat_nav_series[-1] if strat_nav_series else 1.0)
                    continue

                price_map = dict(zip(day_quotes["symbol"], day_quotes["price"]))

                # ---- 步骤 0: 停牌/摘牌持仓巡检 ----
                # 转债强赎或到期退市后行情终止：连续 3 个交易日无行情视为已摘牌离场，
                # 按最后已知市价强制平仓回流现金 (扣除交易成本)，避免持仓永久冻结导致净值失真。
                for sym in list(positions.keys()):
                    pos = positions[sym]
                    cur_price = price_map.get(sym)
                    if cur_price is not None:
                        pos["last_price"] = cur_price
                        pos["no_quote_days"] = 0
                    else:
                        pos["no_quote_days"] = pos.get("no_quote_days", 0) + 1
                        if pos["no_quote_days"] >= 3:
                            last = pos.get("last_price", pos["avg_price"])
                            sell_val = pos["amount"] * last
                            cost = sell_val * (self.commission_rate + self.slippage_rate)
                            cash += (sell_val - cost)
                            del positions[sym]

                # ---- 步骤 1: 撮合上一交易日收盘生成的调仓信号 (T+1 成交) ----
                if pending_signal is not None:
                    target_symbols = pending_signal["target_symbols"]
                    weight_map = pending_signal["weight_map"]

                    # 卖出不在目标池中的标的 (T+1 停牌无行情的顺延至下轮调仓再尝试)
                    for sym in list(positions.keys()):
                        if sym not in target_symbols:
                            cur_price = price_map.get(sym)
                            if cur_price is None:
                                continue
                            sell_val = positions[sym]["amount"] * cur_price
                            cost = sell_val * (self.commission_rate + self.slippage_rate)
                            cash += (sell_val - cost)
                            del positions[sym]

                    # 按权重买入新标的 (T+1 停牌的标的自动跳过)
                    current_market_val = sum(pos["amount"] * price_map.get(s, pos.get("last_price", pos["avg_price"])) for s, pos in positions.items())
                    total_assets = cash + current_market_val

                    if target_symbols:
                        for sym in target_symbols:
                            if sym not in positions:
                                target_w = weight_map.get(sym, 1.0 / len(target_symbols))
                                target_money = total_assets * target_w
                                cur_price = price_map.get(sym, 0.0)
                                if cur_price > 0:
                                    # 1手 = 10张
                                    target_amount = int(target_money / (cur_price * 10)) * 10
                                    if target_amount > 0:
                                        buy_val = target_amount * cur_price
                                        cost = buy_val * (self.commission_rate + self.slippage_rate)
                                        if cash >= (buy_val + cost):
                                            cash -= (buy_val + cost)
                                            positions[sym] = {
                                                "amount": target_amount,
                                                "avg_price": cur_price,
                                                "last_price": cur_price,
                                                "no_quote_days": 0
                                            }
                    pending_signal = None

                # ---- 步骤 2: 今日收盘生成新调仓信号 (顺延至下一交易日撮合) ----
                if t_idx % self.rebalance_interval_days == 0:
                    selected_df = strat.select_portfolio(current_date, day_quotes)
                    target_symbols = set(selected_df["bond_code"].tolist()) if not selected_df.empty else set()
                    if not selected_df.empty and target_symbols:
                        default_w = [1.0 / len(target_symbols)] * len(selected_df)
                        weight_map = dict(zip(selected_df["bond_code"], selected_df.get("weight", default_w)))
                    else:
                        weight_map = {}
                    pending_signal = {"target_symbols": target_symbols, "weight_map": weight_map}

                # ---- 步骤 3: 当日收盘盯市估值 (Mark-to-Market，停牌按最后市价) ----
                end_market_val = sum(pos["amount"] * price_map.get(s, pos.get("last_price", pos["avg_price"])) for s, pos in positions.items())
                end_total_assets = cash + end_market_val
                nav = end_total_assets / self.initial_capital
                strat_nav_series.append(round(float(nav), 4))

            nav_dict[strat.name] = strat_nav_series
            
        # 组装返回结果
        nav_df = pd.DataFrame(nav_dict, index=trade_dates)
        nav_df.index.name = "date"
        
        metrics_summary = {}
        for col in nav_df.columns:
            metrics_summary[col] = QuantMetrics.calculate_performance(nav_df[col])
            metrics_summary[col]["is_simulated"] = False  # 真实历史个券截面撮合结果

        drawdown_df = pd.DataFrame(index=trade_dates)
        for col in nav_df.columns:
            drawdown_df[col] = QuantMetrics.calculate_drawdown_series(nav_df[col])

        return nav_df, metrics_summary, drawdown_df

    def _run_factor_simulation(self) -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]], pd.DataFrame]:
        """
        因子特征推演引擎 (基于真实基准行情的快速模拟)
        ⚠️ 注意：本引擎的净值曲线由预设 alpha/beta/噪声参数合成，并非真实撮合结果，
        仅用于快速风格试算，所有指标均带 is_simulated=True 标记，前端必须显著提示。
        """
        print(f"⚡ 执行【因子特征推演回测】 ({self.start_date} ~ {self.end_date})...")

        bench_df = CBDataFetcher.get_index_history(
            symbol=self.benchmark_symbol,
            start_date=self.start_date,
            end_date=self.end_date
        )
        if bench_df.empty or len(bench_df) < 10:
            dates = pd.date_range(start=self.start_date, end=self.end_date, freq="B")
            bench_df = pd.DataFrame({"date": dates, "close": 100.0})

        dates = pd.to_datetime(bench_df["date"]).tolist()
        bench_base = bench_df["close"].iloc[0]
        bench_nav = (bench_df["close"] / bench_base).tolist()

        nav_dict: Dict[str, List[float]] = {
            "中证转债基准": bench_nav
        }
        for strat in self.strategies:
            nav_dict[strat.name] = [1.0]

        np.random.seed(42)
        benchmark_returns = bench_df["close"].pct_change().fillna(0).values

        strategy_profiles = {
            "经典双低轮动": {"beta": 0.85, "alpha_annual": 0.085, "vol_mult": 0.90, "cost_friction": 0.0003},
            "高YTM深度防御": {"beta": 0.45, "alpha_annual": 0.040, "vol_mult": 0.50, "cost_friction": 0.0001},
            "小盘高弹性进攻": {"beta": 1.35, "alpha_annual": 0.120, "vol_mult": 1.40, "cost_friction": 0.0005},
            "AI多智能体增强": {"beta": 0.90, "alpha_annual": 0.145, "vol_mult": 0.85, "cost_friction": 0.0003},
            "AI动态价格点协同策略": {"beta": 0.80, "alpha_annual": 0.168, "vol_mult": 0.75, "cost_friction": 0.00012}
        }

        num_days = len(dates)
        daily_dt = 1.0 / 244.0

        for strat in self.strategies:
            profile = strategy_profiles.get(strat.name, {"beta": 1.0, "alpha_annual": 0.05, "vol_mult": 1.0, "cost_friction": 0.0002})
            nav_series = [1.0]
            
            for t in range(1, num_days):
                bench_ret = benchmark_returns[t]
                daily_alpha = profile["alpha_annual"] * daily_dt
                idiosyncratic_noise = np.random.normal(0, 0.004 * profile["vol_mult"])
                friction = profile["cost_friction"] if (t % self.rebalance_interval_days == 0) else 0.0
                
                strat_daily_ret = (profile["beta"] * bench_ret) + daily_alpha + idiosyncratic_noise - friction
                
                if bench_ret < -0.015:
                    if "防御" in strat.name or "双低" in strat.name:
                        strat_daily_ret *= 0.65
                    elif "AI" in strat.name:
                        strat_daily_ret = max(strat_daily_ret, -0.008)
                
                new_nav = max(nav_series[-1] * (1.0 + strat_daily_ret), 0.01)
                nav_series.append(new_nav)
                
            nav_dict[strat.name] = nav_series

        nav_df = pd.DataFrame(nav_dict, index=dates)
        nav_df.index.name = "date"

        metrics_summary = {}
        for col in nav_df.columns:
            metrics_summary[col] = QuantMetrics.calculate_performance(nav_df[col])
            if col != "中证转债基准":
                # 基准列为真实指数行情，策略列为参数合成的模拟净值
                metrics_summary[col]["is_simulated"] = True
            else:
                metrics_summary[col]["is_simulated"] = False

        drawdown_df = pd.DataFrame(index=dates)
        for col in nav_df.columns:
            drawdown_df[col] = QuantMetrics.calculate_drawdown_series(nav_df[col])

        print("⚠️ [警告] 当前展示的为【因子特征推演】模拟净值 (非真实撮合结果)，指标仅供参考！")

        return nav_df, metrics_summary, drawdown_df
