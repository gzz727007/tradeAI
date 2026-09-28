"""
多资产量化数据湖基类 (Multi-Asset Quant Data Lake Base)
支持统一的 Parquet 高性能列式读写、断点续传、元数据追踪与时间序列切片
面向资产: A股可转债(CB)、A股股票(Stock)、A股ETF、美股(US_Stock)、基准指数(Index)
"""

import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
import pandas as pd
import numpy as np

# 确保根目录在 sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

class BaseAssetDataLake:
    """多资产数据湖抽象基类"""
    
    def __init__(self, asset_type: str, data_root: Optional[Path] = None):
        """
        :param asset_type: 资产类别标识 ('cb', 'etf', 'stock', 'us_stock', 'index')
        :param data_root: 数据根目录 (默认 tradeAI/data)
        """
        self.asset_type = asset_type.lower()
        self.data_root = data_root or (BASE_DIR / "data")
        
        # 资产专属存储目录
        self.asset_dir = self.data_root / self.asset_type
        self.cache_dir = self.asset_dir / ".cache"
        self.daily_file = self.asset_dir / "daily.parquet"
        self.basic_file = self.asset_dir / "basic.parquet"
        
        # 确保目录存在
        self.asset_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def load_daily(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        columns: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        加载历史日线全量或切片大宽表 (极致性能，0.1秒级载入)
        :param start_date: 开始日期 (如 '2023-01-01' 或 '20230101')
        :param end_date: 结束日期
        :param symbols: 指定标的代码列表
        :param columns: 指定读取的列字段 (利用 Parquet 列裁剪进一步提升加载速度)
        """
        if not self.daily_file.exists():
            return pd.DataFrame()
            
        try:
            # 利用 pyarrow 进行列裁剪读取
            df = pd.read_parquet(self.daily_file, columns=columns)
            if df.empty:
                return df
                
            # 统一日期格式为 YYYY-MM-DD 字符串
            if "trade_date" in df.columns:
                df["trade_date"] = df["trade_date"].astype(str).str[:10]
                if start_date:
                    s_date = str(start_date).replace("/", "-").replace(".", "")
                    if len(s_date) == 8:
                        s_date = f"{s_date[:4]}-{s_date[4:6]}-{s_date[6:]}"
                    df = df[df["trade_date"] >= s_date]
                if end_date:
                    e_date = str(end_date).replace("/", "-").replace(".", "")
                    if len(e_date) == 8:
                        e_date = f"{e_date[:4]}-{e_date[4:6]}-{e_date[6:]}"
                    df = df[df["trade_date"] <= e_date]
                    
            if symbols and "symbol" in df.columns:
                sym_set = set(symbols)
                df = df[df["symbol"].isin(sym_set)]
                
            return df
        except Exception as e:
            print(f"❌ 读取 {self.asset_type} 日线大宽表失败: {e}")
            return pd.DataFrame()

    def save_daily(self, df: pd.DataFrame, compression: str = "snappy") -> bool:
        """
        保存合并后的历史日线大宽表至 Parquet
        """
        if df.empty:
            print(f"⚠️ 警告: 尝试写入空的 {self.asset_type} 数据表")
            return False
            
        try:
            # 建立标准排序复合索引并写入
            sort_cols = [c for c in ["trade_date", "symbol"] if c in df.columns]
            if sort_cols:
                df = df.sort_values(by=sort_cols).reset_index(drop=True)
                
            df.to_parquet(self.daily_file, compression=compression, index=False)
            file_size_mb = self.daily_file.stat().st_size / (1024 * 1024)
            print(f"💾 [{self.asset_type.upper()}] 成功写入日线大宽表: {self.daily_file.name} "
                  f"({len(df):,} 条记录, 占用硬盘: {file_size_mb:.2f} MB)")
            return True
        except Exception as e:
            print(f"❌ 写入 {self.asset_type} 日线大宽表失败: {e}")
            return False

    def load_basic(self) -> pd.DataFrame:
        """读取资产基础静态信息表"""
        if not self.basic_file.exists():
            return pd.DataFrame()
        try:
            return pd.read_parquet(self.basic_file)
        except Exception:
            return pd.DataFrame()

    def save_basic(self, df: pd.DataFrame) -> bool:
        """保存资产基础静态信息表"""
        if df.empty:
            return False
        try:
            df.to_parquet(self.basic_file, index=False)
            return True
        except Exception as e:
            print(f"❌ 写入基础信息表失败: {e}")
            return False

    # ==============================================================
    # 断点续传与单标的缓存机制
    # ==============================================================
    def save_checkpoint(self, symbol: str, df: pd.DataFrame) -> bool:
        """保存单只标的的下载快照，用于断点续传"""
        if df.empty:
            return False
        chk_file = self.cache_dir / f"{symbol}.parquet"
        try:
            df.to_parquet(chk_file, index=False)
            return True
        except Exception:
            return False

    def load_checkpoint(self, symbol: str) -> Optional[pd.DataFrame]:
        """读取单只标的的断点续传快照"""
        chk_file = self.cache_dir / f"{symbol}.parquet"
        if chk_file.exists():
            try:
                return pd.read_parquet(chk_file)
            except Exception:
                return None
        return None

    def list_cached_symbols(self) -> List[str]:
        """列出已成功下载并缓存的标的代码清单"""
        if not self.cache_dir.exists():
            return []
        return [f.stem for f in self.cache_dir.glob("*.parquet")]

    def consolidate_checkpoints(self) -> pd.DataFrame:
        """将缓存区所有单标的历史数据整合成最终的主大宽表"""
        cached_files = list(self.cache_dir.glob("*.parquet"))
        if not cached_files:
            return pd.DataFrame()
            
        dfs = []
        for f in cached_files:
            try:
                sub_df = pd.read_parquet(f)
                if not sub_df.empty:
                    dfs.append(sub_df)
            except Exception:
                pass
                
        if not dfs:
            return pd.DataFrame()
            
        full_df = pd.concat(dfs, ignore_index=True)
        self.save_daily(full_df)
        return full_df
