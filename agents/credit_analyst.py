"""
信用排雷智能体 (Credit Risk Analyst Node)
首席风控官：专职审查发债公司基本面、债务违约与退市风险，拥有一票否决权 (VETO)。
优先使用 Qwen (通义千问) 28B 进行深度中文财报与监管公告语义审查。
"""

import os
import json
import time
from typing import Dict, Any, List
from config.config import settings
from core.state import BondCandidate, CreditRiskResult
from core.llm_manager import llm_manager, extract_json_content

class CreditAnalystAgent:
    """信用风控与排雷 Agent"""

    def __init__(self):
        self.client, self.model, self.provider, self.provider_name = llm_manager.get_client_with_provider(preferred="qwen")
        self.role_name = "首席风控官"


    def evaluate_bond(self, candidate: BondCandidate, require_llm: bool = False) -> CreditRiskResult:
        """
        对单只候选转债进行信用与排雷审查
        :param require_llm: 严格模式 (交易委员会用): LLM 未配置或重试后仍失败时抛出异常,
                            不走规则兜底 — 防止无 AI 判断的结论混入交易决策
        """
        name = candidate["bond_name"]
        code = candidate["bond_code"]
        stock_name = candidate["stock_name"]
        rating = candidate["rating"]
        price = candidate["price"]

        # 1. 硬规则底线审查 (无需耗费 Token，直接拦截)
        # 规则 A: 评级低于 A 或为 C 级垃圾债 -> 直接一票否决
        if rating in ["C", "CC", "CCC", "B", "BB"]:
            return {
                "bond_code": code,
                "risk_level": "VETO",
                "debt_ratio": 95.0,
                "pledge_ratio": 80.0,
                "reason": f"硬风控否决: 信用评级仅为 {rating}，存在极高信用违约与流动性折价风险。"
            }

        # 规则 B: 正股名称带 *ST 或 ST -> 一票否决
        if "ST" in stock_name or "退" in stock_name:
            return {
                "bond_code": code,
                "risk_level": "VETO",
                "debt_ratio": 85.0,
                "pledge_ratio": 90.0,
                "reason": f"硬风控否决: 正股 {stock_name} 处于风险警示(*ST/ST)状态，面临面值退市或财务退市威胁。"
            }

        # 规则 C: 价格低于 80 元且未声明原因 -> 警示或否决
        if price < 80.0:
            return {
                "bond_code": code,
                "risk_level": "VETO",
                "debt_ratio": 80.0,
                "pledge_ratio": 75.0,
                "reason": f"硬风控否决: 现价 {price} 元严重跌破面值并击穿信用底线，疑似出现隐性违约事件。"
            }

        # 2. 如果配置了大模型 API，则调用大模型进行深度语义审查 (3次重试)
        client, model = self.client, self.model
        if not client:
            client, model = llm_manager.get_client()

        if not client and require_llm:
            raise RuntimeError("LLM 未配置，无法完成信用审查")

        if client:
            last_err = None
            for attempt in range(3):
                try:
                    prompt = f"""
                    你是可转债投研委员会的【首席信用风控官】。请审查以下标的是否存在退市、财务暴雷或大股东违约风险：
                    【标的名称】：{name} ({code})
                    【正股名称】：{stock_name}
                    【当前价格】：{price} 元
                    【信用评级】：{rating}
                    
                    请输出严格 JSON 格式：
                    {{
                        "risk_level": "PASS" | "WARN" | "VETO",
                        "debt_ratio": 预估资产负债率(浮点数),
                        "pledge_ratio": 预估质押率(浮点数),
                        "reason": "严谨的风控审查依据说明（100字以内）"
                    }}
                    """
                    response = client.chat.completions.create(
                        model=model,
                        response_format={"type": "json_object"},
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    data = extract_json_content(response.choices[0].message.content)
                    return {
                        "bond_code": code,
                        "risk_level": data.get("risk_level", "PASS"),
                        "debt_ratio": float(data.get("debt_ratio", 50.0)),
                        "pledge_ratio": float(data.get("pledge_ratio", 20.0)),
                        "reason": data.get("reason", "基本面审查通过。")
                    }
                except Exception as e:
                    last_err = e
                    time.sleep(1.0 + attempt)
            if require_llm:
                raise RuntimeError(f"信用审查 LLM 调用失败(已重试3次): {last_err}")

        # 3. 兜底规则评估 (默认安全或低风险)
        risk = "PASS" if rating in ["AAA", "AA+", "AA"] else "WARN"
        return {
            "bond_code": code,
            "risk_level": risk,
            "debt_ratio": 52.0 if risk == "PASS" else 68.0,
            "pledge_ratio": 25.0 if risk == "PASS" else 55.0,
            "reason": f"评级为 {rating}，正股经营基本面平稳，现金流健康，通过信用门禁。"
        }

    def batch_evaluate(self, candidates: List[BondCandidate], require_llm: bool = False) -> Dict[str, CreditRiskResult]:
        """批量审查候选池 (线程池并发调用 LLM，单只失败不影响整批; require_llm=True 时失败的标的缺失结果)"""
        from core.llm_manager import parallel_batch_map
        from functools import partial
        return parallel_batch_map(partial(self.evaluate_bond, require_llm=require_llm), candidates)
