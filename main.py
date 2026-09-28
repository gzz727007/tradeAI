"""
A股可转债多智能体投研交易系统统一执行入口
使用说明:
  python main.py --live      # 运行今日实时 LangGraph 多智能体投研并生成组合报告
  python main.py --backtest  # 运行多策略历史对决回测并输出指标表格
  python main.py --ui        # 启动 Streamlit 可视化看板 (浏览器大屏)
"""

import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 修复 Windows 控制台 GBK 编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from graph.workflow import create_cb_workflow
from notification.notifier import Notifier
from core.backtest_engine import CBBacktestEngine
from strategies.classic_double_low import ClassicDoubleLowStrategy
from strategies.high_ytm import HighYTMStrategy
from strategies.small_cap_momentum import SmallCapMomentumStrategy

def run_live():
    """执行今日实时 LangGraph 投研流"""
    print("\n" + "="*60)
    print(f"🚀 [LangGraph 生产流] 启动今日可转债多智能体研判与组合生成 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("="*60)

    app = create_cb_workflow()
    initial_state = {
        "trade_date": "",
        "total_market_count": 0,
        "candidates": [],
        "credit_reviews": {},
        "equity_reviews": {},
        "clause_reviews": {},
        "final_portfolio": [],
        "vetoed_bonds": [],
        "daily_report_markdown": ""
    }
    
    result = app.invoke(initial_state)
    report_md = result["daily_report_markdown"]
    
    print("\n" + report_md + "\n")
    
    # 消息广播推送
    Notifier.notify_all(report_md)
    print("🎉 今日可转债多智能体投研工作流执行完成！")

def run_backtest():
    """执行多策略历史对决回测"""
    print("\n" + "="*60)
    print("🏆 [多策略竞技场] 启动历史多策略对决回测")
    print("="*60)
    
    strategies = [
        ClassicDoubleLowStrategy(top_n=15),
        HighYTMStrategy(top_n=15),
        SmallCapMomentumStrategy(top_n=15)
    ]
    engine = CBBacktestEngine(strategies=strategies, start_date="20230101")
    engine.run()

def run_ui():
    """启动 Streamlit 可视化看板"""
    print("🌐 正在启动 Streamlit 可视化看板大屏...")
    app_path = BASE_DIR / "ui" / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser(description="可转债多智能体投研与多策略对决平台")
    parser.add_argument("--live", action="store_true", help="运行今日实时 LangGraph 投研与调仓流程")
    parser.add_argument("--backtest", action="store_true", help="运行多策略历史对决回测")
    parser.add_argument("--ui", action="store_true", help="启动 Streamlit 可视化看板")
    
    args = parser.parse_args()
    
    if args.live:
        run_live()
    elif args.backtest:
        run_backtest()
    elif args.ui:
        run_ui()
    else:
        # 默认模式：打印帮助并执行一次实时研判
        print("未指定参数，默认执行今日实时投研研判流程 (输入 python main.py --help 查看更多模式)")
        run_live()

if __name__ == "__main__":
    main()
