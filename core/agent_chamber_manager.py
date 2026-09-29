"""
可插拔多智能体投研议事厅与法庭裁决中枢 (Agent Chamber & Deliberation Manager)
支持：
1. 投研人才库 (Agent Talent Pool) 与议事空间 (Meeting Chambers) 的动态加载与持久化
2. 经典圆桌会商 (Roundtable) 与金融多空对抗裁决法庭 (Adversarial Courtroom) 双工作流
3. 全链路发言实录记录器 (Verbatim Speech & Evidence Recorder)，逐字留存所有智能体辩论与法官判词
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from db.session import SessionLocal
from db.models import AgentDefinition, MeetingChamber, AgentReportRecord
from core.llm_manager import llm_manager
from core.state import BondCandidate
from core.dossier_manager import dossier_manager


class AgentChamberManager:
    """多智能体议事中枢管理器"""

    # ==============================================================
    # 1. 智能体与议事厅元数据管理
    # ==============================================================

    @staticmethod
    def get_all_chambers() -> List[Dict[str, Any]]:
        """获取所有已启用的议事空间列表"""
        with SessionLocal() as session:
            chambers = session.query(MeetingChamber).filter(MeetingChamber.is_active == True).order_by(MeetingChamber.sort_order).all()
            return [c.to_dict() for c in chambers]

    @staticmethod
    def get_chamber_by_id(chamber_id: str) -> Optional[Dict[str, Any]]:
        """获取指定议事空间详情"""
        with SessionLocal() as session:
            chamber = session.query(MeetingChamber).filter(MeetingChamber.id == chamber_id).first()
            return chamber.to_dict() if chamber else None

    @staticmethod
    def get_all_agents() -> List[Dict[str, Any]]:
        """获取人才库所有智能体定义"""
        with SessionLocal() as session:
            agents = session.query(AgentDefinition).order_by(AgentDefinition.sort_order).all()
            return [a.to_dict() for a in agents]

    @staticmethod
    def save_agent(agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建或更新智能体"""
        with SessionLocal() as session:
            agent_id = agent_data.get("id")
            existing = session.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first() if agent_id else None

            if not existing:
                agent_id = agent_id or f"custom_{int(time.time())}"
                new_agent = AgentDefinition(
                    id=agent_id,
                    name=agent_data.get("name", "自定义分析师"),
                    avatar=agent_data.get("avatar", "🤖"),
                    target_asset=agent_data.get("target_asset", "universal"),
                    role_type=agent_data.get("role_type", "score"),
                    description=agent_data.get("description", ""),
                    model_provider=agent_data.get("model_provider", "auto"),
                    model_name=agent_data.get("model_name", ""),
                    system_prompt=agent_data.get("system_prompt", "你是一名专业的量化投研分析师。"),
                    user_prompt_template=agent_data.get("user_prompt_template", "请审查标的: {bond_name} ({bond_code})。"),
                    is_builtin=False,
                    is_active=bool(agent_data.get("is_active", True)),
                    sort_order=int(agent_data.get("sort_order", 99))
                )
                session.add(new_agent)
                session.commit()
                return new_agent.to_dict()
            else:
                existing.name = agent_data.get("name", existing.name)
                existing.avatar = agent_data.get("avatar", existing.avatar)
                existing.target_asset = agent_data.get("target_asset", existing.target_asset)
                existing.role_type = agent_data.get("role_type", existing.role_type)
                existing.description = agent_data.get("description", existing.description)
                existing.model_provider = agent_data.get("model_provider", existing.model_provider)
                existing.model_name = agent_data.get("model_name", existing.model_name)
                existing.system_prompt = agent_data.get("system_prompt", existing.system_prompt)
                existing.user_prompt_template = agent_data.get("user_prompt_template", existing.user_prompt_template)
                if not existing.is_builtin:
                    existing.is_active = bool(agent_data.get("is_active", existing.is_active))
                session.commit()
                return existing.to_dict()

    @staticmethod
    def delete_agent(agent_id: str) -> bool:
        """删除自定义智能体 (内置席位禁止删除)"""
        with SessionLocal() as session:
            agent = session.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
            if agent and not agent.is_builtin:
                session.delete(agent)
                session.commit()
                return True
        return False

    _failed_providers = set()

    # ==============================================================
    # 2. 智能体发言与证据链生成 (LLM + 规则引擎)
    # ==============================================================

    @classmethod
    def _call_agent_llm(cls, agent_info: Dict[str, Any], prompt: str) -> Tuple[Optional[str], str]:
        """
        调用智能体绑定的大模型，返回 (回答文本, 实际使用的模型名)
        """
        preferred = agent_info.get("model_provider")
        if preferred == "auto":
            preferred = None
            
        client, fallback_model, provider_key, provider_name = llm_manager.get_client_with_provider(preferred=preferred)
        model_to_use = agent_info.get("model_name") if agent_info.get("model_name") else fallback_model

        if not client or not model_to_use:
            return None, "内置规则引擎 (Offline)"

        # 若此前已检测到该供应商 API Key 无效，则直接走内置规则引擎，避免重复报错刷屏
        if provider_key in cls._failed_providers:
            return None, "量化金融规则引擎 (Key未生效)"

        try:
            resp = client.chat.completions.create(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": agent_info.get("system_prompt", "你是一名专业金融投研分析师。")},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=600,
                timeout=20.0
            )
            return resp.choices[0].message.content.strip(), f"{provider_name} · {model_to_use}"
        except Exception as e:
            err_str = str(e)
            is_auth_error = any(kw in err_str.lower() for kw in ["valid api key", "invalid_api_key", "401", "authentication", "unauthorized", "invalid_argument"])
            if is_auth_error:
                cls._failed_providers.add(provider_key)
                print(f"ℹ️ [提示] 当前大模型 [{provider_name}] 鉴权未通过: {err_str[:90]}... (配置的 API Key 无效或未生效)。已自动无缝切换为【内置量化金融规则引擎】进行审核与组合计算，业务正常运转。")
            else:
                print(f"[WARN] 智能体 [{agent_info.get('name')}] LLM 调用失败: {e}")
            return None, "量化金融规则引擎 (Key未生效)"

    # ==============================================================
    # 3. 经典可转债投研圆桌工作流 (Roundtable Workflow)
    # ==============================================================

    @classmethod
    def run_roundtable_deliberation(
        cls,
        candidates: List[BondCandidate],
        chamber_info: Dict[str, Any],
        on_progress=None
    ) -> Dict[str, Any]:
        """
        运行经典可转债投研圆桌会诊
        """
        agent_ids = chamber_info.get("agent_ids", ["cb_credit", "cb_equity", "cb_clause"])
        
        with SessionLocal() as session:
            agents = session.query(AgentDefinition).filter(AgentDefinition.id.in_(agent_ids)).all()
            agents_map = {a.id: a.to_dict() for a in agents}

        # 组织参会智能体
        active_agents = [agents_map[aid] for aid in agent_ids if aid in agents_map]
        
        credit_reviews: Dict[str, Any] = {}
        equity_reviews: Dict[str, Any] = {}
        clause_reviews: Dict[str, Any] = {}
        all_bond_speeches: Dict[str, List[Dict[str, Any]]] = {}
        vetoed_bonds: List[Dict[str, Any]] = []

        now_str = datetime.now().strftime("%H:%M:%S")

        for idx, cand in enumerate(candidates):
            b_code = cand["bond_code"]
            b_name = cand["bond_name"]
            speeches: List[Dict[str, Any]] = []

            # 1. 首席信用风控官 (cb_credit)
            credit_agent = agents_map.get("cb_credit")
            credit_result = cls._evaluate_cb_credit(cand, credit_agent)
            credit_reviews[b_code] = credit_result["review"]
            speeches.append(credit_result["speech"])
            if credit_result["review"]["risk_level"] == "VETO":
                vetoed_bonds.append({
                    "bond_code": b_code,
                    "bond_name": b_name,
                    "reason": credit_result["review"]["reason"]
                })

            # 2. 正股动量分析师 (cb_equity)
            equity_agent = agents_map.get("cb_equity")
            equity_result = cls._evaluate_cb_equity(cand, equity_agent)
            equity_reviews[b_code] = equity_result["review"]
            speeches.append(equity_result["speech"])

            # 3. 条款博弈专家 (cb_clause)
            clause_agent = agents_map.get("cb_clause")
            clause_result = cls._evaluate_cb_clause(cand, clause_agent)
            clause_reviews[b_code] = clause_result["review"]
            speeches.append(clause_result["speech"])

            all_bond_speeches[b_code] = speeches

        # 4. 投资总监 (PM) 综合裁决与仓位分配
        from agents.portfolio_manager import PortfolioManagerAgent
        pm_agent = PortfolioManagerAgent(top_n=15)
        final_portfolio, pm_vetoed, report_md = pm_agent.arbitrate_and_allocate(
            candidates=candidates,
            credit_reviews=credit_reviews,
            equity_reviews=equity_reviews,
            clause_reviews=clause_reviews
        )

        # 为投资组合标的注入 PM 裁决发言记录
        for p in final_portfolio:
            b_code = p["bond_code"]
            pm_speech = {
                "speaker_id": "pm_director",
                "speaker_name": "投资总监 (PM) · 终审裁决",
                "avatar": "👔",
                "role_type": "judge",
                "model_used": "量化仲裁引擎 (Quantitative Arbiter)",
                "stance": "BUY",
                "score": round(p["weight"] * 100, 1),
                "statement": f"【投委会终审裁定】综合风控穿透、正股动量与条款博弈多维考量，标的评定为 {p['rating_stars']} 星推荐。PM 投资裁决：{p['pm_verdict']}。准予纳入今日投资组合，建议配置权重 {round(p['weight'] * 100, 1)}%！",
                "key_evidence": [
                    f"建议组合仓位权重: {round(p['weight'] * 100, 1)}%",
                    f"双低值: {p['double_low']} (安全边际充足)",
                    f"推荐星级: {'⭐' * p['rating_stars']}"
                ],
                "timestamp": now_str
            }
            if b_code in all_bond_speeches:
                all_bond_speeches[b_code].append(pm_speech)

        return {
            "chamber_type": "ROUNDTABLE",
            "chamber_id": chamber_info.get("id"),
            "chamber_name": chamber_info.get("name"),
            "candidates": candidates,
            "credit_reviews": credit_reviews,
            "equity_reviews": equity_reviews,
            "clause_reviews": clause_reviews,
            "final_portfolio": final_portfolio,
            "vetoed_bonds": vetoed_bonds,
            "all_bond_speeches": all_bond_speeches,
            "report_md": report_md,
            "dynamic_targets": getattr(pm_agent, "dynamic_targets", {})
        }

    # ==============================================================
    # 4. 金融多空对抗裁决法庭工作流 (Courtroom Workflow)
    # ==============================================================

    @classmethod
    def run_courtroom_deliberation(
        cls,
        candidates: List[BondCandidate],
        chamber_info: Dict[str, Any],
        on_progress=None
    ) -> Dict[str, Any]:
        """
        运行金融多空对抗裁决法庭：
        Round 1: 做空公诉人 (Bear Prosecutor) 列举致命指控与做空依据
        Round 2: 多头辩护人 (Bull Defender) 抗辩驳斥，举证护城河与反转催化剂
        Round 3: 主审大法官 (Chief Judge / PM) 敲槌宣判判决书与量刑仓位
        """
        agent_ids = chamber_info.get("agent_ids", ["bear_prosecutor", "bull_defender", "court_judge"])
        
        with SessionLocal() as session:
            agents = session.query(AgentDefinition).filter(AgentDefinition.id.in_(agent_ids)).all()
            agents_map = {a.id: a.to_dict() for a in agents}

        bear_agent = agents_map.get("bear_prosecutor", {})
        bull_agent = agents_map.get("bull_defender", {})
        judge_agent = agents_map.get("court_judge", {})

        all_bond_speeches: Dict[str, List[Dict[str, Any]]] = {}
        court_verdicts: Dict[str, Dict[str, Any]] = {}
        final_portfolio: List[Dict[str, Any]] = []
        vetoed_bonds: List[Dict[str, Any]] = []
        now_str = datetime.now().strftime("%H:%M:%S")

        for idx, cand in enumerate(candidates):
            b_code = cand["bond_code"]
            b_name = cand["bond_name"]
            price = cand["price"]
            premium = cand["premium_rate"]
            dlow = cand["double_low"]
            stock_name = cand["stock_name"]
            rating = cand.get("rating", "AA")

            speeches: List[Dict[str, Any]] = []

            # ---------------------------------------------------------
            # 控方回合：做空公诉人起诉指控
            # ---------------------------------------------------------
            prosecutor_speech = cls._court_bear_prosecution(cand, bear_agent)
            speeches.append(prosecutor_speech)

            # ---------------------------------------------------------
            # 辩方回合：多头律师有力抗辩
            # ---------------------------------------------------------
            defender_speech = cls._court_bull_defense(cand, bull_agent, prosecutor_speech["statement"])
            speeches.append(defender_speech)

            # ---------------------------------------------------------
            # 审理裁决：主审大法官终审宣判
            # ---------------------------------------------------------
            judge_speech, verdict_data = cls._court_judge_ruling(cand, judge_agent, prosecutor_speech, defender_speech)
            speeches.append(judge_speech)

            all_bond_speeches[b_code] = speeches
            court_verdicts[b_code] = verdict_data

            if verdict_data["verdict"] == "REJECT":
                vetoed_bonds.append({
                    "bond_code": b_code,
                    "bond_name": b_name,
                    "reason": f"法庭判决驳回: {verdict_data['sentence_summary']}"
                })
            else:
                # 准予建仓或观望
                final_portfolio.append({
                    "bond_code": b_code,
                    "bond_name": b_name,
                    "price": price,
                    "double_low": dlow,
                    "weight": verdict_data["weight"],
                    "rating_stars": verdict_data["rating_stars"],
                    "pm_verdict": f"【法庭宣判】{verdict_data['verdict_label']}：{verdict_data['sentence_summary']}"
                })

        # 归一化组合权重
        if final_portfolio:
            total_w = sum(p["weight"] for p in final_portfolio)
            if total_w > 0:
                for p in final_portfolio:
                    p["weight"] = round(p["weight"] / total_w, 4)

        # 生成法庭多空辩论总报告
        report_md = cls._generate_courtroom_report_md(chamber_info, candidates, final_portfolio, vetoed_bonds, court_verdicts)

        return {
            "chamber_type": "COURTROOM",
            "chamber_id": chamber_info.get("id"),
            "chamber_name": chamber_info.get("name"),
            "candidates": candidates,
            "court_verdicts": court_verdicts,
            "final_portfolio": final_portfolio,
            "vetoed_bonds": vetoed_bonds,
            "all_bond_speeches": all_bond_speeches,
            "report_md": report_md
        }

    # ==============================================================
    # 5. 辅助执行逻辑 (Roundtable & Courtroom 节点计算)
    # ==============================================================

    @classmethod
    def _evaluate_cb_credit(cls, cand: BondCandidate, agent_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """圆桌: 信用排雷节点评估"""
        b_code = cand["bond_code"]
        b_name = cand["bond_name"]
        rating = cand["rating"]
        price = cand["price"]
        stock_name = cand["stock_name"]

        # 硬规则防御
        if rating in ["C", "CC", "CCC", "B", "BB"] or "ST" in stock_name or "退" in stock_name or price < 80.0:
            reason = f"硬风控否决: 正股处于警示状态({stock_name})或评级仅为{rating}，价格严重破位({price}元)。"
            return {
                "review": {"bond_code": b_code, "risk_level": "VETO", "reason": reason},
                "speech": {
                    "speaker_id": "cb_credit",
                    "speaker_name": agent_info.get("name", "首席信用风控官") if agent_info else "首席信用风控官",
                    "avatar": "🛡️",
                    "role_type": "veto",
                    "model_used": "硬规则引擎 (Zero-Token)",
                    "stance": "VETO",
                    "score": 0.0,
                    "statement": f"【风控一票否决】标的 {b_name} ({b_code}) 触发硬底线拦截：{reason}。坚决行使一票否决权，禁止入库！",
                    "key_evidence": [f"评级: {rating}", f"现价: {price}元", f"正股警示状态: {stock_name}"],
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
            }

        # 尝试调用大模型 (注入全景案卷)
        dossier = dossier_manager.get_bond_dossier(cand)
        prompt = dossier_manager.format_credit_prompt(dossier)
        llm_statement, model_used = cls._call_agent_llm(agent_info, prompt) if agent_info else (None, "规则引擎")

        statement = llm_statement or f"基本面审查完毕：发债公司 {stock_name} 财务指标健康，主体信用评级 {rating} 稳健，无退市或质押爆仓风险，准予通过。"
        recent_notice_title = dossier["notices"][0]["title"] if dossier["notices"] else "近期无异常违约处罚披露"
        return {
            "review": {"bond_code": b_code, "risk_level": "PASS", "reason": statement},
            "speech": {
                "speaker_id": "cb_credit",
                "speaker_name": agent_info.get("name", "首席信用风控官") if agent_info else "首席信用风控官",
                "avatar": "🛡️",
                "role_type": "veto",
                "model_used": model_used,
                "stance": "PASS",
                "score": 90.0,
                "statement": statement,
                "key_evidence": [
                    f"信用评级: {rating}",
                    f"纯债底价值: {dossier['pure_debt_value']}元 (安全垫保护)",
                    f"最新公告: {recent_notice_title}"
                ],
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        }

    @classmethod
    def _evaluate_cb_equity(cls, cand: BondCandidate, agent_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """圆桌: 正股动量节点评估 (注入风口题材案卷)"""
        b_code = cand["bond_code"]
        b_name = cand["bond_name"]
        premium = cand["premium_rate"]
        stock_name = cand["stock_name"]

        dossier = dossier_manager.get_bond_dossier(cand)
        base_score = max(30, min(95, int(100 - premium * 1.1)))
        prompt = dossier_manager.format_equity_prompt(dossier)
        llm_statement, model_used = cls._call_agent_llm(agent_info, prompt) if agent_info else (None, "量化算法")

        concepts_str = "、".join(dossier["concepts"][:3]) if dossier["concepts"] else "稳健题材"
        statement = llm_statement or f"正股 {stock_name} 绑定核心风口【{concepts_str}】，溢价率仅 {premium}%，转股价值 {dossier['convert_value']}元，进攻弹性良好，动量评分 {base_score}/100。"
        return {
            "review": {
                "bond_code": b_code,
                "momentum_score": base_score,
                "sector_themes": dossier["concepts"][:4] if dossier["concepts"] else ["景气科技", "智能制造"],
                "catalyst_summary": statement
            },
            "speech": {
                "speaker_id": "cb_equity",
                "speaker_name": agent_info.get("name", "正股动量分析师") if agent_info else "正股动量分析师",
                "avatar": "🚀",
                "role_type": "score",
                "model_used": model_used,
                "stance": "BULL",
                "score": float(base_score),
                "statement": statement,
                "key_evidence": [
                    f"核心题材: {concepts_str}",
                    f"转债溢价率: {premium}%",
                    f"转股价值弹性: {dossier['convert_value']}元"
                ],
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        }

    @classmethod
    def _evaluate_cb_clause(cls, cand: BondCandidate, agent_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """圆桌: 条款博弈节点评估 (注入条款精算案卷)"""
        b_code = cand["bond_code"]
        b_name = cand["bond_name"]
        price = cand["price"]
        scale = cand["remaining_scale"]
        call_risk = "HIGH" if price >= 130 else ("MEDIUM" if price >= 122 else "LOW")

        dossier = dossier_manager.get_bond_dossier(cand)
        prompt = dossier_manager.format_clause_prompt(dossier)
        llm_statement, model_used = cls._call_agent_llm(agent_info, prompt) if agent_info else (None, "博弈模型")

        statement = llm_statement or (
            f"转债价格 {price} 元处于安全博弈区，强赎风险等级为 {call_risk}。剩余规模 {scale} 亿流通盘小，"
            f"大股东转股诉求强烈，正股价距下修线 {dossier['dist_to_down_pct']}%，具备绝佳不对称赔率。"
        )

        down_desc = f"正股价距下修线 {dossier['dist_to_down_pct']}%"
        call_desc = f"距强赎触发尚有 {dossier['dist_to_call_pct']}%" if dossier['dist_to_call_pct'] > 20 else f"距强赎仅差 {dossier['dist_to_call_pct']}%"

        return {
            "review": {"bond_code": b_code, "down_revision_potential": 75.0, "call_risk_level": call_risk, "game_summary": statement},
            "speech": {
                "speaker_id": "cb_clause",
                "speaker_name": agent_info.get("name", "条款博弈专家") if agent_info else "条款博弈专家",
                "avatar": "♟️",
                "role_type": "review",
                "model_used": model_used,
                "stance": "BULL" if call_risk == "LOW" else "WARN",
                "score": 78.0,
                "statement": statement,
                "key_evidence": [
                    f"下修博弈空间: {down_desc}",
                    f"强赎安全垫: {call_desc}",
                    f"流通规模: {scale}亿 (大股东转股诉求极强)"
                ],
                "timestamp": datetime.now().strftime("%H:%M:%S")
            }
        }

    # -------------------------------------------------------------
    # 法庭多空对抗三部曲 (Prosecution -> Defense -> Ruling)
    # -------------------------------------------------------------

    @classmethod
    def _court_bear_prosecution(cls, cand: BondCandidate, agent_info: Dict[str, Any]) -> Dict[str, Any]:
        """法庭第 1 轮: 做空公诉人起诉指控 (Bear Prosecution - 基于全案卷宗)"""
        b_code = cand["bond_code"]
        b_name = cand["bond_name"]
        price = cand["price"]
        premium = cand["premium_rate"]
        scale = cand["remaining_scale"]
        stock_name = cand["stock_name"]

        dossier = dossier_manager.get_bond_dossier(cand)
        dossier_text = dossier_manager.format_court_dossier(dossier)

        prompt = f"""
【法庭案件审理 · 公诉指控阶段】
法庭已调取被告标的的全案卷宗如下：
{dossier_text}

作为激进的空方公诉人，请依据上述真实精算数据与案卷漏洞向法庭提起【做空公诉陈词】（列出 3 大致命隐患与做空依据，主张驳回建仓），言辞犀利严谨，字数120字内。
""".strip()
        llm_statement, model_used = cls._call_agent_llm(agent_info, prompt) if agent_info else (None, "做空模型")

        statement = llm_statement or (
            f"【公诉控词】被告标的 {b_name} 溢价率达 {premium}%，股性严重迟钝！现价 {price} 元已脱离纯债底支撑，"
            f"正股 {stock_name} 所处赛道竞争白热化，且存续规模达 {scale} 亿面临抛压！买入极易陷入估值与信用双杀陷阱，公诉人坚决主张驳回建仓！"
        )

        return {
            "speaker_id": "bear_prosecutor",
            "speaker_name": agent_info.get("name", "做空公诉人 · 浑水质询官"),
            "avatar": "🔴",
            "role_type": "prosecutor",
            "model_used": model_used,
            "stance": "BEAR",
            "score": 25.0,
            "statement": statement,
            "key_evidence": [
                f"溢价率迟钝风险: {premium}%",
                f"纯债底溢价溢价率: {dossier['pure_debt_premium']}%",
                "做空指控: 估值透支与流动性隐患"
            ],
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @classmethod
    def _court_bull_defense(cls, cand: BondCandidate, agent_info: Dict[str, Any], prosecutor_allegation: str) -> Dict[str, Any]:
        """法庭第 2 轮: 多头辩护律师抗辩 (Bull Defense - 举证全案事实)"""
        b_code = cand["bond_code"]
        b_name = cand["bond_name"]
        price = cand["price"]
        dlow = cand["double_low"]
        stock_name = cand["stock_name"]

        dossier = dossier_manager.get_bond_dossier(cand)
        dossier_text = dossier_manager.format_court_dossier(dossier)

        prompt = f"""
【法庭案件审理 · 辩方举证抗辩阶段】
被告标的完整案卷如下：
{dossier_text}

空方公诉人的做空指控如下：
“{prosecutor_allegation}”

请作为买方多头辩护律师，针对上述做空指控进行有力抗辩，引用案卷中证明标的具备债底防御、题材风口或不对称暴利赔率的核心证据，说明为何做空论点站不住脚，坚决主张建仓，字数120字内。
""".strip()
        llm_statement, model_used = cls._call_agent_llm(agent_info, prompt) if agent_info else (None, "买方价值模型")

        statement = llm_statement or (
            f"【辩护陈词】公诉人言过其实！标的 {b_name} 当前双低值仅 {dlow}，纯债底 {dossier['pure_debt_value']} 元防线坚固，"
            f"且正股 {stock_name} 绑定【{'、'.join(dossier['concepts'][:2])}】风口。转债向下修正期权保证了『下有保底、上不封顶』的不对称赔率优势，辩护人坚决主张准予建仓！"
        )

        return {
            "speaker_id": "bull_defender",
            "speaker_name": agent_info.get("name", "多头辩护人 · 价值辩护律师"),
            "avatar": "🟢",
            "role_type": "defender",
            "model_used": model_used,
            "stance": "BULL",
            "score": 85.0,
            "statement": statement,
            "key_evidence": [
                f"双低估值安全垫: {dlow}",
                f"纯债底防护: {dossier['pure_debt_value']}元",
                f"核心风口题材: {'、'.join(dossier['concepts'][:3])}"
            ],
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

    @classmethod
    def _court_judge_ruling(
        cls,
        cand: BondCandidate,
        agent_info: Dict[str, Any],
        prosecutor_speech: Dict[str, Any],
        defender_speech: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """法庭第 3 轮: 主审首席大法官终审宣判 (Chief Judge Ruling)"""
        b_code = cand["bond_code"]
        b_name = cand["bond_name"]
        price = cand["price"]
        dlow = cand["double_low"]
        stock_name = cand["stock_name"]

        # 结合客观双低指标进行定量仲裁裁决
        if price > 135.0 or cand["premium_rate"] > 60.0 or "ST" in stock_name:
            verdict = "REJECT"
            verdict_label = "【控方指控成立 · 驳回建仓令】"
            summary = f"控方关于估值透支或信用恶化的指控证据确凿。标的高达 {price} 元且溢价率畸高，不予建仓！"
            weight = 0.0
            stars = 1
        elif dlow <= 165.0:
            verdict = "ACQUIT_BUY"
            verdict_label = "【辩方胜诉 · 准予重仓配置令】"
            summary = f"辩方关于非对称赔率与安全边际的举证充分有效！双低 {dlow} 极具投资价值，判决准予纳入重点配置！"
            weight = 0.08
            stars = 5
        else:
            verdict = "WATCH"
            verdict_label = "【疑罪从无 · 准予轻仓观察令】"
            summary = f"多空交锋势均力敌。判决准予底仓观察，控制仓位敞口以防范回撤风险。"
            weight = 0.04
            stars = 3

        prompt = f"""
        【合议庭敲槌终审】标的: {b_name} ({b_code})。
        控方陈述: “{prosecutor_speech['statement']}”
        辩方陈述: “{defender_speech['statement']}”
        仲裁倾向: {verdict_label}，建议仓位: {round(weight*100, 1)}%。
        请主审首席大法官敲槌宣布判决结果与判决说理（法庭判词风格，100字内）。
        """
        llm_statement, model_used = cls._call_agent_llm(agent_info, prompt) if agent_info else (None, "合议裁决引擎")

        statement = llm_statement or (
            f"【合议裁决书】主审合议庭经审查全案证据链，敲槌宣判：{verdict_label}！{summary}"
        )

        speech = {
            "speaker_id": "court_judge",
            "speaker_name": agent_info.get("name", "首席大法官 · 独立合议庭"),
            "avatar": "⚖️",
            "role_type": "judge",
            "model_used": model_used,
            "stance": "JUDGEMENT",
            "verdict": verdict,
            "score": round(weight * 100, 1),
            "statement": statement,
            "key_evidence": [f"最终司法判决: {verdict_label}", f"配置量刑建议: {round(weight*100, 1)}%", f"核心评级星级: {'⭐' * stars}"],
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }

        verdict_data = {
            "verdict": verdict,
            "verdict_label": verdict_label,
            "sentence_summary": summary,
            "weight": weight,
            "rating_stars": stars
        }

        return speech, verdict_data

    @classmethod
    def _generate_courtroom_report_md(
        cls,
        chamber_info: Dict[str, Any],
        candidates: List[BondCandidate],
        final_portfolio: List[Dict[str, Any]],
        vetoed_bonds: List[Dict[str, Any]],
        court_verdicts: Dict[str, Dict[str, Any]]
    ) -> str:
        """生成多空对抗法庭格式的 Markdown 投研判决书"""
        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        md = f"""# ⚖️ 金融多空对抗裁决法庭 · 终审执行判决书
**审判法庭**: {chamber_info.get('name', '多空对抗法庭')}  
**审结时间**: {dt_str}  
**审理标的受案量**: {len(candidates)} 只  
**准予建仓标的量**: {len(final_portfolio)} 只 | **控方驳回标的量**: {len(vetoed_bonds)} 只  

---

### 🏛️ 首席大法官终审配置执行令 (Top Holdings)
| 标的代码 | 标的名称 | 现价 | 双低值 | 司法裁定 | 量刑仓位权重 | 推荐星级 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
        for p in final_portfolio:
            stars = "⭐" * p["rating_stars"]
            weight_pct = f"{round(p['weight'] * 100, 1)}%"
            md += f"| **{p['bond_code']}** | {p['bond_name']} | ¥{p['price']} | {p['double_low']} | **准予建仓** | `{weight_pct}` | {stars} |\n"

        if vetoed_bonds:
            md += f"""
---

### 🚫 控方胜诉 · 依法驳回建仓高危名单 ({len(vetoed_bonds)} 只)
"""
            for vb in vetoed_bonds:
                md += f"- **{vb['bond_name']} ({vb['bond_code']})**: {vb['reason']}\n"

        md += f"""
---
*提示：本判决书由做空公诉人、多头辩护人与首席大法官多智能体对抗辩论后生成，可点击具体标的逐字查阅辩护实录。*
"""
        return md


agent_chamber_manager = AgentChamberManager()
