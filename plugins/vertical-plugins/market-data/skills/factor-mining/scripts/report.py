"""Report generation for factor mining results and portfolio evaluation.

Generates Markdown reports for:
1. Industry stock ranking (from mining + ranking pipeline)
2. Portfolio evaluation (from portfolio assessment)
"""

from __future__ import annotations

from datetime import date
from typing import Any
import numpy as np


def _ascii_chart(
    equity: np.ndarray,
    benchmark: np.ndarray | None = None,
    width: int = 60,
    height: int = 12,
) -> str:
    """Generate ASCII equity curve chart."""
    if len(equity) < 2:
        return "(insufficient data)"

    equity = np.asarray(equity, dtype=float)
    if benchmark is not None:
        benchmark = np.asarray(benchmark, dtype=float)

    # Downsample to width points
    indices = np.round(np.linspace(0, len(equity) - 1, min(width, len(equity)))).astype(int)
    eq = equity[indices]
    bm = benchmark[indices] if benchmark is not None else None

    # Determine y range
    all_vals = np.concatenate([eq] + ([bm] if bm is not None else []))
    y_min = float(np.nanmin(all_vals))
    y_max = float(np.nanmax(all_vals))
    if y_max - y_min < 1e-6:
        y_max = y_min + 0.01

    canvas = [[' '] * width for _ in range(height)]

    # Plot equity
    for i, v in enumerate(eq):
        if np.isnan(v):
            continue
        row = int((1 - (v - y_min) / (y_max - y_min)) * (height - 1))
        row = max(0, min(height - 1, row))
        canvas[row][i] = '█'

    # Plot benchmark
    if bm is not None:
        for i, v in enumerate(bm):
            if np.isnan(v):
                continue
            row = int((1 - (v - y_min) / (y_max - y_min)) * (height - 1))
            row = max(0, min(height - 1, row))
            if canvas[row][i] == ' ':
                canvas[row][i] = '░'

    # Build string with y-axis labels
    result = []
    for r in range(height):
        val = y_max - (y_max - y_min) * r / (height - 1)
        line = ''.join(canvas[r])
        result.append(f"{val:5.2f} │{line}")

    result.append(f"       └{'─' * width}")
    result.append(f"        {eq[0]:.2f}                    →                    {eq[-1]:.2f}")

    if benchmark is not None:
        result.append(f"        █ = strategy  ░ = benchmark")
    else:
        result.append(f"        █ = equity")

    return '\n'.join(result)


def generate_mining_report(
    mining_result: dict[str, Any],
    ranking_result: list[dict[str, Any]] | None = None,
    factor_details: list[dict[str, Any]] | None = None,
) -> str:
    """Generate Markdown report for industry stock ranking.

    Args:
        mining_result: Output from run_mining_pipeline().
        ranking_result: Output from rank_stocks() (optional).
        factor_details: Factor details from rank_stocks().

    Returns:
        Markdown string.
    """
    lines = []
    lines.append(f"# 产业因子挖掘报告")
    lines.append("")
    lines.append(f"**方向:** {mining_result['direction']} — {mining_result.get('direction_description', '')}")
    lines.append(f"**日期:** {date.today().isoformat()}")
    lines.append(f"**标的池:** {mining_result['pool_size']} 只股票")
    lines.append(f"**训练期:** {mining_result.get('train_period', mining_result['period'])}")
    lines.append(f"**测试期:** {mining_result.get('test_period', 'N/A')}")
    lines.append(f"**发现因子数:** {mining_result.get('total_factors_mined', mining_result.get('total_factors', 0))} → 通过验证: {len(mining_result.get('factors', []))}")
    lines.append("")

    # Top factors with train/test IC
    factors = mining_result.get("factors", [])
    if factors:
        lines.append("## 因子列表 (Top 10)")
        lines.append("")
        lines.append("| # | 显著 | 因子表达式 | Train IC | Test IC | ICIR | t-stat | 来源 |")
        lines.append("|---|------|-----------|----------|---------|------|--------|------|")
        for i, f in enumerate(factors[:10]):
            expr = f["expression"][:50] + ("..." if len(f["expression"]) > 50 else "")
            train_ic = f.get('train_ic', f.get('ic', 0))
            test_ic = f.get('test_ic', 0)
            t_stat = f.get('train_t_stat', f.get('t_stat', 0))
            sig = '✅' if f.get('is_significant', False) else '❌'
            icir = f.get('train_icir', f.get('icir', 0))
            lines.append(
                f"| {i+1} | {sig} | `{expr}` | {train_ic:.4f} | {test_ic:.4f} "
                f"| {icir:.4f} | {t_stat:.2f} | {f.get('source', '?')} |"
            )
        lines.append("")

    # Backtest results
    bt = mining_result.get("backtest", {})
    if bt and bt.get("metrics"):
        m = bt["metrics"]
        lines.append("## 回测绩效")
        lines.append("")
        lines.append(f"| 指标 | 策略 | 基准 |")
        lines.append(f"|------|------|------|")
        lines.append(f"| 年化收益 | {m['annualized_return']*100:+.1f}% | — |")
        lines.append(f"| 夏普比率 | {m['sharpe_ratio']:.2f} | — |")
        lines.append(f"| 最大回撤 | {m['max_drawdown']*100:.1f}% | — |")
        lines.append(f"| Calmar比率 | {m['calmar_ratio']:.2f} | — |")
        lines.append(f"| 胜率 | {m['win_rate']*100:.1f}% | — |")
        lines.append(f"| 超额收益 | {m['excess_return']*100:+.1f}% | — |")
        lines.append(f"| 信息比率 | {m['information_ratio']:.2f} | — |")
        lines.append(f"| 交易次数 | {bt['n_trades']} | — |")
        lines.append("")

        # ASCII equity curve
        eq = bt.get('equity_curve')
        bm = bt.get('benchmark_curve')
        if eq is not None and len(eq) > 10:
            split_idx = mining_result.get('split_idx', 0)
            lines.append("### 净值曲线 (测试期)")
            lines.append("")
            lines.append("```")
            lines.append(_ascii_chart(eq[split_idx:], bm[split_idx:] if bm is not None else None))
            lines.append("```")
            lines.append("")

    # Stock ranking (if provided)
    if ranking_result:
        lines.append("## 标的排名")
        lines.append("")
        lines.append("| 排名 | 代码 | 综合评分 | 动量信号 | 信号分类 |")
        lines.append("|------|------|----------|----------|----------|")
        for r in ranking_result[:20]:
            lines.append(
                f"| {r['rank']} | {r['code']} | {r['composite_score']:.3f} "
                f"| {r['momentum_score']:.3f} | {r['signal']} |"
            )
        lines.append("")

        # Signal summary
        signals = {}
        for r in ranking_result:
            sig = r["signal"]
            signals[sig] = signals.get(sig, 0) + 1

        lines.append("### 信号分布")
        lines.append("")
        for sig, count in sorted(signals.items(), key=lambda x: -x[1]):
            lines.append(f"- **{sig}**: {count} 只")
        lines.append("")

        # Highlight strong stocks
        strong = [r for r in ranking_result if r["signal"] == "强势延续"]
        emerging = [r for r in ranking_result if r["signal"] == "信号转强"]
        if strong:
            lines.append("### 🔥 近期强势")
            lines.append("")
            for r in strong[:5]:
                lines.append(f"- **{r['code']}** — 评分 {r['composite_score']:.3f}")
            lines.append("")
        if emerging:
            lines.append("### 📈 信号转强（关注）")
            lines.append("")
            for r in emerging[:5]:
                lines.append(f"- **{r['code']}** — 动量 {r['momentum_score']:.3f}")
            lines.append("")

    lines.append("---")
    lines.append("*本报告由因子挖掘系统自动生成，不构成投资建议。*")
    lines.append("")

    return "\n".join(lines)


def generate_portfolio_report(
    portfolio_result: dict[str, Any],
) -> str:
    """Generate Markdown report for portfolio evaluation.

    Args:
        portfolio_result: Output from evaluate_portfolio().

    Returns:
        Markdown string.
    """
    lines = []
    lines.append("# 持仓评估报告")
    lines.append("")
    lines.append(f"**日期:** {date.today().isoformat()}")
    lines.append(f"**持仓数:** {portfolio_result['diagnostics']['n_holdings']}")
    lines.append(f"**已评估:** {portfolio_result['diagnostics']['n_evaluated']}")
    lines.append("")

    # Portfolio diagnostics
    diag = portfolio_result["diagnostics"]
    lines.append("## 组合诊断")
    lines.append("")
    lines.append(f"- **平均评分:** {diag['avg_score']:.3f}")
    lines.append(f"- **集中度:** {_concentration_label(diag['concentration_risk'])}")
    lines.append("")

    # Holding details
    lines.append("## 持仓详情")
    lines.append("")
    lines.append("| 代码 | 排名 | 综合评分 | 动量信号 | 信号分类 | 健康度 |")
    lines.append("|------|------|----------|----------|----------|--------|")
    for h in portfolio_result["holdings"]:
        rank = h["rank"] or "-"
        score = f"{h['composite_score']:.3f}" if h["composite_score"] is not None else "-"
        momentum = f"{h['momentum_score']:.3f}" if h["momentum_score"] is not None else "-"
        health_label = _health_label(h["health"])
        lines.append(
            f"| {h['code']} | {rank} | {score} | {momentum} | {h['signal']} | {health_label} |"
        )
    lines.append("")

    # Factor context
    factors_used = portfolio_result.get("factors_used", [])
    if factors_used:
        lines.append("## 使用的因子")
        lines.append("")
        for i, f in enumerate(factors_used[:5], 1):
            lines.append(f"{i}. `{f['expression'][:80]}` — IC={f['ic']:.4f}, ICIR={f['icir']:.4f}")
        lines.append("")

    lines.append("---")
    lines.append("*本报告由因子挖掘系统自动生成，不构成投资建议。*")
    lines.append("")

    return "\n".join(lines)


def _concentration_label(risk: str) -> str:
    labels = {
        "high_concentration": "⚠️ 高集中度（多数持仓集中在头部）",
        "moderate": "适中",
        "diversified": "分散",
        "unknown": "未知",
    }
    return labels.get(risk, risk)


def _health_label(health: str) -> str:
    labels = {
        "strong": "🟢 强势",
        "healthy": "🟢 健康",
        "weakening": "🟡 转弱",
        "recovering": "🔵 回暖",
        "weak": "🔴 弱势",
        "unknown": "⚪ 无数据",
    }
    return labels.get(health, health)
