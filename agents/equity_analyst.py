"""
正股动量与题材智能体 (Equity Momentum Analyst Node)
进攻分析师：分析正股技术走势、所属热点风口（算力/机器人/自主可控等），输出弹性评分 (0-100)。
优先使用 Gemini 3.8 Flash 快速抓取与概念匹配。
"""

import json
from typing import Dict, Any, List
from config.config import settings
from core.state import BondCandidate, EquityMomentumResult
from core.llm_manager import llm_manager

class EquityAnalystAgent:
    """正股动量与题材 Agent"""

    def __init__(self):
        self.client, self.model = llm_manager.get_client(preferred="gemini")

    def evaluate_bond(self, candidate: BondCandidate) -> EquityMomentumResult:
        stock_name = candidate["stock_name"]
        code = candidate["bond_code"]
        premium = candidate["premium_rate"]

        # 规则 1: 溢价率越低，股性越强，传导弹性越好
        # 溢价率 < 15%: 强股性; 15%~40%: 平衡型; > 40%: 偏债性
        base_elasticity = max(0, min(100, int(100 - premium * 1.2)))

        client, model = self.client, self.model
        if not client:
            client, model = llm_manager.get_client()

        if client:
            try:
                prompt = f"""
                你是可转债投研团队的【正股与题材分析师】。请分析以下正股所属板块与当前进攻动量：
                【正股名称】：{stock_name}
                【转债溢价率】：{premium}%
                
                请输出严格 JSON 格式：
                {{
                    "momentum_score": 弹性评分(0~100整数),
                    "sector_themes": ["概念1", "概念2"],
                    "catalyst_summary": "一句话题材催化剂或正股动量逻辑"
                }}
                """
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                data = json.loads(response.choices[0].message.content)
                return {
                    "bond_code": code,
                    "momentum_score": float(data.get("momentum_score", base_elasticity)),
                    "sector_themes": data.get("sector_themes", ["高端制造", "成长动量"]),
                    "catalyst_summary": data.get("catalyst_summary", f"正股 {stock_name} 动量传导良好。")
                }
            except Exception:
                pass

        # 兜底启发式评分
        score = base_elasticity if base_elasticity > 30 else 45
        return {
            "bond_code": code,
            "momentum_score": float(score),
            "sector_themes": ["智能制造", "核心资产"],
            "catalyst_summary": f"转股溢价率仅为 {premium}%，若正股 {stock_name} 爆发，转债具备强爆发弹性。"
        }

    def batch_evaluate(self, candidates: List[BondCandidate]) -> Dict[str, EquityMomentumResult]:
        return {c["bond_code"]: self.evaluate_bond(c) for c in candidates}
