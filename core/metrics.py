"""
量化绩效评估工具模块 (Quant Metrics)
提供年化收益率、最大回撤、夏普比率、卡玛比率、月度热力图等标准评价指标计算。
"""

import numpy as np
import pandas as pd
from typing import Dict, Any

class QuantMetrics:
    """标准量化绩效统计指标"""

    @staticmethod
    def calculate_performance(nav_series: pd.Series, risk_free_rate: float = 0.02, periods_per_year: int = 244) -> Dict[str, Any]:
        """
        计算单条净值序列的全面绩效评估
        :param nav_series: 归一化净值序列 (起点为 1.0)
        :param risk_free_rate: 无风险年化收益率 (默认 2%)
        :param periods_per_year: A股一年平均交易日数 (默认 244 天)
        """
        if len(nav_series) < 2:
            return {
                "total_return": 0.0,
                "cagr": 0.0,
                "annual_volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "calmar_ratio": 0.0
            }

        # 1. 累计收益率
        total_return = (nav_series.iloc[-1] / nav_series.iloc[0]) - 1.0

        # 2. 年化复合增长率 (CAGR)
        total_days = len(nav_series)
        years = total_days / periods_per_year
        if years > 0 and nav_series.iloc[-1] > 0:
            cagr = (nav_series.iloc[-1] / nav_series.iloc[0]) ** (1.0 / years) - 1.0
        else:
            cagr = 0.0

        # 3. 日收益率序列
        daily_returns = nav_series.pct_change().dropna()

        # 4. 年化波动率
        annual_vol = daily_returns.std() * np.sqrt(periods_per_year)

        # 5. 最大回撤 (Max Drawdown)
        cummax = nav_series.cummax()
        drawdown = (nav_series - cummax) / cummax
        max_drawdown = abs(drawdown.min())

        # 6. 夏普比率 (Sharpe Ratio)
        excess_daily_rf = risk_free_rate / periods_per_year
        excess_returns = daily_returns - excess_daily_rf
        if daily_returns.std() > 1e-6:
            sharpe = (excess_returns.mean() / daily_returns.std()) * np.sqrt(periods_per_year)
        else:
            sharpe = 0.0

        # 7. 卡玛比率 (Calmar Ratio = CAGR / MaxDD)
        if max_drawdown > 1e-4:
            calmar = cagr / max_drawdown
        else:
            calmar = 0.0

        return {
            "total_return": round(float(total_return) * 100, 2),        # 百分比 %
            "cagr": round(float(cagr) * 100, 2),                        # 年化 %
            "annual_volatility": round(float(annual_vol) * 100, 2),     # 波动率 %
            "max_drawdown": round(float(max_drawdown) * 100, 2),        # 最大回撤 %
            "sharpe_ratio": round(float(sharpe), 2),                    # 夏普
            "calmar_ratio": round(float(calmar), 2),                    # 卡玛
            "trading_days": total_days
        }

    @staticmethod
    def calculate_drawdown_series(nav_series: pd.Series) -> pd.Series:
        """计算完整的回撤时间序列（用于 Underwater 动态水下图）"""
        cummax = nav_series.cummax()
        drawdown = (nav_series - cummax) / cummax
        return drawdown * 100 # 转为百分比
