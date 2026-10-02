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
        self.revision_file = self.asset_dir / "revision.parquet"   # 下修事件日志
        self.redeem_file = self.asset_dir / "redeem.parquet"       # 强赎/到期事件日志
        self.mv_file = self.asset_dir / "stock_mv.parquet"         # 正股历史总市值
        self.mv_cache_dir = self.cache_dir / "stock_mv"            # 逐股市值断点缓存
        self.mv_cache_dir.mkdir(parents=True, exist_ok=True)

    # ==============================================================
    # 事件类数据: 下修日志 / 强赎日志 -> 回填 basic (到期日、最后交易日、下修标记)
    # ==============================================================
    def fetch_event_logs(self) -> Dict[str, pd.DataFrame]:
        """
        抓取集思录下修事件与强赎/到期事件日志:
        1. 落库 revision.parquet / redeem.parquet (事件明细, 供 AI 策略与智能体取用)
        2. 回填 basic.parquet: maturity_date / last_trading_date / redeem_status / revision_active
           (basic 原始接口缺到期日列, 历史版本未存上, 此处用强赎日志 + bond_zh_cov 双重回填)
        """
        result = {"revision": pd.DataFrame(), "redeem": pd.DataFrame()}
        basic = self.load_basic()
        if basic.empty:
            basic = self.fetch_and_update_basic()

        # ---- 1. 下修事件日志 (集思录"下修"页, 近期事件) ----
        try:
            rev = ak.bond_cb_adj_logs_jsl()
            if rev is not None and not rev.empty:
                # 接口只有转债名称, 通过 basic 映射代码
                name_map = dict(zip(basic["name"], basic["symbol"]))
                rev["symbol"] = rev["转债名称"].astype(str).str.strip().map(name_map).fillna("")
                rev = rev[rev["symbol"] != ""].copy()
                rev = rev.rename(columns={
                    "股东大会日": "shareholder_date",
                    "下修前转股价": "convert_price_before",
                    "下修后转股价": "convert_price_after",
                    "新转股价生效日期": "effective_date",
                    "下修底价": "revision_floor",
                })
                rev.to_parquet(self.revision_file, index=False)
                result["revision"] = rev
                print(f"✅ 下修事件日志: {len(rev)} 条已落库 revision.parquet")
        except Exception as e:
            print(f"⚠️ 下修日志抓取失败 (跳过): {type(e).__name__}: {str(e)[:100]}")

        # ---- 2. 强赎/到期事件日志 (含最后交易日, 是退市强平精度的关键) ----
        redeem = pd.DataFrame()
        try:
            raw = ak.bond_cb_redeem_jsl()
            if raw is not None and not raw.empty:
                redeem = raw.rename(columns={
                    "代码": "symbol", "名称": "name", "正股代码": "stock_code",
                    "规模": "issue_scale", "剩余规模": "remaining_scale",
                    "转股起始日": "convert_start_date", "最后交易日": "last_trading_date",
                    "到期日": "maturity_date", "转股价": "convert_price",
                    "强赎触发比": "redeem_trigger_ratio", "强赎触发价": "redeem_trigger_price",
                    "强赎状态": "redeem_status",
                })
                redeem["symbol"] = redeem["symbol"].astype(str).str.zfill(6)
                redeem.to_parquet(self.redeem_file, index=False)
                result["redeem"] = redeem
                print(f"✅ 强赎/到期事件日志: {len(redeem)} 条已落库 redeem.parquet")
        except Exception as e:
            print(f"⚠️ 强赎日志抓取失败 (跳过): {type(e).__name__}: {str(e)[:100]}")

        # ---- 3. 回填 basic.parquet ----
        basic = basic.set_index("symbol")
        # 3a. 到期日: 优先强赎日志, 其次重抓 bond_zh_cov, 最后按 6 年期限近似
        if not redeem.empty and "maturity_date" in redeem.columns:
            mat_map = redeem.dropna(subset=["maturity_date"]).drop_duplicates("symbol").set_index("symbol")["maturity_date"]
            mat_map.index = mat_map.index.astype(str).str.zfill(6)
            basic["maturity_date"] = basic.index.map(mat_map)
        need_refetch = basic["maturity_date"].isna() if "maturity_date" in basic.columns else pd.Series(True, index=basic.index)
        if need_refetch.any():
            try:
                raw = ak.bond_zh_cov()
                ch_col = next((c for c in ["到期时间", "到期日期", "到期日"] if c in raw.columns), None)
                if ch_col:
                    code_col = next((c for c in ["债券代码", "转债代码", "代码"] if c in raw.columns), None)
                    if code_col:
                        m = pd.DataFrame({
                            "symbol": raw[code_col].astype(str).str.zfill(6),
                            "maturity_date": pd.to_datetime(raw[ch_col], errors="coerce").dt.strftime("%Y-%m-%d"),
                        }).dropna().drop_duplicates("symbol").set_index("symbol")["maturity_date"]
                        basic["maturity_date"] = basic["maturity_date"].fillna(basic.index.map(m)) if "maturity_date" in basic.columns else basic.index.map(m)
            except Exception as e:
                print(f"⚠️ bond_zh_cov 到期日回填失败 (跳过): {str(e)[:100]}")
        if "maturity_date" not in basic.columns:
            basic["maturity_date"] = pd.NaT
        # 最后兜底: 按上市日 + 6 年近似 (绝大多数转债期限为 6 年), 保证 remaining_years 可计算
        still_na = basic["maturity_date"].isna()
        if still_na.any() and "list_date" in basic.columns:
            basic.loc[still_na, "maturity_date"] = (
                pd.to_datetime(basic.loc[still_na, "list_date"], errors="coerce")
                + pd.DateOffset(years=6)
            ).dt.strftime("%Y-%m-%d")
            print(f"ℹ️ {still_na.sum()} 只缺失到期日, 已按 上市日+6年 近似回填")

        # 3b. 最后交易日 / 强赎状态 (退市风险标记)
        if not redeem.empty:
            ltd = redeem.dropna(subset=["last_trading_date"]).drop_duplicates("symbol").set_index("symbol")["last_trading_date"]
            ltd.index = ltd.index.astype(str).str.zfill(6)
            basic["last_trading_date"] = basic.index.map(ltd)
            st = redeem.drop_duplicates("symbol").set_index("symbol")["redeem_status"]
            basic["redeem_status"] = basic.index.map(st)
        # 3c. 下修进行中标记
        if not result["revision"].empty:
            active = set(result["revision"]["symbol"])
            basic["revision_active"] = basic.index.isin(active)

        basic = basic.reset_index()
        # 日期列统一为字符串 %Y-%m-%d (redeem 日志给的是 Timestamp, 与 str 兜底混存会炸 pyarrow)
        for _col in ["maturity_date", "last_trading_date", "list_date"]:
            if _col in basic.columns:
                basic[_col] = pd.to_datetime(basic[_col], errors="coerce").dt.strftime("%Y-%m-%d")
        self.save_basic(basic)
        print(f"✅ basic.parquet 已回填事件字段, 当前列: {list(basic.columns)}")
        return result

    # ==============================================================
    # 正股历史总市值 (百度股市通逐日序列, 断点续传) — 优于实时快照代理
    # ==============================================================
    def fetch_stock_market_cap_history(self, max_workers: int = 4) -> pd.DataFrame:
        """
        逐股抓取正股历史总市值序列 (百度股市通, 单位亿元, 约 3 年窗口), 断点续传:
        - 已缓存股票直接跳过; 合并落库 stock_mv.parquet (stock_code, trade_date, stock_market_cap)
        - enrich_daily_panel 会将其按 (trade_date, stock_code) 合入日线面板, 供微盘/市值因子使用
        注: 东财全市场快照接口易被限流封 IP, 百度接口更稳; 且历史序列对回测更精确
        """
        basic = self.load_basic()
        if basic.empty or "stock_code" not in basic.columns:
            print("⚠️ basic 为空或无 stock_code, 跳过市值历史抓取")
            return pd.DataFrame()
        codes = sorted({str(c).zfill(6) for c in basic["stock_code"].dropna() if str(c).strip()})

        cached = {f.stem for f in self.mv_cache_dir.glob("*.parquet")}
        pending = [c for c in codes if c not in cached]
        print(f"🚀 [CB 数据湖] 正股市值历史抓取: 共 {len(codes)} 只正股, 缓存 {len(cached)}, 待抓 {len(pending)}")

        def _fetch_one(code: str) -> Optional[pd.DataFrame]:
            for attempt in range(3):
                try:
                    df = ak.stock_zh_valuation_baidu(symbol=code, indicator="总市值", period="全部")
                    if df is None or df.empty:
                        return None
                    out = pd.DataFrame({
                        "stock_code": code,
                        "trade_date": pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
                        "stock_market_cap": pd.to_numeric(df["value"], errors="coerce"),
                    }).dropna(subset=["stock_market_cap"])
                    if not out.empty:
                        out.to_parquet(self.mv_cache_dir / f"{code}.parquet", index=False)
                    return out
                except Exception:
                    if attempt == 2:
                        return None
                    time.sleep(1.5 * (attempt + 1))

        done = len(cached)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_one, c): c for c in pending}
            for future in concurrent.futures.as_completed(futures):
                done += 1
                if done % 100 == 0 or done == len(codes):
                    print(f"   ➔ [{done}/{len(codes)}] 正股市值抓取进度...")
                time.sleep(0.1)

        files = list(self.mv_cache_dir.glob("*.parquet"))
        if not files:
            print("⚠️ 未抓到任何市值数据")
            return pd.DataFrame()
        mv = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
        mv.to_parquet(self.mv_file, index=False)
        print(f"✅ 正股历史市值落库 stock_mv.parquet: {len(mv):,} 行 / {mv['stock_code'].nunique()} 只正股 "
              f"({mv['trade_date'].min()} ~ {mv['trade_date'].max()})")
        return mv

    # ==============================================================
    # 正股快照: 总市值 (备用通道, 东财限流时自动跳过)
    # ==============================================================
    def fetch_stock_snapshot(self) -> pd.DataFrame:
        """
        抓取全 A 股实时快照, 回填 basic.parquet: stock_market_cap (亿元) / stock_price
        注: 历史逐日市值需逐股全量财务序列 (500+ 次请求), v1 用当前快照做横截面代理已够用
        """
        basic = self.load_basic()
        if basic.empty or "stock_code" not in basic.columns:
            print("⚠️ basic 为空或无 stock_code, 跳过正股快照回填")
            return pd.DataFrame()
        try:
            spot = None
            for _attempt in range(2):  # 东财接口偶发拒连, 退避重试一次
                try:
                    spot = ak.stock_zh_a_spot_em()
                    break
                except Exception as _e:
                    if _attempt == 0:
                        print(f"ℹ️ 东财快照第 1 次失败 ({type(_e).__name__}), 5 秒后重试...")
                        time.sleep(5)
                    else:
                        raise
        except Exception as e:
            print(f"⚠️ 正股快照抓取失败 (市值字段暂缺, 可稍后重试): {type(e).__name__}: {str(e)[:100]}")
            return pd.DataFrame()
        cap_col = next((c for c in spot.columns if c in ("总市值", "总市值-最新")), None)
        price_col = next((c for c in spot.columns if c == "最新价"), None)
        if not cap_col:
            print(f"⚠️ 快照中未找到总市值列, 现有列: {list(spot.columns)[:15]}")
            return pd.DataFrame()
        m = spot.copy()
        m["stock_code"] = m["代码"].astype(str).str.zfill(6)
        m["stock_market_cap"] = pd.to_numeric(m[cap_col], errors="coerce") / 1e8  # 元 -> 亿元
        if price_col:
            m["stock_price"] = pd.to_numeric(m[price_col], errors="coerce")
        basic = basic.set_index("stock_code")
        cap_map = m.dropna(subset=["stock_market_cap"]).drop_duplicates("stock_code").set_index("stock_code")["stock_market_cap"]
        basic["stock_market_cap"] = basic.index.map(cap_map)
        if price_col:
            price_map = m.dropna(subset=["stock_price"]).drop_duplicates("stock_code").set_index("stock_code")["stock_price"]
            basic["stock_price"] = basic.index.map(price_map)
        basic = basic.reset_index()
        self.save_basic(basic)
        filled = basic["stock_market_cap"].notna().sum()
        print(f"✅ 正股市值已回填: {filled}/{len(basic)} 只 (单位: 亿元)")
        return basic

    # ==============================================================
    # 面板富化: 全部本地推导, 幂等可重跑, 无网络依赖
    # ==============================================================
    def enrich_daily_panel(self) -> pd.DataFrame:
        """
        为 daily.parquet 增补策略表达所需的关键衍生字段 (在 consolidate 后调用或独立重跑):
        - name / stock_code / maturity_date / issue_scale / convert_price / stock_market_cap  (basic 横向合并)
        - remaining_years     剩余年限 = (到期日 - 交易日)/365.25, 下修博弈与防守型策略核心字段
        - stock_close_implied 推算正股价 = 转股价值 × 转股价 / 100 (未下修过的券为精确值)
        - stock_mom_20        正股 20 日动量 (微盘反弹类策略核心字段; 含下修跳变的窗口存在近似误差)
        - cb_mom_20           转债自身 20 日动量 (精确)
        - revise_note: 每次重跑全量重算, 幂等
        """
        df = self.load_daily()
        if df.empty:
            print("⚠️ daily.parquet 为空, 无法富化")
            return df
        basic = self.load_basic()
        if basic.empty:
            print("⚠️ basic.parquet 为空, 无法富化")
            return df

        # 1. 合并 basic 静态字段
        join_cols = [c for c in ["symbol", "name", "stock_code", "maturity_date", "issue_scale", "convert_price"]
                     if c in basic.columns]
        df = df.drop(columns=[c for c in join_cols if c != "symbol" and c in df.columns])
        df = df.merge(basic[join_cols], on="symbol", how="left")

        # 1b. 正股历史总市值: 优先逐日序列 stock_mv.parquet (回测级精度), 回退 basic 当前快照
        df = df.drop(columns=["stock_market_cap"], errors="ignore")
        if self.mv_file.exists() and "stock_code" in df.columns:
            mv = pd.read_parquet(self.mv_file)
            df = df.merge(mv, on=["stock_code", "trade_date"], how="left")
            covered = df["stock_market_cap"].notna().mean()
            print(f"ℹ️ 正股历史市值逐日序列覆盖率: {covered:.1%} (百度接口约 3 年窗口, 更早日为 NaN)")
        elif "stock_market_cap" in basic.columns:
            df = df.merge(basic[["symbol", "stock_market_cap"]], on="symbol", how="left")

        # 2. 剩余年限
        mat = pd.to_datetime(df["maturity_date"], errors="coerce")
        td = pd.to_datetime(df["trade_date"], errors="coerce")
        df["remaining_years"] = ((mat - td).dt.days / 365.25).round(3)

        # 3. 推算正股价与动量 (按标的分组时序推导)
        df = df.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
        cp = pd.to_numeric(df["convert_price"], errors="coerce")
        cv = pd.to_numeric(df["convert_value"], errors="coerce")
        df["stock_close_implied"] = (cv * cp / 100.0).round(4)
        g = df.groupby("symbol", sort=False)
        df["stock_mom_20"] = g["stock_close_implied"].pct_change(20).round(5)
        df["cb_mom_20"] = g["close"].pct_change(20).round(5)

        self.save_daily(df)
        new_cols = ["remaining_years", "stock_close_implied", "stock_mom_20", "cb_mom_20", "stock_market_cap"]
        have = [c for c in new_cols if c in df.columns]
        print(f"✅ 日线面板富化完成: 新增 {have}, 总 {len(df):,} 行 / {df['symbol'].nunique()} 只")
        return df

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

    def consolidate_checkpoints(self) -> pd.DataFrame:
        """合并缓存大宽表后自动执行字段富化 (保持 daily.parquet 派生列始终最新)"""
        full_df = super().consolidate_checkpoints()
        if not full_df.empty:
            try:
                full_df = self.enrich_daily_panel()
            except Exception as e:
                print(f"⚠️ 面板富化失败 (不影响基础数据): {type(e).__name__}: {str(e)[:120]}")
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
