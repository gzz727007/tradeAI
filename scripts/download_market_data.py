"""
多资产市场历史数据下载管理器 (Multi-Asset Market Data Downloader)
支持：
- A股可转债 (CB) 历史日线与双低衍生指标
- A股 ETF 基金 (ETF) 历史日线
- A股股票 (Stock) 历史日线
- 美股 (US_Stock) 标普/纳指与科技巨头
- 基准指数 (Index)

用法示例:
python scripts/download_market_data.py --asset cb --limit 50
python scripts/download_market_data.py --asset cb
python scripts/download_market_data.py --asset index
python scripts/download_market_data.py --asset all
"""

import os
import sys
import time
import argparse
from pathlib import Path

# 设置编码与根目录
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from core.data_lake import (
    CBDataLake,
    ETFDataLake,
    StockDataLake,
    USStockDataLake,
    IndexDataLake
)

def run_cb_download(limit: int = 0, workers: int = 5, force: bool = False):
    print("\n" + "=" * 60)
    print("📈 正在执行【A股可转债 (CB)】历史全量数据湖构建...")
    print("=" * 60)
    
    cb_lake = CBDataLake()
    
    # 1. 更新可转债基础清单
    basic_df = cb_lake.load_basic()
    if basic_df.empty or force:
        basic_df = cb_lake.fetch_and_update_basic()
        
    if basic_df.empty:
        print("❌ 无法获取可转债基础资料，请检查网络连接！")
        return
        
    symbols = basic_df["symbol"].tolist()
    if limit > 0:
        symbols = symbols[:limit]
        print(f"⚠️ [测试限额模式] 仅下载前 {limit} 只转债历史")
        
    t0 = time.time()
    daily_df = cb_lake.download_all_history(symbols=symbols, max_workers=workers, force_reload=force)
    cost = time.time() - t0
    
    if not daily_df.empty:
        dates_cnt = daily_df["trade_date"].nunique()
        syms_cnt = daily_df["symbol"].nunique()
        min_date = daily_df["trade_date"].min()
        max_date = daily_df["trade_date"].max()
        file_size_mb = cb_lake.daily_file.stat().st_size / (1024 * 1024)
        print("\n" + "-" * 60)
        print(f"🎉 可转债历史数据湖构建完成！耗时: {cost:.1f} 秒")
        print(f"   • 数据文件: {cb_lake.daily_file}")
        print(f"   • 记录总条数: {len(daily_df):,} 行")
        print(f"   • 覆盖标的数量: {syms_cnt} 只")
        print(f"   • 历史时间跨度: {min_date} ~ {max_date} (共 {dates_cnt} 个交易日)")
        print(f"   • 本地磁盘占用: {file_size_mb:.2f} MB")
        print("-" * 60)

def run_index_download():
    print("\n" + "=" * 60)
    print("📊 正在下载【基准指数 (Index)】历史行情...")
    print("=" * 60)
    idx_lake = IndexDataLake()
    idx_lake.fetch_and_update_basic()
    
    for bm in idx_lake.BENCHMARKS:
        sym = bm["symbol"]
        name = bm["name"]
        print(f"   ➔ 正在同步 {name} ({sym})...")
        df = idx_lake.fetch_index_history(sym)
        if df is not None:
            print(f"      ✅ 成功同步 {len(df)} 天日线")
            
    idx_lake.consolidate_checkpoints()
    print("🎉 基准指数历史数据湖已就绪！")

def run_etf_download():
    print("\n" + "=" * 60)
    print("📦 正在初始化【ETF 基金】数据湖基础清单...")
    print("=" * 60)
    etf_lake = ETFDataLake()
    etf_lake.fetch_and_update_basic()
    print("🎉 ETF 基础数据登记完毕！")

def run_stock_download():
    print("\n" + "=" * 60)
    print("💼 正在初始化【A股股票】数据湖基础清单...")
    print("=" * 60)
    stock_lake = StockDataLake()
    stock_lake.fetch_and_update_basic()
    print("🎉 A股股票基础数据登记完毕！")

def run_us_stock_download():
    print("\n" + "=" * 60)
    print("🗽 正在初始化【美股核心资产】数据湖清单与行情...")
    print("=" * 60)
    us_lake = USStockDataLake()
    us_lake.fetch_and_update_basic()
    for item in us_lake.CORE_SYMBOLS:
        sym = item["symbol"]
        print(f"   ➔ 正在拉取美股标的 {item['name']} ({sym})...")
        df = us_lake.fetch_us_history(sym)
        if df is not None:
            print(f"      ✅ 成功同步 {len(df)} 天日线")
    us_lake.consolidate_checkpoints()
    print("🎉 美股核心资产数据湖已就绪！")

def main():
    parser = argparse.ArgumentParser(description="多资产市场历史数据湖下载器 (tradeAI)")
    parser.add_argument(
        "--asset",
        choices=["cb", "etf", "stock", "us_stock", "index", "all"],
        default="cb",
        help="待下载的资产类别: cb (可转债), etf (ETF), stock (股票), us_stock (美股), index (基准指数), all (全部)"
    )
    parser.add_argument("--limit", type=int, default=0, help="限制下载标的数量 (0 为不限制/全量)")
    parser.add_argument("--workers", type=int, default=5, help="并发工作线程数 (默认 5)")
    parser.add_argument("--force", action="store_true", help="强制重新拉取已缓存的标的")
    args = parser.parse_args()

    print("================================================================")
    print("🚀 tradeAI 商业级多资产量化数据湖同步引擎")
    print(f"   • 当前任务目标: {args.asset.upper()}")
    print(f"   • 本地数据存储: {BASE_DIR / 'data'}")
    print("================================================================")

    if args.asset == "cb":
        run_cb_download(limit=args.limit, workers=args.workers, force=args.force)
    elif args.asset == "index":
        run_index_download()
    elif args.asset == "etf":
        run_etf_download()
    elif args.asset == "stock":
        run_stock_download()
    elif args.asset == "us_stock":
        run_us_stock_download()
    elif args.asset == "all":
        run_index_download()
        run_cb_download(limit=args.limit, workers=args.workers, force=args.force)
        run_etf_download()
        run_stock_download()
        run_us_stock_download()

if __name__ == "__main__":
    main()
