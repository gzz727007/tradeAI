"""
可配置通用可转债策略 (Configurable CB Strategy)
允许直接加载 strategy_manager 中的任意策略定义（参数、规则），
使其能够无缝参与历史对决回测与实盘模拟。
"""

import pandas as pd
from typing import Dict, Any
from strategies.base import BaseCBStrategy

class ConfigurableCBStrategy(BaseCBStrategy):
    def __init__(self, strat_dict: Dict[str, Any]):
        name = strat_dict.get("name", "未命名策略")
        desc = strat_dict.get("description", "")
        params = strat_dict.get("params", {})
        top_n = params.get("top_n", 15)
        
        super().__init__(name=name, description=desc, top_n=top_n)
        self.strat_id = strat_dict.get("id", "")
        self.category = strat_dict.get("category", "自定义")
        self.params = params

    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        df = quotes_df.copy()
        p = self.params
        
        min_p = p.get("min_price", 80.0)
        max_p = p.get("max_price", 150.0)
        max_s = p.get("max_scale", 20.0)
        max_prem = p.get("max_premium", 100.0)
        weight_dl = p.get("double_low_weight", 1.0)
        sort_by = p.get("sort_by", "double_low")
        sort_asc = p.get("sort_ascending", True)

        # 1. 基础价格与规模过滤
        mask = (
            (df["price"] >= min_p) &
            (df["price"] <= max_p) &
            (df["premium_rate"] <= max_prem)
        )
        if "remaining_scale" in df.columns:
            mask = mask & (df["remaining_scale"] <= max_s) & (df["remaining_scale"] > 0)

        # 剔除退市或 C 级违约转债
        if "bond_name" in df.columns:
            mask = mask & (~df["bond_name"].str.contains("退"))
        if "rating" in df.columns:
            mask = mask & (~df["rating"].isin(["C", "D", "CC", "CCC"]))

        filtered = df[mask].copy()
        if filtered.empty:
            filtered = df[(df["price"] >= 85) & (df["price"] <= 140)].copy()

        # 2. 动态计算双低值
        filtered["double_low"] = filtered["price"] + filtered["premium_rate"] * weight_dl

        # 3. 按照策略指定排序字段排序
        if sort_by not in filtered.columns:
            sort_by = "double_low"
            
        ranked = filtered.sort_values(sort_by, ascending=sort_asc).head(self.top_n)
        return self.calculate_weights(ranked)
