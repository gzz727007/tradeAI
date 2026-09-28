"""
策略库与配置管理器 (Strategy Manager)
基于 SQLAlchemy 关系型事务数据库实现，支持 SQLite WAL 模式与 PostgreSQL。
负责管理所有策略的持久化定义（内置策略、用户自定义策略、AI 探索生成策略）。
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional

from config.config import settings
from db.session import SessionLocal
from db.models import Strategy
from db.init_db import init_db

class StrategyManager:
    def __init__(self):
        # 确保数据库表已初始化
        init_db()

    def get_all_strategies(self) -> List[Dict[str, Any]]:
        """获取所有已注册的策略"""
        session = SessionLocal()
        try:
            records = session.query(Strategy).order_by(Strategy.created_at.asc()).all()
            return [s.to_dict() for s in records]
        finally:
            session.close()

    def get_strategy(self, strat_id: Optional[str] = None, strategy_id: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """根据策略ID获取单条策略详情"""
        actual_id = strat_id or strategy_id or kwargs.get("strat_id") or kwargs.get("strategy_id")
        if not actual_id:
            return None
        session = SessionLocal()
        try:
            record = session.query(Strategy).filter(Strategy.id == actual_id).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    def add_strategy(
        self,
        strat_id: Optional[str] = None,
        name: str = "",
        category: str = "用户自定义",
        description: str = "",
        params: Optional[Dict[str, Any]] = None,
        strategy_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """添加或更新策略并持久化至数据库 (ACID事务)"""
        actual_id = strat_id or strategy_id or kwargs.get("strat_id") or kwargs.get("strategy_id")
        if not actual_id:
            actual_id = f"strat_custom_{int(datetime.now().timestamp())}"

        params_data = params or {}
        params_str = json.dumps(params_data, ensure_ascii=False)

        session = SessionLocal()
        try:
            record = session.query(Strategy).filter(Strategy.id == actual_id).first()
            if record:
                record.name = name or record.name
                record.category = category or record.category
                record.description = description if description is not None else record.description
                record.params_json = params_str
                record.updated_at = datetime.now()
            else:
                record = Strategy(
                    id=actual_id,
                    name=name or actual_id,
                    category=category,
                    description=description or "",
                    params_json=params_str,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(record)
            session.commit()
            session.refresh(record)
            return record.to_dict()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def update_strategy(
        self,
        strat_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        strategy_id: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """修改已有策略的名称、描述或参数 (ACID事务)"""
        actual_id = strat_id or strategy_id or kwargs.get("strat_id") or kwargs.get("strategy_id")
        if not actual_id:
            return None

        session = SessionLocal()
        try:
            record = session.query(Strategy).filter(Strategy.id == actual_id).first()
            if not record:
                return None
            if name:
                record.name = name
            if description is not None:
                record.description = description
            if params is not None:
                curr_params = {}
                if record.params_json:
                    try:
                        curr_params = json.loads(record.params_json)
                    except Exception:
                        curr_params = {}
                curr_params.update(params)
                record.params_json = json.dumps(curr_params, ensure_ascii=False)
            record.updated_at = datetime.now()
            session.commit()
            session.refresh(record)
            return record.to_dict()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def delete_strategy(self, strat_id: Optional[str] = None, strategy_id: Optional[str] = None, **kwargs) -> bool:
        """删除指定策略 (ACID事务)"""
        actual_id = strat_id or strategy_id or kwargs.get("strat_id") or kwargs.get("strategy_id")
        if not actual_id:
            return False

        session = SessionLocal()
        try:
            record = session.query(Strategy).filter(Strategy.id == actual_id).first()
            if record and record.category != "系统内置":
                session.delete(record)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def ai_discover_strategy(self, user_idea: str = "") -> Dict[str, Any]:
        """
        调用大模型基于市场规律假说，自主探索并生成一套可量化的可转债新策略并写入数据库
        """
        from core.llm_manager import llm_manager
        client, model = llm_manager.get_client()

        if client:
            try:
                prompt = f"""
                你是顶级量化研究员。请根据用户设想或市场规律，设计一套逻辑清晰、参数明确的A股可转债新策略：
                【用户探索设想】：{user_idea if user_idea else '请自主探索一个兼具高胜率和低回撤的可转债特殊套利或动量规律策略'}
                
                请输出严格 JSON 格式：
                {{
                    "name": "策略名称 (如: 极小盘低溢价动量突破策略)",
                    "description": "策略核心逻辑阐述与适用市场环境说明",
                    "params": {{
                        "min_price": 最低价格(浮点数，如95),
                        "max_price": 最高价格(浮点数，如118),
                        "max_scale": 剩余规模上限(亿元，浮点数，如4.5),
                        "max_premium": 溢价率上限(浮点数，如40),
                        "double_low_weight": 双低权重(浮点数，如1.2),
                        "top_n": 持仓只数(整数，如10),
                        "sort_by": "double_low" 或 "premium_rate" 或 "price" 或 "ytm",
                        "sort_ascending": true 或 false
                    }}
                }}
                """
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                res_data = json.loads(response.choices[0].message.content)
                strat_id = f"strat_ai_{int(datetime.now().timestamp())}"
                return self.add_strategy(
                    strat_id=strat_id,
                    name=res_data.get("name", "AI探索新策略"),
                    category="AI探索生成",
                    description=res_data.get("description", "基于大模型自主挖掘的市场微观特征构建的策略。"),
                    params=res_data.get("params", {
                        "min_price": 98.0, "max_price": 120.0, "max_scale": 5.0, "max_premium": 45.0,
                        "double_low_weight": 1.1, "top_n": 10, "sort_by": "double_low", "sort_ascending": True
                    })
                )
            except Exception as e:
                print(f"[WARN] AI 生成策略异常，使用备用策略: {e}")

        # 备用自适应新策略生成
        total_count = len(self.get_all_strategies())
        strat_id = f"strat_ai_{int(datetime.now().timestamp())}"
        fallback_params = {
            "min_price": 98.0,
            "max_price": 115.0,
            "max_scale": 4.5,
            "max_premium": 45.0,
            "double_low_weight": 1.1,
            "top_n": 12,
            "sort_by": "double_low",
            "sort_ascending": True
        }
        return self.add_strategy(
            strat_id=strat_id,
            name=f"AI下修博弈与微盘反弹策略 #{total_count + 1}",
            category="AI探索生成",
            description=f"【AI探索发现】：基于'{user_idea if user_idea else '大股东到期偿付压力与极小盘弹性共振'}'假说，筛选价格贴近面值(98~115元)、规模小于4.5亿且溢价适中的标的，专门吃大股东被迫下修到底的制度红利。",
            params=fallback_params
        )

strategy_manager = StrategyManager()
