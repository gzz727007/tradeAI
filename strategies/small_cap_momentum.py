"""
策略 3: 小盘高弹性爆发策略 (Small-Cap High Elasticity)
转债历史规律表明：剩余规模低于3.5亿的小盘转债，正股稍有异动极易被主力资金引爆脉冲。
追求进攻弹性与短期正股题材爆发溢价。
"""

import pandas as pd
from strategies.base import BaseCBStrategy

class SmallCapMomentumStrategy(BaseCBStrategy):
    def __init__(self, top_n: int = 15, max_scale: float = 3.5, max_price: float = 125.0, max_premium: float = 50.0):
        super().__init__(
            name="小盘高弹性进攻",
            description="锁定剩余规模<3.5亿、溢价率适中的小盘转债，捕捉正股风口爆发与脉冲机会。",
            top_n=top_n
        )
        self.max_scale = max_scale
        self.max_price = max_price
        self.max_premium = max_premium

    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        df = quotes_df.copy()
        
        # 1. 严格过滤规模与溢价率
        mask = (
            (df["price"] <= self.max_price) &
            (df["premium_rate"] <= self.max_premium)
        )
        if "remaining_scale" in df.columns:
            mask = mask & (df["remaining_scale"] <= self.max_scale) & (df["remaining_scale"] > 0)
            
        filtered = df[mask].copy()
        if len(filtered) == 0:
            return pd.DataFrame(columns=["bond_code", "bond_name", "weight"])

        # 2. 优先按溢价率升序排（溢价越低，股性越强，跟随正股爆发弹性越大）
        ranked = filtered.sort_values("premium_rate", ascending=True).head(self.top_n)
        return self.calculate_weights(ranked)
