# -*- coding: utf-8 -*-
"""电商销售数据看板（Streamlit + Pandas + Plotly）。

运行：
    streamlit run app.py

数据：
    data/sales_data.csv（由 scripts/generate_data.py 与 scripts/preprocess.py 生成）
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "sales_data.csv"
SUMMARY_FILE = BASE_DIR / "data" / "cleaning_summary.txt"
TARGET_2025 = 4_200_000

COLORS = ["#22d3ee", "#3b82f6", "#8b5cf6", "#f59e0b", "#10b981", "#f472b6"]
TEXT = "#dbeafe"
MUTED = "#8fb3d9"
GRID = "rgba(120,170,255,.10)"

st.set_page_config(
    page_title="电商销售数据看板",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
  .stApp {
    background:
      radial-gradient(circle at 18% 0%, rgba(28, 78, 121, .55) 0%, rgba(7, 17, 31, 0) 42%),
      radial-gradient(circle at 88% 8%, rgba(34, 211, 238, .10) 0%, rgba(7, 17, 31, 0) 36%),
      linear-gradient(180deg, #07111f 0%, #050b14 100%);
  }
  [data-testid="stHeader"] { background: rgba(0, 0, 0, 0); }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #081726 0%, #050d18 100%);
    border-right: 1px solid rgba(34, 211, 238, .16);
  }
  .block-container { padding-top: 1.4rem; padding-bottom: 2.2rem; max-width: 1560px; }
  html, body, [class*="css"] {
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  }
  h1, h2, h3, h4 { color: #eaf6ff !important; }
  p, label, span, div { color: #cfe3ff; }

  .sidebar-brand {
    display: flex; align-items: center; gap: 12px;
    padding: 6px 2px 16px 2px;
    border-bottom: 1px solid rgba(34, 211, 238, .16);
    margin-bottom: 16px;
  }
  .brand-mark {
    width: 42px; height: 42px; border-radius: 12px;
    background: linear-gradient(135deg, #22d3ee, #2563eb);
    display: flex; align-items: center; justify-content: center;
    color: #04111f; font-weight: 800; font-size: 18px;
    box-shadow: 0 6px 18px rgba(34, 211, 238, .25);
  }
  .brand-title { font-size: 17px; font-weight: 700; color: #ecf9ff; letter-spacing: .5px; }
  .brand-sub { font-size: 11px; color: #7fa6cc; letter-spacing: 1.6px; text-transform: uppercase; }

  .hero {
    display: flex; justify-content: space-between; align-items: flex-end; gap: 24px;
    padding: 4px 0 18px 0; margin-bottom: 18px;
    border-bottom: 1px solid rgba(34, 211, 238, .16);
  }
  .hero-kicker { color: #22d3ee; font-size: 11px; letter-spacing: 2.6px; font-weight: 700; }
  .hero h1 { font-size: 34px; margin: 7px 0 5px 0; letter-spacing: 1px; }
  .hero-sub { color: #8fb3d9; font-size: 13px; }
  .hero-badge {
    padding: 9px 16px; border-radius: 999px;
    border: 1px solid rgba(34, 211, 238, .32);
    background: rgba(34, 211, 238, .07);
    color: #a5f3fc; font-size: 12px; white-space: nowrap;
  }
  .badge-dot {
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #34d399; margin-right: 7px; box-shadow: 0 0 8px #34d399;
  }

  .kpi-card {
    position: relative; overflow: hidden;
    background: linear-gradient(145deg, rgba(16, 42, 67, .92), rgba(8, 22, 38, .92));
    border: 1px solid rgba(34, 211, 238, .22);
    border-radius: 16px; padding: 17px 18px 15px 18px;
    min-height: 128px;
    box-shadow: 0 10px 24px rgba(0, 0, 0, .26);
  }
  .kpi-card::after {
    content: ""; position: absolute; right: -34px; top: -34px;
    width: 96px; height: 96px;
    background: radial-gradient(circle, rgba(34, 211, 238, .16), rgba(34, 211, 238, 0) 70%);
  }
  .kpi-card.warn { border-color: rgba(245, 158, 11, .55); }
  .kpi-card.danger { border-color: rgba(248, 113, 113, .55); }
  .kpi-label { color: #8fb3d9; font-size: 12px; letter-spacing: 1px; }
  .kpi-value { color: #f2fbff; font-size: 29px; font-weight: 800; margin-top: 7px; letter-spacing: .5px; }
  .kpi-delta { display: block; margin-top: 8px; font-size: 11px; }
  .kpi-delta.up { color: #34d399; }
  .kpi-delta.down { color: #f87171; }
  .kpi-delta.flat { color: #7f9ab8; }
  .kpi-note { color: #7f9ab8; font-size: 10px; margin-top: 4px; }

  .section-title {
    display: flex; align-items: center; gap: 10px;
    font-size: 18px; font-weight: 700; color: #e6f6ff;
    margin: 4px 0 10px 0;
  }
  .section-title::before {
    content: ""; width: 4px; height: 18px; border-radius: 2px;
    background: linear-gradient(180deg, #22d3ee, #2563eb);
  }
  .chart-title { font-size: 14px; font-weight: 700; color: #e6f6ff; margin: 2px 0 2px 0; }
  .chart-sub { font-size: 11px; color: #7fa6cc; margin-bottom: 2px; }

  div[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(9, 24, 40, .72);
    border: 1px solid rgba(56, 189, 248, .16) !important;
    border-radius: 16px;
    padding: 8px 10px 4px 10px;
  }

  .alert-list { display: flex; flex-direction: column; gap: 10px; padding: 4px 2px 8px 2px; }
  .alert-row {
    display: flex; gap: 10px; align-items: flex-start;
    background: rgba(15, 33, 52, .85);
    border: 1px solid rgba(120, 170, 255, .12);
    border-radius: 12px; padding: 10px 12px;
  }
  .alert-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex: 0 0 auto; }
  .alert-dot.good { background: #34d399; box-shadow: 0 0 8px #34d399; }
  .alert-dot.warn { background: #f59e0b; box-shadow: 0 0 8px #f59e0b; }
  .alert-dot.bad { background: #f87171; box-shadow: 0 0 8px #f87171; }
  .alert-title { font-size: 12px; font-weight: 700; color: #e6f6ff; }
  .alert-text { font-size: 11px; color: #9bb8d6; margin-top: 2px; line-height: 1.55; }

  .footer {
    margin-top: 26px; padding-top: 14px;
    border-top: 1px solid rgba(34, 211, 238, .10);
    color: #6f8ba8; font-size: 11px; text-align: center;
  }
  .stTabs [data-baseweb="tab-list"] { gap: 8px; }
  .stTabs [data-baseweb="tab"] {
    height: 38px; border-radius: 10px 10px 0 0;
    padding: 0 16px; color: #8fb3d9;
  }
  .stTabs [aria-selected="true"] {
    color: #22d3ee !important;
    background: rgba(34, 211, 238, .08);
  }
  [data-testid="stAppDeployButton"] { display: none; }
  [data-testid="stToolbar"] { visibility: hidden; height: 0; }
  div[data-testid="stDownloadButton"] button {
    background: rgba(34, 211, 238, .12);
    border: 1px solid rgba(34, 211, 238, .45);
    color: #a5f3fc;
    border-radius: 10px;
  }
  div[data-testid="stDownloadButton"] button:hover {
    background: rgba(34, 211, 238, .22);
    border-color: #22d3ee;
    color: #ecfeff;
  }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    data = pd.read_csv(DATA_FILE, encoding="utf-8-sig", parse_dates=["order_date"])
    return data


def fmt_money(value: float) -> str:
    if value >= 100_000_000:
        return f"¥{value / 100_000_000:.2f} 亿"
    if value >= 10_000:
        return f"¥{value / 10_000:.1f} 万"
    return f"¥{value:,.0f}"


def fmt_int(value: float) -> str:
    return f"{value:,.0f}"


def shift_year(value: pd.Timestamp, years: int = -1) -> pd.Timestamp:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value - pd.DateOffset(years=1)


def apply_filters(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    regions: list[str],
    categories: list[str],
    channels: list[str],
) -> pd.DataFrame:
    mask = data["order_date"].between(start, end)
    if regions:
        mask &= data["region"].isin(regions)
    if categories:
        mask &= data["category"].isin(categories)
    if channels:
        mask &= data["channel"].isin(channels)
    return data[mask].copy()


def style_fig(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        height=height,
        margin=dict(l=6, r=6, t=10, b=6),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Microsoft YaHei, PingFang SC, sans-serif", color=TEXT, size=11),
        hoverlabel=dict(
            bgcolor="#0d2137",
            bordercolor="#22d3ee",
            font=dict(color="#e6f1ff", size=12),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.0,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color=MUTED),
        ),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(120,170,255,.18)")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(120,170,255,.18)")
    return fig


def kpi_card(
    label: str,
    value: str,
    delta: float | None,
    suffix: str = "%",
    inverse: bool = False,
    note: str = "",
    status: str = "",
) -> str:
    if delta is None or pd.isna(delta):
        delta_html = '<span class="kpi-delta flat">— 无同期数据</span>'
    elif abs(delta) < 0.05:
        delta_html = '<span class="kpi-delta flat">— 与同期基本持平</span>'
    else:
        positive = delta >= 0
        good = (not positive) if inverse else positive
        cls = "up" if good else "down"
        arrow = "▲" if positive else "▼"
        delta_html = f'<span class="kpi-delta {cls}">{arrow} {abs(delta):.1f}{suffix} 同比</span>'
    note_html = f'<div class="kpi-note">{note}</div>' if note else ""
    return f"""
    <div class="kpi-card {status}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      {delta_html}
      {note_html}
    </div>
    """


def chart_header(title: str, subtitle: str = "") -> None:
    sub = f'<div class="chart-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="chart-title">{title}</div>{sub}', unsafe_allow_html=True)


def build_alerts(
    data: pd.DataFrame, profit_threshold: float, refund_threshold: float
) -> list[tuple[str, str, str]]:
    alerts: list[tuple[str, str, str]] = []
    if data.empty:
        return [("warn", "暂无数据", "当前筛选条件没有匹配记录，请放宽筛选范围。")]

    margin = data["profit"].sum() / data["sales_amount"].sum() * 100
    refund = data["is_refund"].mean() * 100

    cat = data.groupby("category").agg(
        销售额=("sales_amount", "sum"),
        利润=("profit", "sum"),
        退款率=("is_refund", "mean"),
    )
    cat["利润率"] = cat["利润"] / cat["销售额"] * 100
    cat["退款率"] = cat["退款率"] * 100

    low_margin = cat[cat["利润率"] < profit_threshold].sort_values("利润率")
    high_refund = cat[cat["退款率"] > refund_threshold].sort_values("退款率", ascending=False)

    if low_margin.empty:
        alerts.append(("good", "利润率正常", f"各品类利润率均高于 {profit_threshold:.0f}% 预警线。"))
    else:
        detail = "、".join(f"{name} {row['利润率']:.1f}%" for name, row in low_margin.iterrows())
        alerts.append(("warn", "品类利润率预警", f"{detail}，低于 {profit_threshold:.0f}% 预警线。"))

    if high_refund.empty:
        alerts.append(("good", "退款率正常", f"各品类退款率均低于 {refund_threshold:.0f}% 预警线。"))
    else:
        detail = "、".join(f"{name} {row['退款率']:.1f}%" for name, row in high_refund.iterrows())
        alerts.append(("bad", "品类退款率预警", f"{detail}，高于 {refund_threshold:.0f}% 预警线。"))

    alerts.append(
        (
            "good" if margin >= profit_threshold else "warn",
            "整体经营指标",
            f"整体利润率 {margin:.1f}%，整体退款率 {refund:.1f}%。",
        )
    )
    return alerts


def render_alerts(alerts: list[tuple[str, str, str]]) -> None:
    rows = []
    for level, title, text in alerts:
        rows.append(
            f"""<div class="alert-row">
              <span class="alert-dot {level}"></span>
              <div><div class="alert-title">{title}</div><div class="alert-text">{text}</div></div>
            </div>"""
        )
    st.markdown('<div class="alert-list">' + "".join(rows) + "</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------- 数据与筛选
if not DATA_FILE.exists():
    st.error("找不到 data/sales_data.csv，请先运行 python scripts/generate_data.py 和 python scripts/preprocess.py。")
    st.stop()

df = load_data()
min_date = df["order_date"].min().date()
max_date = df["order_date"].max().date()

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
          <div class="brand-mark">BI</div>
          <div>
            <div class="brand-title">销售数据看板</div>
            <div class="brand-sub">Sales Intelligence</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="chart-title">筛选条件</div>', unsafe_allow_html=True)

    selected_range = st.date_input(
        "统计区间",
        value=(date(2025, 1, 1), date(2025, 12, 31)),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start_date, end_date = selected_range
    else:
        start_date = end_date = selected_range

    region_options = sorted(df["region"].dropna().unique().tolist())
    category_options = sorted(df["category"].dropna().unique().tolist())
    channel_options = sorted(df["channel"].dropna().unique().tolist())

    selected_regions = st.multiselect("地区", region_options, default=region_options)
    selected_categories = st.multiselect("品类", category_options, default=category_options)
    selected_channels = st.multiselect("渠道", channel_options, default=channel_options)

    st.markdown("---")
    st.markdown('<div class="chart-title">预警阈值</div>', unsafe_allow_html=True)
    profit_threshold = st.slider("利润率预警线（%）", 10, 40, 22)
    refund_threshold = st.slider("退款率预警线（%）", 1, 10, 5)

    st.markdown("---")
    st.caption(f"数据源：data/sales_data.csv")
    st.caption(f"样本：{len(df):,} 条订单 · 2024-01-01 至 2025-12-31")

if not selected_regions or not selected_categories or not selected_channels:
    st.warning("请在侧边栏至少选择一个地区、一个品类和一个渠道。")
    st.stop()

start_ts = pd.Timestamp(start_date)
end_ts = pd.Timestamp(end_date)
if start_ts > end_ts:
    start_ts, end_ts = end_ts, start_ts

filtered = apply_filters(
    df, start_ts, end_ts, selected_regions, selected_categories, selected_channels
)
prev_start = shift_year(start_ts, -1)
prev_end = shift_year(end_ts, -1)
prev_filtered = apply_filters(
    df, prev_start, prev_end, selected_regions, selected_categories, selected_channels
)

if filtered.empty:
    st.warning("当前筛选条件没有匹配数据，请调整日期或筛选项。")
    st.stop()

# ---------------------------------------------------------------- 核心指标
sales = float(filtered["sales_amount"].sum())
orders = int(len(filtered))
aov = sales / orders if orders else 0.0
profit = float(filtered["profit"].sum())
margin = profit / sales * 100 if sales else 0.0
refund_rate = float(filtered["is_refund"].mean() * 100)

prev_sales = float(prev_filtered["sales_amount"].sum()) if not prev_filtered.empty else 0.0
prev_orders = int(len(prev_filtered))
prev_aov = prev_sales / prev_orders if prev_orders else 0.0
prev_margin = (
    prev_filtered["profit"].sum() / prev_filtered["sales_amount"].sum() * 100
    if prev_sales
    else 0.0
)
prev_refund = float(prev_filtered["is_refund"].mean() * 100) if prev_orders else 0.0


def yoy(current: float, previous: float) -> float | None:
    if previous <= 0:
        return None
    return (current / previous - 1) * 100


sales_yoy = yoy(sales, prev_sales)
orders_yoy = yoy(orders, prev_orders)
aov_yoy = yoy(aov, prev_aov)
margin_delta = margin - prev_margin if prev_orders else None
refund_delta = refund_rate - prev_refund if prev_orders else None

st.markdown(
    f"""
    <div class="hero">
      <div>
        <div class="hero-kicker">E-COMMERCE SALES INTELLIGENCE</div>
        <h1>电商销售数据看板</h1>
        <div class="hero-sub">全渠道经营分析 · 品类 / 地区 / 渠道多维洞察 · 数据更新至 2025-12-31</div>
      </div>
      <div class="hero-badge"><span class="badge-dot"></span>{len(filtered):,} 条订单 · {start_ts:%Y-%m-%d} 至 {end_ts:%Y-%m-%d}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">经营总览</div>', unsafe_allow_html=True)
kpi_cols = st.columns(5, gap="small")
with kpi_cols[0]:
    st.markdown(kpi_card("总销售额", fmt_money(sales), sales_yoy), unsafe_allow_html=True)
with kpi_cols[1]:
    st.markdown(kpi_card("订单量", fmt_int(orders), orders_yoy, suffix="%"), unsafe_allow_html=True)
with kpi_cols[2]:
    st.markdown(kpi_card("平均客单价", f"¥{aov:,.0f}", aov_yoy), unsafe_allow_html=True)
with kpi_cols[3]:
    status = "warn" if margin < profit_threshold else ""
    st.markdown(
        kpi_card("利润率", f"{margin:.1f}%", margin_delta, suffix="pp", status=status),
        unsafe_allow_html=True,
    )
with kpi_cols[4]:
    status = "danger" if refund_rate > refund_threshold else ""
    st.markdown(
        kpi_card(
            "退款率",
            f"{refund_rate:.1f}%",
            refund_delta,
            suffix="pp",
            inverse=True,
            status=status,
        ),
        unsafe_allow_html=True,
    )

tabs = st.tabs(["经营总览", "品类分析", "区域分析", "明细数据"])

# ---------------------------------------------------------------- 经营总览
with tabs[0]:
    trend_col, gauge_col = st.columns([2.15, 1], gap="small")
    with trend_col:
        with st.container(border=True):
            chart_header("月度销售额趋势", "当前筛选区间与上一年同期对比")
            if start_ts.year == end_ts.year:
                monthly = filtered.groupby(filtered["order_date"].dt.month)["sales_amount"].sum()
                monthly_prev = (
                    prev_filtered.groupby(prev_filtered["order_date"].dt.month)["sales_amount"].sum()
                    if not prev_filtered.empty
                    else pd.Series(dtype=float)
                )
                x = [f"{m}月" for m in range(1, 13)]
                y_current = [float(monthly.get(m, 0)) for m in range(1, 13)]
                fig = go.Figure()
                if not monthly_prev.empty:
                    y_prev = [float(monthly_prev.get(m, 0)) for m in range(1, 13)]
                    fig.add_trace(
                        go.Scatter(
                            x=x,
                            y=y_prev,
                            mode="lines+markers",
                            name=f"{start_ts.year - 1} 年",
                            line=dict(color="#64748b", width=2, dash="dash"),
                            marker=dict(size=4, color="#64748b"),
                            hovertemplate="%{x}<br>销售额 ¥%{y:,.0f}<extra></extra>",
                        )
                    )
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=y_current,
                        mode="lines+markers",
                        name=f"{start_ts.year} 年",
                        line=dict(color="#22d3ee", width=3, shape="spline"),
                        marker=dict(size=7, color="#22d3ee", line=dict(color="#07111f", width=2)),
                        fill="tozeroy",
                        fillcolor="rgba(34,211,238,.10)",
                        hovertemplate="%{x}<br>销售额 ¥%{y:,.0f}<extra></extra>",
                    )
                )
                fig.update_layout(yaxis_title="销售额（元）")
                st.plotly_chart(style_fig(fig, 330), width="stretch", config={"displayModeBar": False})
            else:
                monthly = (
                    filtered.groupby("month_label", as_index=False)["sales_amount"]
                    .sum()
                    .sort_values("month_label")
                )
                fig = go.Figure(
                    go.Scatter(
                        x=monthly["month_label"],
                        y=monthly["sales_amount"],
                        mode="lines+markers",
                        line=dict(color="#22d3ee", width=3, shape="spline"),
                        marker=dict(size=7, color="#22d3ee"),
                        fill="tozeroy",
                        fillcolor="rgba(34,211,238,.10)",
                        hovertemplate="%{x}<br>销售额 ¥%{y:,.0f}<extra></extra>",
                    )
                )
                st.plotly_chart(style_fig(fig, 330), width="stretch", config={"displayModeBar": False})

    with gauge_col:
        with st.container(border=True):
            chart_header("2025 年度目标完成率", f"年度目标 {fmt_money(TARGET_2025)}")
            current_2025 = filtered[filtered["order_date"].dt.year == 2025]["sales_amount"].sum()
            completion = float(current_2025 / TARGET_2025 * 100) if TARGET_2025 else 0.0
            gauge = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=round(completion, 1),
                    number=dict(suffix="%", font=dict(size=34, color="#e6f6ff")),
                    gauge=dict(
                        shape="angular",
                        axis=dict(
                            range=[0, 120],
                            tickwidth=1,
                            tickcolor="#8fb3d9",
                            tickfont=dict(size=9, color="#8fb3d9"),
                        ),
                        bar=dict(color="#22d3ee", thickness=0.62),
                        bgcolor="rgba(13,31,51,.90)",
                        borderwidth=0,
                        steps=[
                            dict(range=[0, 60], color="rgba(248,113,113,.35)"),
                            dict(range=[60, 90], color="rgba(245,158,11,.35)"),
                            dict(range=[90, 120], color="rgba(52,211,153,.30)"),
                        ],
                        threshold=dict(
                            line=dict(color="#f59e0b", width=3),
                            thickness=0.8,
                            value=100,
                        ),
                    ),
                )
            )
            gauge.update_layout(
                height=286,
                margin=dict(l=18, r=18, t=16, b=6),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Microsoft YaHei", color="#cfe3ff"),
            )
            st.plotly_chart(gauge, width="stretch", config={"displayModeBar": False})
            st.caption(f"2025 年累计销售额 {fmt_money(current_2025)}，完成年度目标的 {completion:.1f}%")

    chart_left, chart_right = st.columns([1.25, 1], gap="small")
    with chart_left:
        with st.container(border=True):
            chart_header("品类销售额与利润", "按销售额从高到低排序")
            cat = (
                filtered.groupby("category", as_index=False)
                .agg(销售额=("sales_amount", "sum"), 利润=("profit", "sum"))
                .sort_values("销售额")
            )
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    y=cat["category"],
                    x=cat["销售额"],
                    orientation="h",
                    name="销售额",
                    marker=dict(color="#22d3ee", line=dict(width=0)),
                    hovertemplate="%{y}<br>销售额 ¥%{x:,.0f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Bar(
                    y=cat["category"],
                    x=cat["利润"],
                    orientation="h",
                    name="利润",
                    marker=dict(color="#8b5cf6", line=dict(width=0)),
                    hovertemplate="%{y}<br>利润 ¥%{x:,.0f}<extra></extra>",
                )
            )
            fig.update_layout(barmode="group", xaxis_title="金额（元）")
            st.plotly_chart(style_fig(fig, 330), width="stretch", config={"displayModeBar": False})

    with chart_right:
        with st.container(border=True):
            chart_header("渠道销售结构", "各渠道销售额占比")
            channel = (
                filtered.groupby("channel", as_index=False)["sales_amount"]
                .sum()
                .sort_values("sales_amount", ascending=False)
            )
            fig = go.Figure(
                go.Pie(
                    labels=channel["channel"],
                    values=channel["sales_amount"],
                    hole=0.58,
                    marker=dict(colors=COLORS[: len(channel)], line=dict(color="#07111f", width=2)),
                    textinfo="label+percent",
                    textfont=dict(size=11, color="#e6f6ff"),
                    hovertemplate="%{label}<br>销售额 ¥%{value:,.0f}<br>占比 %{percent}<extra></extra>",
                    sort=False,
                )
            )
            fig.add_annotation(
                text=f"¥{channel['sales_amount'].sum() / 10_000:.0f}万<br><span style='font-size:10px;color:#8fb3d9'>总销售额</span>",
                showarrow=False,
                font=dict(size=18, color="#e6f6ff"),
            )
            st.plotly_chart(style_fig(fig, 330), width="stretch", config={"displayModeBar": False})

    region_col, alert_col = st.columns([1.25, 1], gap="small")
    with region_col:
        with st.container(border=True):
            chart_header("省份销售额 TOP 10", "按当前筛选条件统计")
            province = filtered.groupby("province")["sales_amount"].sum().nlargest(10).sort_values()
            fig = go.Figure(
                go.Bar(
                    x=province.values,
                    y=province.index,
                    orientation="h",
                    marker=dict(
                        color=province.values,
                        colorscale=[[0, "#1d4ed8"], [0.55, "#0ea5e9"], [1, "#22d3ee"]],
                        line=dict(width=0),
                    ),
                    text=[f"¥{value / 10_000:.0f}万" for value in province.values],
                    textposition="outside",
                    textfont=dict(size=10, color="#cfe3ff"),
                    hovertemplate="%{y}<br>销售额 ¥%{x:,.0f}<extra></extra>",
                )
            )
            fig = style_fig(fig, 340)
            fig.update_layout(margin=dict(l=6, r=76, t=10, b=6))
            fig.update_xaxes(range=[0, float(province.max()) * 1.20])
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with alert_col:
        with st.container(border=True):
            chart_header("经营预警", "阈值可在侧边栏调整")
            render_alerts(build_alerts(filtered, profit_threshold, refund_threshold))

# ---------------------------------------------------------------- 品类分析
with tabs[1]:
    st.markdown('<div class="section-title">品类多维分析</div>', unsafe_allow_html=True)
    heat_col, tree_col = st.columns([1.15, 1], gap="small")
    with heat_col:
        with st.container(border=True):
            chart_header("月份 × 品类销售热力图", "颜色越亮代表销售额越高")
            pivot = filtered.pivot_table(
                index=filtered["order_date"].dt.month,
                columns="category",
                values="sales_amount",
                aggfunc="sum",
            ).fillna(0)
            fig = go.Figure(
                go.Heatmap(
                    z=pivot.values,
                    x=pivot.columns.tolist(),
                    y=[f"{month}月" for month in pivot.index.tolist()],
                    colorscale=[
                        [0, "#0b1a2b"],
                        [0.35, "#1e3a8a"],
                        [0.7, "#0ea5e9"],
                        [1, "#22d3ee"],
                    ],
                    hovertemplate="%{y} · %{x}<br>销售额 ¥%{z:,.0f}<extra></extra>",
                    colorbar=dict(
                        thickness=8,
                        len=0.82,
                        tickformat=".2s",
                        title=dict(text="销售额", font=dict(size=10, color="#8fb3d9")),
                        tickfont=dict(size=9, color="#8fb3d9"),
                    ),
                )
            )
            st.plotly_chart(style_fig(fig, 370), width="stretch", config={"displayModeBar": False})

    with tree_col:
        with st.container(border=True):
            chart_header("品类 / 渠道销售贡献", "矩形面积代表销售额，颜色区分品类")
            fig = px.treemap(
                filtered,
                path=[px.Constant("全部品类"), "category", "channel"],
                values="sales_amount",
                color="category",
                color_discrete_sequence=["#0e7490", "#1d4ed8", "#6d28d9", "#b45309", "#047857", "#be185d"],
            )
            fig.update_traces(
                textinfo="label+percent parent",
                textfont=dict(size=11, color="#eaf6ff"),
                hovertemplate="%{label}<br>销售额 ¥%{value:,.0f}<extra></extra>",
                marker=dict(line=dict(color="#07111f", width=2)),
            )
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(style_fig(fig, 370), width="stretch", config={"displayModeBar": False})

    radar_col, table_col = st.columns([1, 1.2], gap="small")
    with radar_col:
        with st.container(border=True):
            chart_header("品类综合能力雷达", "销售额、利润、订单、客单价、评分归一化对比")
            metrics = filtered.groupby("category").agg(
                销售额=("sales_amount", "sum"),
                利润=("profit", "sum"),
                订单量=("order_id", "count"),
                客单价=("sales_amount", "mean"),
                评分=("rating", "mean"),
            )
            normalized = (metrics - metrics.min()) / (metrics.max() - metrics.min() + 1e-9) * 100
            top_categories = metrics["销售额"].nlargest(3).index.tolist()
            fig = go.Figure()
            for index, category in enumerate(top_categories):
                values = normalized.loc[category].tolist()
                values.append(values[0])
                theta = normalized.columns.tolist() + [normalized.columns[0]]
                fig.add_trace(
                    go.Scatterpolar(
                        r=values,
                        theta=theta,
                        fill="toself",
                        name=category,
                        line=dict(color=COLORS[index], width=2),
                        opacity=0.55,
                        hovertemplate="%{theta}<br>得分 %{r:.0f}<extra></extra>",
                    )
                )
            fig.update_layout(
                margin=dict(l=28, r=28, t=34, b=42),
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        gridcolor="rgba(120,170,255,.12)",
                        tickfont=dict(size=8, color="#7fa6cc"),
                    ),
                    angularaxis=dict(
                        gridcolor="rgba(120,170,255,.12)",
                        tickfont=dict(size=10, color="#cfe3ff"),
                    ),
                ),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.10,
                    x=0.5,
                    xanchor="center",
                    font=dict(size=9, color=MUTED),
                ),
            )
            fig = style_fig(fig, 400)
            fig.update_layout(
                margin=dict(l=30, r=30, t=42, b=58),
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    domain=dict(x=[0.04, 0.96], y=[0.13, 0.98]),
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100],
                        gridcolor="rgba(120,170,255,.12)",
                        tickfont=dict(size=8, color="#7fa6cc"),
                    ),
                    angularaxis=dict(
                        gridcolor="rgba(120,170,255,.12)",
                        tickfont=dict(size=9, color="#cfe3ff"),
                    ),
                ),
                legend=dict(
                    orientation="h",
                    yanchor="top",
                    y=-0.18,
                    x=0.5,
                    xanchor="center",
                    font=dict(size=9, color=MUTED),
                ),
            )
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with table_col:
        with st.container(border=True):
            chart_header("品类经营明细", "利润率或退款率超过阈值时标记为关注")
            cat_stats = filtered.groupby("category").agg(
                销售额=("sales_amount", "sum"),
                利润=("profit", "sum"),
                订单量=("order_id", "count"),
                客单价=("sales_amount", "mean"),
                退款率=("is_refund", "mean"),
                评分=("rating", "mean"),
            )
            cat_stats["利润率"] = cat_stats["利润"] / cat_stats["销售额"] * 100
            cat_stats["退款率"] = cat_stats["退款率"] * 100
            cat_stats["预警"] = [
                "关注" if (row["利润率"] < profit_threshold or row["退款率"] > refund_threshold) else "正常"
                for _, row in cat_stats.iterrows()
            ]
            cat_stats = cat_stats.sort_values("销售额", ascending=False).reset_index()
            cat_display = cat_stats.rename(
                columns={
                    "category": "品类",
                    "销售额": "销售额(元)",
                    "利润": "利润(元)",
                    "订单量": "订单量",
                    "客单价": "客单价(元)",
                    "退款率": "退款率",
                    "评分": "平均评分",
                }
            )
            st.dataframe(
                cat_display[["品类", "销售额(元)", "利润(元)", "订单量", "利润率", "退款率", "预警"]],
                width="stretch",
                height=380,
                hide_index=True,
                column_config={
                    "销售额(元)": st.column_config.NumberColumn(format="%.0f"),
                    "利润(元)": st.column_config.NumberColumn(format="%.0f"),
                    "利润率": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=60),
                    "退款率": st.column_config.NumberColumn(format="%.1f%%"),
                },
            )

# ---------------------------------------------------------------- 区域分析
with tabs[2]:
    st.markdown('<div class="section-title">区域与渠道分析</div>', unsafe_allow_html=True)
    region_col, channel_col = st.columns([1.15, 1], gap="small")
    with region_col:
        with st.container(border=True):
            chart_header("地区销售额与利润", "七大区域对比")
            region = (
                filtered.groupby("region", as_index=False)
                .agg(销售额=("sales_amount", "sum"), 利润=("profit", "sum"))
                .sort_values("销售额")
            )
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    y=region["region"],
                    x=region["销售额"],
                    orientation="h",
                    name="销售额",
                    marker_color="#22d3ee",
                    hovertemplate="%{y}<br>销售额 ¥%{x:,.0f}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Bar(
                    y=region["region"],
                    x=region["利润"],
                    orientation="h",
                    name="利润",
                    marker_color="#8b5cf6",
                    hovertemplate="%{y}<br>利润 ¥%{x:,.0f}<extra></extra>",
                )
            )
            fig.update_layout(barmode="group", xaxis_title="金额（元）")
            st.plotly_chart(style_fig(fig, 340), width="stretch", config={"displayModeBar": False})

    with channel_col:
        with st.container(border=True):
            chart_header("渠道 × 地区销售热力图", "观察不同渠道在各区域的渗透")
            pivot = filtered.pivot_table(
                index="channel",
                columns="region",
                values="sales_amount",
                aggfunc="sum",
            ).fillna(0)
            fig = go.Figure(
                go.Heatmap(
                    z=pivot.values,
                    x=pivot.columns.tolist(),
                    y=pivot.index.tolist(),
                    colorscale=[
                        [0, "#0b1a2b"],
                        [0.35, "#1e3a8a"],
                        [0.7, "#0ea5e9"],
                        [1, "#22d3ee"],
                    ],
                    hovertemplate="%{y} · %{x}<br>销售额 ¥%{z:,.0f}<extra></extra>",
                    colorbar=dict(
                        thickness=8,
                        len=0.82,
                        tickformat=".2s",
                        title=dict(text="销售额", font=dict(size=10, color="#8fb3d9")),
                        tickfont=dict(size=9, color="#8fb3d9"),
                    ),
                )
            )
            st.plotly_chart(style_fig(fig, 340), width="stretch", config={"displayModeBar": False})

    with st.container(border=True):
        chart_header("省份经营明细", "按销售额从高到低排序")
        province_stats = filtered.groupby("province").agg(
            销售额=("sales_amount", "sum"),
            利润=("profit", "sum"),
            订单量=("order_id", "count"),
            客单价=("sales_amount", "mean"),
            退款率=("is_refund", "mean"),
            评分=("rating", "mean"),
        )
        province_stats["利润率"] = province_stats["利润"] / province_stats["销售额"] * 100
        province_stats["退款率"] = province_stats["退款率"] * 100
        province_stats = province_stats.sort_values("销售额", ascending=False).reset_index()
        province_display = province_stats.rename(
            columns={
                "province": "省份",
                "销售额": "销售额(元)",
                "利润": "利润(元)",
                "订单量": "订单量",
                "客单价": "客单价(元)",
                "退款率": "退款率",
                "评分": "平均评分",
            }
        )
        st.dataframe(
            province_display[["省份", "销售额(元)", "利润(元)", "订单量", "客单价(元)", "利润率", "退款率", "平均评分"]],
            width="stretch",
            height=360,
            hide_index=True,
            column_config={
                "销售额(元)": st.column_config.NumberColumn(format="%.0f"),
                "利润(元)": st.column_config.NumberColumn(format="%.0f"),
                "客单价(元)": st.column_config.NumberColumn(format="%.0f"),
                "利润率": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=60),
                "退款率": st.column_config.NumberColumn(format="%.1f%%"),
                "平均评分": st.column_config.NumberColumn(format="%.2f"),
            },
        )

# ---------------------------------------------------------------- 明细数据
with tabs[3]:
    st.markdown('<div class="section-title">订单明细与数据导出</div>', unsafe_allow_html=True)
    summary_col, download_col = st.columns([2, 1], gap="small")
    with summary_col:
        st.markdown(
            f"""
            <div class="alert-row">
              <span class="alert-dot good"></span>
              <div>
                <div class="alert-title">当前筛选结果</div>
                <div class="alert-text">共 {len(filtered):,} 条订单，销售额 {fmt_money(sales)}，
                利润 {fmt_money(profit)}，退款订单 {int(filtered['is_refund'].sum()):,} 条。
                数据已按订单日期升序排列。</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with download_col:
        export = filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "导出当前筛选数据（CSV）",
            data=export,
            file_name=f"sales_filtered_{start_ts:%Y%m%d}_{end_ts:%Y%m%d}.csv",
            mime="text/csv",
            width="stretch",
        )

    detail = filtered[
        [
            "order_id", "order_date", "region", "province", "category", "channel",
            "quantity", "sales_amount", "profit", "rating", "is_new_customer", "is_refund",
        ]
    ].copy()
    detail["order_date"] = detail["order_date"].dt.strftime("%Y-%m-%d")
    detail["is_new_customer"] = detail["is_new_customer"].map({0: "否", 1: "是"})
    detail["is_refund"] = detail["is_refund"].map({0: "否", 1: "是"})
    detail = detail.rename(
        columns={
            "order_id": "订单号",
            "order_date": "下单日期",
            "region": "地区",
            "province": "省份",
            "category": "品类",
            "channel": "渠道",
            "quantity": "数量",
            "sales_amount": "销售额(元)",
            "profit": "利润(元)",
            "rating": "评分",
            "is_new_customer": "新客",
            "is_refund": "退款",
        }
    )
    st.dataframe(
        detail,
        width="stretch",
        height=520,
        hide_index=True,
        column_config={
            "销售额(元)": st.column_config.NumberColumn(format="%.2f"),
            "利润(元)": st.column_config.NumberColumn(format="%.2f"),
            "评分": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    with st.expander("查看数据清洗摘要"):
        if SUMMARY_FILE.exists():
            st.code(SUMMARY_FILE.read_text(encoding="utf-8"), language="text")
        else:
            st.caption("暂无清洗摘要文件。")

st.markdown(
    '<div class="footer">数据为模拟数据，仅用于课程实验 · Streamlit + Pandas + Plotly · 刘宝廷 3242052051028</div>',
    unsafe_allow_html=True,
)
