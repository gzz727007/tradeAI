"""
交易日历工具 (Trading Calendar)
基于 akshare 沪深交易日历 (tool_trade_date_hist_sina)，内存缓存 6 小时。
委员会调度与手动触发均以此判断休市，避免假日空跑 LLM。
日历不可用时按 fail-safe 处理: 视为非交易日并打日志 (宁可不跑, 不空耗)。
"""

import time
from datetime import date as _d
from typing import Optional, Set

_CACHE = {"days": None, "fetched_at": 0.0}
_CACHE_TTL = 6 * 3600  # 6 小时刷新一次


def get_trade_dates() -> Optional[Set[str]]:
    """返回全部交易日集合 (YYYY-MM-DD 字符串)；拉取失败返回 None"""
    now = time.time()
    if _CACHE["days"] is not None and now - _CACHE["fetched_at"] < _CACHE_TTL:
        return _CACHE["days"]
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        # akshare 各版本列名不同: 新版 trade_date(字符串), 旧版 trading_date(date对象)
        col = "trade_date" if "trade_date" in df.columns else "trading_date"
        days: Set[str] = set()
        for v in df[col].tolist():
            if hasattr(v, "strftime"):
                days.add(v.strftime("%Y-%m-%d"))
            else:
                days.add(str(v)[:10])
        if days:
            _CACHE["days"] = days
            _CACHE["fetched_at"] = now
            return days
        return None
    except Exception as e:
        print(f"[WARN] 交易日历拉取失败: {e}")
        return None


def is_trading_day(day: Optional[str] = None) -> bool:
    """
    判断是否交易日 (默认今天)。fail-safe: 日历不可用 → 返回 False 并打日志。
    """
    if day is None:
        day = time.strftime("%Y-%m-%d")
    days = get_trade_dates()
    if days is None:
        print(f"[WARN] 交易日历不可用, 按非交易日处理: {day}")
        return False
    if day in days:
        return True
    # 周末一定不在日历中; 工作日不在日历中即法定假日
    try:
        wd = _d.fromisoformat(day).weekday()
        if wd < 5:
            print(f"[委员会] {day} 为法定休市日 (工作日但非交易日), 委员会不运行")
    except ValueError:
        pass
    return False
