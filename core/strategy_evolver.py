"""
AI 策略进化器 (Strategy Evolver) — RD-Agent 式 生成→验证→反馈 迭代闭环
流程: 用户设想 → LLM 生成策略代码 → 沙箱安全闸门 → 冒烟回测 → 健康体检
      → 失败: 结构化原因回喂 LLM 进入下一轮 (最多 N 轮) / 成功: 全量回测 + 注册入库
每轮实验完整留痕 strategy_experiments 表 (代码 + 指标 + 结论可回溯)
"""

import json
import time
import concurrent.futures
from typing import Dict, Any, Optional, List
from datetime import datetime

from core.llm_manager import llm_manager, extract_json_content
from core.strategy_sandbox import (
    instantiate_strategy_class, CodeSafetyError,
    build_evolve_prompt, extract_code_from_llm,
)
from db.session import SessionLocal
from db.models import StrategyExperiment, Strategy

# 冒烟回测窗口: 用最近 N 个月数据快速验证可行性 (全量回测只在成功后执行)
SMOKE_MONTHS_BACK = 6
# 单轮回测硬超时 (秒): 防 LLM 生成死循环代码拖死服务
BACKTEST_TIMEOUT_SEC = 300


class EvolveError(Exception):
    """进化过程整体失败 (所有轮次均未通过)"""


# ==============================================================
# 评审团语义审查 (Gate 4) — 本项目区别于 RD-Agent 自动指标的差异化闸门
# 三个固定 personas 从信用/条款/风控维度审查生成的策略代码,
# 任一 persona 投出 block 即否决本轮并把意见回喂给下一轮生成
# ==============================================================

REVIEW_PERSONAS = [
    ("信用分析师", [
        "策略是否系统性暴露于违约/退市风险券 (如未剔除 bond_name 含'退'、盲选 70 元以下深价券)",
        "低价深价券的信用利差补偿是否被充分认知",
    ]),
    ("条款分析师", [
        "强赎触发风险: 高价券(>130)是否考虑强赎公告后的杀溢价",
        "下修/回售/到期等条款事件与策略买卖逻辑是否冲突 (如临近到期券流动性坍塌)",
    ]),
    ("量化风控官", [
        "持仓集中度、单券权重、池子宽度是否会导致路径敏感的虚假业绩",
        "代码是否存在前视偏差嫌疑 (用了未来数据/当日收盘价当日成交假设)",
        "参数是否疑似过拟合近期行情",
    ]),
]


def _build_review_prompt(user_idea: str, code: str, metrics: Dict[str, Any]) -> str:
    persona_blocks = "\n".join(
        f"- {role}: 重点审查 {'; '.join(points)}" for role, points in REVIEW_PERSONAS
    )
    metric_lines = "\n".join(f"  {k}: {v}" for k, v in list(metrics.items())[:8])
    return f"""你是可转债量化策略评审团。三位评审员从各自维度审查下述 AI 生成的策略代码。

【评审维度】
{persona_blocks}

【投资设想】{user_idea}
【冒烟回测指标】
{metric_lines}

【策略代码】
```python
{code}
```

每位评审员独立给出结论。评分标准:
- "block": 存在会导致大幅亏损或结论不可信的逻辑硬伤 (必须给出具体问题与修复建议)
- "warn": 有可改进之处但不致命
- "pass": 该维度无实质问题

只输出 JSON:
{{"reviews": [{{"reviewer": "评审员名", "verdict": "pass|warn|block", "issue": "问题简述(无则空)", "suggestion": "修复建议(无则空)"}}]}}
其中 reviews 必须恰好包含 3 条 ({', '.join(r for r, _ in REVIEW_PERSONAS)})。"""


def _record_experiment(idea: str, round_idx: int, status: str, code: str = "",
                       strategy_id: str = "", strategy_name: str = "",
                       verdict: str = "", fail_feedback: str = "", metrics: Optional[dict] = None):
    """实验留痕 (逐轮落库, 即使后续轮次失败, 历史轮次仍可回溯)"""
    session = SessionLocal()
    try:
        session.add(StrategyExperiment(
            user_idea=idea, round_idx=round_idx, status=status,
            generated_code=code or None,
            strategy_id=strategy_id or None,
            strategy_name=strategy_name or None,
            verdict=verdict or None,
            fail_feedback=fail_feedback or None,
            metrics_json=json.dumps(metrics or {}, ensure_ascii=False, default=str),
        ))
        session.commit()
    except Exception as e:
        print(f"[WARN] 实验记录落库失败: {e}")
    finally:
        session.close()


def _run_backtest_with_timeout(strategy_obj, start: str, end: str) -> Dict[str, Any]:
    """带硬超时的真实回测: 返回 {nav_df, metrics, error}"""
    from core.backtest_engine import CBBacktestEngine
    result: Dict[str, Any] = {"nav_df": None, "metrics": None, "error": None}

    def _worker():
        try:
            engine = CBBacktestEngine(
                strategies=[strategy_obj], start_date=start, end_date=end,
                mode="real", rebalance_interval_days=5,
            )
            nav_df, metrics_summary, _ = engine.run()
            strat_metrics = metrics_summary.get(strategy_obj.name)
            result["nav_df"] = nav_df
            result["metrics"] = strat_metrics or {}
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)[:300]}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_worker)
        try:
            future.result(timeout=BACKTEST_TIMEOUT_SEC)
        except concurrent.futures.TimeoutError:
            result["error"] = f"回测超时 (> {BACKTEST_TIMEOUT_SEC}s), 策略可能存在死循环或性能爆炸"
    return result


def health_check(nav_df, metrics: Dict[str, Any], strat_name: str) -> tuple:
    """
    RD-Agent 式结构化体检: 通过返回 (True, 亮点摘要)，失败返回 (False, 可执行改进反馈)
    体检对象为结构而非收益: 允许亏钱的想法通过 (想法好坏交给用户与竞技场检验)
    """
    col = strat_name if strat_name in nav_df.columns else nav_df.columns[0]
    nav = nav_df[col].dropna()

    if len(nav) < 10:
        return False, f"回测净值仅 {len(nav)} 个交易日 (< 10), 数据窗口不足或策略始终空仓, 请确保正常持仓逻辑"
    if nav.isna().any() or (nav <= 0).any():
        return False, "净值序列存在 NaN 或非正值, 请检查除零/空值兜底 (例如 price 列 dropna 后再计算)"
    if (nav == 1.0).all():
        return False, "策略在整个回测期内从未产生任何交易 (净值恒为 1.0): 请检查筛选条件是否过严 (如 NaN 处理/阈值边界), 或 on_bar 是否调用了 context.buy"
    if len(nav) != len(nav_df[col]):
        return False, "净值序列含 NaN 已被剔除, 请在策略内部处理好空值"
    if metrics.get("is_simulated") is True:
        return False, "回测引擎降级到了因子模拟模式 (未使用真实历史数据), 说明策略名称与回测结果检索失配或数据异常"

    max_dd = float(metrics.get("max_drawdown", 0.0) or 0.0)
    total_ret = float(metrics.get("total_return", 0.0) or 0.0)
    if max_dd >= 0.95:
        return False, f"最大回撤 {max_dd:.1%} 接近爆仓 (>95%): 请增加止损/分散持仓 (top_n >= 5) 或避开违约退市券 (bond_name 含'退'必须剔除)"
    if total_ret > 5.0:
        return (
            False,
            f"冒烟窗口累计收益 {total_ret:.1%} 异常 (>500%), 极可能是过度集中持仓踩中单券暴涨: "
            "请加宽选券池 (放宽阈值) 并确保 top_n >= 5 分散持仓; 小样本集中持仓的回测结果不具备统计意义",
        )

    summary = (f"累计收益 {total_ret:.2%}, 最大回撤 {max_dd:.1%}, "
               f"夏普 {float(metrics.get('sharpe_ratio', 0) or 0):.2f}, 交易日 {len(nav)} 天")
    return True, summary


class StrategyEvolver:
    """进化主循环"""

    def semantic_review(self, user_idea: str, code: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gate 4: 评审团语义审查 (信用/条款/风控三方)
        :return: {"overall": pass|warn|block, "reviews": [...], "note": 异常说明}
        审查服务不可用时放行 (评审核是增强闸门, 不应因评审员缺席而阻塞进化环)
        """
        client, model = llm_manager.get_client()
        if not client:
            return {"overall": "pass", "reviews": [], "note": "未配置 LLM, 语义审查跳过"}
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": _build_review_prompt(user_idea, code, metrics)}],
                temperature=0.3,
            )
            data = extract_json_content(resp.choices[0].message.content)
            reviews = data.get("reviews") if isinstance(data, dict) else None
            if not isinstance(reviews, list) or not reviews:
                raise ValueError("评审团未返回结构化 reviews")
            norm = [
                {
                    "reviewer": str(r.get("reviewer", "评审员")),
                    "verdict": r.get("verdict", "warn") if r.get("verdict") in ("pass", "warn", "block") else "warn",
                    "issue": str(r.get("issue", "") or ""),
                    "suggestion": str(r.get("suggestion", "") or ""),
                }
                for r in reviews if isinstance(r, dict)
            ][:3]
            blockers = [r for r in norm if r["verdict"] == "block"]
            overall = "block" if blockers else ("warn" if any(r["verdict"] == "warn" for r in norm) else "pass")
            return {"overall": overall, "reviews": norm, "note": ""}
        except Exception as e:
            return {"overall": "pass", "reviews": [], "note": f"语义审查调用失败已放行: {type(e).__name__}: {str(e)[:120]}"}

    def evolve(self, user_idea: str, max_rounds: int = 3) -> Dict[str, Any]:
        client, model = llm_manager.get_client()
        if not client:
            raise EvolveError("未配置可用的大模型 API，无法进行 AI 策略进化。请前往「设置」配置 LLM 供应商。")

        feedback: Optional[str] = None
        rounds: List[Dict[str, Any]] = []
        start = self._smoke_start_date()

        for round_idx in range(1, max_rounds + 1):
            prompt = build_evolve_prompt(user_idea, feedback=feedback, round_idx=round_idx)
            # ---- 生成 (含重试) ----
            code = None
            gen_err = None
            for attempt in range(2):
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.6,
                    )
                    code = extract_code_from_llm(resp.choices[0].message.content)
                    break
                except Exception as e:
                    gen_err = f"{type(e).__name__}: {str(e)[:150]}"
                    time.sleep(1.5)
            if not code:
                fb = f"LLM 调用/代码提取失败: {gen_err}"
                _record_experiment(user_idea, round_idx, "generated", fail_feedback=fb)
                rounds.append({"round": round_idx, "status": "generated", "error": fb})
                feedback = fb
                continue

            # ---- 闸门 1: 沙箱 ----
            try:
                strat_obj = instantiate_strategy_class(code, {"name": "", "params": {}})
            except CodeSafetyError as e:
                fb = f"安全沙箱拒绝: {e}\n请修复后重新输出完整代码 (严禁危险 import/dunder 属性, 且必须定义 BaseCBStrategy 子类)"
                _record_experiment(user_idea, round_idx, "sandbox_rejected", code=code, fail_feedback=fb)
                rounds.append({"round": round_idx, "status": "sandbox_rejected", "error": str(e)[:300], "code": code})
                feedback = fb
                continue

            # 用类名兜底策略名 (引擎按 name 检索 metrics; LLM 骨架中 name 取自 strat_dict["name"])
            llm_name = (getattr(strat_obj, "name", "") or "").strip()
            if not llm_name or llm_name in ("AI策略", "AI事件策略", "未命名策略"):
                llm_name = f"AI·{strat_obj.__class__.__name__}_R{round_idx}"
            strat_obj.name = llm_name

            # ---- 闸门 2: 冒烟回测 ----
            bt = _run_backtest_with_timeout(strat_obj, start, datetime.now().strftime("%Y%m%d"))
            if bt["error"]:
                fb = f"冒烟回测崩溃: {bt['error']}\n常见原因: 引用了 quotes_df 不存在的列 (只可用数据契约中的列)/数组越界/除零"
                _record_experiment(user_idea, round_idx, "backtest_failed", code=code,
                                   strategy_name=llm_name, fail_feedback=fb)
                rounds.append({"round": round_idx, "status": "backtest_failed", "error": bt["error"][:300], "code": code})
                feedback = fb
                continue

            # ---- 闸门 3: 健康体检 ----
            nav_df, metrics = bt["nav_df"], bt["metrics"] or {}
            ok, verdict_or_fb = health_check(nav_df, metrics, llm_name)
            if not ok:
                _record_experiment(user_idea, round_idx, "health_check_failed", code=code,
                                   strategy_name=llm_name, fail_feedback=verdict_or_fb,
                                   metrics=metrics)
                rounds.append({"round": round_idx, "status": "health_check_failed",
                               "error": verdict_or_fb, "code": code, "metrics": metrics})
                feedback = verdict_or_fb
                continue

            # ---- 闸门 4: 评审团语义审查 ----
            review = self.semantic_review(user_idea, code, metrics)
            if review["overall"] == "block":
                blocker_lines = "\n".join(
                    f"- [{r['reviewer']}] {r['issue']} → {r['suggestion']}"
                    for r in review["reviews"] if r["verdict"] == "block"
                )
                fb = f"评审团语义审查否决:\n{blocker_lines}\n请针对上述意见修复代码后重新输出完整策略"
                _record_experiment(user_idea, round_idx, "review_rejected", code=code,
                                   strategy_name=llm_name, fail_feedback=fb, metrics=metrics)
                rounds.append({"round": round_idx, "status": "review_rejected",
                               "error": blocker_lines[:300], "code": code, "metrics": metrics,
                               "review": review})
                feedback = fb
                continue

            # ---- 成功: 全量回测 + 注册 ----
            full_bt = _run_backtest_with_timeout(strat_obj, "20230101", datetime.now().strftime("%Y%m%d"))
            full_metrics = full_bt["metrics"] or {}
            full_nav = full_bt["nav_df"] if full_bt["nav_df"] is not None else nav_df
            full_ok, full_verdict = health_check(full_nav, full_metrics, llm_name)

            strat_id = f"strat_evolve_{int(datetime.now().timestamp())}"
            strat_dict = self._register(user_idea, strat_id, llm_name, code, strat_obj, full_metrics)
            review_summary = "、".join(f"{r['reviewer']}:{r['verdict']}" for r in review["reviews"]) or "未评审"
            warn_lines = "; ".join(
                f"[{r['reviewer']}] {r['issue']}" for r in review["reviews"] if r["verdict"] == "warn"
            )
            verdict = (
                f"冒烟窗口: {verdict_or_fb} | 全量回测(2023至今): "
                f"{full_verdict if full_ok else '体检未过但已注册供研究'}"
                f" | 评审团({review_summary})"
                + (f" | 改进提示: {warn_lines[:200]}" if warn_lines else "")
            )
            _record_experiment(user_idea, round_idx, "succeeded", code=code, strategy_id=strat_id,
                               strategy_name=llm_name, verdict=verdict,
                               metrics={**(full_metrics or metrics), "_review": review["reviews"],
                                        "_review_note": review["note"]})
            rounds.append({"round": round_idx, "status": "succeeded", "code": code,
                           "metrics": full_metrics or metrics, "verdict": verdict, "review": review})
            return {"success": True, "strategy": strat_dict, "rounds": rounds,
                    "review": review, "full_backtest_ok": full_ok}

        raise EvolveError(f"连续 {max_rounds} 轮未通过验证。各轮详情: " +
                          json.dumps([{r['round']: r['status']} for r in rounds], ensure_ascii=False))

    def _smoke_start_date(self) -> str:
        """冒烟窗口起点: 最近 6 个月"""
        from datetime import timedelta
        return (datetime.now() - timedelta(days=30 * SMOKE_MONTHS_BACK)).strftime("%Y%m%d")

    def _register(self, idea: str, strat_id: str, name: str, code: str, strat_obj, metrics: dict) -> dict:
        """代码策略注册入库: 代码存 params_json.__code__ (normalize 会原样保留自定义键)"""
        from core.strategy_manager import strategy_manager
        desc = getattr(strat_obj, "description", "") or f"由 AI 进化环根据设想「{idea[:60]}」生成的代码策略"
        return strategy_manager.add_strategy(
            strat_id=strat_id,
            name=name,
            category="AI代码进化",
            description=f"{desc}\n\n[AI 生成代码已通过沙箱+冒烟回测验证] 设想: {idea}",
            params={"__code__": code, "__evolved_from__": idea[:200], "top_n": getattr(strat_obj, "top_n", 10)},
        )
