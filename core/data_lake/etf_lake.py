"""
ETF 基金数据湖实现类 (ETF Data Lake)
负责：
1. 抓取与维护全市场 ETF 基础资料库 (宽基、行业主题、跨境QDII、商品黄金等)
2. 拉取 ETF 历史日线量价 (OHLCV) 与折溢价率、IOPV 实时净值
3. 提供 ETF 动量轮动与网格回测截面切片
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd
import akshare as ak

from core.data_lake.base import BaseAssetDataLake

class ETFDataLake(BaseAssetDataLake):
    """ETF 基金专属数据湖"""
    
    def __init__(self, data_root: Optional[Path] = None):
        super().__init__(asset_type="etf", data_root=data_root)

    def fetch_and_update_basic(self) -> pd.DataFrame:
        """获取全市场 ETF 清单与跟踪指数"""
        print("🌐 正在从行情源拉取全市场 ETF 清单...")
        try:
            raw_df = ak.fund_etf_spot_em()
            # 常见字段: 代码, 名称, 最新价, 涨跌幅, 成交量, 成交额, 折价率
            df = pd.DataFrame()
            if "代码" in raw_df.columns:
                df["symbol"] = raw_df["代码"].astype(str).str.zfill(6)
            if "名称" in raw_df.columns:
                df["name"] = raw_df["名称"]
                
            df = df.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
            self.save_basic(df)
            print(f"✅ 成功登记全市场 {len(df)} 只 ETF 基础资料！")
            return df
        except Exception as e:
            print(f"❌ 获取 ETF 清单失败: {e}")
            return self.load_basic()

    def fetch_etf_history(self, symbol: str, start_date: str = "20200101") -> Optional[pd.DataFrame]:
        """
        拉取单只 ETF 历史行情
        """
        clean_symbol = str(symbol).strip().zfill(6)
        try:
            # 东方财富 ETF 历史日线
            raw_df = ak.fund_etf_hist_em(symbol=clean_symbol, period="daily", start_date=start_date, adjust="qfq")
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
            
            self.save_checkpoint(clean_symbol, df)
            return df
        except Exception as e:
            return None
