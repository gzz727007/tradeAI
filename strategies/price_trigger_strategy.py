"""
AI 动态价格点协同策略 (AI Dynamic Price-Triggered Strategy)
全面融合三大核心模式：
1. 模式 1 (动态定价): 根据大模型条款博弈与正股阻力，为每个标的设定专属买入上限与第一目标止盈位。
2. 模式 2 (准入排雷): 严格遵守首席风控官一票否决白名单，杜绝违约退市毒药券。
3. 模式 3 (异动仲裁): 脉冲冲高跟踪与高点回撤追踪止盈，解决坐过山车回吐浮盈痛点。
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from strategies.base import BaseEventStrategy
from strategies.context import StrategyContext

class PriceTriggerCBStrategy(BaseEventStrategy):
    """
    AI 价格点与动态阶梯买卖策略
    """

    def __init__(
        self,
        name: str = "AI动态价格点协同策略",
        description: str = "结合大模型动态定价、风控一票否决白名单与脉冲回撤追踪止盈的随时买卖策略",
        default_entry_ceiling: float = 104.5,
        min_entry_floor: float = 80.0,
        default_target_price: float = 120.0,
        default_hard_stop: float = 128.0,
        default_trailing_drop: float = 0.025,
        max_holdings: int = 10,
        max_scale: float = 10.0,
        pulse_threshold: float = 0.08,
        stop_loss_pct: float = 0.08
    ):
        super().__init__(name=name, description=description, top_n=max_holdings)
        self.default_entry_ceiling = float(default_entry_ceiling)
        self.min_entry_floor = float(min_entry_floor)
        self.default_target_price = float(default_target_price)
        self.default_hard_stop = float(default_hard_stop)
        self.default_trailing_drop = float(default_trailing_drop)
        self.max_holdings = int(max_holdings)
        self.max_scale = float(max_scale)
        self.pulse_threshold = float(pulse_threshold)
        self.stop_loss_pct = float(stop_loss_pct)

    def on_start(self, context: StrategyContext):
        """策略启动钩子"""
        context.state["partial_sold"] = set()

    def on_event(self, context: StrategyContext, event: Dict[str, Any]):
        """
        接收大模型会诊结果事件，动态注入准入白名单与定制点位
        """
        evt_type = event.get("type", "")
        if evt_type in ["AGENT_REVIEW_COMPLETE", "UPDATE_DYNAMIC_TARGETS"]:
            data = event.get("data", {})
            targets = data.get("dynamic_targets", {})
            if targets:
                context.dynamic_targets.update(targets)
                # 白名单: 剔除 veto 为 True 的标的
                clean_whitelist = {code for code, t in targets.items() if not t.get("veto", False)}
                if clean_whitelist:
                    context.whitelist = clean_whitelist

    def on_bar(self, context: StrategyContext, market_data: pd.DataFrame):
        """
        核心价格点监控与撮合逻辑 (快思考)
        """
        if market_data.empty:
            return

        # 字段兼容标准化
        code_col = "bond_code" if "bond_code" in market_data.columns else ("symbol" if "symbol" in market_data.columns else "")
        price_col = "price" if "price" in market_data.columns else ("close" if "close" in market_data.columns else "")
        name_col = "bond_name" if "bond_name" in market_data.columns else ("name" if "name" in market_data.columns else code_col)

        if not code_col or not price_col:
            return

        price_map = dict(zip(market_data[code_col], market_data[price_col]))
        name_map = dict(zip(market_data[code_col], market_data[name_col]))
        high_map = dict(zip(market_data[code_col], market_data["high"])) if "high" in market_data.columns else price_map

        partial_sold_set: set = context.state.setdefault("partial_sold", set())

        # =================================================================
        # 第一道工序: 扫描现有持仓做价格点与脉冲判定 (随时卖出/止盈)
        # =================================================================
        for symbol in list(context.positions.keys()):
            pos = context.positions.get(symbol)
            if not pos:
                continue

            current_price = price_map.get(symbol)
            if not current_price or current_price <= 0:
                continue

            # 更新最高价追踪器
            high_price = high_map.get(symbol, current_price)
            pos.update_price_tracker(max(current_price, high_price))

            # 读取该券专属的大模型动态价格点
            dt = context.get_dynamic_target(symbol) or {}
            tp_price = float(dt.get("target_price", self.default_target_price))
            hard_stop = float(dt.get("hard_stop_price", self.default_hard_stop))
            trailing_drop = float(dt.get("trailing_stop_drop", self.default_trailing_drop))

            # -------------------------------------------------------------
            # 价格点触发 ①: 强赎与极端高位硬防线 (价格 >= hard_stop)
            # -------------------------------------------------------------
            if current_price >= hard_stop:
                context.sell(
                    symbol=symbol,
                    price=current_price,
                    pct=1.0,
                    reason=f"触达强赎硬防线 {current_price:.2f}元 (警戒线{hard_stop:.2f}元)，清仓止盈避险"
                )
                partial_sold_set.discard(symbol)
                continue

            # -------------------------------------------------------------
            # 模式 3: 脉冲冲高与动态追踪止盈 (Trailing Stop)
            # 若累计涨幅较大，但从最高点回撤超过 trailing_drop，及时锁定收益
            # -------------------------------------------------------------
            gain_from_cost = (pos.highest_price - pos.avg_price) / max(0.1, pos.avg_price)
            if gain_from_cost >= self.pulse_threshold and pos.highest_price > pos.avg_price:
                drop_from_high = (pos.highest_price - current_price) / pos.highest_price
                if drop_from_high >= trailing_drop:
                    context.sell(
                        symbol=symbol,
                        price=current_price,
                        pct=1.0,
                        reason=f"脉冲冲高至{pos.highest_price:.2f}元后回撤{drop_from_high*100:.1f}%(容忍度{trailing_drop*100:.1f}%)，追踪止盈落袋"
                    )
                    partial_sold_set.discard(symbol)
                    continue

            # -------------------------------------------------------------
            # 价格点触发 ②: 触达第一阶梯目标止盈位 (价格 >= tp_price)
            # -------------------------------------------------------------
            if current_price >= tp_price and symbol not in partial_sold_set:
                # 减持一半仓位锁利，剩余半仓继续博弈更高空间
                context.sell(
                    symbol=symbol,
                    price=current_price,
                    pct=0.5,
                    reason=f"触达第一目标止盈位 {current_price:.2f}元 (目标{tp_price:.2f}元)，分批减持50%仓位"
                )
                partial_sold_set.add(symbol)
                continue

            # -------------------------------------------------------------
            # 价格点触发 ③: 极端信用击穿与硬止损保护 (跌破成本超 stop_loss_pct 或 现价 < 88.0 元)
            # -------------------------------------------------------------
            if self.stop_loss_pct > 0:
                loss_from_cost = (pos.avg_price - current_price) / max(0.1, pos.avg_price)
                if loss_from_cost >= self.stop_loss_pct or current_price < 88.0:
                    context.sell(
                        symbol=symbol,
                        price=current_price,
                        pct=1.0,
                        reason=f"击穿硬风控止损线 (跌幅{loss_from_cost*100:.1f}%或跌破88元)，止损避险"
                    )
                    partial_sold_set.discard(symbol)
                    continue

        # =================================================================
        # 第二道工序: 扫描候选池做买入价格点判定 (随时买入)
        # =================================================================
        if len(context.positions) < self.max_holdings and context.cash > 3000:
            df_candidates = market_data.copy()

            # 过滤标准 A 股转债标的 (11/12 开头，且价格不低于筑底防线，排除退市三板或数据异常券)
            std_mask = (
                df_candidates[code_col].astype(str).str.startswith(('11', '12')) &
                (df_candidates[price_col] >= self.min_entry_floor)
            )
            df_candidates = df_candidates[std_mask]

            # 模式 2: 信用一票否决白名单门禁
            if context.whitelist:
                df_candidates = df_candidates[df_candidates[code_col].isin(context.whitelist)]

            # 排除已持仓
            held_symbols = set(context.positions.keys())
            df_candidates = df_candidates[~df_candidates[code_col].isin(held_symbols)]

            # 规模与基本规则过滤
            if "remaining_scale" in df_candidates.columns:
                df_candidates = df_candidates[df_candidates["remaining_scale"] <= self.max_scale]

            # 计算每只标的的建仓上限价格
            def get_ceiling(sym):
                dt = context.get_dynamic_target(sym) or {}
                return float(dt.get("entry_ceiling", self.default_entry_ceiling))

            ceilings = df_candidates[code_col].map(get_ceiling)
            # 筛选满足买入价格点的标的: 当前价格 <= 建仓上限
            valid_mask = df_candidates[price_col] <= ceilings
            df_buyable = df_candidates[valid_mask].copy()

            if not df_buyable.empty:
                # 按双低或性价比升序排列
                sort_col = "double_low" if "double_low" in df_buyable.columns else price_col
                df_buyable = df_buyable.sort_values(by=sort_col, ascending=True)

                total_assets = context.get_total_assets(price_map)
                target_money_per_pos = total_assets / self.max_holdings

                for _, row in df_buyable.iterrows():
                    sym = row[code_col]
                    p = float(row[price_col])
                    sym_name = str(row.get(name_col, sym))
                    ceiling_p = get_ceiling(sym)

                    order = context.buy(
                        symbol=sym,
                        price=p,
                        target_money=target_money_per_pos,
                        name=sym_name,
                        reason=f"触达安全建仓价格点 {p:.2f}元 (上限{ceiling_p:.2f}元)，大模型白名单通过"
                    )
                    if order:
                        partial_sold_set.discard(sym)

                    if len(context.positions) >= self.max_holdings or context.cash < 2000:
                        break

    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        """
        [截面兼容模式] 供传统回测或快速选券查阅使用
        """
        if quotes_df.empty:
            return pd.DataFrame(columns=["bond_code", "weight"])

        code_col = "bond_code" if "bond_code" in quotes_df.columns else "symbol"
        price_col = "price" if "price" in quotes_df.columns else "close"
        df = quotes_df[quotes_df[price_col] <= self.default_entry_ceiling].copy()
        if "double_low" in df.columns:
            df = df.sort_values(by="double_low", ascending=True)
        top = df.head(self.max_holdings).copy()
        if not top.empty:
            top["bond_code"] = top[code_col]
            top["weight"] = 1.0 / len(top)
            return top[["bond_code", "weight"]]
        return pd.DataFrame(columns=["bond_code", "weight"])
