"""
策略参数与数据契约适配器 (Strategy Parameter & Schema Adapter)
保障多版本迭代下的向前/向后兼容性 (Backward & Forward Compatibility):
1. 当升级代码引入新参数时 (如 sort_by, double_low_weight, ai_filter 等)，老策略数据平滑补充默认值，避免 KeyError；
2. 当未来参数重命名或类型变更时，统一在此处进行别名映射与清洗适配；
3. 保障策略入参在数据库存储、回测引擎与智能体初筛中的严格契约一致性。
"""

from typing import Dict, Any, Optional

# 系统核心默认量化初筛参数字典 (Schema 基准)
DEFAULT_STRATEGY_PARAMS: Dict[str, Any] = {
    "min_price": 95.0,             # 最低价格下限(元)
    "max_price": 130.0,            # 最高价格上限(元)
    "max_scale": 15.0,             # 剩余流通规模上限(亿元)
    "max_premium": 70.0,           # 转股溢价率上限(%)
    "double_low_weight": 1.0,      # 双低加权因子 W (价格 + W * 溢价率)
    "top_n": 15,                   # 入围前N只标的
    "sort_by": "double_low",       # 排序字段: double_low, premium_rate, price, ytm
    "sort_ascending": True,        # 是否升序排列 (True: 小到大, False: 大到小)
    "ai_filter": False             # 是否开启多智能体深度会诊
}

# 参数别名映射表 (兼容历史版本可能出现的命名差异)
PARAM_ALIASES = {
    "scale_limit": "max_scale",
    "scale": "max_scale",
    "premium_limit": "max_premium",
    "premium_rate": "max_premium",
    "price_min": "min_price",
    "price_max": "max_price",
    "w": "double_low_weight",
    "order_by": "sort_by"
}

def normalize_strategy_params(raw_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    清洗并规范化策略参数：
    1. 填充缺失字段的基准默认值；
    2. 处理参数别名转换；
    3. 类型安全转换与边界保护。
    """
    result = dict(DEFAULT_STRATEGY_PARAMS)
    if not raw_params or not isinstance(raw_params, dict):
        return result

    # 1. 别名兼容
    cleaned_input = {}
    for k, v in raw_params.items():
        standard_key = PARAM_ALIASES.get(k, k)
        cleaned_input[standard_key] = v

    # 2. 合并入参
    for k, default_val in DEFAULT_STRATEGY_PARAMS.items():
        if k in cleaned_input and cleaned_input[k] is not None:
            val = cleaned_input[k]
            try:
                # 严格类型适配
                if isinstance(default_val, bool):
                    result[k] = bool(val)
                elif isinstance(default_val, int):
                    result[k] = int(val)
                elif isinstance(default_val, float):
                    result[k] = float(val)
                elif isinstance(default_val, str):
                    result[k] = str(val)
                else:
                    result[k] = val
            except (ValueError, TypeError):
                result[k] = default_val

    # 3. 补充其它非基准但合法的自定义参数
    for k, v in cleaned_input.items():
        if k not in result:
            result[k] = v

    return result
