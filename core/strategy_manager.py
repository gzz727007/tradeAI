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
            # 确保 AI 动态价格点协同策略已作为系统内置策略注册
            pt = session.query(Strategy).filter(Strategy.id == "strat_price_trigger").first()
            if not pt:
                new_s = Strategy(
                    id="strat_price_trigger",
                    name="AI动态价格点协同策略",
                    category="系统内置",
                    description="基于大模型动态定价、风控一票否决白名单与脉冲回撤追踪止盈的事件驱动型价格点随时买卖策略。",
                    params_json=json.dumps({
                        "default_entry_ceiling": 104.5,
                        "default_target_price": 120.0,
                        "default_hard_stop": 128.0,
                        "default_trailing_drop": 0.025,
                        "max_holdings": 10,
                        "max_scale": 10.0,
                        "pulse_threshold": 0.08,
                        "sort_by": "double_low"
                    }, ensure_ascii=False),
                    version=1
                )
                session.add(new_s)
                session.commit()

            records = session.query(Strategy).order_by(Strategy.created_at.asc()).all()
            return [s.to_dict() for s in records]
        finally:
            session.close()

    def create_strategy_instance(self, strat_def: Dict[str, Any]):
        """根据策略定义动态实例化可执行策略对象 (支持事件驱动价格点/传统配置型/AI代码进化型)"""
        s_id = (strat_def.get("id") or "").lower()
        s_name = strat_def.get("name") or ""
        params = strat_def.get("params") or {}

        # AI 代码进化型策略: 沙箱实例化 LLM 生成的策略类
        if params.get("__code__"):
            from core.strategy_sandbox import instantiate_strategy_class, CodeSafetyError
            try:
                inst = instantiate_strategy_class(params["__code__"], strat_def)
                # 数据库注册名覆盖生成时的占位名, 保证竞技场/回测展示一致
                if s_name:
                    inst.name = s_name
                return inst
            except CodeSafetyError as e:
                print(f"[WARN] AI 代码策略 {s_id} 沙箱实例化失败, 回退配置型: {e}")

        if s_id == "strat_price_trigger" or "价格" in s_name or "price" in s_id or "trigger" in s_id:
            from strategies.price_trigger_strategy import PriceTriggerCBStrategy
            return PriceTriggerCBStrategy(
                name=s_name or "AI动态价格点协同策略",
                description=strat_def.get("description", ""),
                default_entry_ceiling=params.get("default_entry_ceiling", 104.5),
                default_target_price=params.get("default_target_price", 120.0),
                default_hard_stop=params.get("default_hard_stop", 128.0),
                default_trailing_drop=params.get("default_trailing_drop", 0.025),
                max_holdings=params.get("max_holdings", 10),
                max_scale=params.get("max_scale", 10.0),
                pulse_threshold=params.get("pulse_threshold", 0.08)
            )

        from strategies.configurable_strategy import ConfigurableCBStrategy
        return ConfigurableCBStrategy(strat_def)

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
        调用大模型基于市场规律假说，自主探索并生成一套可量化的可转债新策略并写入数据库。
        失败时直接抛出异常 (由 API 层转为 502 返回前端)，绝不静默伪造模板策略误导用户。
        """
        from core.llm_manager import llm_manager, extract_json_content
        import time as _time
        client, model = llm_manager.get_client()

        if not client:
            raise RuntimeError("未配置可用的大模型 API，无法进行 AI 策略挖掘。请前往「设置」配置 LLM 供应商。")

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
        last_err = None
        for attempt in range(1, 4):  # 实测中转站约 10-30% 概率返回围栏包裹/超时，3 次重试将成功率推至 99%+
            try:
                response = client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5
                )
                # 健壮解析: 兼容 ```json 围栏 / 前后缀噪声
                res_data = extract_json_content(response.choices[0].message.content)
                if "name" not in res_data or "params" not in res_data:
                    raise ValueError(f"LLM 返回字段缺失: {list(res_data.keys())}")
                strat_id = f"strat_ai_{int(datetime.now().timestamp())}"
                return self.add_strategy(
                    strat_id=strat_id,
                    name=res_data.get("name", "AI探索新策略"),
                    category="AI探索生成",
                    description=res_data.get("description", "基于大模型自主挖掘的市场微观特征构建的策略。"),
                    params=res_data.get("params")
                )
            except Exception as e:
                last_err = e
                print(f"[WARN] AI 生成策略第 {attempt}/3 次尝试失败: {type(e).__name__}: {str(e)[:120]}")
                if attempt < 3:
                    _time.sleep(1.5 * attempt)

        raise RuntimeError(f"AI 策略挖掘连续 3 次失败，最后错误: {type(last_err).__name__}: {str(last_err)[:200]}")

strategy_manager = StrategyManager()
