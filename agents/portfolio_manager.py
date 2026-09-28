"""
投资总监决策智能体 (Portfolio Manager Node)
投资总监（PM）：汇聚信用排雷、正股动量与条款博弈三方汇报，
严格执行信用一票否决，进行综合打分加权，生成最终 Top 10~15 投资组合及执行报告。
"""

import json
from typing import List, Dict, Any, Tuple
from config.config import settings
from core.state import (
    BondCandidate,
    CreditRiskResult,
    EquityMomentumResult,
    ClauseGameResult,
    PortfolioItem
)

class PortfolioManagerAgent:
    """投资总监决策与组合配置 Agent"""

    def __init__(self, top_n: int = settings.PORTFOLIO_TOP_N):
        self.top_n = top_n

    def arbitrate_and_allocate(
        self,
        candidates: List[BondCandidate],
        credit_reviews: Dict[str, CreditRiskResult],
        equity_reviews: Dict[str, EquityMomentumResult],
        clause_reviews: Dict[str, ClauseGameResult]
    ) -> Tuple[List[PortfolioItem], List[Dict[str, str]], str]:
        """
        仲裁决策并分配最终持仓
        :return: (final_portfolio, vetoed_bonds, markdown_report)
        """
        final_candidates: List[Tuple[float, BondCandidate, str, int]] = []
        vetoed_bonds: List[Dict[str, str]] = []

        for c in candidates:
            code = c["bond_code"]
            name = c["bond_name"]
            
            credit = credit_reviews.get(code, {"risk_level": "PASS", "reason": "无异常"})
            equity = equity_reviews.get(code, {"momentum_score": 50.0, "catalyst_summary": "平稳"})
            clause = clause_reviews.get(code, {"down_revision_potential": 50.0, "game_summary": "平稳"})

            # ========================
            # 1. 信用一票否决门禁 (VETO)
            # ========================
            if credit["risk_level"] == "VETO":
                vetoed_bonds.append({
                    "bond_code": code,
                    "bond_name": name,
                    "veto_reason": credit["reason"]
                })
                continue

            # ========================
            # 2. 多维度综合加权打分 (Composite Scoring)
            # ========================
            # 双低性价比得分 (双低越低分越高，基准双低100分设为80分基准)
            double_low_score = max(0.0, 150.0 - c["double_low"])
            
            # 正股进攻动量得分
            momentum_score = equity["momentum_score"]
            
            # 条款博弈加分
            clause_score = clause["down_revision_potential"]

            # 综合得分: 双低底座(40%) + 进攻动量(35%) + 条款催化(25%)
            composite_score = (double_low_score * 0.40) + (momentum_score * 0.35) + (clause_score * 0.25)

            # 若信用风控为 WARN，扣除 15 分惩罚分
            if credit["risk_level"] == "WARN":
                composite_score -= 15.0

            # 星级评定 (3~5 星)
            stars = 5 if composite_score >= 80 else (4 if composite_score >= 65 else 3)
            
            verdict = (
                f"双低值 {c['double_low']} 具备优异安全垫；"
                f"{equity['catalyst_summary']}；"
                f"{clause['game_summary']}"
            )

            final_candidates.append((composite_score, c, verdict, stars))

        # 3. 按综合得分降序排列，截取 Top N
        final_candidates.sort(key=lambda x: x[0], reverse=True)
        selected = final_candidates[:self.top_n]

        # 4. 计算等权分配权重
        portfolio: List[PortfolioItem] = []
        n = len(selected)
        weight = round(1.0 / n, 4) if n > 0 else 0.0

        for score, c, verdict, stars in selected:
            portfolio.append({
                "bond_code": c["bond_code"],
                "bond_name": c["bond_name"],
                "price": c["price"],
                "double_low": c["double_low"],
                "weight": weight,
                "rating_stars": stars,
                "pm_verdict": verdict
            })

        # 5. 生成结构化投研报告
        report = self._build_markdown_report(portfolio, vetoed_bonds)
        return portfolio, vetoed_bonds, report

    def _build_markdown_report(self, portfolio: List[PortfolioItem], vetoed_bonds: List[Dict[str, str]]) -> str:
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

        if vetoed_bonds:
            lines.append("\n## 🚫 今日信用排雷一票否决名单\n")
            lines.append("| 转债代码 | 转债名称 | 否决拦截理由 |")
            lines.append("| :--- | :--- | :--- |")
            for v in vetoed_bonds:
                lines.append(f"| {v['bond_code']} | {v['bond_name']} | {v['veto_reason']} |")

        return "\n".join(lines)
