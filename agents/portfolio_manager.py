"""
投资总监决策智能体 (Portfolio Manager Node)
投资总监（PM）：汇聚信用排雷、正股动量与条款博弈三方汇报，
严格执行信用一票否决，进行综合打分加权，生成最终 Top 10~15 投资组合、
AI 动态价格点（买入上限/目标止盈/强赎防线/追踪回撤）及执行报告。
"""

import json
from typing import List, Dict, Any, Tuple, Optional
from config.config import settings
from core.state import (
    BondCandidate,
    CreditRiskResult,
    EquityMomentumResult,
    ClauseGameResult,
    PortfolioItem,
    DynamicPriceTarget
)

class ArbitrateResult(tuple):
    """兼容三元组拆包的复合仲裁结果"""
    def __new__(cls, portfolio, vetoed_bonds, report, dynamic_targets):
        obj = super().__new__(cls, (portfolio, vetoed_bonds, report))
        obj.portfolio = portfolio
        obj.vetoed_bonds = vetoed_bonds
        obj.report = report
        obj.dynamic_targets = dynamic_targets
        return obj

class PortfolioManagerAgent:
    """投资总监决策与组合配置 Agent"""

    def __init__(self, top_n: int = settings.PORTFOLIO_TOP_N):
        self.top_n = top_n
        self.dynamic_targets: Dict[str, DynamicPriceTarget] = {}

    def arbitrate_and_allocate(
        self,
        candidates: List[BondCandidate],
        credit_reviews: Dict[str, CreditRiskResult],
        equity_reviews: Dict[str, EquityMomentumResult],
        clause_reviews: Dict[str, ClauseGameResult]
    ) -> ArbitrateResult:
        """
        仲裁决策并分配最终持仓与动态价格带
        :return: ArbitrateResult(portfolio, vetoed_bonds, report, dynamic_targets)
        """
        final_candidates: List[Tuple[float, BondCandidate, str, int]] = []
        vetoed_bonds: List[Dict[str, str]] = []
        dynamic_targets: Dict[str, DynamicPriceTarget] = {}

        for c in candidates:
            code = c["bond_code"]
            name = c["bond_name"]
            price = float(c.get("price", 100.0))
            
            credit = credit_reviews.get(code, {"risk_level": "PASS", "reason": "无异常"})
            equity = equity_reviews.get(code, {"momentum_score": 50.0, "catalyst_summary": "平稳"})
            clause = clause_reviews.get(code, {"down_revision_potential": 50.0, "game_summary": "平稳"})

            is_veto = (credit.get("risk_level") == "VETO")
            momentum_score = float(equity.get("momentum_score", 50.0))
            clause_score = float(clause.get("down_revision_potential", 50.0))

            # ====================================================
            # 模式 1: 测算该标的的个性化 AI 动态价格带 (Dynamic Price Targets)
            # ====================================================
            if is_veto:
                entry_ceiling = 0.0
                target_price = 0.0
                hard_stop_price = 0.0
                trailing_stop_drop = 0.0
                rationale = f"一票否决拦截: {credit.get('reason', '基本面风险')}"
            else:
                # 建议买入价格上限: 101.0 ~ 105.5元 (下修意愿越强，大股东越有动力托底，入场容忍度越高)
                entry_ceiling = round(101.0 + (clause_score / 100.0) * 4.5, 2)
                # 建议第一目标止盈价: 116.0 ~ 126.0元 (正股动量越强，弹性空间越大)
                target_price = round(116.0 + (momentum_score / 100.0) * 10.0, 2)
                # 强赎硬避险警戒线: 默认 128.0 元 (若现价已贴近则为 129.5 元)
                hard_stop_price = 129.5 if price >= 126.0 else 128.0
                # 追踪止盈高点回撤容忍度: 2.0% ~ 3.5%
                trailing_stop_drop = round(0.020 + (momentum_score / 100.0) * 0.015, 3)
                rationale = (
                    f"建议建仓上限 {entry_ceiling}元 (下修博弈 {int(clause_score)}分)；"
                    f"第一止盈位 {target_price}元 (正股动量 {int(momentum_score)}分)；"
                    f"强赎防线 {hard_stop_price}元；高点追踪容忍度 {round(trailing_stop_drop*100, 1)}%"
                )

            dynamic_targets[code] = {
                "bond_code": code,
                "bond_name": name,
                "entry_ceiling": entry_ceiling,
                "target_price": target_price,
                "hard_stop_price": hard_stop_price,
                "trailing_stop_drop": trailing_stop_drop,
                "veto": is_veto,
                "rationale": rationale
            }

            # ====================================================
            # 模式 2: 信用一票否决门禁 (VETO)
            # ====================================================
            if is_veto:
                vetoed_bonds.append({
                    "bond_code": code,
                    "bond_name": name,
                    "veto_reason": credit.get("reason", "信用排雷否决")
                })
                continue

            # ====================================================
            # 多维度综合加权打分 (Composite Scoring)
            # ====================================================
            double_low_score = max(0.0, 150.0 - float(c.get("double_low", 100.0)))
            composite_score = (double_low_score * 0.40) + (momentum_score * 0.35) + (clause_score * 0.25)

            if credit.get("risk_level") == "WARN":
                composite_score -= 15.0

            stars = 5 if composite_score >= 80 else (4 if composite_score >= 65 else 3)
            
            verdict = (
                f"双低值 {c.get('double_low', '-')} 具备优异安全垫；"
                f"{equity.get('catalyst_summary', '动量中性')}；"
                f"{clause.get('game_summary', '条款防御性良好')}"
            )

            final_candidates.append((composite_score, c, verdict, stars))

        # 按综合得分降序排列，截取 Top N
        final_candidates.sort(key=lambda x: x[0], reverse=True)
        selected = final_candidates[:self.top_n]

        portfolio: List[PortfolioItem] = []
        n = len(selected)
        weight = round(1.0 / n, 4) if n > 0 else 0.0

        for score, c, verdict, stars in selected:
            b_code = c["bond_code"]
            portfolio.append({
                "bond_code": b_code,
                "bond_name": c["bond_name"],
                "price": float(c["price"]),
                "double_low": float(c.get("double_low", 0.0)),
                "weight": weight,
                "rating_stars": stars,
                "pm_verdict": verdict,
                "dynamic_targets": dynamic_targets.get(b_code)
            })

        self.dynamic_targets = dynamic_targets

        # 生成结构化投研报告 (附带 AI 动态价格带建议)
        report = self._build_markdown_report(portfolio, vetoed_bonds, dynamic_targets)
        return ArbitrateResult(portfolio, vetoed_bonds, report, dynamic_targets)

    def _build_markdown_report(
        self,
        portfolio: List[PortfolioItem],
        vetoed_bonds: List[Dict[str, str]],
        dynamic_targets: Dict[str, DynamicPriceTarget]
    ) -> str:
        lines = [
            "# 📑 A股可转债多智能体投研与组合内参\n",
            f"**推荐持仓数量**：{len(portfolio)} 只 | **单只配置权重**：{round(portfolio[0]['weight']*100, 2) if portfolio else 0}%\n",
            "## 🏆 今日推荐买入/持有组合\n",
            "| 转债代码 | 转债名称 | 现价(元) | 双低值 | 权重 | 推荐星级 | PM 投研裁决依据 |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for p in portfolio:
            stars_str = "⭐" * p["rating_stars"]
            lines.append(f"| {p['bond_code']} | {p['bond_name']} | {p['price']} | {p['double_low']} | {round(p['weight']*100, 1)}% | {stars_str} | {p['pm_verdict']} |")

        if portfolio:
            lines.append("\n## 🎯 AI 智能体动态量化定价与点位建议 (随时买卖价格点)\n")
            lines.append("| 转债代码 | 转债名称 | 现价 | 建议建仓上限 | 建议第一止盈 | 强赎防线 | 高点追踪回撤 | 定价推演依据 |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for p in portfolio:
                dt = dynamic_targets.get(p["bond_code"])
                if dt:
                    lines.append(
                        f"| {dt['bond_code']} | {dt['bond_name']} | {p['price']}元 | "
                        f"**≤ {dt['entry_ceiling']}元** | **≥ {dt['target_price']}元** | "
                        f"{dt['hard_stop_price']}元 | {round(dt['trailing_stop_drop']*100, 1)}% | "
                        f"{dt['rationale']} |"
                    )

        if vetoed_bonds:
            lines.append("\n## 🚫 今日信用排雷一票否决名单\n")
            lines.append("| 转债代码 | 转债名称 | 否决拦截理由 |")
            lines.append("| :--- | :--- | :--- |")
            for v in vetoed_bonds:
                lines.append(f"| {v['bond_code']} | {v['bond_name']} | {v['veto_reason']} |")

        return "\n".join(lines)
