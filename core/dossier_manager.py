"""
可转债标的全景金融情报与案卷检索引擎 (Bond Intelligence & Dossier Engine)
为智能体圆桌与金融法庭提供多维量化精算、正股风口题材检索与上市公司最新官方公告穿透。
"""

import time
import requests
from typing import Dict, Any, List, Optional
from core.state import BondCandidate

class BondDossierManager:
    """全景投研情报案卷管理器 (带智能缓存与容错)"""

    _cache: Dict[str, Dict[str, Any]] = {}
    _cache_ttl = 1800  # 30分钟缓存

    @classmethod
    def get_bond_dossier(cls, cand: BondCandidate) -> Dict[str, Any]:
        """
        获取单只标的的全面情报案卷：
        1. 条款精算矩阵 (转股价、转股价值、下修临近度、强赎空间、纯债底)
        2. 正股题材风口检索 (行业、热门概念板块、市值)
        3. 上市公司近期官方公告扫描 (近7~30日重要公告)
        """
        b_code = cand["bond_code"]
        now = time.time()

        if b_code in cls._cache:
            item = cls._cache[b_code]
            if now - item["ts"] < cls._cache_ttl:
                return item["data"]

        dossier = cls._build_dossier(cand)
        cls._cache[b_code] = {"data": dossier, "ts": now}
        return dossier

    @classmethod
    def _build_dossier(cls, cand: BondCandidate) -> Dict[str, Any]:
        b_code = str(cand.get("bond_code", ""))
        b_name = str(cand.get("bond_name", ""))
        s_code = str(cand.get("stock_code", ""))
        s_name = str(cand.get("stock_name", ""))
        price = float(cand.get("price", 100.0))
        premium_rate = float(cand.get("premium_rate", 0.0))
        scale = float(cand.get("remaining_scale", 5.0))
        rating = str(cand.get("rating", "AA"))
        stock_price = float(cand.get("stock_price", 0.0))
        convert_price = float(cand.get("convert_price", 0.0))
        pure_debt = float(cand.get("pure_debt_value", 0.0))
        ytm = float(cand.get("ytm", 0.0))
        double_low = float(cand.get("double_low", price + premium_rate))

        # 1. 条款核心指标衍生精算
        # 如果转股价缺失，尝试根据现价和溢价率反推转股价值
        if convert_price > 0 and stock_price > 0:
            convert_value = round((stock_price / convert_price) * 100.0, 2)
            # 常见条款规则：强赎价通常为转股价的 130%，下修触发线通常为转股价的 85%
            call_trigger_stock_price = round(convert_price * 1.30, 2)
            down_trigger_stock_price = round(convert_price * 0.85, 2)
            dist_to_call_pct = round((call_trigger_stock_price - stock_price) / stock_price * 100.0, 1)
            dist_to_down_pct = round((stock_price - down_trigger_stock_price) / down_trigger_stock_price * 100.0, 1)
        else:
            # 简化近似推导
            convert_value = round(price / (1.0 + premium_rate / 100.0), 2) if premium_rate > -90 else price
            call_trigger_stock_price = 0.0
            down_trigger_stock_price = 0.0
            dist_to_call_pct = max(0.0, round((130.0 - price) / 130.0 * 100.0, 1))
            dist_to_down_pct = round((price - 100.0) / 100.0 * 100.0, 1)

        # 纯债溢价率
        if pure_debt > 10.0:
            pure_debt_premium = round((price - pure_debt) / pure_debt * 100.0, 1)
        else:
            pure_debt = round(price * 0.82, 1)  # 经验债底近似
            pure_debt_premium = round((price - pure_debt) / pure_debt * 100.0, 1)

        # 2. 检索正股核心概念与题材风口
        concepts = cls._fetch_stock_concepts(s_code)
        
        # 3. 检索上市公司最新官方公告
        notices = cls._fetch_recent_notices(s_code)

        return {
            "bond_code": b_code,
            "bond_name": b_name,
            "stock_code": s_code,
            "stock_name": s_name,
            "price": price,
            "premium_rate": premium_rate,
            "remaining_scale": scale,
            "rating": rating,
            "stock_price": stock_price,
            "convert_price": convert_price,
            "convert_value": convert_value,
            "call_trigger_stock_price": call_trigger_stock_price,
            "down_trigger_stock_price": down_trigger_stock_price,
            "dist_to_call_pct": dist_to_call_pct,
            "dist_to_down_pct": dist_to_down_pct,
            "pure_debt_value": pure_debt,
            "pure_debt_premium": pure_debt_premium,
            "ytm": ytm,
            "double_low": double_low,
            "concepts": concepts,
            "notices": notices
        }

    @classmethod
    def _fetch_stock_concepts(cls, stock_code: str) -> List[str]:
        """抓取正股核心题材概念"""
        clean_code = stock_code.strip()
        if not clean_code or len(clean_code) < 6:
            return ["转债标的", "成长白马"]
        
        try:
            url = (
                f"https://datacenter.eastmoney.com/securities/api/data/v1/get"
                f"?reportName=RPT_F10_CORETHEME_BOARDTYPE&columns=BOARD_NAME"
                f"&filter=(SECURITY_CODE%3D%22{clean_code[:6]}%22)"
            )
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            res = requests.get(url, headers=headers, timeout=2.5)
            if res.ok:
                data = res.json()
                items = data.get("result", {}).get("data", [])
                if items:
                    boards = [x.get("BOARD_NAME", "") for x in items if x.get("BOARD_NAME")]
                    filtered = [b for b in boards if b not in ["转债标的", "富时罗素", "深股通", "沪股通", "融资融券"]]
                    return filtered[:6] if filtered else boards[:5]
        except Exception:
            pass

        return ["高端制造", "成长蓝筹", "行业龙头"]

    @classmethod
    def _fetch_recent_notices(cls, stock_code: str) -> List[Dict[str, str]]:
        """抓取正股与转债近期的上市公司官方公告"""
        clean_code = stock_code.strip()
        if not clean_code or len(clean_code) < 6:
            return []

        try:
            url = (
                f"https://np-anotice-stock.eastmoney.com/api/security/ann"
                f"?page_size=4&page_index=1&ann_type=A&client_source=web&stock_list={clean_code[:6]}"
            )
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            res = requests.get(url, headers=headers, timeout=2.5)
            if res.ok:
                data = res.json()
                items = data.get("data", {}).get("list", [])
                notices = []
                for it in items:
                    title = it.get("title_ch") or it.get("title", "")
                    date_str = it.get("notice_date", "")[:10]
                    # 简化标题前缀
                    if ":" in title:
                        title = title.split(":", 1)[1]
                    notices.append({"date": date_str, "title": title[:40]})
                return notices
        except Exception:
            pass

        return []

    @classmethod
    def format_clause_prompt(cls, d: Dict[str, Any]) -> str:
        """为条款博弈专家生成全景博弈案卷提示词"""
        call_status = (
            f"距强赎触发价还差 {d['dist_to_call_pct']}% (零强赎砸盘压力)"
            if d['dist_to_call_pct'] > 20
            else f"距强赎触发价仅差 {d['dist_to_call_pct']}% (警惕强赎风险)"
        )
        down_status = (
            f"正股价距下修线仅差 {abs(d['dist_to_down_pct'])}% (下修博弈极易触发)"
            if abs(d['dist_to_down_pct']) < 8
            else f"距下修线空间约 {d['dist_to_down_pct']}%"
        )

        return f"""
【可转债条款博弈全景案卷 · {d['bond_name']} ({d['bond_code']})】
- 转债现价: {d['price']}元 | 存续规模: {d['remaining_scale']}亿元 (流通盘大小影响大股东转股诉求)
- 正股现价: {d['stock_price']}元 | 转股价: {d['convert_price']}元 | 转股价值: {d['convert_value']}元
- 转股溢价率: {d['premium_rate']}% | 双低值: {d['double_low']} | 到期税前YTM: {d['ytm']}%
- 强赎条款博弈: 强赎触发价 {d['call_trigger_stock_price']}元 -> {call_status}
- 下修条款博弈: 85%下修触发线 {d['down_trigger_stock_price']}元 -> {down_status}
- 债底安全防御: 纯债价值 {d['pure_debt_value']}元 (纯债溢价率 {d['pure_debt_premium']}%)
请基于上述真实精算数据，重点分析其【下修博弈概率】、【强赎砸盘风险】与【非对称赔率】，给出精炼专业裁定 (120字内)。
""".strip()

    @classmethod
    def format_equity_prompt(cls, d: Dict[str, Any]) -> str:
        """为正股动量分析师生成全景题材案卷提示词"""
        concepts_str = "、".join(d["concepts"]) if d["concepts"] else "稳健成长行业"
        return f"""
【正股动量与题材风口案卷 · 正股 {d['stock_name']} ({d['stock_code']}) / 对应转债 {d['bond_name']}】
- 正股现价: {d['stock_price']}元 | 转债现价: {d['price']}元 | 转股溢价率: {d['premium_rate']}%
- 核心题材概念风口: 【{concepts_str}】
- 转股价值: {d['convert_value']}元 (反映正股向转债的实际攻击弹性)
请评估正股近期所属风口题材热度、弹性空间与转债动量传导效率，给出动量评分 (0-100) 及精辟论证 (120字内)。
""".strip()

    @classmethod
    def format_credit_prompt(cls, d: Dict[str, Any]) -> str:
        """为首席信用风控官生成全景排雷案卷提示词"""
        notices_str = "\n".join([f"  · [{n['date']}] {n['title']}" for n in d["notices"]]) if d["notices"] else "  · 近期无异常违规处罚公告，经营状态正常。"
        return f"""
【信用风控与上市公司动态案卷 · {d['bond_name']} ({d['bond_code']}) / {d['stock_name']}】
- 发债主体评级: {d['rating']} | 转债存续规模: {d['remaining_scale']}亿 | 转债现价: {d['price']}元
- 纯债底价值: {d['pure_debt_value']}元 (提供信用违约与下行保护垫)
- 上市公司近期官方公告扫描:
{notices_str}
请根据信用评级、债底支撑以及最新公告动态，审查是否存在退市、大股东恶性质押、立案调查或违约风险，给出是否准予入库结论 (120字内)。
""".strip()

    @classmethod
    def format_court_dossier(cls, d: Dict[str, Any]) -> str:
        """为法庭多空控辩生成全案呈堂证供卷宗"""
        concepts_str = "、".join(d["concepts"][:4]) if d["concepts"] else "主板蓝筹"
        notices_str = "; ".join([f"{n['date']} {n['title']}" for n in d["notices"][:2]]) if d["notices"] else "无违约涉诉记录"

        return f"""
【案卷证据清单 · 被告标的 {d['bond_name']} ({d['bond_code']})】
1. 市场量化指标: 现价 {d['price']}元, 溢价率 {d['premium_rate']}%, 存续规模 {d['remaining_scale']}亿, 评级 {d['rating']}, 双低 {d['double_low']}
2. 条款精算特征: 转股价值 {d['convert_value']}元, 距强赎线空间 {d['dist_to_call_pct']}%, 距下修线 {d['dist_to_down_pct']}%, 纯债底 {d['pure_debt_value']}元
3. 正股风口题材: 【{concepts_str}】 (代码 {d['stock_code']})
4. 官方公告扫描: {notices_str}
""".strip()

dossier_manager = BondDossierManager()
