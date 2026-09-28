"""
策略 1: 经典双低轮动策略 (Classic Dual-Low)
全市场最经典的转债量化规则基准，追求性价比与防守反击。
双低值 = 转债价格 + 转股溢价率 * 100 * 权重
"""

import pandas as pd
from strategies.base import BaseCBStrategy
from config.config import settings

class ClassicDoubleLowStrategy(BaseCBStrategy):
    def __init__(self, top_n: int = 15, max_price: float = 130.0, min_price: float = 95.0, max_scale: float = 15.0):
        super().__init__(
            name="经典双低轮动",
            description="筛选低价格+低溢价率标的，规避高价强赎与极大盘滞涨品种，等权持有。",
            top_n=top_n
        )
        self.max_price = max_price
        self.min_price = min_price
        self.max_scale = max_scale

    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        df = quotes_df.copy()
        
        # 1. 硬性区间过滤
        mask = (
            (df["price"] >= self.min_price) &
            (df["price"] <= self.max_price)
        )
        if "remaining_scale" in df.columns:
            mask = mask & (df["remaining_scale"] <= self.max_scale)
            
        filtered = df[mask].copy()
        if len(filtered) == 0:
            return pd.DataFrame(columns=["bond_code", "bond_name", "weight"])

        # 2. 按双低值升序排列
        if "double_low" not in filtered.columns:
            filtered["double_low"] = filtered["price"] + filtered["premium_rate"] * settings.DEFAULT_DOUBLE_LOW_WEIGHT
            
        ranked = filtered.sort_values("double_low", ascending=True).head(self.top_n)
        return self.calculate_weights(ranked)
