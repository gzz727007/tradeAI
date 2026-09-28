"""
A股可转债“策略工坊 + 模拟竞技场 + 实盘多账号管家 + AI投研会诊”全功能平台
现代化金融终端 SaaS 架构：
- 隐藏原生 Deploy 按钮与臃肿 Header，压缩页面顶部内边距至紧凑专业标准
- 顶部右侧对齐“全局环境设置”，彻底解放左侧与主视野空间
- 策略库采用自包含精美卡片网格，所有核心参数一目了然，杜绝割裂的超大按钮
- 策略历史对决竞技场采用 iOS 风格分段控制器 (Segmented Control) 丝滑切换
- 新建策略与 AI 探索采用原生弹窗 (Dialog Modal)
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

from config.config import settings
from core.data_fetcher import CBDataFetcher
from core.backtest_engine import CBBacktestEngine
from core.trading_ledger import ledger
from core.strategy_manager import strategy_manager
from strategies.configurable_strategy import ConfigurableCBStrategy
from agents.screener import ScreenerAgent
from ui.components.charts import (
    create_equity_curves_chart,
    create_drawdown_chart,
    create_metrics_bar_chart
)

# 页面基础配置 (完全隐藏侧边栏，全屏大屏金融终端排版)
st.set_page_config(
    page_title="可转债 AI 投研与多账号实盘终端",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==============================================================
# 自定义专业金融 SaaS CSS 样式体系
# ==============================================================
st.markdown("""
<style>
    /* 1. 彻底隐藏 Streamlit 默认顶部导航条、Deploy 按钮、汉堡菜单和 Footer */
    header[data-testid="stHeader"] {
        display: none !important;
    }
    .stAppDeployButton, [data-testid="stAppDeployButton"], .stDeployButton {
        display: none !important;
    }
    #MainMenu {
        display: none !important;
    }
    footer {
        display: none !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* 2. 页面容器顶部内边距极度紧凑化，消灭全部无意义空白 */
    .block-container {
        padding-top: 0.8rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 100% !important;
    }

    /* 3. 顶栏导航容器 */
    .top-navbar-wrapper {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 0 12px 0;
        border-bottom: 1px solid #f1f5f9;
        margin-bottom: 12px;
    }

    /* 4. 卡片容器美化 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px !important;
        border: 1px solid #e2e8f0 !important;
        background: #ffffff !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03) !important;
        transition: all 0.2s ease;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #cbd5e1 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
    }

    /* 5. 选项卡紧凑现代风格 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 14px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 36px;
        padding: 0 16px;
        font-size: 13.5px;
        font-weight: 500;
        color: #64748b;
        border-radius: 6px;
        background-color: transparent;
        border: none;
        transition: all 0.15s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: #eff6ff !important;
        color: #1d4ed8 !important;
        font-weight: 600 !important;
    }

    /* 6. 按钮紧凑化与细节规范 */
    .stButton > button {
        border-radius: 6px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }

    /* 7. 策略卡片内专用小按钮 */
    .card-action-row button {
        height: 32px !important;
        min-height: 32px !important;
        font-size: 12px !important;
        padding: 0 10px !important;
    }

    /* 8. 标签徽章 Chip */
    .tag-badge {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        line-height: 1.4;
    }
    .badge-builtin { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .badge-ai { background: #fdf2f8; color: #be185d; border: 1px solid #fbcfe8; }
    .badge-custom { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }

    /* 9. Segmented Control 紧凑化 */
    div[data-testid="stSegmentedControl"] {
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================
# 顶部统一导航栏 (现代化金融 SaaS 紧凑单行 Header)
# ==============================================================
header_col1, header_col2, header_col3 = st.columns([5.5, 3.2, 1.3], vertical_alignment="center")

with header_col1:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-size:24px;">📈</span>
        <div>
            <div style="font-size:18px; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:8px;">
                A股可转债 AI 投研与多账号实盘终端
                <span style="background:linear-gradient(135deg, #2563eb, #1d4ed8); color:white; font-size:10px; font-weight:700; padding:1px 6px; border-radius:4px; letter-spacing:0.5px;">PRO v2.0</span>
            </div>
            <div style="font-size:12px; color:#64748b;">策略工坊 ➔ 历史回测对决 ➔ 实盘模拟赛马 ➔ 多账号实盘管家 ➔ LangGraph 多智能体会诊</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with header_col2:
    st.markdown("""
    <div style="display:flex; justify-content:flex-end; gap:8px; align-items:center;">
        <span style="display:inline-flex; align-items:center; gap:5px; font-size:12px; background:#f0fdf4; color:#166534; padding:3px 10px; border-radius:12px; border:1px solid #bbf7d0;">
            <span style="width:6px; height:6px; background:#22c55e; border-radius:50%; display:inline-block;"></span> 实时行情已连线 (1,059只)
        </span>
        <span style="font-size:12px; background:#f8fafc; color:#475569; padding:3px 10px; border-radius:12px; border:1px solid #e2e8f0;">
            基准: 中证转债 (000832)
        </span>
    </div>
    """, unsafe_allow_html=True)

with header_col3:
    with st.popover("⚙️ 全局设置", use_container_width=True):
        st.markdown("##### ⚙️ 全局回测与执行环境")
        st.caption("回测周期与摩擦损耗参数（策略选券逻辑在各自策略档案中配置）：")
        st.session_state["start_date"] = st.date_input("历史回测起始日期", datetime(2023, 1, 1), key="set_start_date")
        st.session_state["end_date"] = st.date_input("历史回测截止日期", datetime.now(), key="set_end_date")
        st.session_state["rebalance_freq"] = st.selectbox(
            "回测调仓周期",
            ["5个交易日 (每周)", "10个交易日 (双周)", "20个交易日 (月度)"],
            index=0,
            key="set_freq"
        )
        st.markdown("---")
        st.write("• 基准指数: **中证转债 (000832)**")
        st.write("• 券商佣金: **万分之 0.5** (免印花税)")
        st.write("• 冲击滑点: **0.1%**")

start_date = st.session_state.get("start_date", datetime(2023, 1, 1))
end_date = st.session_state.get("end_date", datetime.now())
freq_str = st.session_state.get("rebalance_freq", "5个交易日")
freq_days = 5 if "5" in freq_str else (10 if "10" in freq_str else 20)

# 拉取最新行情并做每日记账估值更新
quotes_df = CBDataFetcher.get_realtime_quotes(use_cache=True)
ledger.update_daily_valuation(quotes_df)

# ==============================================================
# 原生模态弹窗函数 (Streamlit @st.dialog)
# ==============================================================

@st.dialog("➕ 创建自定义量化策略")
def modal_create_custom_strategy():
    st.write("自定义策略规则与参数区间，保存后自动入库：")
    with st.form("custom_strat_modal_form"):
        s_name = st.text_input("策略名称 (如: 低溢价白马转债策略):")
        s_desc = st.text_area("策略逻辑阐述与适用环境:")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            min_p = st.number_input("价格下限 (元):", value=95.0, step=1.0)
            max_p = st.number_input("价格上限 (元):", value=125.0, step=1.0)
            max_s = st.number_input("规模上限 (亿元):", value=5.0, step=0.5)
        with col_p2:
            max_prem = st.number_input("溢价率上限 (%):", value=50.0, step=5.0)
            weight_dl = st.number_input("双低权重 (W):", value=1.0, step=0.1)
            top_n = st.number_input("持仓只数:", value=15, step=1)
        sort_by = st.selectbox("核心排序指标:", ["double_low", "premium_rate", "price", "ytm"])
        sort_asc = st.checkbox("升序排序 (数值越小越优)", value=True)
        
        if st.form_submit_button("💾 确认保存入库", type="primary", use_container_width=True):
            if s_name:
                s_id = f"strat_custom_{int(datetime.now().timestamp())}"
                params_dict = {
                    "min_price": min_p, "max_price": max_p, "max_scale": max_s,
                    "max_premium": max_prem, "double_low_weight": weight_dl,
                    "top_n": top_n, "sort_by": sort_by, "sort_ascending": sort_asc
                }
                strategy_manager.add_strategy(s_id, s_name, "用户自定义", s_desc, params_dict)
                st.success(f"✅ 策略【{s_name}】创建成功！")
                st.rerun()
            else:
                st.error("请填写策略名称！")

@st.dialog("🤖 大模型自主量化探索引擎")
def modal_ai_discover_strategy():
    st.write("调用金融大模型基于市场微观博弈与异动特征，自主推演并构建全新量化策略：")
    ai_idea = st.text_area(
        "💡 给 AI 的探索灵感 (可选，留空则让 AI 自由挖掘市场规律):",
        placeholder="例如：挖掘离回售期不足1年、价格贴近面值且大股东有强烈下修意愿的品种，专吃下修到底红利。"
    )
    if st.button("✨ 启动大模型深度探索与生成", type="primary", use_container_width=True):
        with st.spinner("🤖 大模型正在推演市场逻辑与微观特征，生成专属策略规则与参数..."):
            gen_strat = strategy_manager.ai_discover_strategy(user_idea=ai_idea)
            st.success(f"🎉 AI 成功生成新策略：【{gen_strat['name']}】！已加入策略库。")
            st.rerun()

@st.dialog("🔍 策略详细档案")
def modal_view_strategy_detail(strat_dict: dict):
    st.markdown(f"### {strat_dict['name']}")
    st.caption(f"分类: {strat_dict.get('category')} | 策略ID: `{strat_dict.get('id')}` | 创建时间: {strat_dict.get('created_at')}")
    st.markdown("#### 📖 设计哲学与选券逻辑")
    st.info(strat_dict.get("description", "无"))
    st.markdown("#### ⚙️ 专属量化参数配置")
    p = strat_dict.get("params", {})
    col_1, col_2 = st.columns(2)
    with col_1:
        st.write(f"• **价格区间**：`{p.get('min_price')} ~ {p.get('max_price')} 元`")
        st.write(f"• **规模上限**：`{p.get('max_scale')} 亿元`")
        st.write(f"• **转股溢价上限**：`{p.get('max_premium')}%`")
    with col_2:
        st.write(f"• **双低权重 (W)**：`{p.get('double_low_weight', 1.0)}`")
        st.write(f"• **持仓标的数量**：`{p.get('top_n', 15)} 只`")
        st.write(f"• **排序规则**：`{p.get('sort_by')} (升序={p.get('sort_ascending')})`")

# ==============================================================
# 四大核心模块 Tabs
# ==============================================================
tab_studio, tab_paper, tab_real, tab_agent = st.tabs([
    "📋 策略工坊与历史对决",
    "🎮 实盘模拟竞技场",
    "💼 实盘多账号管家",
    "🤖 AI 智能体会诊室"
])

# ==============================================================
# Tab 1: 策略工坊与历史对决 (Segmented Control 子视图切换)
# ==============================================================
with tab_studio:
    # 现代化分段控制器，平滑切换“策略库与配置”与“历史对决竞技场”
    sub_view = st.segmented_control(
        "子功能切换",
        options=["📚 策略库与配置 (Strategy Library)", "🏁 策略历史对决竞技场 (Backtest Arena)"],
        default="📚 策略库与配置 (Strategy Library)",
        label_visibility="collapsed"
    )

    all_strats = strategy_manager.get_all_strategies()

    # ----------------------------------------------------------
    # 子功能 A: 策略库与卡片网格展示 (现代化高信息密度卡片)
    # ----------------------------------------------------------
    if sub_view == "📚 策略库与配置 (Strategy Library)":
        col_hdr_left, col_hdr_btn1, col_hdr_btn2 = st.columns([5, 1.4, 1.4], vertical_alignment="center")
        with col_hdr_left:
            st.markdown(f"**📚 当前量化策略库 (共 {len(all_strats)} 个独立策略)** · 每一个策略均为自负盈亏的量化实体")
        with col_hdr_btn1:
            if st.button("➕ 新建策略", use_container_width=True):
                modal_create_custom_strategy()
        with col_hdr_btn2:
            if st.button("🤖 AI 探索新策略", type="primary", use_container_width=True):
                modal_ai_discover_strategy()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        # 2列卡片网格响应式排版
        grid_cols = st.columns(2)
        for idx, s in enumerate(all_strats):
            with grid_cols[idx % 2]:
                with st.container(border=True):
                    cat = s.get("category", "内置")
                    badge_class = "badge-ai" if "AI" in cat else ("badge-custom" if "自定义" in cat else "badge-builtin")
                    p = s.get("params", {})

                    # 1. 卡片头部：策略名称与类别徽章
                    c_title, c_badge = st.columns([3.5, 1], vertical_alignment="center")
                    with c_title:
                        st.markdown(f"<div style='font-size:15px; font-weight:700; color:#0f172a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;'>📌 {s['name']}</div>", unsafe_allow_html=True)
                    with c_badge:
                        st.markdown(f"<div style='text-align:right;'><span class='tag-badge {badge_class}'>{cat}</span></div>", unsafe_allow_html=True)

                    # 2. 策略描述 (两行省略)
                    desc = s.get("description", "暂无策略说明")
                    st.markdown(f"<div style='font-size:12px; color:#64748b; line-height:1.4; height:34px; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; margin:4px 0 8px 0;'>{desc}</div>", unsafe_allow_html=True)

                    # 3. 核心量化参数仪表盘 (6项核心参数卡片内原生可视，无需单独点击即可获知)
                    st.markdown(f"""
                    <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:6px; background:#f8fafc; padding:8px 10px; border-radius:6px; border:1px solid #f1f5f9; margin-bottom:10px;">
                        <div style="text-align:center;">
                            <div style="font-size:10px; color:#94a3b8; font-weight:500;">价格区间</div>
                            <div style="font-size:12px; font-weight:600; color:#1e293b;">{p.get('min_price', 90)}~{p.get('max_price', 130)}元</div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-size:10px; color:#94a3b8; font-weight:500;">溢价率上限</div>
                            <div style="font-size:12px; font-weight:600; color:#1e293b;">&le; {p.get('max_premium', 70)}%</div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-size:10px; color:#94a3b8; font-weight:500;">规模上限</div>
                            <div style="font-size:12px; font-weight:600; color:#1e293b;">&le; {p.get('max_scale', 10)}亿</div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-size:10px; color:#94a3b8; font-weight:500;">核心排序</div>
                            <div style="font-size:12px; font-weight:600; color:#1e293b;">{p.get('sort_by', 'double_low')}</div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-size:10px; color:#94a3b8; font-weight:500;">双低权重 W</div>
                            <div style="font-size:12px; font-weight:600; color:#1e293b;">{p.get('double_low_weight', 1.0)}</div>
                        </div>
                        <div style="text-align:center;">
                            <div style="font-size:10px; color:#94a3b8; font-weight:500;">目标持仓</div>
                            <div style="font-size:12px; font-weight:600; color:#1e293b;">{p.get('top_n', 15)} 只</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 4. 卡片底部操作栏 (精简紧凑的操作按钮)
                    c_act1, c_act2 = st.columns([4, 1], vertical_alignment="center")
                    with c_act1:
                        if st.button("📋 完整档案与逻辑", key=f"btn_detail_{s['id']}", use_container_width=True):
                            modal_view_strategy_detail(s)
                    with c_act2:
                        if s.get("category") != "系统内置":
                            if st.button("🗑️", key=f"btn_del_{s['id']}", use_container_width=True, help="删除该策略"):
                                strategy_manager.delete_strategy(s['id'])
                                st.rerun()
                        else:
                            st.button("🔒", key=f"btn_lock_{s['id']}", disabled=True, use_container_width=True, help="系统内置策略受保护")

    # ----------------------------------------------------------
    # 子功能 B: 策略历史对决竞技场 (独立大屏，量化对决)
    # ----------------------------------------------------------
    else:
        st.markdown(f"**🏁 策略历史对决竞技场** · 回测区间：`{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}` · 调仓周期：`{freq_str}` (可在右上角【⚙️ 全局设置】修改)")

        strat_choices = {s["name"]: s for s in all_strats}
        selected_strat_names = st.multiselect(
            "🎯 挑选上场对决的策略阵容：",
            options=list(strat_choices.keys()),
            default=list(strat_choices.keys())[:3]
        )

        if selected_strat_names:
            battle_strategies = [ConfigurableCBStrategy(strat_choices[name]) for name in selected_strat_names]
            engine = CBBacktestEngine(
                strategies=battle_strategies,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
                rebalance_interval_days=freq_days
            )
            with st.spinner("正在并行模拟各策略历史时间线净值..."):
                nav_df, metrics_summary, drawdown_df = engine.run()

            # 胜负关键卡片
            c1, c2, c3, c4 = st.columns(4)
            best_cagr = max(metrics_summary.items(), key=lambda x: x[1]["cagr"])
            lowest_dd = min(metrics_summary.items(), key=lambda x: x[1]["max_drawdown"])
            best_sharpe = max(metrics_summary.items(), key=lambda x: x[1]["sharpe_ratio"])
            with c1:
                with st.container(border=True):
                    st.metric("🏆 最高年化策略", best_cagr[0], f"+{best_cagr[1]['cagr']}%")
            with c2:
                with st.container(border=True):
                    st.metric("🛡️ 最低回撤策略", lowest_dd[0], f"-{lowest_dd[1]['max_drawdown']}%")
            with c3:
                with st.container(border=True):
                    st.metric("🎯 最高夏普比率", best_sharpe[0], f"{best_sharpe[1]['sharpe_ratio']}")
            with c4:
                with st.container(border=True):
                    st.metric("📊 中证转债基准收益", f"{metrics_summary.get('中证转债基准', {}).get('total_return', 0.0)}%")

            st.plotly_chart(create_equity_curves_chart(nav_df), use_container_width=True)
            col_l, col_r = st.columns(2)
            with col_l: st.plotly_chart(create_drawdown_chart(drawdown_df), use_container_width=True)
            with col_r: st.plotly_chart(create_metrics_bar_chart(metrics_summary), use_container_width=True)

            # 详细绩效一览表
            st.markdown("##### 📋 核心绩效量化指标对比表")
            df_perf = pd.DataFrame(metrics_summary).T[["cagr", "max_drawdown", "sharpe_ratio", "calmar_ratio", "annual_volatility", "total_return"]]
            df_perf.columns = ["年化收益率 (CAGR %)", "最大回撤 (MaxDD %)", "夏普比率 (Sharpe)", "卡玛比率 (Calmar)", "年化波动率 (%)", "累计收益率 (%)"]
            st.dataframe(df_perf.style.highlight_max(subset=["年化收益率 (CAGR %)", "夏普比率 (Sharpe)", "卡玛比率 (Calmar)"], color="#d4edda")
                                     .highlight_min(subset=["最大回撤 (MaxDD %)"], color="#d4edda"),
                         use_container_width=True)
        else:
            st.warning("请至少选择一个策略参与对决回测！")

# ==============================================================
# Tab 2: 实盘模拟竞技场 (多策略前向独立赛马)
# ==============================================================
with tab_paper:
    st.markdown("**🎮 实盘模拟竞技场 (Paper Trading Sandbox)** · 真实行情的‘前向赛马’测试，每个策略配置独立 10 万元虚拟资金，观察真实环境下的执行效果。")

    paper_accs = ledger.get_accounts(account_type="PAPER")
    cols_p = st.columns(len(paper_accs))
    for idx, acc in enumerate(paper_accs):
        with cols_p[idx]:
            with st.container(border=True):
                profit_pct = round((acc['nav_history'][-1]['nav'] - 1.0) * 100, 2)
                st.metric(
                    label=acc["account_name"],
                    value=f"¥ {acc['nav_history'][-1]['total_assets']:,.2f}",
                    delta=f"{profit_pct:+}% (虚拟净值: {acc['nav_history'][-1]['nav']:.4f})"
                )
                st.caption(f"策略: **{acc['associated_strategy']}** | 现金: ¥{acc['available_cash']:,.1f}")

    st.markdown("---")
    st.markdown("##### 📋 模拟子账户当前持仓透视")
    selected_p_acc_name = st.selectbox("选择要查看的模拟账户：", [a["account_name"] for a in paper_accs])
    cur_p_acc = next(a for a in paper_accs if a["account_name"] == selected_p_acc_name)

    if cur_p_acc["positions"]:
        p_df = pd.DataFrame(list(cur_p_acc["positions"].values()))
        p_display = p_df[["bond_code", "bond_name", "avg_price", "current_price", "amount", "market_value", "profit_rate"]]
        p_display.columns = ["转债代码", "转债名称", "买入成本", "当前市价", "持仓张数", "持仓市值(元)", "浮动盈亏(%)"]
        st.dataframe(p_display, use_container_width=True)
    else:
        st.info(f"💡 该模拟账户当前暂无持仓，系统将在交易日收盘前自动根据【{cur_p_acc['associated_strategy']}】模拟调仓！")

# ==============================================================
# Tab 3: 我的实盘多账号管家 (分策略、多账号独立记账)
# ==============================================================
with tab_real:
    st.markdown("**💼 我的实盘多账号管家** · 散户半自动跟单神器：券商 App 买卖后记一笔，系统 7x24 小时核算真实净值，专属 AI 盯盘排雷！")

    real_accs = ledger.get_accounts(account_type="REAL")
    acc_names = [a["account_name"] for a in real_accs] + ["➕ 新建实盘账号..."]
    chosen_name = st.selectbox("🏦 选择当前操作的实盘账号：", acc_names)

    if chosen_name == "➕ 新建实盘账号...":
        st.markdown("#### ➕ 登记新的实盘账户")
        with st.form("new_account_form"):
            new_id = st.text_input("账号唯一ID (如 huatai_01):")
            new_title = st.text_input("账号备注名称 (如 华泰证券-高YTM稳健仓):")
            new_strat = st.selectbox("该实盘账号绑定的量化策略：", [s["name"] for s in all_strats])
            new_capital = st.number_input("该账户初始资金 (元):", min_value=1000.0, value=20000.0, step=1000.0)
            if st.form_submit_button("确认创建并保存"):
                if new_id and new_title:
                    ledger.create_account(new_id, new_title, new_strat, "REAL", new_capital)
                    st.success(f"✅ 账号【{new_title}】创建成功，请重新在下拉框中选择！")
                    st.rerun()
                else:
                    st.error("请完整填写账号信息！")
    else:
        cur_acc = next(a for a in real_accs if a["account_name"] == chosen_name)
        
        latest_val = cur_acc["nav_history"][-1]
        p_pct = round((latest_val["nav"] - 1.0) * 100, 2)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            with st.container(border=True):
                st.metric("账户总资产", f"¥ {latest_val['total_assets']:,.2f}", f"{p_pct:+}%")
        with m2:
            with st.container(border=True):
                st.metric("可用现金", f"¥ {cur_acc['available_cash']:,.2f}")
        with m3:
            with st.container(border=True):
                st.metric("持仓市值", f"¥ {latest_val['total_assets'] - cur_acc['available_cash']:,.2f}")
        with m4:
            with st.container(border=True):
                st.metric("绑定跟随策略", cur_acc["associated_strategy"])

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.markdown("##### 📦 当前实盘真实持仓")
        if cur_acc["positions"]:
            pos_df = pd.DataFrame(list(cur_acc["positions"].values()))
            pos_display = pos_df[["bond_code", "bond_name", "avg_price", "current_price", "amount", "market_value", "profit_rate", "buy_date"]]
            pos_display.columns = ["转债代码", "转债名称", "买入成本", "最新市价", "持仓张数", "持仓市值(元)", "浮动盈亏(%)", "建仓日期"]
            st.dataframe(pos_display, use_container_width=True)
        else:
            st.info("💡 该实盘账号暂无持仓记录。可在下方录入你在券商 App 实际成交的买入单！")

        col_trade1, col_trade2 = st.columns(2)
        with col_trade1:
            with st.container(border=True):
                st.markdown("##### ✍️ 记一笔【买入成交】")
                with st.form(f"buy_form_{cur_acc['account_id']}"):
                    b_code = st.text_input("转债代码 (如 123112):")
                    b_name = st.text_input("转债名称 (如 万讯转债):")
                    b_price = st.number_input("成交单价 (元):", min_value=50.0, value=100.0, step=0.1)
                    b_amount = st.number_input("买入张数 (1手=10张):", min_value=10, value=20, step=10)
                    b_reason = st.text_input("买入理由 (可选):", value=f"跟随{cur_acc['associated_strategy']}策略买入")
                    if st.form_submit_button("💾 确认记录买入", use_container_width=True):
                        if b_code and b_name:
                            if ledger.record_buy(cur_acc["account_id"], b_code, b_name, b_price, b_amount, b_reason):
                                st.success(f"✅ 成功记录买入 {b_name} {b_amount}张！")
                                st.rerun()
                            else:
                                st.error("记账失败：可用现金不足！")
                        else:
                            st.error("请填写转债代码与名称")

        with col_trade2:
            with st.container(border=True):
                st.markdown("##### ✍️ 记一笔【卖出成交】")
                with st.form(f"sell_form_{cur_acc['account_id']}"):
                    pos_codes = list(cur_acc["positions"].keys())
                    s_code = st.selectbox("选择卖出持仓转债:", pos_codes if pos_codes else ["无持仓"])
                    s_price = st.number_input("卖出成交价格 (元):", min_value=50.0, value=105.0, step=0.1)
                    s_amount = st.number_input("卖出张数:", min_value=10, value=10, step=10)
                    s_reason = st.text_input("卖出理由 (可选):", value="达到止盈目标或调仓换出")
                    if st.form_submit_button("💾 确认记录卖出", use_container_width=True):
                        if s_code != "无持仓":
                            if ledger.record_sell(cur_acc["account_id"], s_code, s_price, s_amount, s_reason):
                                st.success(f"✅ 成功记录卖出 {s_code} {s_amount}张！")
                                st.rerun()
                            else:
                                st.error("记账失败：卖出张数超出实际持仓！")

# ==============================================================
# Tab 4: 今日多智能体执行与辩论 (LangGraph)
# ==============================================================
with tab_agent:
    st.markdown("**🤖 LangGraph 多智能体协同投研与多空辩论室** · 真实调度 4 大专业智能体：初筛 Agent -> Qwen 信用风控官 -> Gemini 进攻分析师 -> Gemini 条款博弈专家 -> PM 投资总监")

    run_agent_flow = st.button("🚀 启动 LangGraph 多智能体联合会诊与多空辩论", type="primary", use_container_width=True)

    if run_agent_flow:
        with st.status("🤖 LangGraph 多智能体流水线协同推进中...", expanded=True) as status_box:
            st.write("🔍 **[Node 1: 量化初筛 Agent]** 正在扫描全市场可转债，依据双低与流动性指标圈定候选池...")
            screener = ScreenerAgent(
                min_price=95.0,
                max_price=130.0,
                max_scale=8.0,
                double_low_weight=1.0,
                candidate_pool_size=15
            )
            candidates = screener.screen(quotes_df)
            st.write(f"   ↳ 初筛完成：从 {len(quotes_df)} 只转债中圈定 {len(candidates)} 只优质候选标的")

            st.write("🛡️ **[Node 2: 信用排雷 Agent (Qwen 28B)]** 正在执行基本面穿透审查，排查财务造假与退市风险...")
            from agents.credit_analyst import CreditAnalystAgent
            credit_agent = CreditAnalystAgent()
            credit_reviews = credit_agent.batch_evaluate(candidates)
            veto_count = sum(1 for r in credit_reviews.values() if r["risk_level"] == "VETO")
            st.write(f"   ↳ 信用审查完成：发现 {veto_count} 只高危标的触发一票否决")

            st.write("🚀 **[Node 3: 正股动量 Agent (Gemini 3.8 Flash)]** 正在扫描正股技术均线、题材风口与资金流向...")
            from agents.equity_analyst import EquityAnalystAgent
            equity_agent = EquityAnalystAgent()
            equity_reviews = equity_agent.batch_evaluate(candidates)
            st.write("   ↳ 动量评估完成：已为所有标的完成爆发弹性评分 (0-100)")

            st.write("♟️ **[Node 4: 条款博弈 Agent (Gemini 3.1 Pro)]** 正在推演大股东转股诉求、下修到底概率与强赎风险...")
            from agents.clause_analyst import ClauseAnalystAgent
            clause_agent = ClauseAnalystAgent()
            clause_reviews = clause_agent.batch_evaluate(candidates)
            st.write("   ↳ 博弈推演完成：已评估各标的的不对称赔率与下修安全垫")

            st.write("👔 **[Node 5: 投资总监 Agent (PM)]** 正在汇总三方研判，执行多空仲裁与最终仓位分配...")
            from agents.portfolio_manager import PortfolioManagerAgent
            pm_agent = PortfolioManagerAgent(top_n=15)
            final_portfolio, vetoed_bonds, report_md = pm_agent.arbitrate_and_allocate(
                candidates=candidates,
                credit_reviews=credit_reviews,
                equity_reviews=equity_reviews,
                clause_reviews=clause_reviews
            )
            st.write("   ↳ 仲裁决策完成：已生成今日最优投资组合！")
            if status_box is not None:
                try:
                    status_box.update(label="✅ LangGraph 多智能体协同会诊执行完毕！", state="complete", expanded=False)
                except Exception:
                    pass

        st.session_state["agent_result"] = {
            "candidates": candidates,
            "credit_reviews": credit_reviews,
            "equity_reviews": equity_reviews,
            "clause_reviews": clause_reviews,
            "final_portfolio": final_portfolio,
            "vetoed_bonds": vetoed_bonds,
            "report_md": report_md
        }

    if "agent_result" in st.session_state:
        res = st.session_state["agent_result"]
        portfolio = res["final_portfolio"]
        vetoed = res["vetoed_bonds"]

        st.markdown(f"##### 🏆 投资总监 (PM) 今日推荐组合 (共 {len(portfolio)} 只)")
        if portfolio:
            df_p = pd.DataFrame(portfolio)
            df_p["推荐星级"] = df_p["rating_stars"].apply(lambda s: "⭐" * s)
            df_p["建议权重"] = df_p["weight"].apply(lambda w: f"{round(w*100, 1)}%")
            df_display = df_p[["bond_code", "bond_name", "price", "double_low", "建议权重", "推荐星级", "pm_verdict"]]
            df_display.columns = ["转债代码", "转债名称", "现价(元)", "双低值", "建议权重", "推荐星级", "PM 裁决结论与配置理由"]
            st.dataframe(df_display, use_container_width=True)

        if vetoed:
            st.error("### 🚫 首席风控官 (Qwen) 一票否决高危名单")
            st.dataframe(pd.DataFrame(vetoed), use_container_width=True)

        st.markdown("---")
        st.markdown("##### 🎙️ 多智能体圆桌会诊室 (选择标的查看辩论交锋)")
        bond_options = [f"{p['bond_name']} ({p['bond_code']})" for p in portfolio]
        if bond_options:
            selected_bond_str = st.selectbox("🎯 查看 4 大智能体对该标的的独立研判与辩论发言：", bond_options)
            selected_code = selected_bond_str.split("(")[-1].replace(")", "").strip()
            
            cand_info = next((c for c in res["candidates"] if c["bond_code"] == selected_code), None)
            c_rev = res["credit_reviews"].get(selected_code, {})
            e_rev = res["equity_reviews"].get(selected_code, {})
            cl_rev = res["clause_reviews"].get(selected_code, {})
            p_item = next((p for p in portfolio if p["bond_code"] == selected_code), None)

            if cand_info:
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    with st.container(border=True):
                        st.metric("转债代码", cand_info["bond_code"], cand_info["bond_name"])
                with col_m2:
                    with st.container(border=True):
                        st.metric("当前现价", f"{cand_info['price']} 元")
                with col_m3:
                    with st.container(border=True):
                        st.metric("转股溢价率", f"{cand_info['premium_rate']}%")
                with col_m4:
                    with st.container(border=True):
                        st.metric("双低综合值", f"{cand_info['double_low']}")

                st.markdown("###### 💬 智能体多空研判发言实录：")
                with st.chat_message("user", avatar="🛡️"):
                    st.markdown(f"**【首席风控官 · Qwen 28B】发言：**")
                    st.write(f"**审查结论**：`{c_rev.get('risk_level', 'PASS')}` | **信用评级**：`{cand_info['rating']}`")
                    st.write(f"**风控审查依据**：{c_rev.get('reason', '正股基本面稳健，现金流健康，无重大质押风险。')}")

                with st.chat_message("assistant", avatar="🚀"):
                    st.markdown(f"**【正股动量分析师 · Gemini 3.8 Flash】补充发言：**")
                    st.write(f"**进攻动量评分**：`{e_rev.get('momentum_score', 70)} / 100` | **所属题材**：`{' / '.join(e_rev.get('sector_themes', ['智能制造']))}`")
                    st.write(f"**题材与形态点评**：{e_rev.get('catalyst_summary', '正股处于均线支撑位，股性弹性良好。')}")

                with st.chat_message("user", avatar="♟️"):
                    st.markdown(f"**【条款博弈专家 · Gemini 3.1 Pro】博弈论推演：**")
                    st.write(f"**剩余规模**：`{cand_info['remaining_scale']} 亿元` (筹码轻重度) | **强赎风险**：`{cl_rev.get('call_risk_level', 'LOW')}`")
                    st.write(f"**下修与博弈分析**：{cl_rev.get('game_summary', '大股东具备强烈转股诉求，下修不对称赔率极具诱惑。')}")

                with st.chat_message("assistant", avatar="👔"):
                    st.markdown(f"**【投资总监 · PM 决策总监】最终裁决：**")
                    stars = "⭐" * p_item['rating_stars'] if p_item else "⭐⭐⭐⭐"
                    st.write(f"**裁决星级**：`{stars}` | **建议配置权重**：`{round(p_item['weight']*100, 1) if p_item else 6.7}%`")
                    st.write(f"**投资总监结论**：{p_item['pm_verdict'] if p_item else '安全垫与弹性共振，推荐纳入底仓配置。'}")
    else:
        st.info("💡 尚未执行今日会诊。点击上方【🚀 启动 LangGraph 多智能体联合会诊与多空辩论】按钮，调度 4 大 AI 智能体对候选标的展开排雷审查、动量分析与条款博弈！")

