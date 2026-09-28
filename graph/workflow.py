"""
LangGraph 多智能体协同状态图 (StateGraph Workflow)
编排初筛 -> 并发分析 (信用/动量/条款) -> PM 仲裁与报告生成的全生命周期。
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from datetime import datetime
from langgraph.graph import StateGraph, START, END

from core.state import CBTradeState
from core.data_fetcher import CBDataFetcher
from agents.screener import ScreenerAgent
from agents.credit_analyst import CreditAnalystAgent
from agents.equity_analyst import EquityAnalystAgent
from agents.clause_analyst import ClauseAnalystAgent
from agents.portfolio_manager import PortfolioManagerAgent

# 初始化各 Agent 实例
screener_agent = ScreenerAgent()
credit_agent = CreditAnalystAgent()
equity_agent = EquityAnalystAgent()
clause_agent = ClauseAnalystAgent()
pm_agent = PortfolioManagerAgent()

# ========================
# 节点函数定义 (Node Functions)
# ========================

def screener_node(state: CBTradeState) -> dict:
    """1. 量化初筛节点"""
    print("🔍 [Node: Screener] 正在拉取全市场实时行情并执行量化初筛...")
    quotes = CBDataFetcher.get_realtime_quotes(use_cache=True)
    candidates = screener_agent.screen(quotes)
    return {
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
        "total_market_count": len(quotes),
        "candidates": candidates
    }

def credit_node(state: CBTradeState) -> dict:
    """2. 信用排雷节点 (Qwen)"""
    print(f"🛡️ [Node: Credit Risk] 正在对 {len(state['candidates'])} 只标的进行基本面与信用审查...")
    credit_reviews = credit_agent.batch_evaluate(state["candidates"])
    return {"credit_reviews": credit_reviews}

def equity_node(state: CBTradeState) -> dict:
    """3. 正股动量节点 (Gemini Flash)"""
    print(f"🚀 [Node: Equity Momentum] 正在分析 {len(state['candidates'])} 只标的正股技术形态与题材...")
    equity_reviews = equity_agent.batch_evaluate(state["candidates"])
    return {"equity_reviews": equity_reviews}

def clause_node(state: CBTradeState) -> dict:
    """4. 条款博弈节点 (Gemini Pro)"""
    print(f"♟️ [Node: Clause Game] 正在评估 {len(state['candidates'])} 只标的条款博弈潜力...")
    clause_reviews = clause_agent.batch_evaluate(state["candidates"])
    return {"clause_reviews": clause_reviews}

def pm_node(state: CBTradeState) -> dict:
    """5. 投资总监仲裁决策节点"""
    print("👔 [Node: Portfolio Manager] 正在汇总三方研判、执行信用一票否决与组合打分...")
    portfolio, vetoed, report = pm_agent.arbitrate_and_allocate(
        candidates=state["candidates"],
        credit_reviews=state["credit_reviews"],
        equity_reviews=state["equity_reviews"],
        clause_reviews=state["clause_reviews"]
    )
    return {
        "final_portfolio": portfolio,
        "vetoed_bonds": vetoed,
        "daily_report_markdown": report
    }

# ========================
# 构建 LangGraph 状态图
# ========================

def create_cb_workflow():
    workflow = StateGraph(CBTradeState)

    # 注册节点
    workflow.add_node("screener", screener_node)
    workflow.add_node("credit_risk", credit_node)
    workflow.add_node("equity_momentum", equity_node)
    workflow.add_node("clause_game", clause_node)
    workflow.add_node("pm_decision", pm_node)

    # 编排边 (Edge Flow)
    # START -> screener -> 并发分支 (credit, equity, clause) -> pm_decision -> END
    workflow.add_edge(START, "screener")
    
    workflow.add_edge("screener", "credit_risk")
    workflow.add_edge("screener", "equity_momentum")
    workflow.add_edge("screener", "clause_game")
    
    workflow.add_edge("credit_risk", "pm_decision")
    workflow.add_edge("equity_momentum", "pm_decision")
    workflow.add_edge("clause_game", "pm_decision")
    
    workflow.add_edge("pm_decision", END)

    app = workflow.compile()
    return app

if __name__ == "__main__":
    # 测试运行 LangGraph 完整工作流
    print("🚀 启动 LangGraph 可转债多智能体投研流...")
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
    final_output = app.invoke(initial_state)
    print("\n" + "="*50)
    print(final_output["daily_report_markdown"])
    print("="*50)
