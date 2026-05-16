"""Plotly chart functions for the paper-trader Jupyter UI."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from IPython.display import HTML, display


def plot_equity_curve(nav_records: list[dict]) -> go.Figure:
    """Plot strategy NAV vs benchmark NAV over time."""
    if not nav_records:
        return go.Figure().update_layout(title="No data")

    df = pd.DataFrame(nav_records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["trade_date"], y=df["nav"], name="Strategy NAV", line=dict(color="#2563eb", width=2)))
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=df["benchmark_value"] * df["nav"].iloc[0],
            name="Benchmark",
            line=dict(color="#94a3b8", width=1.5, dash="dash"),
        )
    )
    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="NAV (RMB)",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def plot_drawdown(nav_records: list[dict]) -> go.Figure:
    """Plot underwater drawdown chart."""
    if not nav_records:
        return go.Figure().update_layout(title="No data")

    df = pd.DataFrame(nav_records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["peak"] = df["nav"].cummax()
    df["drawdown"] = (df["peak"] - df["nav"]) / df["peak"]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["trade_date"],
            y=-df["drawdown"] * 100,
            fill="tozeroy",
            fillcolor="rgba(239, 68, 68, 0.3)",
            line=dict(color="#ef4444", width=1),
            name="Drawdown",
        )
    )
    fig.update_layout(
        title="Drawdown",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template="plotly_white",
        height=300,
    )
    return fig


def plot_excess_returns(nav_records: list[dict]) -> go.Figure:
    """Plot cumulative excess return over benchmark."""
    if not nav_records:
        return go.Figure().update_layout(title="No data")

    df = pd.DataFrame(nav_records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["cum_excess"] = (1 + df["excess_return"]).cumprod() - 1

    colors = ["#22c55e" if v >= 0 else "#ef4444" for v in df["cum_excess"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(x=df["trade_date"], y=df["cum_excess"] * 100, marker_color=colors, name="Cumulative Excess")
    )
    fig.update_layout(
        title="Cumulative Excess Return vs Benchmark",
        xaxis_title="Date",
        yaxis_title="Excess Return (%)",
        template="plotly_white",
        height=300,
        showlegend=False,
    )
    return fig


def plot_kline(
    bar_data: list[dict],
    trades: list[dict] | None = None,
    title: str = "K-Line Chart",
) -> go.Figure:
    """Plot candlestick chart with optional buy/sell markers."""
    if not bar_data:
        return go.Figure().update_layout(title="No data")

    df = pd.DataFrame(bar_data)
    date_col = "date" if "date" in df.columns else "trade_date"
    df["date_fmt"] = pd.to_datetime(df[date_col], format="%Y%m%d")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df["date_fmt"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )

    # Volume
    colors = ["#22c55e" if c >= o else "#ef4444" for c, o in zip(df["close"], df["open"])]
    fig.add_trace(
        go.Bar(x=df["date_fmt"], y=df["volume"], marker_color=colors, opacity=0.5, name="Volume", showlegend=False),
        row=2,
        col=1,
    )

    # Trade markers
    if trades:
        for t in trades:
            t_date = pd.to_datetime(t["trade_date"], format="%Y%m%d")
            marker_color = "#22c55e" if t["direction"] == "buy" else "#ef4444"
            marker_symbol = "triangle-up" if t["direction"] == "buy" else "triangle-down"
            fig.add_trace(
                go.Scatter(
                    x=[t_date],
                    y=[t["price"]],
                    mode="markers",
                    marker=dict(size=12, color=marker_color, symbol=marker_symbol),
                    name=f'{t["direction"].upper()} {t["stock_code"]}',
                    showlegend=False,
                ),
                row=1,
                col=1,
            )

    fig.update_layout(
        title=title,
        template="plotly_white",
        height=500,
        xaxis_rangeslider_visible=False,
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    return fig


def plot_cost_breakdown(trades: list[dict]) -> go.Figure:
    """Plot transaction cost breakdown pie chart."""
    if not trades:
        return go.Figure().update_layout(title="No trades")

    total_commission = sum(t.get("commission", 0) for t in trades)
    total_stamp = sum(t.get("stamp_duty", 0) for t in trades)
    total_slip = sum(t.get("slippage_cost", 0) for t in trades)

    fig = go.Figure(
        data=[
            go.Pie(
                labels=["Commission", "Stamp Duty", "Slippage"],
                values=[total_commission, total_stamp, total_slip],
                marker=dict(colors=["#3b82f6", "#f59e0b", "#8b5cf6"]),
                textinfo="label+value",
                texttemplate="%{label}<br>¥%{value:,.2f}",
            )
        ]
    )
    fig.update_layout(title="Transaction Cost Breakdown", template="plotly_white", height=350)
    return fig


def plot_performance_card(perf: dict) -> None:
    """Display performance metrics as an HTML card."""
    total_ret = perf.get("total_return", 0)
    ann_ret = perf.get("annual_return", 0)
    sharpe = perf.get("sharpe_ratio", 0)
    max_dd = perf.get("max_drawdown", 0)
    win_rate = perf.get("win_rate", 0)
    excess = perf.get("excess_annual_return", 0)
    trades = perf.get("total_trades", 0)
    cost = perf.get("total_cost", 0)

    def _color(val, invert=False):
        if isinstance(val, str):
            return "#6b7280"
        positive = val >= 0
        if invert:
            positive = not positive
        return "#22c55e" if positive else "#ef4444"

    html = f"""
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:12px; font-family:system-ui;">
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Total Return</div>
        <div style="font-size:24px; font-weight:bold; color:{_color(total_ret)};">{total_ret*100:.2f}%</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Annual Return</div>
        <div style="font-size:24px; font-weight:bold; color:{_color(ann_ret)};">{ann_ret*100:.2f}%</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Sharpe Ratio</div>
        <div style="font-size:24px; font-weight:bold; color:{_color(sharpe)};">{sharpe:.4f}</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Max Drawdown</div>
        <div style="font-size:24px; font-weight:bold; color:{_color(max_dd, invert=True)};">{max_dd*100:.2f}%</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Win Rate</div>
        <div style="font-size:24px; font-weight:bold; color:{_color(win_rate)};">{win_rate*100:.1f}%</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Excess Return</div>
        <div style="font-size:24px; font-weight:bold; color:{_color(excess)};">{excess*100:.2f}%</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Total Trades</div>
        <div style="font-size:24px; font-weight:bold; color:#1e293b;">{trades}</div>
      </div>
      <div style="background:#f8fafc; border-radius:8px; padding:16px; text-align:center;">
        <div style="font-size:12px; color:#64748b;">Total Cost</div>
        <div style="font-size:24px; font-weight:bold; color:#1e293b;">¥{cost:,.2f}</div>
      </div>
    </div>
    """
    display(HTML(html))


def display_positions_table(positions: list[dict]) -> pd.DataFrame:
    """Display current positions as a styled DataFrame."""
    if not positions:
        return pd.DataFrame({"Message": ["No positions"]})

    df = pd.DataFrame(positions)
    display_cols = ["stock_code", "shares", "sellable_shares", "cost_basis", "market_value", "unrealized_pnl"]
    available = [c for c in display_cols if c in df.columns]
    df = df[available].copy()
    df.columns = ["Code", "Shares", "Sellable", "Cost Basis", "Market Value", "Unrealized PnL"]
    return df.style.format({"Cost Basis": "¥{:.2f}", "Market Value": "¥{:.0f}", "Unrealized PnL": "¥{:.0f}"})


def display_trades_table(trades: list[dict]) -> pd.DataFrame:
    """Display trade log as a styled DataFrame."""
    if not trades:
        return pd.DataFrame({"Message": ["No trades"]})

    df = pd.DataFrame(trades)
    display_cols = ["trade_date", "stock_code", "direction", "shares", "price", "amount", "total_cost"]
    available = [c for c in display_cols if c in df.columns]
    df = df[available].copy()
    df.columns = ["Date", "Code", "Dir", "Shares", "Price", "Amount", "Cost"]
    return df.style.format({"Price": "¥{:.3f}", "Amount": "¥{:.0f}", "Cost": "¥{:.2f}"})
