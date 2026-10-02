"""
委员会实时行情快照模块 (Realtime Snapshot for Trading Committee)
提供: 强制新鲜快照 (带防抖限速) / 昨收锚定价 (数据湖日线) / 候选标的构造。
转债与正股实时价均来自 bond_zh_cov 快照 (含 正股最新价 列)。
"""

import time
from typing import Dict, List, Any, Optional

import pandas as pd

from core.data_fetcher import CBDataFetcher

# 模块级快照防抖: 避免 30 分钟刷新 + 手动触发在短时间内重复打网络接口
_SNAPSHOT_CACHE: Dict[str, Any] = {"df": None, "ts": 0.0}
_SNAPSHOT_MIN_INTERVAL = 60.0  # 秒

# 昨收映射按日缓存 (当日不变)
_PREV_CLOSE_CACHE: Dict[str, Any] = {"date": "", "map": {}}


def get_fresh_snapshot(force: bool = False) -> pd.DataFrame:
    """
    获取委员会用的实时行情快照 (转债现价 + 正股现价 + 溢价率 + 剩余规模 + 评级)。
    盘中绕过 data_fetcher 的 30 分钟缓存强制拉新；本地再做 60 秒防抖。
    """
    now_ts = time.time()
    if (
        not force
        and _SNAPSHOT_CACHE["df"] is not None
        and (now_ts - _SNAPSHOT_CACHE["ts"] < _SNAPSHOT_MIN_INTERVAL)
    ):
        return _SNAPSHOT_CACHE["df"]

    # use_cache=False: 强制走网络拉最新 (bond_zh_cov 含正股最新价)
    df = CBDataFetcher.get_realtime_quotes(use_cache=False)

    if df is not None and not df.empty:
        _SNAPSHOT_CACHE["df"] = df
        _SNAPSHOT_CACHE["ts"] = now_ts
    elif _SNAPSHOT_CACHE["df"] is not None:
        # 拉新失败时降级用上一份快照，绝不让委员会空转
        print("[WARN] 实时快照拉取失败，降级使用上一次缓存快照")
        return _SNAPSHOT_CACHE["df"]
    return df


def get_snapshot_by_codes(snapshot: pd.DataFrame, codes: List[str]) -> pd.DataFrame:
    """从快照中筛选指定代码的行 (保持快照原列)"""
    if snapshot is None or snapshot.empty or not codes:
        return pd.DataFrame()
    return snapshot[snapshot["bond_code"].astype(str).isin(codes)].copy()


def get_prev_close_map(codes: Optional[List[str]] = None) -> Dict[str, float]:
    """
    昨收锚定价映射: 取数据湖日线中最近一个"严格早于今天"的交易日收盘价。
    当日盘中不变，可按日缓存。无日线数据的标的返回空 (由调用方用现价兜底)。
    """
    from core.data_lake.cb_lake import CBDataLake

    today_str = time.strftime("%Y-%m-%d")
    if _PREV_CLOSE_CACHE["date"] == today_str and _PREV_CLOSE_CACHE["map"]:
        result = _PREV_CLOSE_CACHE["map"]
        if not codes:
            return dict(result)
        return {c: result[c] for c in codes if c in result}

    lake = CBDataLake()
    try:
        daily = lake.load_daily()
    except Exception as e:
        print(f"[WARN] 读取数据湖日线失败，昨收锚定不可用: {e}")
        return {}

    if daily.empty or "trade_date" not in daily.columns:
        return {}

    hist = daily[daily["trade_date"].astype(str) < today_str]
    if hist.empty:
        return {}
    last_day = hist["trade_date"].astype(str).max()
    last_rows = hist[hist["trade_date"].astype(str) == last_day]

    mapping: Dict[str, float] = {}
    for _, row in last_rows.iterrows():
        try:
            code = str(row.get("symbol", row.get("bond_code", "")))
            close = float(row.get("close", row.get("price", 0.0)))
            if code and close > 0:
                mapping[code] = close
        except Exception:
            continue

    _PREV_CLOSE_CACHE["date"] = today_str
    _PREV_CLOSE_CACHE["map"] = mapping
    if not codes:
        return dict(mapping)
    return {c: mapping[c] for c in codes if c in mapping}


def build_candidates(snapshot: pd.DataFrame, codes: List[str]) -> List[Dict[str, Any]]:
    """
    将快照行构造为 BondCandidate 结构 (供三分析师逐只审查)。
    缺失字段用中性默认值填充，保证 LLM Prompt 永远有值可插。
    """
    sub = get_snapshot_by_codes(snapshot, codes)
    candidates: List[Dict[str, Any]] = []
    if sub.empty:
        return candidates

    for _, row in sub.iterrows():
        candidates.append({
            "bond_code": str(row.get("bond_code", "")),
            "bond_name": str(row.get("bond_name", "")),
            "price": float(row.get("price", 100.0) or 100.0),
            "premium_rate": float(row.get("premium_rate", 0.0) or 0.0),
            "double_low": float(row.get("double_low", 0.0) or 0.0),
            "stock_code": str(row.get("stock_code", "")),
            "stock_name": str(row.get("stock_name", "")),
            "stock_price": float(row.get("stock_price", 0.0) or 0.0),
            "remaining_scale": float(row.get("remaining_scale", 0.0) or 0.0),
            "rating": str(row.get("rating", "AA") or "AA"),
            "ytm": float(row.get("ytm", 0.0) or 0.0)
        })
    return candidates


def get_current_price_map(snapshot: pd.DataFrame) -> Dict[str, float]:
    """快照 → {bond_code: 现价} 映射"""
    if snapshot is None or snapshot.empty:
        return {}
    result: Dict[str, float] = {}
    for _, row in snapshot.iterrows():
        try:
            code = str(row.get("bond_code", ""))
            price = float(row.get("price", 0.0) or 0.0)
            if code and price > 0:
                result[code] = price
        except Exception:
            continue
    return result
