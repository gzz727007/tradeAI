"""
量化策略上下文与订单模型 (Strategy Context & Execution Models)
为事件驱动型策略提供统一的账户、持仓、订单状态及大模型动态目标存储。
跨品种通用设计 (可转债 / A股股票 / ETF / 期货均适用)。
"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
import uuid
from datetime import datetime

@dataclass
class PositionInfo:
    """单个标的持仓明细"""
    symbol: str
    name: str = ""
    amount: int = 0                  # 持仓数量 (1手 = 10张)
    avg_price: float = 0.0           # 持仓均价成本
    highest_price: float = 0.0       # 买入以来的最高价 (用于追踪止盈)
    lowest_price: float = 0.0        # 买入以来的最低价
    entry_date: str = ""             # 初次建仓日期
    dynamic_target: Optional[Dict[str, Any]] = None  # 大模型赋予的个性化动态点位
    last_price: float = 0.0          # 最后一次有行情的市价 (停牌/摘牌期间用于盯市估值)
    missing_quote_days: int = 0      # 连续无行情交易日计数 (强赎/退市摘牌识别)

    @property
    def cost_basis(self) -> float:
        return self.amount * self.avg_price

    def update_price_tracker(self, current_price: float):
        """跟踪最高价与最低价"""
        if current_price > self.highest_price:
            self.highest_price = current_price
        if self.lowest_price <= 0.0 or current_price < self.lowest_price:
            self.lowest_price = current_price

@dataclass
class Order:
    """策略生成的委托订单"""
    order_id: str
    symbol: str
    action: str                      # "BUY" 或 "SELL"
    price: float                     # 触发价格 / 期望成交价
    amount: int                      # 委托张数/股数 (可转债必须是10的整数倍)
    reason: str = ""                 # 决策理由 (如: 触及动态止盈位122.5元 / 大模型一票否决)
    status: str = "FILLED"           # "FILLED", "PENDING", "REJECTED"
    timestamp: str = ""
    fee: float = 0.0                 # 预估佣金手续费

class StrategyContext:
    """
    策略运行上下文 (Context)
    向策略大脑暴露当前的资金、持仓、大模型动态价格点和下单 API。
    """
    def __init__(self, initial_capital: float = 100000.0, commission_rate: float = 0.00005, slippage_rate: float = 0.0005):
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.current_date: str = ""
        
        # 持仓表: {symbol: PositionInfo}
        self.positions: Dict[str, PositionInfo] = {}
        
        # 准入白名单 (大模型首席风控官审查通过的标的池)
        self.whitelist: Set[str] = set()
        
        # 大模型动态价格带字典: {symbol: {"entry_ceiling": 104.5, "target_price": 122.0, "hard_stop_price": 128.0, "trailing_stop_drop": 0.025, ...}}
        self.dynamic_targets: Dict[str, Dict[str, Any]] = {}
        
        # 委托流水表
        self.orders: List[Order] = []
        
        # 策略自定义状态持久化字典
        self.state: Dict[str, Any] = {}

    def get_position(self, symbol: str) -> Optional[PositionInfo]:
        """获取指定标的的持仓信息"""
        return self.positions.get(symbol)

    def is_in_whitelist(self, symbol: str) -> bool:
        """检查标的是否在大模型准入白名单中 (若白名单为空则默认不过滤)"""
        if not self.whitelist:
            return True
        return symbol in self.whitelist

    def get_dynamic_target(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取大模型为该券定制的动态价格点"""
        return self.dynamic_targets.get(symbol)

    def buy(
        self,
        symbol: str,
        price: float,
        amount: int = 0,
        target_money: float = 0.0,
        name: str = "",
        reason: str = ""
    ) -> Optional[Order]:
        """
        发出买入指令
        :param symbol: 标的代码 (如 '113050')
        :param price: 当前市价/买入价
        :param amount: 买入数量 (转债需整10，优先使用)
        :param target_money: 目标金额 (若 amount 为 0，则根据金额自动换算数量)
        :param name: 标的名称
        :param reason: 买入触发原因
        """
        if price <= 0:
            return None
            
        # 若指定了目标金额，换算数量 (1手=10张)
        if amount <= 0 and target_money > 0:
            amount = int(target_money / (price * 10)) * 10

        if amount <= 0:
            return None

        # 估算成交额与成本 (手续费+滑点)
        execution_price = price * (1.0 + self.slippage_rate)
        trade_val = amount * execution_price
        fee = max(trade_val * self.commission_rate, 0.1)
        total_cost = trade_val + fee

        # 资金可用性校验
        if self.cash < total_cost:
            # 资金不足时，尽可能买入最大整数手
            max_amount = int((self.cash / (execution_price * (1.0 + self.commission_rate))) / 10) * 10
            if max_amount < 10:
                return None
            amount = max_amount
            trade_val = amount * execution_price
            fee = max(trade_val * self.commission_rate, 0.1)
            total_cost = trade_val + fee

        # 扣减现金
        self.cash -= total_cost

        # 更新持仓
        if symbol in self.positions:
            pos = self.positions[symbol]
            new_amount = pos.amount + amount
            new_avg = (pos.amount * pos.avg_price + trade_val) / new_amount
            pos.amount = new_amount
            pos.avg_price = new_avg
            pos.update_price_tracker(price)
            pos.last_price = price
            pos.missing_quote_days = 0
        else:
            self.positions[symbol] = PositionInfo(
                symbol=symbol,
                name=name or symbol,
                amount=amount,
                avg_price=execution_price,
                highest_price=price,
                lowest_price=price,
                entry_date=self.current_date,
                dynamic_target=self.dynamic_targets.get(symbol),
                last_price=price
            )

        order = Order(
            order_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            action="BUY",
            price=round(execution_price, 3),
            amount=amount,
            reason=reason,
            status="FILLED",
            timestamp=self.current_date,
            fee=round(fee, 2)
        )
        self.orders.append(order)
        return order

    def sell(
        self,
        symbol: str,
        price: float,
        amount: int = 0,
        pct: float = 1.0,
        reason: str = ""
    ) -> Optional[Order]:
        """
        发出卖出指令
        :param symbol: 标的代码
        :param price: 卖出市价
        :param amount: 卖出张数 (优先)
        :param pct: 卖出持仓百分比 (0.1 ~ 1.0，如 0.5 代表减持半仓)
        :param reason: 卖出触发原因 (如 触发止盈 / 强赎清仓)
        """
        if symbol not in self.positions or price <= 0:
            return None

        pos = self.positions[symbol]
        if amount <= 0:
            amount = int((pos.amount * min(1.0, max(0.0, pct))) / 10) * 10

        if amount <= 0:
            return None

        amount = min(amount, pos.amount)

        # 估算成交额与费用
        execution_price = price * (1.0 - self.slippage_rate)
        sell_val = amount * execution_price
        fee = max(sell_val * self.commission_rate, 0.1)
        net_cash = sell_val - fee

        # 增加现金
        self.cash += net_cash

        # 更新持仓
        pos.amount -= amount
        if pos.amount <= 0:
            del self.positions[symbol]

        order = Order(
            order_id=str(uuid.uuid4())[:8],
            symbol=symbol,
            action="SELL",
            price=round(execution_price, 3),
            amount=amount,
            reason=reason,
            status="FILLED",
            timestamp=self.current_date,
            fee=round(fee, 2)
        )
        self.orders.append(order)
        return order

    def get_market_value(self, price_map: Dict[str, float]) -> float:
        """获取所有持仓当前市值 (停牌期间按最后已知市价盯市，而非冻结在成本价)"""
        val = 0.0
        for s, pos in self.positions.items():
            p = price_map.get(s)
            if p is None:
                p = pos.last_price if pos.last_price > 0 else pos.avg_price
            val += pos.amount * p
        return val

    def force_liquidate_stale(self, price_map: Dict[str, float], max_missing_days: int = 3) -> int:
        """
        停牌/摘牌持仓强制平仓巡检 (由回测引擎每个交易日驱动一次)。
        转债触发强赎或到期退市后行情终止，若连续 max_missing_days 个交易日无行情，
        视为已摘牌离场：按最后已知市价强制卖出回流现金 (扣除佣金与滑点)，
        避免持仓被永久冻结在成本价导致净值失真。
        :return: 本日强制平仓的标的数量
        """
        liquidated = 0
        for sym in list(self.positions.keys()):
            pos = self.positions.get(sym)
            if pos is None:
                continue
            cur_price = price_map.get(sym)
            if cur_price is not None:
                pos.last_price = cur_price
                pos.missing_quote_days = 0
                continue
            pos.missing_quote_days += 1
            if pos.missing_quote_days >= max_missing_days:
                last = pos.last_price if pos.last_price > 0 else pos.avg_price
                if last > 0:
                    self.sell(sym, last, reason="停牌/强赎摘牌强制平仓")
                    if sym not in self.positions:
                        liquidated += 1
        return liquidated

    def get_total_assets(self, price_map: Dict[str, float]) -> float:
        """获取总资产 = 可用现金 + 持仓市值"""
        return self.cash + self.get_market_value(price_map)
