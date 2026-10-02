"""
AI 策略代码沙箱 (Strategy Code Sandbox) — v1
LLM 生成策略代码的三道安全闸门与执行器，是"生成→回测→体检→反馈"进化环的安全底座：

1. AST 静态白名单校验: 禁危险 import/内建调用/dunder 属性链，只放行纯计算生态
2. 受限命名空间执行: 白名单 builtins + 预注入 pandas/numpy，隔断 jailbreak 通道
3. 契约校验: 必须产出 BaseCBStrategy 子类且实现 select_portfolio / on_bar 之一

安全边界说明 (v1): 单机单用户场景，防的是 LLM 幻觉误产危险代码 (误删文件/联网/死循环写盘)，
非恶意对抗；进程级硬隔离留待 v2 子进程池。
"""

import ast
from typing import Dict, Any, Tuple, Optional, List

# ==============================================================
# 白名单定义
# ==============================================================

# 允许 import 的第三方/标准库模块 (纯计算生态，无 IO/网络/进程能力)
ALLOWED_IMPORTS = {
    "pandas", "numpy", "math", "statistics", "decimal",
    "datetime", "typing", "itertools", "collections", "functools",
}

# 禁用的内建函数名 ( jailsbreak 主通道: IO/执行/反射 )
FORBIDDEN_BUILTINS = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "dir", "setattr", "delattr",
    "memoryview", "bytearray",  # super 放行: 逃逸链靠 dunder 属性访问, 已被单独封死
}

# 生成代码中禁用任何 dunder (双下划线) 属性访问/赋值，封死 __class__/__globals__/__subclasses__ 逃逸链
def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


class CodeSafetyError(Exception):
    """策略代码未通过安全校验"""


def validate_strategy_code(code: str) -> Tuple[bool, List[str]]:
    """
    AST 静态安全校验
    :return: (是否通过, 违规原因列表)
    """
    errors: List[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, [f"语法错误: line {e.lineno}: {e.msg}"]

    for node in ast.walk(tree):
        # ---- import 闸门 ----
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORTS:
                    errors.append(f"line {node.lineno}: 禁止 import '{alias.name}' (白名单外)")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root and root not in ALLOWED_IMPORTS:
                errors.append(f"line {node.lineno}: 禁止 from '{node.module}' import (白名单外)")

        # ---- 内建函数调用闸门 (覆盖所有函数调用的函数名) ----
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in FORBIDDEN_BUILTINS:
                errors.append(f"line {node.lineno}: 禁止调用内建 '{fn.id}()'")
            if isinstance(fn, ast.Attribute) and fn.attr in FORBIDDEN_BUILTINS:
                errors.append(f"line {node.lineno}: 禁止调用方法 '.{fn.attr}()'")

        # ---- dunder 属性/名称闸门 (仅放行构造必需的 __init__) ----
        elif isinstance(node, ast.Attribute):
            if _is_dunder(node.attr) and node.attr != "__init__":
                errors.append(f"line {node.lineno}: 禁止访问 dunder 属性 '.{node.attr}'")
        elif isinstance(node, ast.Name):
            if _is_dunder(node.id) and node.id not in ("__init__",):
                errors.append(f"line {node.lineno}: 禁止引用 dunder 名称 '{node.id}'")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_dunder(node.name) and node.name != "__init__":
                errors.append(f"line {node.lineno}: 禁止定义 dunder 方法 '{node.name}'")

    return len(errors) == 0, errors[:20]  # 最多返回前 20 条避免刷屏


# ==============================================================
# 受限命名空间执行
# ==============================================================

def _build_restricted_builtins() -> Dict[str, Any]:
    """构建白名单内建函数字典 (从 __builtins__ 中摘除所有危险能力)"""
    import builtins as _b
    safe_names = [
        # 数值与逻辑
        "abs", "all", "any", "bool", "dict", "divmod", "enumerate", "filter", "float",
        "format", "frozenset", "hash", "int", "isinstance", "issubclass", "len", "list",
        "map", "max", "min", "next", "object", "pow", "print", "range", "repr", "reversed",
        "round", "set", "slice", "sorted", "str", "sum", "super", "tuple", "type", "zip",
        "True", "False", "None",
    ]
    restricted = {n: getattr(_b, n) for n in safe_names if hasattr(_b, n)}

    # 受控 __import__: 仅放行白名单模块 (import 语句运行时必需; AST 已静态拦截, 此为双保险)
    def _guarded_import(name, *args, **kwargs):
        if name.split(".")[0] not in ALLOWED_IMPORTS:
            raise ImportError(f"沙箱禁止 import '{name}'")
        return getattr(_b, "__import__")(name, *args, **kwargs)

    restricted["__import__"] = _guarded_import
    # __build_class__: class 语句运行时钩子 (类创建机制本身, 无逃逸面)
    restricted["__build_class__"] = getattr(_b, "__build_class__")
    return restricted


def instantiate_strategy_class(code: str, strat_dict: Dict[str, Any]):
    """
    在受限命名空间中执行策略代码并实例化策略对象
    契约: 代码须定义 BaseCBStrategy 子类; 构造优先尝试 Cls(strat_dict)，回退 Cls()
    :raises CodeSafetyError: 安全校验未通过 / 未找到策略类 / 实例化失败
    """
    ok, errors = validate_strategy_code(code)
    if not ok:
        raise CodeSafetyError("安全校验未通过: " + "; ".join(errors))

    # 预注入数据科学生态 (生成代码无需自行 import 也可直接用 pd/np)
    import pandas as pd
    import numpy as np
    import math
    from datetime import datetime, timedelta
    from strategies.base import BaseCBStrategy, BaseEventStrategy

    namespace: Dict[str, Any] = {
        "__builtins__": _build_restricted_builtins(),
        "__name__": "<ai_strategy>",  # class 定义运行时需要模块名
        "pd": pd, "np": np, "numpy": np, "pandas": pd, "math": math,
        "datetime": datetime, "timedelta": timedelta,
        # 策略基类预注入: 生成代码直接 class XxxStrategy(BaseCBStrategy) 继承
        "BaseCBStrategy": BaseCBStrategy, "BaseEventStrategy": BaseEventStrategy,
    }
    try:
        exec(compile(code, "<ai_strategy>", "exec"), namespace)
    except Exception as e:
        raise CodeSafetyError(f"代码执行失败: {type(e).__name__}: {str(e)[:200]}")

    # 寻找代码中定义的策略类 (BaseCBStrategy 子类，排除基类自身)
    candidates = [
        obj for obj in namespace.values()
        if isinstance(obj, type)
        and issubclass(obj, BaseCBStrategy)
        and obj not in (BaseCBStrategy, BaseEventStrategy)
        and obj.__module__ == "<ai_strategy>"
    ]
    if not candidates:
        raise CodeSafetyError("未找到 BaseCBStrategy 子类，请定义 class XxxStrategy(BaseCBStrategy)")

    cls = candidates[0]
    for args in ((strat_dict,), ()):
        try:
            instance = cls(*args)
            instance.__module__ = cls.__module__
            return instance
        except TypeError:
            continue
        except Exception as e:
            raise CodeSafetyError(f"策略实例化失败 ({cls.__name__}): {type(e).__name__}: {str(e)[:200]}")
    raise CodeSafetyError(f"策略类 {cls.__name__} 构造签名不兼容 (需支持 Cls(strat_dict) 或 Cls())")


# ==============================================================
# 生成 Prompt 的数据契约与参考代码 (few-shot 先验)
# ==============================================================

QUOTES_CONTRACT = """
【数据契约】 select_portfolio(current_date, quotes_df) 的 quotes_df 为某交易日全市场转债截面 DataFrame，列包括:
- symbol / bond_code: 转债代码      - bond_name / name: 转债简称 (含"退"字=退市券, 必须剔除)
- price: 转债收盘价(元)             - premium_rate: 转股溢价率(%) 
- pure_debt_value: 纯债价值         - convert_value: 转股价值
- double_low: 双低值(=price+premium_rate)
- remaining_years: 剩余年限(年)      - issue_scale: 发行规模(亿元)
- convert_price: 转股价             - maturity_date: 到期日
- stock_code / stock_name: 正股代码/简称
- stock_market_cap: 正股总市值(亿元, 可能为 NaN, 筛选前需 dropna)
- stock_mom_20: 正股 20 日动量(收益率小数, 可能 NaN)
- cb_mom_20: 转债自身 20 日动量(收益率小数, 可能 NaN)
【返回】 DataFrame, 必含列: bond_code(字符串), weight(浮点, 自动等权可调用 self.calculate_weights(df))
【注意】 any 列都可能缺 NaN，请先 fillna/dropna 处理; 选出的每权重和不需要归一(引擎会按 weight_map 买入)。
"""

REFERENCE_CODE = '''
【参考骨架 1: 截面轮动 (推荐大多数策略)】
import pandas as pd
class MyRotationStrategy(BaseCBStrategy):
    def __init__(self, strat_dict=None):
        p = (strat_dict or {}).get("params", {})
        super().__init__(name=(strat_dict or {}).get("name", "AI策略"), top_n=int(p.get("top_n", 10)))
        self.params = p
        self.strategy_mode = "ROTATION"
    def select_portfolio(self, current_date, quotes_df):
        df = quotes_df.copy()
        df = df[~df["bond_name"].astype(str).str.contains("退", na=False)]
        df = df[(df["price"] >= 95) & (df["price"] <= 130)]
        df = df.dropna(subset=["stock_market_cap"])
        df = df[df["stock_market_cap"] <= 30]          # 微盘
        df = df[df["stock_mom_20"] > 0]                 # 正股动量为正
        ranked = df.sort_values("double_low").head(self.top_n)
        return self.calculate_weights(ranked)

【参考骨架 2: 事件/价格点驱动 (on_bar 自主买卖)】
class MyEventStrategy(BaseEventStrategy):   # strategy_mode 自动为 EVENT_PRICE
    def __init__(self, strat_dict=None):
        super().__init__(name=(strat_dict or {}).get("name", "AI事件策略"))
    def on_bar(self, context, market_data):
        # context.buy(symbol, price, target_money=金额, reason=...) / context.sell(symbol, price, reason=...)
        # context.positions 持仓字典; context.get_total_assets(price_map) 总资产
        # market_data 即 quotes_df 同契约; 典型用法: 对每行判断价格点触发
        price_map = dict(zip(market_data["symbol"], market_data["price"]))
        for _, row in market_data.iterrows():
            ...
【硬性约定】
1. 只输出一个 Python 代码块，其中必须包含且仅包含一个策略类定义(继承 BaseCBStrategy 或 BaseEventStrategy)
2. 严禁 import os/sys/subprocess/socket/requests/urllib/open 文件读写；只允许 pandas/numpy/math/datetime/typing/itertools/collections/functools
3. 轮动类用 select_portfolio，事件类用 on_bar；不要重写 on_start 之外的其它生命周期钩子
4. 所有阈值参数从 self.params 读取并给出合理默认值，硬编码数值不超过 3 个
'''


def build_evolve_prompt(user_idea: str, feedback: Optional[str] = None, round_idx: int = 1) -> str:
    """构造 RD-Agent 式代码生成 prompt: 设想 + 数据契约 + 参考骨架 + 上一轮失败反馈"""
    parts = [
        "你是顶级可转债量化研究员兼工程师。请将下述投资设想实现为一个可回测的 Python 策略类。",
        f"【投资设想】{user_idea}",
        QUOTES_CONTRACT,
        REFERENCE_CODE,
    ]
    if feedback:
        parts.append(
            f"【第 {round_idx - 1} 轮验证失败反馈 — 必须针对性修复】\n{feedback}\n"
        )
    parts.append("请输出修正后的完整策略代码 (仅一个代码块)。")
    return "\n".join(parts)


def extract_code_from_llm(text: str) -> str:
    """从 LLM 返回中提取 Python 代码块 (兼容 ```python 围栏 / 裸代码)"""
    import re
    if "```" in text:
        blocks = re.findall(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
        if blocks:
            return max(blocks, key=len).strip()
    return text.strip()
