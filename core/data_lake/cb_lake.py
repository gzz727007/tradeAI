"""
可转债数据湖实现类 (Convertible Bond Data Lake)
负责：
1. 抓取与维护全市场转债基础信息库 (basic.parquet)
2. 批量拉取全市场历史日线与衍生价值指标 (收盘价、转股价值、转股溢价率、纯债价值、纯债溢价率、双低值)
3. 断点续传与全局大宽表合并 (daily.parquet)
4. 提供调仓日截面瞬间切片 (Cross-sectional Slice)
"""

import time
import concurrent.futures
from typing import Optional, List, Dict, Any, Callable
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import akshare as ak

from core.data_lake.base import BaseAssetDataLake
from config.config import settings

class CBDataLake(BaseAssetDataLake):
    """可转债专属数据湖"""
    
    def __init__(self, data_root: Optional[Path] = None):
        super().__init__(asset_type="cb", data_root=data_root)

    def fetch_and_update_basic(self) -> pd.DataFrame:
        """
        获取全市场可转债基础资料清单（含存续与历史转债），并保存至 basic.parquet
        """
        print("🌐 正在从行情源拉取全市场可转债基础信息清单...")
        try:
            # 优先从 bond_zh_cov 获取全量清单
            raw_df = ak.bond_zh_cov()
        except Exception:
            try:
                raw_df = ak.bond_cov_comparison()
            except Exception as e:
                print(f"❌ 获取转债基础信息失败: {e}")
                return self.load_basic()

        # 映射规范字段
        col_map = {
            "债券代码": "symbol",
            "转债代码": "symbol",
            "代码": "symbol",
            "债券简称": "name",
            "转债名称": "name",
            "名称": "name",
            "正股代码": "stock_code",
            "正股简称": "stock_name",
            "正股名称": "stock_name",
            "上市时间": "list_date",
            "上市日期": "list_date",
            "到期时间": "maturity_date",
            "到期日期": "maturity_date",
            "发行规模": "issue_scale",
            "发行规模(亿)": "issue_scale",
            "转股价": "convert_price"
        }
        
        df = pd.DataFrame()
        for ch, en in col_map.items():
            if ch in raw_df.columns and en not in df.columns:
                df[en] = raw_df[ch]
                
        # 确保代码补齐 6 位字符串与日期标准化
        if "symbol" in df.columns:
            df["symbol"] = df["symbol"].astype(str).str.zfill(6)
            if "list_date" in df.columns:
                df["list_date"] = pd.to_datetime(df["list_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            if "maturity_date" in df.columns:
                df["maturity_date"] = pd.to_datetime(df["maturity_date"], errors="coerce").dt.strftime("%Y-%m-%d")
            df = df.drop_duplicates(subset=["symbol"]).reset_index(drop=True)
            self.save_basic(df)
            print(f"✅ 成功登记全市场 {len(df)} 只可转债基础信息！")
            return df
        return pd.DataFrame()

    def fetch_bond_history(self, symbol: str, retries: int = 3) -> Optional[pd.DataFrame]:
        """
        拉取单只可转债的全量历史日线与核心价值指标
        :param symbol: 6位可转债代码 (如 '113050')
        """
        clean_symbol = str(symbol).strip().zfill(6)
        
        for attempt in range(retries):
            try:
                # 获取东方财富可转债价值分析历史数据
                # 包含字段：日期、收盘价、纯债价值、转股价值、纯债溢价率、转股溢价率
                raw_df = ak.bond_zh_cov_value_analysis(symbol=clean_symbol)
                if raw_df is None or raw_df.empty:
                    return None
                    
                df = pd.DataFrame()
                
                # 智能识别列 (防止编码导致的汉字乱码)
                # 原接口列名通常对应：日期, 收盘价, 纯债价值, 转股价值, 纯债溢价率, 转股溢价率
                raw_cols = list(raw_df.columns)
                if len(raw_cols) >= 6:
                    df["trade_date"] = raw_df.iloc[:, 0].astype(str).str[:10]
                    df["close"] = pd.to_numeric(raw_df.iloc[:, 1], errors="coerce")
                    df["pure_debt_value"] = pd.to_numeric(raw_df.iloc[:, 2], errors="coerce")
                    df["convert_value"] = pd.to_numeric(raw_df.iloc[:, 3], errors="coerce")
                    df["pure_debt_premium_rate"] = pd.to_numeric(raw_df.iloc[:, 4], errors="coerce")
                    df["premium_rate"] = pd.to_numeric(raw_df.iloc[:, 5], errors="coerce")
                else:
                    return None

                df["symbol"] = clean_symbol
                
                # 剔除价格异常为 NaN 或小于等于 0 的非交易日
                df = df.dropna(subset=["close"]).copy()
                df = df[df["close"] > 0].copy()
                
                # 计算量化核心因子：双低值 (Double-Low = 收盘价 + 转股溢价率)
                # 溢价率若为空则填 0
                df["premium_rate"] = df["premium_rate"].fillna(0.0)
                df["pure_debt_value"] = df["pure_debt_value"].fillna(100.0)
                df["double_low"] = df["close"] + df["premium_rate"] * settings.DEFAULT_DOUBLE_LOW_WEIGHT
                
                # 保证各列格式统一
                df["close"] = df["close"].round(3)
                df["premium_rate"] = df["premium_rate"].round(3)
                df["double_low"] = df["double_low"].round(3)
                df["pure_debt_value"] = df["pure_debt_value"].round(3)
                
                # 保存断点缓存
                self.save_checkpoint(clean_symbol, df)
                return df
            except Exception as e:
                if attempt == retries - 1:
                    # 最后一次尝试失败
                    return None
                time.sleep(1.0)
        return None

    def download_all_history(
        self,
        symbols: Optional[List[str]] = None,
        max_workers: int = 5,
        force_reload: bool = False,
        progress_cb: Optional[Callable[[int, int, str], None]] = None
    ) -> pd.DataFrame:
        """
        批量并发下载全市场可转债历史日线面板，并自动合并为全局大宽表
        :param symbols: 可选指定待下载的转债代码列表；若为 None 则自动读取 basic.parquet 全量
        :param max_workers: 并发线程数 (默认 5，温和抓取，防止反爬封禁)
        :param force_reload: 是否强制重新下载 (False 时自动跳过已缓存的转债)
        :param progress_cb: 进度回调函数 callback(current, total, msg)
        """
        if not symbols:
            basic_df = self.load_basic()
            if basic_df.empty:
                basic_df = self.fetch_and_update_basic()
            if not basic_df.empty and "symbol" in basic_df.columns:
                # 按照上市日期升序排列，让具有成熟完整历史周期的标的优先下载
                if "list_date" in basic_df.columns:
                    sorted_basic = basic_df.sort_values(by="list_date", ascending=True)
                else:
                    sorted_basic = basic_df
                symbols = sorted_basic["symbol"].tolist()
            else:
                symbols = []

        if not symbols:
            print("⚠️ 未获取到可转债标的代码列表！")
            return pd.DataFrame()

        total = len(symbols)
        cached_set = set(self.list_cached_symbols()) if not force_reload else set()
        pending_symbols = [s for s in symbols if s not in cached_set]
        
        print(f"🚀 [CB 数据湖] 启动全量历史数据拉取任务:")
        print(f"   • 全市场标的总数: {total} 只")
        print(f"   • 本地缓存已存在: {len(cached_set)} 只 (跳过重复下载)")
        print(f"   • 本次待拉取数量: {len(pending_symbols)} 只")
        print(f"   • 并发工作线程数: {max_workers}")

        if not pending_symbols:
            print("🎉 所有转债历史已存在于缓存区，正在校验合并大宽表...")
            return self.consolidate_checkpoints()

        completed_count = len(cached_set)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sym = {executor.submit(self.fetch_bond_history, sym): sym for sym in pending_symbols}
            
            for future in concurrent.futures.as_completed(future_to_sym):
                sym = future_to_sym[future]
                completed_count += 1
                try:
                    res = future.result()
                    status_text = f"成功 ({len(res)} 天)" if res is not None else "无历史/未上市"
                except Exception as ex:
                    status_text = f"异常 ({ex})"
                
                msg = f"[{completed_count}/{total}] 转债 {sym} 下载完成: {status_text}"
                if completed_count % 10 == 0 or completed_count == total:
                    print(f"   ➔ {msg}")
                if progress_cb:
                    progress_cb(completed_count, total, msg)
                    
                # 适度礼貌延迟，保护公开数据源
                time.sleep(0.05)

        print("\n📦 全部下载线程完成，正在将所有分标的缓存编译合并为【全量历史日线大宽表】...")
        full_df = self.consolidate_checkpoints()
        return full_df

    def get_cross_section(self, trade_date: str) -> pd.DataFrame:
        """
        核心回测切片方法：瞬间获取某一交易日全市场的转债截面
        用于按双低值、溢价率、纯债价值等实时横向排序打分！
        """
        clean_date = str(trade_date).replace("/", "-").replace(".", "")
        if len(clean_date) == 8:
            clean_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}"
            
        daily_df = self.load_daily(start_date=clean_date, end_date=clean_date)
        if daily_df.empty:
            return pd.DataFrame()
            
        # 补充基础信息 (转债名称、正股代码)
        basic_df = self.load_basic()
        if not basic_df.empty and "symbol" in basic_df.columns:
            name_map = dict(zip(basic_df["symbol"], basic_df["name"]))
            stock_map = dict(zip(basic_df["symbol"], basic_df["stock_code"])) if "stock_code" in basic_df.columns else {}
            daily_df["name"] = daily_df["symbol"].map(name_map).fillna(daily_df["symbol"])
            daily_df["stock_code"] = daily_df["symbol"].map(stock_map).fillna("")
            
        return daily_df.sort_values(by="double_low").reset_index(drop=True)
