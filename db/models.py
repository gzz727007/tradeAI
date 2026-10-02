"""
业务数据模型定义 (SQLAlchemy ORM Models)
包含：策略定义、历次回测归档、多账号资产、持仓明细、调仓流水记录。
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    Boolean
)
from sqlalchemy.orm import relationship
from db.session import Base

class Strategy(Base):
    """量化策略档案表"""
    __tablename__ = "strategies"

    id = Column(String(64), primary_key=True, index=True, comment="策略唯一标识符")
    name = Column(String(128), nullable=False, comment="策略名称")
    category = Column(String(64), nullable=False, default="用户自定义", comment="策略分类: 系统内置/用户自定义/AI探索生成")
    description = Column(Text, nullable=True, comment="策略逻辑原理与说明")
    params_json = Column(Text, nullable=False, default="{}", comment="策略选券与权重参数JSON")
    version = Column(Integer, default=1, comment="策略数据版本号")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    backtest_records = relationship("BacktestRecord", back_populates="strategy", cascade="all, delete-orphan")

    def to_dict(self):
        import json
        from core.strategy_adapter import normalize_strategy_params
        params = {}
        if self.params_json:
            try:
                params = json.loads(self.params_json)
            except Exception:
                params = {}
        normalized = normalize_strategy_params(params)
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description or "",
            "params": normalized,
            "version": self.version or 1,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M") if self.updated_at else ""
        }


class BacktestRecord(Base):
    """历次历史回测归档表"""
    __tablename__ = "backtest_records"

    id = Column(String(64), primary_key=True, index=True, comment="回测唯一ID (如 bt_179044...)")
    strategy_id = Column(String(64), ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True)
    strategy_name = Column(String(128), nullable=False, comment="回测时策略名称")
    start_date = Column(String(32), nullable=False, comment="回测开始日期")
    end_date = Column(String(32), nullable=False, comment="回测结束日期")
    rebalance_freq = Column(Integer, default=5, comment="调仓周期(天)")
    mode = Column(String(32), default="real", comment="回测模式: real(点对点真实撮合) / fast(因子仿真)")
    total_return = Column(Float, default=0.0, comment="累计收益率(%)")
    annual_return = Column(Float, default=0.0, comment="年化收益率(%)")
    max_drawdown = Column(Float, default=0.0, comment="最大回撤(%)")
    sharpe_ratio = Column(Float, default=0.0, comment="夏普比率")
    win_rate = Column(Float, default=0.0, comment="胜率(%)")
    benchmark_return = Column(Float, default=0.0, comment="基准中证转债收益(%)")
    metrics_json = Column(Text, nullable=True, comment="波动率、索提诺、盈亏比等详细量化指标JSON")
    curve_data_json = Column(Text, nullable=True, comment="累计净值走势曲线与回撤时序JSON")
    created_at = Column(DateTime, default=datetime.now, comment="回测运行时间")

    strategy = relationship("Strategy", back_populates="backtest_records")

    def to_dict(self, include_curve: bool = True):
        import json
        metrics = {}
        if self.metrics_json:
            try:
                metrics = json.loads(self.metrics_json)
            except Exception:
                pass
        
        curve_data = {}
        if include_curve and self.curve_data_json:
            try:
                curve_data = json.loads(self.curve_data_json)
            except Exception:
                pass

        data = {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "rebalance_freq": self.rebalance_freq,
            "mode": self.mode,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "win_rate": self.win_rate,
            "benchmark_return": self.benchmark_return,
            "metrics": metrics,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }
        if include_curve:
            data["curve_data"] = curve_data
        return data


class Account(Base):
    """多账户资产表 (模拟盘 / 实盘)"""
    __tablename__ = "accounts"

    id = Column(String(64), primary_key=True, index=True, comment="账号唯一ID (如 paper_double_low)")
    name = Column(String(128), nullable=False, comment="账号显示名称")
    account_type = Column(String(32), nullable=False, default="PAPER", comment="账号类别: PAPER(模拟盘) / REAL(实盘)")
    associated_strategy = Column(String(128), nullable=True, comment="绑定的主策略名称")
    initial_capital = Column(Float, default=100000.0, comment="初始资金(元)")
    available_cash = Column(Float, default=100000.0, comment="当前可用现金(元)")
    total_asset = Column(Float, default=100000.0, comment="当前总资产(元)")
    status = Column(String(32), default="ACTIVE", comment="运行状态: ACTIVE / PAUSED")
    nav_history_json = Column(Text, default="[]", comment="历史净值与总资产时序JSON")
    created_at = Column(DateTime, default=datetime.now, comment="开户时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    positions = relationship("Position", back_populates="account", cascade="all, delete-orphan")
    trades = relationship("TradeOrder", back_populates="account", cascade="all, delete-orphan")

    def to_dict(self):
        import json
        nav_hist = []
        if self.nav_history_json:
            try:
                nav_hist = json.loads(self.nav_history_json)
            except Exception:
                pass
        
        pos_dict = {}
        for p in self.positions:
            pos_dict[p.symbol] = p.to_dict()

        trade_list = [t.to_dict() for t in sorted(self.trades, key=lambda x: x.trade_time, reverse=True)]

        return {
            "account_id": self.id,
            "account_name": self.name,
            "account_type": self.account_type,
            "associated_strategy": self.associated_strategy or "",
            "initial_capital": self.initial_capital,
            "available_cash": self.available_cash,
            "total_asset": self.total_asset,
            "status": self.status,
            "positions": pos_dict,
            "history_trades": trade_list,
            "nav_history": nav_hist,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else ""
        }


class Position(Base):
    """账户持仓明细表"""
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(64), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True, comment="转债代码 (如 128089)")
    name = Column(String(64), nullable=False, comment="转债简称 (如 麦米转债)")
    amount = Column(Integer, default=0, comment="持仓张数 (1手=10张)")
    avg_price = Column(Float, default=0.0, comment="持仓均价(元)")
    current_price = Column(Float, default=0.0, comment="最新收盘价/现价")
    market_value = Column(Float, default=0.0, comment="持仓最新市值(元)")
    profit_rate = Column(Float, default=0.0, comment="浮动盈亏比例(%)")
    buy_date = Column(String(32), nullable=True, comment="建仓日期")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uix_account_symbol"),
    )

    account = relationship("Account", back_populates="positions")

    def to_dict(self):
        return {
            "bond_code": self.symbol,
            "bond_name": self.name,
            "amount": self.amount,
            "avg_price": round(self.avg_price, 3),
            "current_price": round(self.current_price, 3) if self.current_price else round(self.avg_price, 3),
            "market_value": round(self.market_value, 2),
            "profit_rate": round(self.profit_rate, 2),
            "buy_date": self.buy_date or ""
        }


class TradeOrder(Base):
    """交易与调仓流水表 (严格审计日志)"""
    __tablename__ = "trade_orders"

    id = Column(String(64), primary_key=True, index=True, comment="流水订单ID")
    account_id = Column(String(64), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True, comment="转债代码")
    name = Column(String(64), nullable=False, comment="转债简称")
    action = Column(String(16), nullable=False, comment="操作方向: BUY / SELL")
    price = Column(Float, nullable=False, comment="成交价格(元)")
    amount = Column(Integer, nullable=False, comment="成交张数")
    fee = Column(Float, default=0.0, comment="交易手续费(元)")
    reason = Column(Text, nullable=True, comment="调仓触发理由或策略信号")
    trade_time = Column(DateTime, default=datetime.now, comment="成交时间")

    account = relationship("Account", back_populates="trades")

    def to_dict(self):
        return {
            "order_id": self.id,
            "trade_time": self.trade_time.strftime("%Y-%m-%d %H:%M:%S") if self.trade_time else "",
            "action": self.action,
            "bond_code": self.symbol,
            "bond_name": self.name,
            "price": self.price,
            "amount": self.amount,
            "fee": round(self.fee, 2),
            "reason": self.reason or ""
        }


class AgentReportRecord(Base):
    """今日智能体投研会诊档案表 (持久化保留历次投委会辩论实录与PM裁决)"""
    __tablename__ = "agent_report_records"

    id = Column(String(64), primary_key=True, index=True, comment="会诊唯一编号 (如 rpt_179044...)")
    strategy_id = Column(String(64), nullable=True, comment="挂载的前置初筛策略ID")
    strategy_name = Column(String(128), nullable=True, comment="挂载的前置初筛策略名称")
    run_time = Column(String(32), nullable=False, comment="会诊运行时间戳")
    candidates_count = Column(Integer, default=0, comment="初筛入围标的数量")
    vetoed_count = Column(Integer, default=0, comment="风控一票否决标的数量")
    portfolio_count = Column(Integer, default=0, comment="PM终审入围标的数量")
    report_md = Column(Text, nullable=True, comment="结构化研报Markdown原文")
    result_json = Column(Text, nullable=False, comment="完整会诊结果JSON数据包")
    created_at = Column(DateTime, default=datetime.now, comment="归档时间")

    def to_dict(self):
        import json
        res = {}
        if self.result_json:
            try:
                res = json.loads(self.result_json)
            except Exception:
                res = {}
        return res


class AgentDefinition(Base):
    """投研智能体人才库表 (Agent Definition)"""
    __tablename__ = "agents"

    id = Column(String(64), primary_key=True, index=True, comment="智能体唯一代号 (如 bear_prosecutor)")
    name = Column(String(128), nullable=False, comment="智能体角色名称")
    avatar = Column(String(32), default="🤖", comment="头像或Emoji")
    target_asset = Column(String(32), default="universal", comment="适用资产: cb/stock/us_stock/universal")
    role_type = Column(String(32), default="score", comment="职责类型: veto(风控否决)/score(弹性评分)/review(条款研判)/prosecutor(控方)/defender(辩方)/judge(法官裁决)")
    description = Column(Text, nullable=True, comment="职责描述与投资哲学定位")
    model_provider = Column(String(32), default="auto", comment="首选大模型渠道: auto/gemini/deepseek/qwen/openai")
    model_name = Column(String(64), nullable=True, comment="指定的模型名称(为空则使用默认)")
    system_prompt = Column(Text, nullable=False, comment="专家人设与推演准则 System Prompt")
    user_prompt_template = Column(Text, nullable=False, comment="标的评估 Prompt 模板(支持插值)")
    is_builtin = Column(Boolean, default=False, comment="是否系统内置不可删除")
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="展示与执行排序")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "avatar": self.avatar or "🤖",
            "target_asset": self.target_asset or "universal",
            "role_type": self.role_type or "score",
            "description": self.description or "",
            "model_provider": self.model_provider or "auto",
            "model_name": self.model_name or "",
            "system_prompt": self.system_prompt or "",
            "user_prompt_template": self.user_prompt_template or "",
            "is_builtin": bool(self.is_builtin),
            "is_active": bool(self.is_active),
            "sort_order": self.sort_order or 0,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else ""
        }


class MeetingChamber(Base):
    """议事空间与法庭类型表 (Meeting Chambers & Assemblies)"""
    __tablename__ = "meeting_chambers"

    id = Column(String(64), primary_key=True, index=True, comment="议事厅代号 (如 chamber_adversarial_court)")
    name = Column(String(128), nullable=False, comment="议事厅名称")
    chamber_type = Column(String(32), default="ROUNDTABLE", comment="议事范式: ROUNDTABLE(投研圆桌) / COURTROOM(对抗法庭)")
    target_asset = Column(String(32), default="cb", comment="资产分类: cb/stock/us_stock/universal")
    description = Column(Text, nullable=True, comment="议事厅审理目标与议程说明")
    icon = Column(String(32), default="🏛️", comment="议事厅图标")
    agent_ids_json = Column(Text, default="[]", comment="挂载参会的智能体ID列表JSON")
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="展示排序")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        import json
        agent_ids = []
        if self.agent_ids_json:
            try:
                agent_ids = json.loads(self.agent_ids_json)
            except Exception:
                agent_ids = []
        return {
            "id": self.id,
            "name": self.name,
            "chamber_type": self.chamber_type,
            "target_asset": self.target_asset,
            "description": self.description or "",
            "icon": self.icon or "🏛️",
            "agent_ids": agent_ids,
            "is_active": bool(self.is_active),
            "sort_order": self.sort_order or 0,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else ""
        }


class CommitteeDecision(Base):
    """AI 交易委员会准入决策 (逐只三分析师语义审查留痕)"""
    __tablename__ = "committee_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    trade_date = Column(String(32), nullable=False, index=True, comment="交易日期 YYYY-MM-DD")
    stage = Column(String(32), nullable=False, default="premarket", comment="审查阶段: premarket(盘前)/midday(午间复检)/manual(手动)")
    bond_code = Column(String(32), nullable=False, index=True, comment="转债代码")
    bond_name = Column(String(64), nullable=False, default="", comment="转债简称")
    decision = Column(String(32), nullable=False, comment="准入结论: approve(准入)/watch(观察-禁新买)/reject(否决)")
    reason = Column(Text, nullable=True, comment="综合裁决理由")
    review_json = Column(Text, nullable=True, comment="三分析师审查明细JSON (信用/条款/动量)")
    created_at = Column(DateTime, default=datetime.now, comment="决策时间")

    __table_args__ = (
        UniqueConstraint("trade_date", "stage", "bond_code", name="uix_committee_decision"),
    )

    def to_dict(self):
        import json
        review = {}
        if self.review_json:
            try:
                review = json.loads(self.review_json)
            except Exception:
                review = {}
        return {
            "id": self.id,
            "trade_date": self.trade_date,
            "stage": self.stage,
            "bond_code": self.bond_code,
            "bond_name": self.bond_name,
            "decision": self.decision,
            "reason": self.reason or "",
            "review": review,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }


class CommitteePricePlan(Base):
    """AI 委员会限价交易计划 (约束式定价快照，交易程序严格按此执行)"""
    __tablename__ = "committee_price_plans"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    trade_date = Column(String(32), nullable=False, index=True, comment="交易日期 YYYY-MM-DD")
    bond_code = Column(String(32), nullable=False, index=True, comment="转债代码")
    bond_name = Column(String(64), nullable=False, default="", comment="转债简称")
    action = Column(String(16), nullable=False, default="HOLD", comment="主操作建议: BUY/SELL/HOLD")
    buy_limit_price = Column(Float, nullable=True, comment="买入限价 (≤昨收×1.02)")
    sell_limit_price = Column(Float, nullable=True, comment="卖出限价 (≥昨收×0.98)")
    band_low = Column(Float, nullable=True, comment="约束区间下界(锚定昨收)")
    band_high = Column(Float, nullable=True, comment="约束区间上界(锚定昨收)")
    prev_close = Column(Float, nullable=True, comment="昨收锚定价")
    current_price = Column(Float, nullable=True, comment="最近一次刷新时的现价")
    ai_priced = Column(Boolean, default=False, comment="是否 AI 定价 (False=规则兜底)")
    status = Column(String(32), default="pending", comment="计划状态: pending/executable/missed/alert/expired")
    reason = Column(Text, nullable=True, comment="定价理由 (AI 给出)")
    stage = Column(String(32), default="premarket", comment="计划生成阶段")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="最后刷新时间")
    created_at = Column(DateTime, default=datetime.now, comment="计划创建时间")

    __table_args__ = (
        UniqueConstraint("trade_date", "bond_code", name="uix_committee_plan"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "trade_date": self.trade_date,
            "bond_code": self.bond_code,
            "bond_name": self.bond_name,
            "action": self.action,
            "buy_limit_price": self.buy_limit_price,
            "sell_limit_price": self.sell_limit_price,
            "band_low": self.band_low,
            "band_high": self.band_high,
            "prev_close": self.prev_close,
            "current_price": self.current_price,
            "ai_priced": bool(self.ai_priced),
            "status": self.status,
            "reason": self.reason or "",
            "stage": self.stage,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else ""
        }


class CommitteeState(Base):
    """委员会运行状态单例表 (id=1, 保存总开关/绑定策略/当日调度水位)"""
    __tablename__ = "committee_state"

    id = Column(Integer, primary_key=True, comment="固定为1")
    bound_strategy = Column(String(128), default="", comment="绑定的候选策略名 (空=自动取默认双低)")
    auto_execute = Column(Boolean, default=False, comment="全自动执行总开关 (审查+定价后直接调仓)")
    enabled = Column(Boolean, default=True, comment="委员会总开关")
    last_gate_date = Column(String(32), default="", comment="最近一次盘前准入日期")
    last_midday_date = Column(String(32), default="", comment="最近一次午间复检日期")
    last_refresh_at = Column(DateTime, nullable=True, comment="最近一次盘中价格刷新时间")
    last_execute_date = Column(String(32), default="", comment="最近一次自动调仓日期")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        return {
            "bound_strategy": self.bound_strategy or "",
            "auto_execute": bool(self.auto_execute),
            "enabled": bool(self.enabled),
            "last_gate_date": self.last_gate_date or "",
            "last_midday_date": self.last_midday_date or "",
            "last_refresh_at": self.last_refresh_at.strftime("%Y-%m-%d %H:%M:%S") if self.last_refresh_at else "",
            "last_execute_date": self.last_execute_date or "",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else ""
        }


class StrategyExperiment(Base):
    """AI 策略进化实验记录表 (RD-Agent 式 生成→回测→体检→反馈 每轮留痕)"""
    __tablename__ = "strategy_experiments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_idea = Column(Text, nullable=False, comment="用户投资设想原话")
    round_idx = Column(Integer, nullable=False, default=1, comment="迭代轮次 (1 起)")
    status = Column(String(32), nullable=False, default="generated", comment="本轮结局: generated/sandbox_rejected/backtest_failed/health_check_failed/succeeded")
    strategy_id = Column(String(64), nullable=True, index=True, comment="成功后注册的策略ID")
    strategy_name = Column(String(128), nullable=True, comment="LLM 命名的策略名")
    generated_code = Column(Text, nullable=True, comment="本轮 LLM 生成的完整策略代码")
    verdict = Column(Text, nullable=True, comment="体检结论 (成功时为指标亮点摘要)")
    fail_feedback = Column(Text, nullable=True, comment="结构化失败原因 (回喂给下一轮生成)")
    metrics_json = Column(Text, nullable=True, comment="本轮回测指标 JSON (nav/回撤/交易数等)")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def to_dict(self):
        import json
        metrics = {}
        if self.metrics_json:
            try:
                metrics = json.loads(self.metrics_json)
            except Exception:
                pass
        return {
            "id": self.id,
            "user_idea": self.user_idea,
            "round_idx": self.round_idx,
            "status": self.status,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "code": self.generated_code or "",
            "verdict": self.verdict or "",
            "fail_feedback": self.fail_feedback or "",
            "metrics": metrics,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }



