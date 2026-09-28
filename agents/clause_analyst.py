"""
条款博弈智能体 (Clause Game Analyst Node)
期权与博弈专家：深度评估下修博弈空间（下修到底概率）、强赎砸盘风险与到期偿还压力。
优先使用 Gemini 3.1 Pro 进行长程博弈与公司大股东动机推演。
"""

import json
from typing import Dict, Any, List
from config.config import settings
from core.state import BondCandidate, ClauseGameResult
from core.llm_manager import llm_manager

class ClauseAnalystAgent:
    """条款博弈与不对称赔率 Agent"""

    def __init__(self):
        self.client, self.model = llm_manager.get_client(preferred="gemini")


    def evaluate_bond(self, candidate: BondCandidate) -> ClauseGameResult:
        code = candidate["bond_code"]
        price = candidate["price"]
        scale = candidate["remaining_scale"]
        premium = candidate["premium_rate"]

        # 规则 1: 强赎风险 (Price > 130 则强赎风险激增)
        call_risk = "HIGH" if price >= 130 else ("MEDIUM" if price >= 122 else "LOW")

        # 规则 2: 下修意愿推演 (价格低于110元、规模较小、大股东有转股逃债诉求)
        down_revision_score = 50.0
        if price <= 105.0:
            down_revision_score += 30.0
        if scale <= 5.0:
            down_revision_score += 15.0

        client, model = self.client, self.model
        if not client:
            client, model = llm_manager.get_client()

        if client:
            try:
                prompt = f"""
                你是可转债特有制度的【条款博弈专家】。请评估以下转债的下修潜力与强赎风险：
                【标的名称】：{candidate['bond_name']} ({code})
                【转债价格】：{price} 元
                【转股溢价率】：{premium}%
                【剩余规模】：{scale} 亿元
                
                请输出严格 JSON 格式：
                {{
                    "down_revision_potential": 下修催化潜力(0~100浮点数),
                    "call_risk_level": "LOW" | "MEDIUM" | "HIGH",
                    "game_summary": "条款博弈核心逻辑与不对称赔率评述"
                }}
                """
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2
                )
                data = json.loads(response.choices[0].message.content)
                return {
                    "bond_code": code,
                    "down_revision_potential": float(data.get("down_revision_potential", down_revision_score)),
                    "call_risk_level": data.get("call_risk_level", call_risk),
                    "game_summary": data.get("game_summary", "条款防御价值良好。")
                }
            except Exception:
                pass

        # 兜底启发式博弈总结
        summary = (
            f"剩余规模仅 {scale} 亿元，筹码轻；现价 {price} 元距离面值很近，"
            f"公司偿债压力迫使大股东具备强烈的下修转股价意愿，下修不对称赔率极高。"
            if price <= 110 else f"现价 {price} 元暂无迫切下修需求，主要依靠正股内生性上涨驱动。"
        )
        return {
            "bond_code": code,
            "down_revision_potential": min(100.0, down_revision_score),
            "call_risk_level": call_risk,
            "game_summary": summary
        }

    def batch_evaluate(self, candidates: List[BondCandidate]) -> Dict[str, ClauseGameResult]:
        return {c["bond_code"]: self.evaluate_bond(c) for c in candidates}
