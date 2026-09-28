"""
基准指数数据湖实现类 (Benchmark Index Data Lake)
负责：
维护中证转债 (sh000832)、沪深300 (sh000300)、中证500 (sh000905)、中证1000 (sh000852)
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd
import akshare as ak

from core.data_lake.base import BaseAssetDataLake

class IndexDataLake(BaseAssetDataLake):
    """基准与宽基指数专属数据湖"""
    
    BENCHMARKS = [
        {"symbol": "sh000832", "name": "中证转债指数"},
        {"symbol": "sh000300", "name": "沪深300指数"},
        {"symbol": "sh000905", "name": "中证500指数"},
        {"symbol": "sh000852", "name": "中证1000指数"}
    ]

    def __init__(self, data_root: Optional[Path] = None):
        super().__init__(asset_type="index", data_root=data_root)

    def fetch_and_update_basic(self) -> pd.DataFrame:
        df = pd.DataFrame(self.BENCHMARKS)
        self.save_basic(df)
        return df

    def fetch_index_history(self, symbol: str = "sh000832", start_date: str = "20200101") -> Optional[pd.DataFrame]:
        clean_symbol = symbol.lower()
        try:
            raw_df = ak.stock_zh_index_daily_em(symbol=clean_symbol)
            if raw_df is None or raw_df.empty:
                return None
            df = pd.DataFrame()
            df["trade_date"] = raw_df["date"].astype(str).str[:10]
            df["symbol"] = clean_symbol
            df["close"] = pd.to_numeric(raw_df["close"], errors="coerce")
            df["open"] = pd.to_numeric(raw_df["open"], errors="coerce")
            df["high"] = pd.to_numeric(raw_df["high"], errors="coerce")
            df["low"] = pd.to_numeric(raw_df["low"], errors="coerce")
            df["volume"] = pd.to_numeric(raw_df["volume"], errors="coerce")
            
            self.save_checkpoint(clean_symbol, df)
            return df
        except Exception:
            return None
