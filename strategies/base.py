"""
可转债策略抽象基类与通用生命周期规范 (Base Strategy & Event-Driven Protocol)
支持双模设计：
1. 经典横截面轮动模式 (select_portfolio) - 兼容老策略
2. 现代事件驱动与价格点触发模式 (on_start, on_bar, on_event, on_day_close) - 支撑大模型协同与价格点交易
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
import pandas as pd
from strategies.context import StrategyContext, Order, PositionInfo

class BaseCBStrategy(ABC):
    """
    可转债及通用量化策略抽象基类
    """

    def __init__(self, name: str, description: str = "", top_n: int = 15):
        self.name = name
        self.description = description
        self.top_n = top_n
        self.strategy_mode: str = "ROTATION"  # "ROTATION" (定期轮动) 或 "EVENT_PRICE" (价格点事件驱动)

    def on_start(self, context: StrategyContext):
        """策略启动/初始化钩子 (可在此注入大模型初始白名单、目标价字典与参数)"""
        pass

    def on_bar(self, context: StrategyContext, market_data: pd.DataFrame):
        """
        行情/K线驱动核心钩子
        每当时间轴推进或盘中行情刷新时被调用。
        默认行为：若是轮动模式，则根据 select_portfolio 自动换算目标仓位。
        """
        if self.strategy_mode == "ROTATION":
            self._default_rotation_on_bar(context, market_data)

    def on_order_status(self, context: StrategyContext, order: Order):
        """报单成交/状态更新回调"""
        pass

    def on_event(self, context: StrategyContext, event: Dict[str, Any]):
        """
        接收外部异步事件 (如: 智能体会诊完成、突发公司公告、脉冲预警等)
        :param event: {"type": "AGENT_REVIEW_COMPLETE" | "PULSE_ALERT" | "ANNOUNCEMENT", "data": ...}
        """
        pass

    def on_day_close(self, context: StrategyContext):
        """交易日收盘盘点"""
        pass

    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        """
        [经典截面模式] 在给定的交易日，根据当日全市场行情切片选出目标持仓组合
        """
        return pd.DataFrame(columns=["bond_code", "weight"])

    def calculate_weights(self, selected_df: pd.DataFrame) -> pd.DataFrame:
        """默认等权分配权重"""
        df = selected_df.copy()
        if len(df) > 0:
            df["weight"] = 1.0 / len(df)
        else:
            df["weight"] = 0.0
        return df

    def _default_rotation_on_bar(self, context: StrategyContext, market_data: pd.DataFrame):
        """默认轮动撮合逻辑：将策略选出的组合调整为等权持仓"""
        if market_data.empty:
            return
            
        selected_df = self.select_portfolio(context.current_date, market_data)
        if selected_df.empty:
            return

        target_symbols = set(selected_df["bond_code"].tolist())
        price_map = dict(zip(market_data["bond_code" if "bond_code" in market_data.columns else "symbol"],
                             market_data["price" if "price" in market_data.columns else "close"]))

        # 1. 卖出不在目标池中的标的
        for sym in list(context.positions.keys()):
            if sym not in target_symbols:
                cur_p = price_map.get(sym, context.positions[sym].avg_price)
                context.sell(sym, price=cur_p, reason="轮动移出目标组合")

        # 2. 调仓买入新标的
        tot_asset = context.get_total_assets(price_map)
        target_per_asset = tot_asset / max(1, len(target_symbols))

        for sym in target_symbols:
            if sym not in context.positions:
                cur_p = price_map.get(sym, 0.0)
                if cur_p > 0:
                    context.buy(sym, price=cur_p, target_money=target_per_asset, reason="轮动纳入目标组合")


class BaseEventStrategy(BaseCBStrategy):
    """
    事件驱动型与价格点交易策略基类
    核心由 on_bar 内部的价格判定、阶梯止盈、网格逻辑驱动，摆脱僵化的定期换仓。
    """
    def __init__(self, name: str, description: str = "", top_n: int = 15):
        super().__init__(name=name, description=description, top_n=top_n)
        self.strategy_mode = "EVENT_PRICE"

    @abstractmethod
    def on_bar(self, context: StrategyContext, market_data: pd.DataFrame):
        """子类必须实现具体的价格点买卖逻辑"""
        pass
