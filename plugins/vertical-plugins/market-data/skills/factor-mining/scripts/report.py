"""Report generation for factor mining results and portfolio evaluation.

Generates Markdown reports for:
1. Industry stock ranking (from mining + ranking pipeline)
2. Portfolio evaluation (from portfolio assessment)
"""

from __future__ import annotations

from datetime import date
from typing import Any


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
    lines.append(f"**回测期:** {mining_result['period']} ({mining_result.get('n_trading_days', '?')} 交易日)")
    lines.append(f"**发现因子数:** {mining_result['total_factors']}")
    lines.append("")

    # Top factors
    factors = mining_result.get("factors", [])
    if factors:
        lines.append("## 因子列表 (Top 10)")
        lines.append("")
        lines.append("| # | 因子表达式 | IC | ICIR | 换手率 | 适应度 | 来源 |")
        lines.append("|---|-----------|-----|------|--------|--------|------|")
        for i, f in enumerate(factors[:10]):
            expr = f["expression"][:60] + ("..." if len(f["expression"]) > 60 else "")
            lines.append(
                f"| {i+1} | `{expr}` | {f['ic']:.4f} | {f['icir']:.4f} "
                f"| {f['turnover']:.2f} | {f['fitness']:.4f} | {f.get('source', '?')} |"
            )
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
