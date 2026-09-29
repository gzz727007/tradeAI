"""
LangGraph 多智能体协同状态模型 (CB Trade State)
定义可转债投研各节点共享的状态字典结构。
"""

from typing import TypedDict, List, Dict, Any, Optional

class BondCandidate(TypedDict):
    bond_code: str
    bond_name: str
    price: float
    premium_rate: float
    double_low: float
    stock_code: str
    stock_name: str
    stock_price: float
    remaining_scale: float
    rating: str
    ytm: float

class CreditRiskResult(TypedDict):
    bond_code: str
    risk_level: str  # "PASS" (安全), "WARN" (关注), "VETO" (一票否决)
    debt_ratio: Optional[float]
    pledge_ratio: Optional[float]
    reason: str

class EquityMomentumResult(TypedDict):
    bond_code: str
    momentum_score: float  # 0 ~ 100
    sector_themes: List[str]
    catalyst_summary: str

class ClauseGameResult(TypedDict):
    bond_code: str
    down_revision_potential: float  # 0 ~ 100
    call_risk_level: str            # "LOW", "MEDIUM", "HIGH"
    game_summary: str

class DynamicPriceTarget(TypedDict):
    bond_code: str
    bond_name: str
    entry_ceiling: float          # 建议买入价上限（低于此价建仓）
    target_price: float           # 建议第一目标止盈价
    hard_stop_price: float        # 强赎硬避险警戒线（默认128.0）
    trailing_stop_drop: float     # 脉冲后最高点回撤追踪止盈容忍度 (例如 0.025 代表 2.5%)
    veto: bool                    # 信用风控是否一票否决
    rationale: str                # 定价依据总结

class PortfolioItem(TypedDict):
    bond_code: str
    bond_name: str
    price: float
    double_low: float
    weight: float
    rating_stars: int               # 1 ~ 5 星推荐
    pm_verdict: str
    dynamic_targets: Optional[DynamicPriceTarget]

class CBTradeState(TypedDict):
    # 基础运行上下文
    trade_date: str
    total_market_count: int
    
    # 阶段 1: 初筛候选池
    candidates: List[BondCandidate]
    
    # 阶段 2: 三大分析师并行研判结果 (以 bond_code 为 key)
    credit_reviews: Dict[str, CreditRiskResult]
    equity_reviews: Dict[str, EquityMomentumResult]
    clause_reviews: Dict[str, ClauseGameResult]
    
    # 阶段 3: 仲裁与最终决策
    final_portfolio: List[PortfolioItem]
    vetoed_bonds: List[Dict[str, str]]
    dynamic_targets: Dict[str, DynamicPriceTarget]
    
    # 阶段 4: 报告展示
    daily_report_markdown: str
