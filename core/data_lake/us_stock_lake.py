"""
美股与跨境资产数据湖实现类 (US Stock & Cross-Border Data Lake)
负责：
1. 抓取与维护美股标普500 (SPY)、纳指100 (QQQ)、美股科技七巨头 (Magnificent 7)
2. 支持使用 yfinance 或 AkShare 美股接口抓取历史复权日线
3. 记录 USD/CNY 汇率，提供多币种资产组合折算
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import pandas as pd
import akshare as ak

from core.data_lake.base import BaseAssetDataLake

class USStockDataLake(BaseAssetDataLake):
    """美股与全球宏观资产专属数据湖"""
    
    # 常用高流动性标的 (核心 ETF + 科技巨头)
    CORE_SYMBOLS = [
        {"symbol": "SPY", "name": "标普500 ETF"},
        {"symbol": "QQQ", "name": "纳斯达克100 ETF"},
        {"symbol": "SOXX", "name": "费城半导体 ETF"},
        {"symbol": "AAPL", "name": "苹果"},
        {"symbol": "NVDA", "name": "英伟达"},
        {"symbol": "MSFT", "name": "微软"},
        {"symbol": "GOOGL", "name": "谷歌"},
        {"symbol": "AMZN", "name": "亚马逊"},
        {"symbol": "TSLA", "name": "特斯拉"},
        {"symbol": "TLT", "name": "20年+美债 ETF"}
    ]

    def __init__(self, data_root: Optional[Path] = None):
        super().__init__(asset_type="us_stock", data_root=data_root)

    def fetch_and_update_basic(self) -> pd.DataFrame:
        """初始化美股核心标的清单"""
        df = pd.DataFrame(self.CORE_SYMBOLS)
        self.save_basic(df)
        print(f"✅ 成功登记美股核心资产清单 ({len(df)} 只)！")
        return df

    def fetch_us_history(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        拉取单只美股日线行情 (优先支持 ak.stock_us_hist 或 yfinance)
        """
        clean_symbol = str(symbol).strip().upper()
        try:
            # 尝试通过 AkShare 东方财富美股日线接口
            raw_df = ak.stock_us_hist(symbol=f"105.{clean_symbol}", adjust="qfq")
            if raw_df is None or raw_df.empty:
                # 尝试纳斯达克代码 106. 或 107.
                for prefix in ["106.", "107."]:
                    raw_df = ak.stock_us_hist(symbol=f"{prefix}{clean_symbol}", adjust="qfq")
                    if raw_df is not None and not raw_df.empty:
                        break
            
            if raw_df is not None and not raw_df.empty:
                df = pd.DataFrame()
                df["trade_date"] = raw_df["日期"].astype(str).str[:10]
                df["symbol"] = clean_symbol
                df["open"] = pd.to_numeric(raw_df["开盘"], errors="coerce")
                df["high"] = pd.to_numeric(raw_df["最高"], errors="coerce")
                df["low"] = pd.to_numeric(raw_df["最低"], errors="coerce")
                df["close"] = pd.to_numeric(raw_df["收盘"], errors="coerce")
                df["volume"] = pd.to_numeric(raw_df["成交量"], errors="coerce")
                
                self.save_checkpoint(clean_symbol, df)
                return df
        except Exception:
            pass
            
        # 备选：如果本地环境安装了 yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(clean_symbol)
            hist = ticker.history(period="5y")
            if not hist.empty:
                df = pd.DataFrame()
                df["trade_date"] = hist.index.strftime("%Y-%m-%d")
                df["symbol"] = clean_symbol
                df["open"] = hist["Open"].values
                df["high"] = hist["High"].values
                df["low"] = hist["Low"].values
                df["close"] = hist["Close"].values
                df["volume"] = hist["Volume"].values
                self.save_checkpoint(clean_symbol, df)
                return df
        except Exception:
            pass
            
        return None
