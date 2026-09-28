"""
策略 2: 高 YTM 深度价值防御策略 (High YTM Defense)
以保本为第一要义，筛选到期收益率最高（或纯债贴水最深）的低价转债。
适合极度风险厌恶、追求类纯债底仓收益的防守场景。
"""

import pandas as pd
from strategies.base import BaseCBStrategy

class HighYTMStrategy(BaseCBStrategy):
    def __init__(self, top_n: int = 15, max_price: float = 115.0):
        super().__init__(
            name="高YTM深度防御",
            description="只选到期收益率高、价格低于115元的纯防守品种，享受稳定债息与极强底价保护。",
            top_n=top_n
        )
        self.max_price = max_price

    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        df = quotes_df.copy()
        
        # 1. 价格严格限制在 115 元以下
        filtered = df[df["price"] <= self.max_price].copy()
        if len(filtered) == 0:
            return pd.DataFrame(columns=["bond_code", "bond_name", "weight"])

        # 2. 按 YTM 到期收益率降序（或按价格升序）排列
        if "ytm" in filtered.columns and filtered["ytm"].max() > 0:
            ranked = filtered.sort_values("ytm", ascending=False).head(self.top_n)
        else:
            # 若无 YTM 数据，以纯债溢价率最低或现价最低作为代理
            ranked = filtered.sort_values("price", ascending=True).head(self.top_n)

        return self.calculate_weights(ranked)
