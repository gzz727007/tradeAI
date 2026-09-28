"""
A股股票数据湖实现类 (A-Share Stock Data Lake)
负责：
1. 抓取与维护全市场 A 股基础资料库 (申万行业、上市日期、退市状态)
2. 拉取前复权日线 (QFQ)、换手率、自由流通市值、PE/PB 估值
3. 提供股票多因子选股与板块动量截面切片
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd
import akshare as ak

from core.data_lake.base import BaseAssetDataLake

class StockDataLake(BaseAssetDataLake):
    """A股股票专属数据湖"""
    
    def __init__(self, data_root: Optional[Path] = None):
        super().__init__(asset_type="stock", data_root=data_root)

    def fetch_and_update_basic(self) -> pd.DataFrame:
        """获取全市场 A 股代码与名称清单"""
        print("🌐 正在从行情源拉取全市场 A 股清单...")
        try:
            raw_df = ak.stock_info_a_code_name()
            df = pd.DataFrame()
            if "code" in raw_df.columns:
                df["symbol"] = raw_df["code"].astype(str).str.zfill(6)
            if "name" in raw_df.columns:
                df["name"] = raw_df["name"]
                
            df = df.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
            self.save_basic(df)
            print(f"✅ 成功登记全市场 {len(df)} 只 A 股基础资料！")
            return df
        except Exception as e:
            print(f"❌ 获取股票清单失败: {e}")
            return self.load_basic()

    def fetch_stock_history(self, symbol: str, start_date: str = "20200101") -> Optional[pd.DataFrame]:
        """拉取单只股票前复权历史日线"""
        clean_symbol = str(symbol).strip().zfill(6)
        try:
            raw_df = ak.stock_zh_a_hist(symbol=clean_symbol, period="daily", start_date=start_date, adjust="qfq")
            if raw_df is None or raw_df.empty:
                return None
                
            df = pd.DataFrame()
            df["trade_date"] = raw_df["日期"].astype(str).str[:10]
            df["symbol"] = clean_symbol
            df["open"] = pd.to_numeric(raw_df["开盘"], errors="coerce")
            df["high"] = pd.to_numeric(raw_df["最高"], errors="coerce")
            df["low"] = pd.to_numeric(raw_df["最低"], errors="coerce")
            df["close"] = pd.to_numeric(raw_df["收盘"], errors="coerce")
            df["volume"] = pd.to_numeric(raw_df["成交量"], errors="coerce")
            df["amount"] = pd.to_numeric(raw_df["成交额"], errors="coerce")
            if "换手率" in raw_df.columns:
                df["turnover_rate"] = pd.to_numeric(raw_df["换手率"], errors="coerce")
                
            self.save_checkpoint(clean_symbol, df)
            return df
        except Exception as e:
            return None
