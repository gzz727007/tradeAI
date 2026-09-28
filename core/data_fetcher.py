"""
可转债数据获取引擎 (Data Fetcher)
集成 AkShare 免费公开接口，提供实时行情、历史指数与正股基本面抓取，并配备本地缓存机制。
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

# 确保项目根目录在 sys.path 中
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pandas as pd
import akshare as ak

from config.config import settings

CACHE_DIR = settings.DATA_DIR
CACHE_DIR.mkdir(parents=True, exist_ok=True)

class CBDataFetcher:
    """可转债数据中心"""
    
    @staticmethod
    def get_realtime_quotes(use_cache: bool = True, max_cache_age_seconds: int = 1800) -> pd.DataFrame:
        """
        获取全市场可转债实时/最新交易日行情数据
        包括：代码、名称、现价、转股价、转股溢价率、纯债价值、剩余规模、评级等
        """
        cache_file = CACHE_DIR / "cb_realtime_cache.parquet"
        
        # 缓存检查 (默认30分钟内使用缓存)
        if use_cache and cache_file.exists():
            file_age = time.time() - cache_file.stat().st_mtime
            if file_age < max_cache_age_seconds:
                try:
                    df = pd.read_parquet(cache_file)
                    print(f"✅ [缓存命中] 读取本地可转债行情 ({len(df)}只), 缓存时间: {int(file_age)}秒前")
                    return df
                except Exception as e:
                    print(f"⚠️ 缓存读取失败，重新拉取网络数据: {e}")
        
        print("🌐 正在从 AkShare 拉取全市场可转债最新行情数据...")
        try:
            # 获取集思录/东方财富可转债比价表
            raw_df = ak.bond_cov_comparison()
        except Exception as e:
            print(f"⚠️ bond_cov_comparison 失败，尝试备用接口 bond_zh_cov: {e}")
            try:
                raw_df = ak.bond_zh_cov()
            except Exception as e2:
                raise RuntimeError(f"❌ 无法从数据源获取可转债行情: {e2}")

        # 标准化字段映射
        # 常见返回字段: 序号, 转债代码, 转债名称, 转债最新价, 转股溢价率, 正股代码, 正股名称, 正股最新价, 转股价, 纯债价值, 剩余规模, 债券评级
        df = pd.DataFrame()
        
        # 智能匹配字段名
        col_map = {
            "转债代码": "bond_code",
            "债券代码": "bond_code",
            "证券代码": "bond_code",
            "代码": "bond_code",
            "转债名称": "bond_name",
            "债券简称": "bond_name",
            "证券简称": "bond_name",
            "名称": "bond_name",
            "转债最新价": "price",
            "债现价": "price",
            "最新价": "price",
            "转股溢价率": "premium_rate",
            "溢价率": "premium_rate",
            "正股代码": "stock_code",
            "正股名称": "stock_name",
            "正股简称": "stock_name",
            "正股最新价": "stock_price",
            "正股价": "stock_price",
            "转股价": "convert_price",
            "纯债价值": "pure_debt_value",
            "剩余规模": "remaining_scale",
            "转债余额": "remaining_scale",
            "发行规模": "remaining_scale",
            "债券评级": "rating",
            "信用评级": "rating",
            "到期收益率": "ytm",
            "到期税前收益率": "ytm"
        }
        
        for ch_col, en_col in col_map.items():
            if ch_col in raw_df.columns and en_col not in df.columns:
                df[en_col] = raw_df[ch_col]
                
        # 确保关键数值列为 float
        numeric_cols = ["price", "premium_rate", "stock_price", "convert_price", "pure_debt_value", "remaining_scale", "ytm"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = 0.0

        # 如果没有到期收益率，默认为 0.0
        if "ytm" not in df.columns:
            df["ytm"] = 0.0
            
        if "rating" not in df.columns:
            df["rating"] = "AA"

        # 过滤无效停牌/退市或价格为空的转债
        df = df.dropna(subset=["price", "bond_code"])
        df = df[df["price"] > 0].copy()
        
        # 计算核心量化指标：双低值 (Double-Low)
        # 双低 = 价格 + 溢价率 * 100 * weight
        df["double_low"] = df["price"] + df["premium_rate"] * settings.DEFAULT_DOUBLE_LOW_WEIGHT
        
        # 保存本地持久化缓存
        try:
            df.to_parquet(cache_file)
            print(f"💾 成功缓存 {len(df)} 只可转债行情至: {cache_file.name}")
        except Exception as e:
            print(f"⚠️ 写入缓存失败: {e}")
            
        return df

    @staticmethod
    def get_index_history(symbol: str = "sh000832", start_date: str = "20210101", end_date: str = None) -> pd.DataFrame:
        """
        获取可转债基准指数历史日线行情 (默认: sh000832 中证转债指数)
        作为策略回测对决的标准基准 (Benchmark)
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
            
        cache_file = CACHE_DIR / f"index_{symbol}_{start_date}_{end_date}.parquet"
        if cache_file.exists():
            return pd.read_parquet(cache_file)
            
        print(f"🌐 正在拉取中证转债指数历史行情 ({symbol}, {start_date} ~ {end_date})...")
        try:
            df = ak.stock_zh_index_daily_tx(symbol=symbol)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            # 过滤时间
            mask = (df["date"] >= pd.to_datetime(start_date)) & (df["date"] <= pd.to_datetime(end_date))
            df = df[mask].reset_index(drop=True)
            df.to_parquet(cache_file)
            print(f"💾 成功缓存中证转债指数历史数据 ({len(df)} 交易日) 至: {cache_file.name}")
            return df
        except Exception as e:
            print(f"⚠️ 拉取中证转债指数失败: {e}")
            return pd.DataFrame()

if __name__ == "__main__":
    # 测试数据获取
    quotes = CBDataFetcher.get_realtime_quotes(use_cache=False)
    print("\n📊 可转债实时行情预览 (前 5 只双低最优标的):")
    top5 = quotes.sort_values("double_low").head(5)[["bond_code", "bond_name", "price", "premium_rate", "double_low", "remaining_scale", "rating"]]
    print(top5.to_string(index=False))
