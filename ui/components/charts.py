"""
交互式图表组件库 (Plotly Charts)
提供多策略净值走势图、水下回撤图、指标雷达对比图的生成逻辑。
"""

import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

COLOR_PALETTE = {
    "中证转债基准": "#9E9E9E",    # 灰色
    "经典双低轮动": "#2196F3",    # 蓝色
    "高YTM深度防御": "#4CAF50",    # 绿色
    "小盘高弹性进攻": "#FF9800",    # 橙色
    "AI多智能体增强": "#E91E63"     # 亮粉色/主打推荐
}

def create_equity_curves_chart(nav_df: pd.DataFrame) -> go.Figure:
    """创建多策略累计净值走势图"""
    fig = go.Figure()
    
    for col in nav_df.columns:
        color = COLOR_PALETTE.get(col, "#00BCD4")
        width = 3.0 if "AI" in col else (2.0 if "基准" in col else 1.8)
        dash = "dash" if "基准" in col else "solid"
        
        fig.add_trace(go.Scatter(
            x=nav_df.index,
            y=nav_df[col],
            mode="lines",
            name=col,
            line=dict(color=color, width=width, dash=dash),
            hovertemplate=f"<b>{col}</b><br>日期: %{{x|%Y-%m-%d}}<br>净值: %{{y:.4f}}<extra></extra>"
        ))
        
    fig.update_layout(
        title="<b>多策略历史累计净值对决 (以 1.0 为基准归一化)</b>",
        xaxis_title="交易日期",
        yaxis_title="归一化累计净值",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig

def create_drawdown_chart(drawdown_df: pd.DataFrame) -> go.Figure:
    """创建动态水下回撤图 (Underwater Plot)"""
    fig = go.Figure()
    
    for col in drawdown_df.columns:
        color = COLOR_PALETTE.get(col, "#00BCD4")
        fig.add_trace(go.Scatter(
            x=drawdown_df.index,
            y=drawdown_df[col],
            mode="lines",
            name=col,
            line=dict(color=color, width=1.5),
            hovertemplate=f"<b>{col}</b>: %{{y:.2f}}%<extra></extra>"
        ))
        
    fig.update_layout(
        title="<b>各策略动态水下回撤对比 (Underwater Drawdown %)</b>",
        xaxis_title="交易日期",
        yaxis_title="回撤百分比 (%)",
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig

def create_metrics_bar_chart(metrics_summary: Dict[str, Dict[str, Any]]) -> go.Figure:
    """创建策略夏普与卡玛比率对比柱状图"""
    strategies = list(metrics_summary.keys())
    sharpes = [metrics_summary[s]["sharpe_ratio"] for s in strategies]
    calmars = [metrics_summary[s]["calmar_ratio"] for s in strategies]
    
    fig = go.Figure(data=[
        go.Bar(name="夏普比率 (Sharpe)", x=strategies, y=sharpes, marker_color="#3F51B5"),
        go.Bar(name="卡玛比率 (Calmar=年化/回撤)", x=strategies, y=calmars, marker_color="#009688")
    ])
    
    fig.update_layout(
        title="<b>风险调整后收益质量对比 (夏普 & 卡玛比率，越高越优秀)</b>",
        barmode="group",
        template="plotly_white",
        yaxis_title="比率数值",
        margin=dict(l=40, r=40, t=60, b=40)
    )
    return fig
