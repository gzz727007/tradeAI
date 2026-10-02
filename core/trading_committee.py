"""
AI 交易委员会 (Trading Committee)
交易执行层的实时 AI 决策引擎，与策略进化环的代码评审团职责分离:
1. 盘前准入 premarket_gate: 策略初筛标的逐只经三分析师语义审查，approve/watch/reject，通过的才进入真正交易池
2. 约束式定价 build_price_plan: AI 只能在硬约束区间内选位定价 (买入≤昨收×1.02、卖出≥昨收×0.98)，防幻觉
3. 午间复检 midday_review: 11:35 半日复盘，重审准入+重定价，输出卖出警示 (强赎区/信用恶化强制卖出建议)
4. 盘中刷新 price_refresh: 每 30 分钟用实时快照 (转债+正股) 更新计划状态与可成交性
5. 后台调度线程: 交易日 09:15 准入 → 每30分钟刷新 → 11:35 复检 → 15:00 归档
auto_execute 总开关打开时，准入/复检完成后自动调用 ledger 调仓，交易程序严格按 AI 限价执行。
"""

import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from config.config import settings
from core.llm_manager import llm_manager, extract_json_content, parallel_batch_map
from core.trading_calendar import is_trading_day
from core.realtime_quotes import (
    get_fresh_snapshot,
    get_prev_close_map,
    build_candidates,
    get_current_price_map,
)
from db.session import SessionLocal
from db.models import CommitteeDecision, CommitteePricePlan, CommitteeState


class TradingCommittee:
    """交易委员会服务 (单例)"""

    def __init__(self):
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ==============================================================
    # 状态与设置
    # ==============================================================

    def get_state(self) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            row = session.query(CommitteeState).filter(CommitteeState.id == 1).first()
            if not row:
                row = CommitteeState(
                    id=1,
                    auto_execute=settings.COMMITTEE_AUTO_EXECUTE,
                    enabled=settings.COMMITTEE_ENABLED,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    def update_settings(self, bound_strategy: Optional[str] = None,
                        auto_execute: Optional[bool] = None,
                        enabled: Optional[bool] = None) -> Dict[str, Any]:
        session = SessionLocal()
        try:
            row = session.query(CommitteeState).filter(CommitteeState.id == 1).first()
            if not row:
                row = CommitteeState(id=1)
                session.add(row)
            if bound_strategy is not None:
                row.bound_strategy = bound_strategy.strip()
            if auto_execute is not None:
                row.auto_execute = bool(auto_execute)
            if enabled is not None:
                row.enabled = bool(enabled)
            session.commit()
            session.refresh(row)
            return row.to_dict()
        finally:
            session.close()

    # ==============================================================
    # 候选来源: 绑定策略在实时快照上选券
    # ==============================================================

    def _resolve_strategy(self, bound_name: str):
        """解析绑定策略 (精确 id/名称匹配)，失败回退经典双低"""
        from core.strategy_manager import StrategyManager
        from strategies.configurable_strategy import ConfigurableCBStrategy

        ident = (bound_name or "").strip()
        if ident:
            try:
                sm = StrategyManager()
                for s in sm.get_all_strategies():
                    if s.get("id", "") == ident or s.get("name", "") == ident:
                        return sm.create_strategy_instance(s)
            except Exception as e:
                print(f"[WARN] 委员会绑定策略解析失败，回退默认双低: {e}")
        return ConfigurableCBStrategy({
            "id": "strat_committee_default",
            "name": "委员会默认双低轮动",
            "params": {"min_price": 90, "max_price": 135, "max_premium": 60,
                       "double_low_weight": 1.0, "top_n": 12,
                       "sort_by": "double_low", "sort_ascending": True}
        })

    def _resolve_candidates(self, snapshot) -> tuple:
        """运行绑定策略选券 → (候选列表, 策略名)"""
        state = self.get_state()
        strat = self._resolve_strategy(state.get("bound_strategy", ""))
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            selected = strat.select_portfolio(today, snapshot)
        except Exception as e:
            print(f"[ERROR] 委员会选券异常，回退默认双低: {e}")
            strat = self._resolve_strategy("")
            selected = strat.select_portfolio(today, snapshot)
        codes = [str(c) for c in (selected["bond_code"].tolist() if selected is not None and not selected.empty else [])]
        candidates = build_candidates(snapshot, codes)
        return candidates, getattr(strat, "name", "未知策略")

    def _get_holding_symbols(self) -> Dict[str, str]:
        """全部账户当前持仓 {bond_code: bond_name} (持仓无需准入，直接进入定价)"""
        from db.models import Position
        holdings: Dict[str, str] = {}
        session = SessionLocal()
        try:
            rows = session.query(Position).all()
            for p in rows:
                holdings[str(p.symbol)] = p.name or str(p.symbol)
        finally:
            session.close()
        return holdings

    # ==============================================================
    # LLM 可用性预检 (严格模式: 系统必须依赖 LLM, 失败即中止不降级)
    # ==============================================================

    def _ensure_llm_ready(self) -> Optional[str]:
        """
        委员会运行前 LLM 预检: 未配置或不可达时返回错误信息 (None=可用)。
        委员会的准入判断与定价全部依赖 LLM，禁止在无 AI 判断时生成决策/计划，
        否则 auto_execute 会按无人审查的中性价自动下单 (fail-safe 原则)。
        """
        client, model = llm_manager.get_client()
        if not client:
            return "LLM 未配置: 请先在「AI 智能体会诊室」设置中配置大模型 API，委员会拒绝在无 AI 判断的情况下运行"
        try:
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                temperature=0
            )
            return None
        except Exception as e:
            return f"LLM 不可达: {e} — 本轮委员会已中止, 未生成任何决策与计划, 请检查中转服务后重试"

    # ==============================================================
    # 盘前准入 / 午间复检
    # ==============================================================

    def premarket_gate(self, stage: str = "premarket", force: bool = False) -> Dict[str, Any]:
        """
        逐只准入审查: 信用排雷(一票否决) + 条款博弈 + 正股动量。
        - reject: 信用 VETO，禁止进入交易池，已持仓的将在调仓中被卖出
        - watch : 信用 WARN 或强赎风险 HIGH，可继续持有但禁止新买入
        - approve: 进入真正交易池
        严格模式: LLM 未配置/不可达/审查失败 → 整轮中止，不生成决策与计划 (保留上一版计划)。
        审查与定价全部成功后，才标记当日完成并允许 auto_execute 调仓。
        :param force: 跳过休市检查 (仅限休市日手动测试，调度器永远不传)
        """
        with self._lock:
            # 0. 休市检查: 节假日/周末委员会不运行 (fail-safe: 日历不可用同样不跑)
            if not force and not is_trading_day():
                return {"success": False,
                        "message": "今日为休市日 (周末或法定假日)，委员会不运行。休市日测试可在请求中传 force=true"}

            # 1. LLM 预检: 失败即中止，绝不降级
            llm_err = self._ensure_llm_ready()
            if llm_err:
                print(f"[委员会] {llm_err}")
                return {"success": False, "message": llm_err}

            date = datetime.now().strftime("%Y-%m-%d")
            snapshot = get_fresh_snapshot()
            if snapshot is None or snapshot.empty:
                return {"success": False, "message": "实时行情快照不可用，准入中止 (保留昨日计划)"}

            candidates, strategy_name = self._resolve_candidates(snapshot)
            if not candidates:
                return {"success": False, "message": f"策略 [{strategy_name}] 选券结果为空，准入中止"}

            # 三分析师并行审查 — require_llm 严格模式: 单只失败其结果缺失，整轮中止
            from agents.credit_analyst import CreditAnalystAgent
            from agents.equity_analyst import EquityAnalystAgent
            from agents.clause_analyst import ClauseAnalystAgent

            credit = CreditAnalystAgent().batch_evaluate(candidates, require_llm=True)
            equity = EquityAnalystAgent().batch_evaluate(candidates, require_llm=True)
            clause = ClauseAnalystAgent().batch_evaluate(candidates, require_llm=True)

            missing = [c["bond_code"] for c in candidates
                       if not credit.get(c["bond_code"]) or not equity.get(c["bond_code"]) or not clause.get(c["bond_code"])]
            if missing:
                msg = f"LLM 审查不完整 ({len(missing)} 只失败: {missing[:5]}), 本轮中止, 未生成任何决策与计划"
                print(f"[委员会] {msg}")
                return {"success": False, "message": msg}

            results = []
            for cand in candidates:
                code = cand["bond_code"]
                c = credit.get(code, {})
                e = equity.get(code, {})
                g = clause.get(code, {})
                risk = str(c.get("risk_level", "PASS")).upper()
                call_risk = str(g.get("call_risk_level", "LOW")).upper()

                if risk == "VETO":
                    decision = "reject"
                    reason = str(c.get("reason", "信用风控一票否决"))
                elif risk == "WARN" or call_risk == "HIGH":
                    decision = "watch"
                    warn_src = c.get("reason") if risk == "WARN" else f"强赎风险等级 {call_risk}: {g.get('game_summary', '')}"
                    reason = str(warn_src or "风险关注，禁止新买入")
                else:
                    decision = "approve"
                    reason = f"动量评分 {e.get('momentum_score', 0):.0f}；{e.get('catalyst_summary', '')} {g.get('game_summary', '')}".strip()

                results.append({
                    "bond_code": code,
                    "bond_name": cand.get("bond_name", code),
                    "decision": decision,
                    "reason": reason[:300],
                    "review": {"credit": c, "equity": e, "clause": g}
                })

            self._save_decisions(date, stage, results)
            plan = self.build_price_plan(snapshot, stage=stage)
            if not plan.get("success"):
                # 定价失败: 决策结论已留痕, 但不标记当日完成 (调度器下轮重试)、不自动执行、保留旧计划
                msg = plan.get("message") or "AI 定价失败, 本轮中止 (保留原有计划)"
                print(f"[委员会] {stage} 定价失败: {msg}")
                return {
                    "success": False,
                    "message": msg,
                    "trade_date": date, "stage": stage, "strategy": strategy_name,
                    "candidates_count": len(results),
                    "approved": [r for r in results if r["decision"] == "approve"],
                    "watch": [r for r in results if r["decision"] == "watch"],
                    "rejected": [r for r in results if r["decision"] == "reject"],
                    "plan_count": 0,
                }
            self._mark_done("last_gate_date" if stage == "premarket" else "last_midday_date", date)

            print(f"[委员会] {stage} 准入完成: 策略[{strategy_name}] 候选{len(results)}只 → "
                  f"准入{sum(1 for r in results if r['decision'] == 'approve')} / "
                  f"观察{sum(1 for r in results if r['decision'] == 'watch')} / "
                  f"否决{sum(1 for r in results if r['decision'] == 'reject')}; 计划{plan.get('plan_count', 0)}条")

            return {
                "success": True,
                "trade_date": date,
                "stage": stage,
                "strategy": strategy_name,
                "candidates_count": len(results),
                "approved": [r for r in results if r["decision"] == "approve"],
                "watch": [r for r in results if r["decision"] == "watch"],
                "rejected": [r for r in results if r["decision"] == "reject"],
                "plan_count": plan.get("plan_count", 0),
                "pricing_warnings": plan.get("warnings", [])
            }

    def midday_review(self, force: bool = False) -> Dict[str, Any]:
        """午间复检: 重跑准入 + 用盘中现价重新定价，持仓触发卖出警示"""
        summary = self.premarket_gate(stage="midday", force=force)
        if summary.get("success"):
            alerts = self._collect_holding_alerts()
            summary["holding_alerts"] = alerts
        return summary

    def _save_decisions(self, date: str, stage: str, results: List[Dict[str, Any]]):
        session = SessionLocal()
        try:
            for r in results:
                row = session.query(CommitteeDecision).filter(
                    CommitteeDecision.trade_date == date,
                    CommitteeDecision.stage == stage,
                    CommitteeDecision.bond_code == r["bond_code"]
                ).first()
                if not row:
                    row = CommitteeDecision(trade_date=date, stage=stage, bond_code=r["bond_code"], created_at=datetime.now())
                    session.add(row)
                row.bond_name = r["bond_name"]
                row.decision = r["decision"]
                row.reason = r["reason"]
                row.review_json = json.dumps(r["review"], ensure_ascii=False)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _mark_done(self, field: str, date: str):
        session = SessionLocal()
        try:
            row = session.query(CommitteeState).filter(CommitteeState.id == 1).first()
            if not row:
                row = CommitteeState(id=1)
                session.add(row)
            setattr(row, field, date)
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    # ==============================================================
    # 约束式定价
    # ==============================================================

    def _price_bands(self, anchor: float) -> Dict[str, float]:
        """按昨收锚定计算约束区间"""
        return {
            "buy_low": round(anchor * (1 + settings.COMMITTEE_BUY_FLOOR_PCT), 3),
            "buy_high": round(anchor * (1 + settings.COMMITTEE_BUY_CAP_PCT), 3),
            "sell_low": round(anchor * (1 + settings.COMMITTEE_SELL_FLOOR_PCT), 3),
            "sell_high": round(anchor * (1 + settings.COMMITTEE_SELL_CAP_PCT), 3),
        }

    def _price_one(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        单只约束式定价: AI 在区间内选位并给理由，越界强制裁剪。
        严格模式: LLM 未配置或重试3次仍失败 → 抛异常, 由 build_price_plan 中止本轮 (保留旧计划)。
        task: {bond_code, bond_name, is_holding, decision, current_price, prev_close, premium_rate, remaining_scale, rating}
        """
        code = task["bond_code"]
        anchor = float(task.get("prev_close") or task.get("current_price") or 100.0)
        current = float(task.get("current_price") or anchor)
        bands = self._price_bands(anchor)
        is_holding = task.get("is_holding", False)
        decision = task.get("decision", "approve")

        # 强制卖出信号: 持仓进入强赎警戒区 (≥130) → 只卖不买
        force_sell = is_holding and current >= 130.0

        base = {
            "bond_code": code,
            "bond_name": task.get("bond_name", code),
            "is_holding": is_holding,
            "decision": decision,
            "prev_close": anchor,
            "current_price": current,
            **bands,
        }

        # 严格模式: LLM 未配置或重试3次仍失败 → 抛异常中止本轮 (绝不产出无 AI 判断的中性价计划)
        client, model = llm_manager.get_client()
        if not client:
            raise RuntimeError("LLM 未配置，委员会拒绝定价")

        last_err = None
        for attempt in range(3):
            try:
                decision_text = {"approve": "已准入(可买)", "watch": "观察(禁新买, 可持有)", "reject": "已否决(禁止交易)"}.get(decision, decision)
                prompt = f"""
你是可转债交易委员会的【执行定价委员】。请为以下标的制定今日限价交易计划。

【硬约束】(必须严格遵守，超出区间的报价会被系统强制裁剪):
- 买入限价区间: {bands['buy_low']:.2f} ~ {bands['buy_high']:.2f} 元
- 卖出限价区间: {bands['sell_low']:.2f} ~ {bands['sell_high']:.2f} 元
- 昨收锚定价: {anchor:.2f} 元

【标的信息】{task.get('bond_name', code)} ({code})
- 现价: {current:.2f} 元 | 转股溢价率: {task.get('premium_rate', 0)}% | 剩余规模: {task.get('remaining_scale', 0)} 亿 | 评级: {task.get('rating', 'AA')}
- 委员会准入结论: {decision_text}
- 是否已持仓: {'是' if is_holding else '否'}

【定价要求】
- 在区间内选择挂单位置: 激进(贴近现价易成交) / 中性(区间中位) / 防守(保护性价位)
- 已持仓标的需给出卖出保护价；未持仓标的需给出买入挂单价
{('- 该标的现价已达强赎警戒区(≥130元)，必须输出 action=SELL' if force_sell else '')}
- reason 用80字以内说明选位思路

请输出严格 JSON:
{{
    "action": "BUY" | "SELL" | "HOLD",
    "buy_limit_price": 买入挂单价(浮点, 必须在买入区间内, 不打算买入填 null),
    "sell_limit_price": 卖出挂单价(浮点, 必须在卖出区间内, 无卖出计划填 null),
    "reason": "定价逻辑说明"
}}
"""
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )
                data = extract_json_content(response.choices[0].message.content) or {}

                buy_p = data.get("buy_limit_price")
                sell_p = data.get("sell_limit_price")
                action = str(data.get("action", "HOLD")).upper()
                if action not in ("BUY", "SELL", "HOLD"):
                    action = "HOLD"

                buy_limit = self._clamp(buy_p, bands["buy_low"], bands["buy_high"]) if buy_p is not None else None
                sell_limit = self._clamp(sell_p, bands["sell_low"], bands["sell_high"]) if sell_p is not None else None

                # watch 禁新买 / 强制卖出约束
                if decision == "watch":
                    buy_limit = None
                    if action == "BUY":
                        action = "HOLD"
                if force_sell:
                    action = "SELL"
                    sell_limit = bands["sell_low"]

                # 兜底: action 与价格缺失自洽
                if action == "BUY" and buy_limit is None:
                    buy_limit = round((bands["buy_low"] + bands["buy_high"]) / 2, 3)
                if action == "SELL" and sell_limit is None:
                    sell_limit = round((bands["sell_low"] + bands["sell_high"]) / 2, 3)

                base.update({
                    "action": action,
                    "buy_limit_price": buy_limit,
                    "sell_limit_price": sell_limit,
                    "ai_priced": True,
                    "reason": str(data.get("reason", ""))[:300],
                })
                return base
            except Exception as e:
                last_err = e
                time.sleep(1.0 + attempt)

        raise RuntimeError(f"定价 LLM 调用失败(已重试3次): {last_err}")

    @staticmethod
    def _clamp(price: Any, low: float, high: float) -> Optional[float]:
        try:
            p = float(price)
        except (TypeError, ValueError):
            return None
        return round(max(low, min(high, p)), 3)

    def build_price_plan(self, snapshot, stage: str = "premarket") -> Dict[str, Any]:
        """
        为 交易池(准入+观察) + 全部持仓 生成当日限价计划 (每标的一条, upsert)。
        持仓标的同时给出卖出保护价；池内准入标的给出买入挂单价。
        """
        with self._lock:
            date = datetime.now().strftime("%Y-%m-%d")
            decisions = self.get_decision_map(date, stage=stage)
            if not decisions:
                # 无当日准入结论时回退任意已有阶段的结论 (手动触发前可能没跑过审查)
                decisions = self.get_decision_map(date)
            holdings = self._get_holding_symbols()
            price_map = get_current_price_map(snapshot)

            pool_codes = [c for c, d in decisions.items() if d in ("approve", "watch")]
            all_codes = list(dict.fromkeys(pool_codes + list(holdings.keys())))
            if not all_codes:
                return {"success": False, "plan_count": 0, "warnings": ["交易池与持仓均为空"]}

            prev_close_map = get_prev_close_map(all_codes)
            warnings: List[str] = []

            # 构造定价任务
            sub_snapshot = snapshot[snapshot["bond_code"].astype(str).isin(all_codes)] if snapshot is not None and not snapshot.empty else None
            meta_map: Dict[str, Dict[str, Any]] = {}
            if sub_snapshot is not None and not sub_snapshot.empty:
                for _, row in sub_snapshot.iterrows():
                    meta_map[str(row.get("bond_code", ""))] = {
                        "bond_name": str(row.get("bond_name", "") or ""),
                        "premium_rate": row.get("premium_rate", 0.0),
                        "remaining_scale": row.get("remaining_scale", 0.0),
                        "rating": row.get("rating", "AA"),
                    }

            tasks = []
            for code in all_codes:
                prev_close = prev_close_map.get(code)
                current = price_map.get(code)
                if prev_close is None and current is None:
                    warnings.append(f"{code}: 无昨收且无现价，跳过定价")
                    continue
                if prev_close is None:
                    warnings.append(f"{code}: 数据湖无昨收，以现价 {current} 为锚 (约束区间可能失真)")
                meta = meta_map.get(code, {})
                tasks.append({
                    "bond_code": code,
                    "bond_name": holdings.get(code) or meta.get("bond_name", code) or code,
                    "is_holding": code in holdings,
                    "decision": decisions.get(code, "approve"),
                    "current_price": current,
                    "prev_close": prev_close,
                    "premium_rate": meta.get("premium_rate", 0.0),
                    "remaining_scale": meta.get("remaining_scale", 0.0),
                    "rating": meta.get("rating", "AA"),
                })

            # parallel_batch_map 返回 {bond_code: 结果dict}; _price_one 严格模式下失败的标的结果缺失
            priced_map = parallel_batch_map(self._price_one, tasks)
            priced = [v for v in priced_map.values() if isinstance(v, dict) and v.get("bond_code")]
            failed_codes = [t["bond_code"] for t in tasks
                            if not isinstance(priced_map.get(t["bond_code"]), dict) or not priced_map.get(t["bond_code"])]
            if failed_codes:
                msg = (f"AI 定价不完整 ({len(failed_codes)}/{len(tasks)} 只失败: {failed_codes[:5]}), "
                       "本轮已中止, 未更新任何计划 (保留上一版 AI 计划)")
                print(f"[委员会] {msg}")
                return {"success": False, "plan_count": 0, "warnings": warnings, "message": msg}

            session = SessionLocal()
            try:
                for p in priced:
                    row = session.query(CommitteePricePlan).filter(
                        CommitteePricePlan.trade_date == date,
                        CommitteePricePlan.bond_code == p["bond_code"]
                    ).first()
                    if not row:
                        row = CommitteePricePlan(trade_date=date, bond_code=p["bond_code"])
                        session.add(row)
                    row.bond_name = p["bond_name"]
                    row.action = p["action"]
                    row.buy_limit_price = p["buy_limit_price"]
                    row.sell_limit_price = p["sell_limit_price"]
                    row.band_low = p["buy_low"]
                    row.band_high = p["sell_high"]
                    row.prev_close = p["prev_close"]
                    row.current_price = p["current_price"]
                    row.ai_priced = p["ai_priced"]
                    row.status = "pending"
                    row.reason = p["reason"]
                    row.stage = stage
                    row.updated_at = datetime.now()
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

            print(f"[委员会] 当日限价计划已生成 {len(priced)} 条 (stage={stage}, AI定价 {sum(1 for p in priced if p['ai_priced'])} 条)")
            return {"success": True, "plan_count": len(priced), "warnings": warnings}

    # ==============================================================
    # 盘中价格刷新 (每 30 分钟)
    # ==============================================================

    def price_refresh(self) -> Dict[str, Any]:
        """
        盘中刷新: 用实时快照更新计划现价与可成交状态 (不做 LLM 调用，轻量高频)。
        - BUY executable: 现价 ≤ 买入限价 (可按限价买入)
        - SELL executable: 现价 ≥ 卖出限价 (可按限价卖出)
        - missed: 现价越过约束上界 (买入错过，约束纪律不追价)
        - alert : 持仓现价跌破卖出下限 或 进入强赎警戒区
        """
        with self._lock:
            date = datetime.now().strftime("%Y-%m-%d")
            snapshot = get_fresh_snapshot()
            if snapshot is None or snapshot.empty:
                return {"success": False, "message": "实时快照不可用，保留现有计划"}

            price_map = get_current_price_map(snapshot)
            holdings = self._get_holding_symbols()
            session = SessionLocal()
            updated = 0
            alerts: List[str] = []
            try:
                rows = session.query(CommitteePricePlan).filter(CommitteePricePlan.trade_date == date).all()
                for row in rows:
                    cur = price_map.get(row.bond_code)
                    if cur is None:
                        continue
                    row.current_price = cur
                    row.updated_at = datetime.now()
                    bands = self._price_bands(float(row.prev_close or cur))
                    is_holding = row.bond_code in holdings

                    if row.action == "SELL" and row.sell_limit_price and cur >= row.sell_limit_price:
                        row.status = "executable"
                    elif row.action == "BUY" and row.buy_limit_price and cur <= row.buy_limit_price:
                        row.status = "executable"
                    elif row.action == "BUY" and cur > bands["buy_high"]:
                        row.status = "missed"
                    elif is_holding and (cur < bands["sell_low"] or cur >= 130.0):
                        row.status = "alert"
                        warn = "进入强赎警戒区(≥130)" if cur >= 130.0 else "跌破卖出约束下限"
                        alerts.append(f"{row.bond_name}({row.bond_code}): 现价 {cur:.2f} — {warn}")
                    else:
                        row.status = "pending"
                    updated += 1
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

            self._mark_refresh_time()
            print(f"[委员会] 盘中刷新完成: 更新 {updated} 条计划")
            return {"success": True, "updated": updated, "alerts": alerts}

    def _collect_holding_alerts(self) -> List[str]:
        """午间复检的持仓警示 (强赎区 / 计划卖出)"""
        date = datetime.now().strftime("%Y-%m-%d")
        alerts: List[str] = []
        session = SessionLocal()
        try:
            rows = session.query(CommitteePricePlan).filter(CommitteePricePlan.trade_date == date).all()
            for row in rows:
                if row.action == "SELL":
                    alerts.append(f"{row.bond_name}({row.bond_code}): 建议卖出 — {row.reason}")
        finally:
            session.close()
        return alerts

    def _mark_refresh_time(self):
        session = SessionLocal()
        try:
            row = session.query(CommitteeState).filter(CommitteeState.id == 1).first()
            if not row:
                row = CommitteeState(id=1)
                session.add(row)
            row.last_refresh_at = datetime.now()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def _expire_plans(self, date: str):
        session = SessionLocal()
        try:
            rows = session.query(CommitteePricePlan).filter(
                CommitteePricePlan.trade_date == date,
                CommitteePricePlan.status != "expired"
            ).all()
            for row in rows:
                row.status = "expired"
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    # ==============================================================
    # 查询接口 (供 ledger 执行与前端 API)
    # ==============================================================

    def get_decision_map(self, trade_date: str, stage: Optional[str] = None) -> Dict[str, str]:
        """{bond_code: decision}; 指定 stage 无记录时回退该日最新阶段"""
        session = SessionLocal()
        try:
            q = session.query(CommitteeDecision).filter(CommitteeDecision.trade_date == trade_date)
            if stage:
                q = q.filter(CommitteeDecision.stage == stage)
            rows = q.all()
            if not rows and stage:
                rows = session.query(CommitteeDecision).filter(
                    CommitteeDecision.trade_date == trade_date).all()
            return {r.bond_code: r.decision for r in rows}
        finally:
            session.close()

    def get_plan_map(self, trade_date: str) -> Dict[str, Dict[str, Any]]:
        """{bond_code: {action, buy_limit_price, sell_limit_price, ai_priced}} — 供执行器取限价"""
        session = SessionLocal()
        try:
            rows = session.query(CommitteePricePlan).filter(CommitteePricePlan.trade_date == trade_date).all()
            return {
                r.bond_code: {
                    "action": r.action,
                    "buy_limit_price": r.buy_limit_price,
                    "sell_limit_price": r.sell_limit_price,
                    "ai_priced": bool(r.ai_priced),
                } for r in rows
            }
        finally:
            session.close()

    def get_today_overview(self) -> Dict[str, Any]:
        """前端面板聚合: 状态 + 当日各阶段决策 + 价格计划"""
        date = datetime.now().strftime("%Y-%m-%d")
        state = self.get_state()
        session = SessionLocal()
        try:
            decisions = [r.to_dict() for r in session.query(CommitteeDecision)
                         .filter(CommitteeDecision.trade_date == date)
                         .order_by(CommitteeDecision.id.asc()).all()]
            plans = [r.to_dict() for r in session.query(CommitteePricePlan)
                     .filter(CommitteePricePlan.trade_date == date)
                     .order_by(CommitteePricePlan.id.asc()).all()]
        finally:
            session.close()
        return {
            "trade_date": date,
            "state": state,
            "scheduler_running": bool(self._thread and self._thread.is_alive()),
            "decisions": decisions,
            "plans": plans,
        }

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        session = SessionLocal()
        try:
            rows = session.query(CommitteeDecision).order_by(
                CommitteeDecision.created_at.desc()).limit(limit).all()
            return [r.to_dict() for r in rows]
        finally:
            session.close()

    # ==============================================================
    # 自动执行
    # ==============================================================

    def _execute_plans(self, force: bool = False) -> List[Dict[str, Any]]:
        """对绑定策略的账号触发调仓 (ledger 自动采用委员会限价与准入过滤)
        force=True 时无视 auto_execute 开关 (手动触发执行)"""
        from core.trading_ledger import ledger

        state = self.get_state()
        if not force and not state.get("auto_execute"):
            return []
        bound = (state.get("bound_strategy") or "").strip()
        accounts = ledger.get_accounts()
        results = []
        for acc in accounts:
            if acc.get("status") in ("ENDED", "IDLE"):
                continue
            if bound and (acc.get("associated_strategy") or "") != bound:
                continue
            try:
                res = ledger.trigger_paper_rebalance(acc.get("account_id"))
                res["account_id"] = acc.get("account_id")
                res["account_name"] = acc.get("account_name")
                results.append(res)
            except Exception as e:
                print(f"[ERROR] 委员会自动调仓 {acc.get('account_id')} 失败: {e}")
                results.append({"account_id": acc.get("account_id"), "success": False, "message": str(e)})
        if results:
            self._mark_done("last_execute_date", datetime.now().strftime("%Y-%m-%d"))
        return results

    def execute_now(self) -> List[Dict[str, Any]]:
        """手动强制按当日委员会计划执行调仓"""
        with self._lock:
            return self._execute_plans(force=True)

    # ==============================================================
    # 后台调度线程
    # ==============================================================

    def start_scheduler(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, name="committee-scheduler", daemon=True)
        self._thread.start()
        print("[委员会] 后台调度线程已启动 (09:15准入 / 每30分钟刷新 / 11:35复检 / 15:00归档)")

    def stop_scheduler(self):
        self._stop_event.set()

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                print(f"[ERROR] 交易委员会调度异常: {e}")
            self._stop_event.wait(60)

    def _tick(self):
        state = self.get_state()
        if not state.get("enabled"):
            return
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        # 交易日历检查: 周末与法定假日一律不运行 (连 LLM 预检也不做, 不空耗)
        if not is_trading_day(date):
            return
        hm = now.strftime("%H:%M")
        gate_t = settings.COMMITTEE_GATE_TIME      # 09:15
        midday_t = settings.COMMITTEE_MIDDAY_TIME  # 11:35
        close_t = "15:00"
        if hm < gate_t:
            return

        # 1. 盘前准入 (每日一次; 失败不标记完成, 下轮重试, 且不触发自动执行)
        if state.get("last_gate_date") != date:
            gate_res = self.premarket_gate(stage="premarket")
            if gate_res.get("success") and self.get_state().get("auto_execute"):
                self._execute_plans()
            return  # 一轮 tick 只做一件事，避免与刷新叠加阻塞

        # 2. 午间复检 (每日一次; 失败不标记完成, 下轮重试, 且不触发自动执行)
        if gate_t <= hm < close_t and hm >= midday_t and state.get("last_midday_date") != date:
            midday_res = self.midday_review()
            if midday_res.get("success") and self.get_state().get("auto_execute"):
                self._execute_plans()
            return

        # 3. 盘中每 30 分钟价格刷新
        in_session = ("09:30" <= hm <= "11:35") or ("12:55" <= hm <= close_t)
        if in_session:
            last = state.get("last_refresh_at")
            need_refresh = True
            if last:
                try:
                    last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                    need_refresh = (now - last_dt).total_seconds() >= settings.COMMITTEE_REFRESH_MINUTES * 60
                except ValueError:
                    need_refresh = True
            if need_refresh:
                self.price_refresh()

        # 4. 收盘归档
        if hm >= close_t and state.get("last_gate_date") == date:
            self._expire_plans(date)


committee = TradingCommittee()
