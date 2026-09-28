"""
量化初筛智能体节点 (Screener Node)
基于多因子量化规则从全市场 500+ 只可转债中精准圈定 Top 25~30 候选标的池。
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd
from typing import List, Dict, Any

from config.config import settings
from core.state import BondCandidate

class ScreenerAgent:
    """可转债量化初筛 Agent"""

    def __init__(
        self,
        min_price: float = settings.MIN_PRICE,
        max_price: float = settings.MAX_PRICE,
        max_scale: float = settings.MAX_REMAINING_SCALE,
        max_premium: float = 75.0,
        double_low_weight: float = settings.DEFAULT_DOUBLE_LOW_WEIGHT,
        candidate_pool_size: int = 30,
        sort_by: str = "double_low",
        sort_ascending: bool = True
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.max_scale = max_scale
        self.max_premium = max_premium
        self.double_low_weight = double_low_weight
        self.candidate_pool_size = candidate_pool_size
        self.sort_by = sort_by
        self.sort_ascending = sort_ascending

    def screen(self, quotes_df: pd.DataFrame) -> List[BondCandidate]:
        """
        执行初筛逻辑
        :param quotes_df: 全市场可转债实时行情表
        :return: 结构化候选池列表
        """
        df = quotes_df.copy()
        
        # 1. 基础价格与估值过滤
        mask = (
            (df["price"] >= self.min_price) &
            (df["price"] <= self.max_price) &
            (df["premium_rate"] <= self.max_premium)
        )
        
        # 2. 规模过滤 (避开超大盘中行、光大等滞涨大象转债)
        if "remaining_scale" in df.columns:
            mask = mask & (df["remaining_scale"] <= self.max_scale) & (df["remaining_scale"] > 0)

        # 3. 基础卫生过滤 (直接剔除已退市债、名称带退或代码以40开头的品种、C级违约债)
        if "bond_name" in df.columns:
            mask = mask & (~df["bond_name"].str.contains("退"))
        if "bond_code" in df.columns:
            mask = mask & (~df["bond_code"].str.startswith("40"))
        if "rating" in df.columns:
            mask = mask & (~df["rating"].isin(["C", "D", "CC", "CCC"]))
            
        filtered = df[mask].copy()
        if filtered.empty:
            print("⚠️ 初筛结果为空，放宽规模与溢价限制")
            filtered = df[(df["price"] >= 90) & (df["price"] <= 135) & (~df["bond_name"].str.contains("退"))].copy()

        # 3. 重新计算加权双低值
        filtered["double_low"] = filtered["price"] + filtered["premium_rate"] * self.double_low_weight

        # 4. 根据指定的排序因子执行排序
        sort_col = "double_low"
        ascending = self.sort_ascending
        if self.sort_by == "premium_rate":
            sort_col = "premium_rate"
            ascending = True
        elif self.sort_by == "price":
            sort_col = "price"
            ascending = True
        elif self.sort_by == "ytm" and "ytm" in filtered.columns:
            sort_col = "ytm"
            ascending = False
        elif self.sort_by == "double_low":
            sort_col = "double_low"
            ascending = True

        top_candidates = filtered.sort_values(sort_col, ascending=ascending).head(self.candidate_pool_size)

        candidates: List[BondCandidate] = []
        for _, row in top_candidates.iterrows():
            item: BondCandidate = {
                "bond_code": str(row.get("bond_code", "")),
                "bond_name": str(row.get("bond_name", "")),
                "price": round(float(row.get("price", 0.0)), 2),
                "premium_rate": round(float(row.get("premium_rate", 0.0)), 2),
                "double_low": round(float(row.get("double_low", 0.0)), 2),
                "stock_code": str(row.get("stock_code", "")),
                "stock_name": str(row.get("stock_name", "")),
                "stock_price": round(float(row.get("stock_price", 0.0)), 2),
                "remaining_scale": round(float(row.get("remaining_scale", 0.0)), 2),
                "rating": str(row.get("rating", "AA")),
                "ytm": round(float(row.get("ytm", 0.0)), 2)
            }
            candidates.append(item)

        print(f"🎯 [Screener Agent] 从 {len(quotes_df)} 只全市场转债中筛选出 {len(candidates)} 只优质候选标的")
        return candidates
