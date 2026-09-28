"""
可转债策略抽象基类 (Base Strategy)
为多策略并行对比提供统一的标准接口规范。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any
import pandas as pd

class BaseCBStrategy(ABC):
    """可转债策略基类"""

    def __init__(self, name: str, description: str = "", top_n: int = 15):
        self.name = name
        self.description = description
        self.top_n = top_n

    @abstractmethod
    def select_portfolio(self, current_date: str, quotes_df: pd.DataFrame) -> pd.DataFrame:
        """
        在给定的交易日，根据当日全市场行情切片选出目标持仓组合
        :param current_date: 当前日期 (YYYY-MM-DD)
        :param quotes_df: 当日全市场可转债行情 DataFrame
        :return: 包含目标持有转债及其建议权重的 DataFrame (必须包含 bond_code, weight)
        """
        pass

    def calculate_weights(self, selected_df: pd.DataFrame) -> pd.DataFrame:
        """默认等权分配权重"""
        df = selected_df.copy()
        if len(df) > 0:
            df["weight"] = 1.0 / len(df)
        else:
            df["weight"] = 0.0
        return df
