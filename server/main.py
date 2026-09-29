"""
A股可转债 AI 投研与多账号实盘终端 - FastAPI 高性能后端
提供纯净 RESTful API 与实时 WebSocket 智能体流式推送服务
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import pandas as pd
import numpy as np

from config.config import settings
from core.data_fetcher import CBDataFetcher
from core.strategy_manager import strategy_manager
from core.backtest_engine import CBBacktestEngine
from core.trading_ledger import ledger
from strategies.configurable_strategy import ConfigurableCBStrategy
from agents.screener import ScreenerAgent
from agents.credit_analyst import CreditAnalystAgent
from agents.equity_analyst import EquityAnalystAgent
from agents.clause_analyst import ClauseAnalystAgent
from agents.portfolio_manager import PortfolioManagerAgent
from core.agent_chamber_manager import agent_chamber_manager

import json
from db import init_db, SessionLocal, BacktestRecord

app = FastAPI(
    title="CB Quant AI API",
    description="A股可转债 AI 投研、多策略历史对决与多账号实盘系统接口",
    version="2.0.0"
)

@app.on_event("startup")
def on_startup():
    init_db()
    # 自动从数据库恢复最新一次 AI 投研会诊记录到缓存 (重启/升级代码不丢失)
    try:
        from db import SessionLocal, AgentReportRecord
        with SessionLocal() as session:
            latest_rpt = session.query(AgentReportRecord).order_by(AgentReportRecord.created_at.desc()).first()
            if latest_rpt:
                AGENT_CACHE["data"] = latest_rpt.to_dict()
                print(f"[INFO] 成功从数据库载入最新智能体会诊记录: {latest_rpt.strategy_name} ({latest_rpt.run_time})")
    except Exception as e:
        print("[WARN] 恢复会诊记录缓存提示:", e)

# 允许跨域访问 (开发环境与独立 SPA 前端)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 智能体会诊全局缓存 (避免每次刷新重新消耗 API)
AGENT_CACHE: Dict[str, Any] = {}

# ==============================================================
# Pydantic 交互模型
# ==============================================================

class StrategyParams(BaseModel):
    min_price: float = 95.0
    max_price: float = 125.0
    max_scale: float = 5.0
    max_premium: float = 50.0
    double_low_weight: float = 1.0
    top_n: int = 15
    sort_by: str = "double_low"
    sort_ascending: bool = True

class StrategyCreateRequest(BaseModel):
    name: str
    description: str
    category: str = "用户自定义"
    params: StrategyParams

class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    params: Optional[StrategyParams] = None

class StrategyCloneRequest(BaseModel):
    new_name: Optional[str] = None

class AIDiscoverRequest(BaseModel):
    user_idea: Optional[str] = ""

class BacktestRequest(BaseModel):
    strategy_ids: List[str]
    start_date: str = "20230101"
    end_date: Optional[str] = None
    rebalance_interval_days: int = 5
    mode: str = "auto"  # 'auto', 'real', 'fast'

class AccountCreateRequest(BaseModel):
    account_id: str
    account_name: str
    associated_strategy: str
    account_type: str = "REAL"  # REAL or PAPER
    initial_capital: float = 20000.0
    auto_seed: Optional[bool] = False

class TradeBuyRequest(BaseModel):
    bond_code: str
    bond_name: str
    price: float
    amount: int
    reason: Optional[str] = "跟随策略买入"

class TradeSellRequest(BaseModel):
    bond_code: str
    price: float
    amount: int
    reason: Optional[str] = "止盈或调仓换出"

# ==============================================================
# 1. 系统与行情数据 API (System & Market)
# ==============================================================

_STATUS_CACHE: Dict[str, Any] = {"data": None, "ts": 0.0}

@app.get("/api/system/status")
def get_system_status():
    import time
    now_ts = time.time()
    if _STATUS_CACHE["data"] and (now_ts - _STATUS_CACHE["ts"] < 30.0):
        return _STATUS_CACHE["data"]

    try:
        quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=True)
        ledger.update_daily_valuation(quotes_df, force=False)
    except Exception as e:
        print(f"⚠️ 系统状态接口获取实时行情异常 (已容错): {e}")
        quotes_df = pd.DataFrame()
    
    # 检查本地数据湖状态
    from core.data_lake import CBDataLake
    cb_lake = CBDataLake()
    cached_cnt = len(cb_lake.list_cached_symbols())
    daily_ready = cb_lake.daily_file.exists()
    
    res = {
        "status": "online",
        "market": "CN-A-Share-CB",
        "total_bonds": len(quotes_df),
        "benchmark": "中证转债 (000832)",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_lake": {
            "ready": daily_ready,
            "cached_symbols": cached_cnt,
            "total_symbols": 1059,
            "percentage": round(cached_cnt / 1059.0 * 100, 1)
        }
    }
    _STATUS_CACHE["data"] = res
    _STATUS_CACHE["ts"] = now_ts
    return res

@app.get("/api/market/quotes")
def get_market_quotes(
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    sort_by: str = "double_low",
    ascending: bool = True
):
    quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=True)
    df = quotes_df.copy()
    
    if search:
        s = search.strip().upper()
        df = df[df["bond_code"].str.contains(s) | df["bond_name"].str.contains(s)]
    
    if sort_by in df.columns:
        df = df.sort_values(by=sort_by, ascending=ascending)
        
    total = len(df)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    items = df.iloc[start_idx:end_idx].to_dict(orient="records")
    
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items
    }

# ==============================================================
# 2. 策略档案与 AI 挖掘 API (Strategies)
# ==============================================================

@app.get("/api/strategies")
def get_strategies():
    return strategy_manager.get_all_strategies()

@app.post("/api/strategies")
def create_strategy(req: StrategyCreateRequest):
    s_id = f"strat_custom_{int(datetime.now().timestamp())}"
    saved = strategy_manager.add_strategy(
        strat_id=s_id,
        name=req.name,
        category=req.category,
        description=req.description,
        params=req.params.model_dump()
    )
    return {"message": "策略创建成功", "strategy": saved}

@app.put("/api/strategies/{strategy_id}")
def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    existing = strategy_manager.get_strategy(strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="策略不存在")
    if existing.get("category") == "系统内置":
        raise HTTPException(status_code=400, detail="系统内置经典策略受保护不可直接修改，请点击【复制为新策略】创建副本后再进行微调！")
    
    params_dict = req.params.model_dump() if req.params is not None else None
    updated = strategy_manager.update_strategy(
        strat_id=strategy_id,
        name=req.name,
        description=req.description,
        params=params_dict
    )
    return {"message": "策略更新成功", "strategy": updated}

@app.post("/api/strategies/{strategy_id}/clone")
def clone_strategy(strategy_id: str, req: Optional[StrategyCloneRequest] = None):
    existing = strategy_manager.get_strategy(strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="策略不存在")
    
    new_id = f"strat_custom_{int(datetime.now().timestamp())}"
    new_name = req.new_name if (req and req.new_name) else f"{existing['name']} (副本)"
    
    saved = strategy_manager.add_strategy(
        strat_id=new_id,
        name=new_name,
        category="用户自定义",
        description=f"基于【{existing['name']}】复制微调。{existing.get('description', '')}",
        params=dict(existing.get("params", {}))
    )
    return {"message": "策略复制成功", "strategy": strategy_manager.get_strategy(new_id)}

@app.delete("/api/strategies/{strategy_id}")
def delete_strategy(strategy_id: str):
    success = strategy_manager.delete_strategy(strategy_id)
    if not success:
        raise HTTPException(status_code=400, detail="系统内置策略不可删除或策略不存在")
    return {"message": "策略已成功删除", "strategy_id": strategy_id}

@app.post("/api/strategies/ai-discover")
def ai_discover_strategy(req: AIDiscoverRequest):
    new_strat = strategy_manager.ai_discover_strategy(user_idea=req.user_idea)
    return {"message": "AI 成功挖掘新策略", "strategy": new_strat}

# ==============================================================
# 3. 策略历史对决回测 API (Backtest Arena)
# ==============================================================

@app.post("/api/backtest/run")
def run_backtest(req: BacktestRequest):
    all_strats = {s["id"]: s for s in strategy_manager.get_all_strategies()}
    battle_strats = []
    for sid in req.strategy_ids:
        if sid in all_strats:
            battle_strats.append(ConfigurableCBStrategy(all_strats[sid]))
            
    if not battle_strats:
        raise HTTPException(status_code=400, detail="未选择有效的参战策略")
        
    end_d = req.end_date if req.end_date else datetime.now().strftime("%Y%m%d")
    engine = CBBacktestEngine(
        strategies=battle_strats,
        start_date=req.start_date,
        end_date=end_d,
        rebalance_interval_days=req.rebalance_interval_days,
        mode=req.mode
    )
    
    nav_df, metrics_summary, drawdown_df = engine.run()
    
    # 格式化时间序列给 ECharts / 前端直接使用
    nav_df_reset = nav_df.reset_index()
    date_col = "trade_date" if "trade_date" in nav_df_reset.columns else nav_df_reset.columns[0]
    dates = [str(d)[:10] for d in nav_df_reset[date_col].tolist()]
    
    nav_series = {}
    for col in nav_df.columns:
        nav_series[col] = [round(float(v), 4) for v in nav_df[col].tolist()]
        
    dd_series = {}
    for col in drawdown_df.columns:
        dd_series[col] = [round(float(v), 2) for v in drawdown_df[col].tolist()]
        
    # 写入数据库事务归档 (保持回测历史完整可追溯)
    session = SessionLocal()
    try:
        bm_metrics = metrics_summary.get("中证转债 (基准)", {})
        for sid in req.strategy_ids:
            if sid in all_strats:
                strat_def = all_strats[sid]
                s_name = strat_def["name"]
                s_metrics = metrics_summary.get(s_name, {})
                bt_id = f"bt_{int(datetime.now().timestamp())}_{sid}"
                curve_payload = {
                    "dates": dates,
                    "nav": nav_series.get(s_name, []),
                    "drawdown": dd_series.get(s_name, []),
                    "benchmark_nav": nav_series.get("中证转债 (基准)", [])
                }
                record = BacktestRecord(
                    id=bt_id,
                    strategy_id=sid,
                    strategy_name=s_name,
                    start_date=req.start_date,
                    end_date=end_d,
                    rebalance_freq=req.rebalance_interval_days,
                    mode=req.mode,
                    total_return=float(s_metrics.get("total_return", 0.0)),
                    annual_return=float(s_metrics.get("annual_return", 0.0)),
                    max_drawdown=float(s_metrics.get("max_drawdown", 0.0)),
                    sharpe_ratio=float(s_metrics.get("sharpe_ratio", 0.0)),
                    win_rate=float(s_metrics.get("win_rate", 0.0)),
                    benchmark_return=float(bm_metrics.get("total_return", 0.0)),
                    metrics_json=json.dumps(s_metrics, ensure_ascii=False),
                    curve_data_json=json.dumps(curve_payload, ensure_ascii=False),
                    created_at=datetime.now()
                )
                session.add(record)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[WARN] 保存回测历史记录失败: {e}")
    finally:
        session.close()

    return {
        "dates": dates,
        "nav_series": nav_series,
        "drawdown_series": dd_series,
        "metrics_summary": metrics_summary
    }

@app.get("/api/backtests")
def get_backtest_records(strategy_id: Optional[str] = None, limit: int = 50):
    session = SessionLocal()
    try:
        q = session.query(BacktestRecord)
        if strategy_id:
            q = q.filter(BacktestRecord.strategy_id == strategy_id)
        records = q.order_by(BacktestRecord.created_at.desc()).limit(limit).all()
        return [r.to_dict(include_curve=False) for r in records]
    finally:
        session.close()

@app.get("/api/backtests/{backtest_id}")
def get_backtest_record_detail(backtest_id: str):
    session = SessionLocal()
    try:
        record = session.query(BacktestRecord).filter(BacktestRecord.id == backtest_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="回测记录不存在")
        return record.to_dict(include_curve=True)
    finally:
        session.close()

@app.delete("/api/backtests/{backtest_id}")
def delete_backtest_record(backtest_id: str):
    session = SessionLocal()
    try:
        record = session.query(BacktestRecord).filter(BacktestRecord.id == backtest_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="回测记录不存在")
        session.delete(record)
        session.commit()
        return {"message": "回测记录已成功删除", "id": backtest_id}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# ==============================================================
# 4. 多账户记账与实盘跟单 API (Accounts & Ledger)
# ==============================================================

@app.get("/api/accounts")
def get_accounts(account_type: Optional[str] = None):
    # 极速响应：优先使用本地缓存行情核算持仓，绝不因外部网络波动阻塞前端界面
    quotes_df = CBDataFetcher.get_cached_quotes_fast()
    if not quotes_df.empty:
        ledger.update_daily_valuation(quotes_df, force=False)
    return ledger.get_accounts(account_type=account_type)

@app.post("/api/accounts/refresh_valuation")
def refresh_accounts_valuation():
    """显式强制拉取最新全市场行情并重新核算所有账户持仓估值"""
    quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=False)
    summary = ledger.update_daily_valuation(quotes_df, force=True)
    return {"message": "最新行情与持仓估值已刷新", "summary": summary}

@app.post("/api/accounts")
def create_account(req: AccountCreateRequest):
    ok = ledger.create_account(
        account_id=req.account_id,
        name=req.account_name,
        strategy=req.associated_strategy,
        account_type=req.account_type,
        initial_capital=req.initial_capital
    )
    if not ok:
        raise HTTPException(status_code=400, detail="创建账户失败，账户ID可能已存在")

    if req.auto_seed and req.account_type.upper() == "PAPER":
        try:
            ledger.seed_paper_account_history(req.account_id, lookback_days=60)
        except Exception as e:
            print(f"[WARN] 自动预演失败: {e}")

    return {"message": "账户创建成功", "account": ledger.get_account(req.account_id)}

@app.post("/api/accounts/{account_id}/buy")
def account_buy(account_id: str, req: TradeBuyRequest):
    success = ledger.record_buy(
        account_id=account_id,
        bond_code=req.bond_code,
        bond_name=req.bond_name,
        price=req.price,
        amount=req.amount,
        reason=req.reason
    )
    if not success:
        raise HTTPException(status_code=400, detail="记账失败：可用现金不足或账户不存在")
    return {"message": "买入成交记录成功"}

@app.post("/api/accounts/{account_id}/sell")
def account_sell(account_id: str, req: TradeSellRequest):
    success = ledger.record_sell(
        account_id=account_id,
        bond_code=req.bond_code,
        price=req.price,
        amount=req.amount,
        reason=req.reason
    )
    if not success:
        raise HTTPException(status_code=400, detail="记账失败：卖出张数超出持仓或账户不存在")
    return {"message": "卖出成交记录成功"}

# --------------------------------------------------------------
# 模拟赛马竞技场专属生命周期控制与收益曲线 API (Paper Sandbox APIs)
# --------------------------------------------------------------

@app.get("/api/paper/accounts/{account_id}/nav_history")
def get_paper_account_nav_history(account_id: str):
    res = ledger.get_account_nav_history(account_id)
    if not res:
        raise HTTPException(status_code=404, detail="模拟账户不存在")
    return res

@app.post("/api/paper/accounts/{account_id}/start")
def start_paper_account(account_id: str):
    ok = ledger.set_account_status(account_id, "RUNNING")
    if not ok:
        raise HTTPException(status_code=404, detail="模拟账户不存在")
    return {"message": "模拟赛马已启动，进入前向跟踪状态", "status": "RUNNING"}

@app.post("/api/paper/accounts/{account_id}/pause")
def pause_paper_account(account_id: str):
    ok = ledger.set_account_status(account_id, "PAUSED")
    if not ok:
        raise HTTPException(status_code=404, detail="模拟账户不存在")
    return {"message": "模拟赛马已暂停", "status": "PAUSED"}

@app.post("/api/paper/accounts/{account_id}/end")
def end_paper_account(account_id: str):
    ok = ledger.set_account_status(account_id, "ENDED")
    if not ok:
        raise HTTPException(status_code=404, detail="模拟账户不存在")
    return {"message": "模拟赛马已完结归档", "status": "ENDED"}

@app.post("/api/paper/accounts/{account_id}/reset")
def reset_paper_account(account_id: str):
    ok = ledger.reset_account(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模拟账户不存在")
    return {"message": "模拟账户已重置（资金恢复初始，持仓已清空）", "status": "IDLE"}

@app.post("/api/paper/accounts/{account_id}/rebalance")
def rebalance_paper_account(account_id: str):
    res = ledger.trigger_paper_rebalance(account_id)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", res.get("error", "调仓执行失败")))
    return res

@app.post("/api/paper/accounts/{account_id}/seed_history")
def seed_paper_account_history_endpoint(account_id: str, lookback_days: int = 60):
    res = ledger.seed_paper_account_history(account_id, lookback_days=lookback_days)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message", "历史轨迹补齐失败"))
    return res

@app.delete("/api/paper/accounts/{account_id}")
def delete_paper_account(account_id: str):
    ok = ledger.delete_account(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模拟账户不存在")
    return {"message": "模拟账户已成功删除"}


# ==============================================================
# 5. LangGraph 多智能体协同会诊 & WebSocket 流式事件
# ==============================================================

def resolve_screening_params(strategy_id: Any = None):
    if hasattr(strategy_id, "default"):
        strategy_id = strategy_id.default
    if strategy_id and not isinstance(strategy_id, str):
        strategy_id = str(strategy_id)
    strat = None
    if strategy_id and strategy_id != "default":
        strat = strategy_manager.get_strategy(strategy_id)
    
    if strat and "params" in strat:
        p = strat["params"]
        min_price = float(p.get("min_price", 95.0))
        max_price = float(p.get("max_price", 130.0))
        max_scale = float(p.get("max_scale", 8.0))
        max_premium = float(p.get("max_premium", 75.0))
        double_low_weight = float(p.get("double_low_weight", 1.0))
        candidate_pool_size = max(15, int(p.get("top_n", 15)))
        sort_by = str(p.get("sort_by", "double_low"))
        sort_ascending = bool(p.get("sort_ascending", True))
        strat_name = strat.get("name", "自定义策略")
        strat_cat = strat.get("category", "策略库选送")
    else:
        min_price = 95.0
        max_price = 130.0
        max_scale = 8.0
        max_premium = 75.0
        double_low_weight = 1.0
        candidate_pool_size = 15
        sort_by = "double_low"
        sort_ascending = True
        strat_name = "默认经典双低初筛"
        strat_cat = "系统默认"

    screener = ScreenerAgent(
        min_price=min_price,
        max_price=max_price,
        max_scale=max_scale,
        max_premium=max_premium,
        double_low_weight=double_low_weight,
        candidate_pool_size=candidate_pool_size,
        sort_by=sort_by,
        sort_ascending=sort_ascending
    )
    return screener, strat_name, strat_cat, {
        "min_price": min_price,
        "max_price": max_price,
        "max_scale": max_scale,
        "max_premium": max_premium,
        "double_low_weight": double_low_weight,
        "top_n": candidate_pool_size,
        "sort_by": sort_by
    }

def build_models_used(credit_agent, equity_agent, clause_agent):
    return {
        "active_provider": llm_manager.get_config().get("active_provider", "gemini"),
        "credit": {
            "role": "首席风控官",
            "provider": getattr(credit_agent, "provider", ""),
            "provider_name": getattr(credit_agent, "provider_name", ""),
            "model": getattr(credit_agent, "model", ""),
            "is_llm": bool(credit_agent.client),
            "label": f"首席风控官 · {credit_agent.model or '硬规则引擎'}"
        },
        "equity": {
            "role": "正股动量分析师",
            "provider": getattr(equity_agent, "provider", ""),
            "provider_name": getattr(equity_agent, "provider_name", ""),
            "model": getattr(equity_agent, "model", ""),
            "is_llm": bool(equity_agent.client),
            "label": f"正股动量分析师 · {equity_agent.model or '弹性算法'}"
        },
        "clause": {
            "role": "条款博弈专家",
            "provider": getattr(clause_agent, "provider", ""),
            "provider_name": getattr(clause_agent, "provider_name", ""),
            "model": getattr(clause_agent, "model", ""),
            "is_llm": bool(clause_agent.client),
            "label": f"条款博弈专家 · {clause_agent.model or '博弈模型'}"
        },
        "pm": {
            "role": "投资总监 (PM)",
            "provider": "builtin",
            "provider_name": "量化仲裁引擎",
            "model": "Rule-Based Arbiter",
            "is_llm": False,
            "label": "投资总监 (PM) · 最终裁决"
        }
    }

@app.get("/api/chambers")
def get_chambers():
    """获取所有可用议事空间 (投研圆桌 / 对抗法庭)"""
    return agent_chamber_manager.get_all_chambers()

@app.get("/api/chambers/{chamber_id}")
def get_chamber_detail(chamber_id: str):
    """获取指定议事空间详情"""
    chamber = agent_chamber_manager.get_chamber_by_id(chamber_id)
    if not chamber:
        raise HTTPException(status_code=404, detail="议事空间不存在")
    return chamber

@app.get("/api/agents/talent_pool")
def get_agent_talent_pool():
    """获取投研人才库所有智能体列表"""
    return agent_chamber_manager.get_all_agents()

@app.post("/api/agents/custom")
def save_custom_agent(agent_data: Dict[str, Any] = Body(...)):
    """创建或更新自定义智能体"""
    return agent_chamber_manager.save_agent(agent_data)

@app.delete("/api/agents/custom/{agent_id}")
def delete_custom_agent(agent_id: str):
    """删除自定义智能体"""
    success = agent_chamber_manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="内置智能体席位不可删除或智能体不存在")
    return {"success": True, "message": "删除成功"}

@app.get("/api/agents/result")
def get_agents_result():
    if "data" in AGENT_CACHE:
        return AGENT_CACHE["data"]
    try:
        from db import SessionLocal, AgentReportRecord
        with SessionLocal() as session:
            latest = session.query(AgentReportRecord).order_by(AgentReportRecord.created_at.desc()).first()
            if latest and latest.result_json:
                data = json.loads(latest.result_json)
                AGENT_CACHE["data"] = data
                return data
    except Exception:
        pass
    return {"has_run": False}

@app.get("/api/agents/history")
def get_agent_reports_history(limit: int = 50):
    """获取所有历史投研会审报告的归档清单"""
    from db import SessionLocal, AgentReportRecord
    with SessionLocal() as session:
        records = session.query(AgentReportRecord).order_by(AgentReportRecord.created_at.desc()).limit(limit).all()
        items = []
        for r in records:
            chamber_name = "可转债投研圆桌"
            chamber_type = "ROUNDTABLE"
            if r.result_json:
                try:
                    rj = json.loads(r.result_json)
                    chamber_name = rj.get("chamber_name", chamber_name)
                    chamber_type = rj.get("chamber_type", chamber_type)
                except Exception:
                    pass
            items.append({
                "id": r.id,
                "strategy_id": r.strategy_id,
                "strategy_name": r.strategy_name or "默认初筛",
                "run_time": r.run_time,
                "candidates_count": r.candidates_count,
                "vetoed_count": r.vetoed_count,
                "portfolio_count": r.portfolio_count,
                "chamber_name": chamber_name,
                "chamber_type": chamber_type,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else r.run_time
            })
        return items

@app.get("/api/agents/history/{report_id}")
def get_agent_report_detail(report_id: str):
    """获取指定单期历史会审报告的完整结果与全量发言数据"""
    from db import SessionLocal, AgentReportRecord
    with SessionLocal() as session:
        r = session.query(AgentReportRecord).filter(AgentReportRecord.id == report_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="未找到该历史会审报告")
        if r.result_json:
            try:
                data = json.loads(r.result_json)
                data["is_archived"] = True
                return data
            except Exception:
                pass
        return {
            "has_run": True,
            "run_time": r.run_time,
            "strategy_id": r.strategy_id,
            "strategy_name": r.strategy_name,
            "report_md": r.report_md,
            "is_archived": True
        }

@app.delete("/api/agents/history/{report_id}")
def delete_agent_report(report_id: str):
    """删除指定的历史会审归档"""
    from db import SessionLocal, AgentReportRecord
    with SessionLocal() as session:
        r = session.query(AgentReportRecord).filter(AgentReportRecord.id == report_id).first()
        if r:
            session.delete(r)
            session.commit()
            return {"success": True, "message": "历史报告已删除"}
        raise HTTPException(status_code=404, detail="未找到该历史会审报告")

@app.post("/api/agents/run")
async def run_agents_pipeline(
    strategy_id: Optional[str] = Query(None),
    chamber_id: Optional[str] = Query("chamber_cb_roundtable")
):
    if hasattr(strategy_id, "default"):
        strategy_id = strategy_id.default
    if not isinstance(strategy_id, str):
        strategy_id = None

    quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=True)
    screener, strat_name, strat_cat, strat_params = resolve_screening_params(strategy_id)
    candidates = screener.screen(quotes_df)
    
    if hasattr(chamber_id, "default"):
        chamber_id = chamber_id.default
    if not chamber_id or not isinstance(chamber_id, str):
        chamber_id = "chamber_cb_roundtable"
        
    chamber_info = agent_chamber_manager.get_chamber_by_id(chamber_id)
    if not chamber_info:
        chamber_info = {
            "id": "chamber_cb_roundtable",
            "name": "🏛️ 可转债多智能体投研圆桌",
            "chamber_type": "ROUNDTABLE",
            "target_asset": "cb",
            "agent_ids": ["cb_credit", "cb_equity", "cb_clause"]
        }

    # 执行相应范式的会审 (圆桌 vs 法庭)
    if chamber_info.get("chamber_type") == "COURTROOM":
        chamber_result = agent_chamber_manager.run_courtroom_deliberation(candidates, chamber_info)
    else:
        chamber_result = agent_chamber_manager.run_roundtable_deliberation(candidates, chamber_info)

    credit_agent = CreditAnalystAgent()
    equity_agent = EquityAnalystAgent()
    clause_agent = ClauseAnalystAgent()
    models_used = build_models_used(credit_agent, equity_agent, clause_agent)
    
    res = {
        "has_run": True,
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "strategy_id": strategy_id,
        "strategy_name": strat_name,
        "strategy_category": strat_cat,
        "strategy_params": strat_params,
        "screened_count": len(candidates),
        "chamber_id": chamber_info.get("id"),
        "chamber_name": chamber_info.get("name"),
        "chamber_type": chamber_info.get("chamber_type"),
        "models_used": models_used,
        "candidates": candidates,
        "credit_reviews": chamber_result.get("credit_reviews", {}),
        "equity_reviews": chamber_result.get("equity_reviews", {}),
        "clause_reviews": chamber_result.get("clause_reviews", {}),
        "court_verdicts": chamber_result.get("court_verdicts", {}),
        "all_bond_speeches": chamber_result.get("all_bond_speeches", {}),
        "final_portfolio": chamber_result.get("final_portfolio", []),
        "vetoed_bonds": chamber_result.get("vetoed_bonds", []),
        "report_md": chamber_result.get("report_md", "")
    }
    AGENT_CACHE["data"] = res

    # 持久化本次投研会诊记录至关系型数据库 (永久归档保留)
    try:
        from db import SessionLocal, AgentReportRecord
        with SessionLocal() as session:
            rpt_id = f"rpt_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
            rpt = AgentReportRecord(
                id=rpt_id,
                strategy_id=strategy_id,
                strategy_name=strat_name,
                run_time=res["run_time"],
                candidates_count=len(candidates),
                vetoed_count=len(res["vetoed_bonds"]),
                portfolio_count=len(res["final_portfolio"]),
                report_md=res["report_md"],
                result_json=json.dumps(res, ensure_ascii=False)
            )
            session.add(rpt)
            session.commit()
    except Exception as e:
        print("[WARN] 持久化智能体会诊记录到数据库失败:", e)

    # 自动广播推送飞书/微信
    try:
        from notification.notifier import Notifier
        Notifier.notify_all(res["report_md"])
    except Exception as e:
        print("Notification push error:", e)

    return res

@app.post("/api/agents/notify")
def manual_notify():
    if "data" in AGENT_CACHE and "report_md" in AGENT_CACHE["data"]:
        try:
            from notification.notifier import Notifier
            Notifier.notify_all(AGENT_CACHE["data"]["report_md"])
            return {"message": "已成功广播推送至飞书/企业微信！"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=400, detail="暂无可用投研报告，请先运行智能体会诊")

@app.websocket("/ws/agents/stream")
async def websocket_agents_stream(websocket: WebSocket):
    await websocket.accept()
    strategy_id = websocket.query_params.get("strategy_id")
    chamber_id = websocket.query_params.get("chamber_id", "chamber_cb_roundtable")
    try:
        screener, strat_name, strat_cat, strat_params = resolve_screening_params(strategy_id)
        chamber_info = agent_chamber_manager.get_chamber_by_id(chamber_id or "chamber_cb_roundtable")
        if not chamber_info:
            chamber_info = {
                "id": "chamber_cb_roundtable",
                "name": "🏛️ 可转债多智能体投研圆桌",
                "chamber_type": "ROUNDTABLE",
                "target_asset": "cb",
                "agent_ids": ["cb_credit", "cb_equity", "cb_clause"]
            }

        await websocket.send_json({
            "step": "init",
            "message": f"正在接入议事空间【{chamber_info['name']}】· 挂载标的源：【{strat_name}】..."
        })
        await asyncio.sleep(0.4)
        
        quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=True)
        await websocket.send_json({
            "step": "screening",
            "message": f"🔍 [Node 1: 量化初筛 Agent] 挂载策略【{strat_name}】，执行价格({strat_params['min_price']}~{strat_params['max_price']}元)、规模(≤{strat_params['max_scale']}亿)、溢价率(≤{strat_params['max_premium']}%)精准圈定..."
        })
        
        candidates = screener.screen(quotes_df)
        await websocket.send_json({
            "step": "screening_done",
            "candidates_count": len(candidates),
            "message": f"✅ [Node 1 完成] 依据策略【{strat_name}】锁定 {len(candidates)} 只优质候选品种送审"
        })
        await asyncio.sleep(0.4)
        
        if chamber_info.get("chamber_type") == "COURTROOM":
            # 对抗法庭工作流
            await websocket.send_json({
                "step": "court_open",
                "message": "⚖️ [多空对抗裁决法庭 · 开庭] 书记员宣布开庭，进入多空控辩交叉质询审理程序..."
            })
            await asyncio.sleep(0.5)

            await websocket.send_json({
                "step": "prosecution",
                "message": "🔴 [控方第一回合] 激进空头公诉人出庭质询，呈递标的造假破绽与估值泡沫控诉证据..."
            })
            await asyncio.sleep(0.6)

            await websocket.send_json({
                "step": "defense",
                "message": "🟢 [辩方第二回合] 价值多头辩护人举证抗辩，呈递反转催化剂、核心护城河与非对称赔率辩词..."
            })
            await asyncio.sleep(0.6)

            await websocket.send_json({
                "step": "judge",
                "message": "⚖️ [合议庭终审裁决] 主审首席大法官兼听多空论证，敲槌宣读终审判决书与量刑仓位..."
            })
            chamber_result = agent_chamber_manager.run_courtroom_deliberation(candidates, chamber_info)
            await asyncio.sleep(0.4)
        else:
            # 圆桌投研工作流
            credit_agent = CreditAnalystAgent()
            credit_label = f"{credit_agent.provider_name} · {credit_agent.model}" if credit_agent.client else "内置硬风控"
            await websocket.send_json({
                "step": "credit",
                "message": f"🛡️ [Node 2: 首席风控官 · {credit_label}] 穿透审查大股东财务真实性与退市质押风险..."
            })
            await asyncio.sleep(0.4)
            
            equity_agent = EquityAnalystAgent()
            equity_label = f"{equity_agent.provider_name} · {equity_agent.model}" if equity_agent.client else "量化动量算法"
            await websocket.send_json({
                "step": "equity",
                "message": f"🚀 [Node 3: 正股动量 Agent · {equity_label}] 扫描正股题材风口与技术均线形态..."
            })
            await asyncio.sleep(0.4)
            
            clause_agent = ClauseAnalystAgent()
            clause_label = f"{clause_agent.provider_name} · {clause_agent.model}" if clause_agent.client else "博弈赔率模型"
            await websocket.send_json({
                "step": "clause",
                "message": f"♟️ [Node 4: 条款博弈 Agent · {clause_label}] 推演下修概率与强赎风险不对称赔率..."
            })
            await asyncio.sleep(0.4)
            
            await websocket.send_json({
                "step": "pm",
                "message": "👔 [Node 5: 投资总监 Agent · PM] 多空辩论仲裁汇总，生成最终组合配置与评级权重..."
            })
            chamber_result = agent_chamber_manager.run_roundtable_deliberation(candidates, chamber_info)
            await asyncio.sleep(0.4)

        credit_agent = CreditAnalystAgent()
        equity_agent = EquityAnalystAgent()
        clause_agent = ClauseAnalystAgent()
        models_used = build_models_used(credit_agent, equity_agent, clause_agent)

        res = {
            "has_run": True,
            "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy_id": strategy_id,
            "strategy_name": strat_name,
            "strategy_category": strat_cat,
            "strategy_params": strat_params,
            "screened_count": len(candidates),
            "chamber_id": chamber_info.get("id"),
            "chamber_name": chamber_info.get("name"),
            "chamber_type": chamber_info.get("chamber_type"),
            "models_used": models_used,
            "candidates": candidates,
            "credit_reviews": chamber_result.get("credit_reviews", {}),
            "equity_reviews": chamber_result.get("equity_reviews", {}),
            "clause_reviews": chamber_result.get("clause_reviews", {}),
            "court_verdicts": chamber_result.get("court_verdicts", {}),
            "all_bond_speeches": chamber_result.get("all_bond_speeches", {}),
            "final_portfolio": chamber_result.get("final_portfolio", []),
            "vetoed_bonds": chamber_result.get("vetoed_bonds", []),
            "report_md": chamber_result.get("report_md", "")
        }
        AGENT_CACHE["data"] = res

        # 持久化本次投研会诊记录至关系型数据库
        try:
            from db import SessionLocal, AgentReportRecord
            with SessionLocal() as session:
                rpt_id = f"rpt_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"
                rpt = AgentReportRecord(
                    id=rpt_id,
                    strategy_id=strategy_id,
                    strategy_name=strat_name,
                    run_time=res["run_time"],
                    candidates_count=len(candidates),
                    vetoed_count=len(res["vetoed_bonds"]),
                    portfolio_count=len(res["final_portfolio"]),
                    report_md=res["report_md"],
                    result_json=json.dumps(res, ensure_ascii=False)
                )
                session.add(rpt)
                session.commit()
        except Exception as e:
            print("[WARN] 持久化智能体会诊记录到数据库失败:", e)

        # 自动广播推送飞书/微信群
        try:
            from notification.notifier import Notifier
            Notifier.notify_all(res["report_md"])
        except Exception:
            pass
        
        await websocket.send_json({
            "step": "complete",
            "message": "🎉 今日多智能体联合会诊全部完成！(已同步推送飞书/微信)",
            "data": res
        })
        
    except WebSocketDisconnect:
        pass
# ==============================================================
# 6. 数据湖可视化中枢 API (Data Lake Management)
# ==============================================================

from core.datalake_manager import datalake_manager

@app.get("/api/datalake/overview")
def get_datalake_overview():
    """获取多资产数据湖概览指标、容量与覆盖率"""
    return datalake_manager.get_overview()

@app.get("/api/datalake/symbols")
def get_datalake_symbols(
    category: str = Query("cb", description="资产类别: cb/us_stock/etf/stock/index"),
    search: str = Query("", description="搜索转债代码或简称"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """搜索与浏览数据湖中的标的元数据与切片文件状态"""
    return datalake_manager.list_symbols(category=category, search=search, page=page, page_size=page_size)

@app.get("/api/datalake/preview/{symbol}")
def preview_datalake_symbol(
    symbol: str,
    category: str = Query("cb", description="资产类别: cb/us_stock/etf/stock/index"),
    limit: int = Query(30, ge=5, le=100)
):
    """预览单只标的的底层真实历史日线切片数据"""
    return datalake_manager.preview_symbol(symbol=symbol, category=category, limit=limit)

class DataLakeSyncRequest(BaseModel):
    action: str = "incremental_update" # incremental_update / health_check / download_us_stock / download_etf / download_stock
    symbols: Optional[List[str]] = None

@app.post("/api/datalake/sync")
def start_datalake_sync(req: DataLakeSyncRequest):
    """触发数据湖后台增量同步或全量体检任务 (支持用户自定义标的集合)"""
    return datalake_manager.start_sync_job(action_type=req.action, custom_symbols=req.symbols)

@app.get("/api/datalake/sync/status")
def get_datalake_sync_status():
    """获取当前正在执行的数据湖任务进度与日志"""
    return datalake_manager.get_task_status()

class DataLakeResolveRequest(BaseModel):
    symbols: List[str]
    category: str = "stock"

@app.post("/api/datalake/resolve_symbols")
def resolve_datalake_symbols(req: DataLakeResolveRequest):
    """实时全网解析股票/ETF/美股/转债的基础信息与实时估值 (公司简称、所属交易所、最新价、PE、PB、总市值)"""
    return datalake_manager.resolve_symbols_metadata(symbols=req.symbols, category=req.category)

# ========================
# LLM 大模型供应商与 Token 管理
# ========================
from core.llm_manager import llm_manager

class LLMSaveConfigRequest(BaseModel):
    provider: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""

class LLMTestRequest(BaseModel):
    provider: str
    api_key: str = ""
    base_url: str = ""
    model: str = ""

@app.get("/api/llm/config")
def get_llm_config():
    """获取大模型供应商配置状态与支持列表"""
    return llm_manager.get_config()

@app.post("/api/llm/config")
def save_llm_config(req: LLMSaveConfigRequest):
    """保存并持久化大模型配置 (写入 .env 与运行时内存)"""
    return llm_manager.save_config(
        provider=req.provider,
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model
    )

@app.post("/api/llm/test")
def test_llm_connection(req: LLMTestRequest):
    """测试指定大模型供应商端点与 API Key 连通性"""
    return llm_manager.test_connection(
        provider=req.provider,
        api_key=req.api_key,
        base_url=req.base_url,
        model=req.model
    )



from fastapi.responses import FileResponse

# 前端生产环境构建静态托管 (如果前端已打包)
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        if full_path.startswith("api/") or full_path.startswith("ws/"):
            raise HTTPException(status_code=404, detail="API route not found")
        file_path = FRONTEND_DIST / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8088, reload=True)
