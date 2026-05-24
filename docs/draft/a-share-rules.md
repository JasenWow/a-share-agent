# A-Share Market Rules

> Canonical reference for A-share market constraints that must be respected across all agents, skills, and backtesting engines. Every agent must consult this file when generating trading signals, backtests, or portfolio recommendations.
>
> When in doubt about a market rule, this document is the source of truth.

## T+1 Settlement

A-shares operate on T+1 settlement: **stocks bought today cannot be sold until tomorrow**.

- **Trade execution**: Signal generated at day T close → trade executes at T+1 open → position is sellable from T+2 open.
- **Label construction**: `Label = Close(T+2) / Open(T+1) - 1`
- **Backtesting implication**: Same-day round-trip trades are **impossible**. The backtester must enforce this as a hard constraint.

## Board Price Limits

Daily price movement is bounded by board-specific limits. Orders beyond these limits are rejected.

| Board | Code Prefix | Daily Limit | Notes |
|-------|-------------|-------------|-------|
| Main Board (主板) | 600xxx, 000xxx, 001xxx | ±10% | Standard |
| ChiNext (创业板) | 300xxx | ±20% | Since 2020-08-24 |
| STAR Market (科创板) | 688xxx | ±20% | Since 2019-07-22 |
| BSE (北交所) | 8xxxxx, 4xxxxx | ±30% | Since 2021-11-15 |
| ST / *ST | any | ±5% | Special treatment stocks |

**Implications for screening**: Stocks at the upper limit (涨停) cannot be bought. Stocks at the lower limit (跌停) cannot be sold. Agents must check price vs. limit before generating actionable signals.

**Backtesting rule**: Skip signals for stocks at their daily limit. Do not assume fills at limit prices.

## Transaction Costs (2026)

Every trade incurs costs. Backtests and portfolio optimizations must include all three components.

| Component | Rate | Direction | Notes |
|-----------|------|-----------|-------|
| Commission (佣金) | 0.025% per side | Both buy and sell | Assume 万2.5 full-commission |
| Stamp duty (印花税) | 0.05% | Sell only | Reduced from 0.1% on 2023-08-28 |
| Slippage (滑点) | 0.05–0.20% | Both | Varies by market cap and liquidity |

**Total estimated round-trip cost**:
- Large-cap (沪深300): ~0.20%
- Mid-cap (中证500): ~0.30%
- Small-cap (中证1000): ~0.40%

**Default assumptions for backtesting**: Commission 0.025% each way, stamp duty 0.05% sell-only, slippage 0.05% one-way.

## Exclusion Rules

The following stocks must be excluded from screening, factor construction, and backtesting **unless the user explicitly overrides**.

| Exclusion | Rule | Reason |
|-----------|------|--------|
| ST / *ST stocks | Stock name contains "ST" | Distorted financials, extreme risk |
| Suspended stocks (停牌) | Trading status = suspended | Cannot trade |
| Newly listed (次新股) | Listed < 252 trading days (1 year) | IPO effect distorts factor signals |
| Delisted stocks (退市) | Delist status = active | Survivorship bias, no trading |
| Limit-up stocks (涨停) | Price = upper limit price | Cannot buy |
| Limit-down stocks (跌停) | Price = lower limit price | Cannot sell |

**Agent behavior**: Always display exclusion counts in screening results. Warn if a requested stock falls into any exclusion category.

## Industry Classification

The system uses **Shenwan Industry Classification (申万行业分类)** as the standard taxonomy.

| Level | Count | Usage |
|-------|-------|-------|
| Level 1 (一级行业) | ~31 | Primary classification for screening, sector exposure, neutralization |
| Level 2 (二级行业) | ~134 | Detailed sector comparison |
| Level 3 (三级行业) | ~346 | Fine-grained peer grouping |

All industry references across agents must use Shenwan Level 1 unless a more granular level is specified. The standard 31 sectors include: 银行, 非银金融, 食品饮料, 医药生物, 电子, 计算机, 传媒, 通信, 电力设备, 汽车, 家用电器, 建筑装饰, 公用事业, 房地产, 煤炭, 石油石化, 基础化工, 钢铁, 有色金属, 机械设备, 国防军工, 交通运输, 商贸零售, 社会服务, 综合, 农林牧渔, 纺织服饰, 轻工制造, 环保, 美容护理, 建筑材料.

## Special Events

| Event | Chinese Term | Impact | Agent Handling |
|-------|-------------|--------|----------------|
| Trading suspension/resumption | 停复牌 | Stock becomes non-tradeable | Mark as non-tradeable during suspension |
| Ex-rights/ex-dividend | 除权除息 | Price adjustment needed | Use adjusted prices (复权) for historical analysis |
| Lock-up expiry | 解禁 | Large selling pressure possible | Flag in catalyst tracker |
| Shareholder increase/decrease | 增减持 | Signal of insider sentiment | Include in equity researcher output |
| Special treatment change | ST摘帽/戴帽 | Major risk/reward shift | Update exclusion rules dynamically |

## Regulatory Constraints

| Constraint | Detail | Relevance |
|------------|--------|-----------|
| Order frequency | Max 15 orders/second per account | Knowledge record only (no auto-trading) |
| Short selling restrictions | Only designated stocks; requires margin account; strict borrowing limits | Backtesting long-short strategies must note constraints |
| Reduction rules (减持新规) | Controlling shareholders face holding period and volume restrictions | Relevant for catalyst tracking |
| Information disclosure | Quarterly and annual report deadlines | Data freshness validation |

## Factor-Specific Rules

When constructing or testing factors, apply this preprocessing pipeline in order:

```
Raw Factor → MAD Winsorization (3σ) → ZScore Standardization → [Optional] Industry + Cap Neutralization
```

**MAD Winsorization**:
- Median = median(factor_values)
- MAD = median(|factor_values - Median|)
- Clip to [Median - 3 × MAD × 1.4826, Median + 3 × MAD × 1.4826]

**ZScore Standardization**:
- zscore = (factor - mean) / std

**Industry + Cap Neutralization** (optional):
- Regress: factor ~ log(流通市值) + 申万一级行业_dummies
- Use residuals as neutralized factor

**Label construction for factor testing**:
- Signal at T close → Trade at T+1 open → Return realized at T+2 close
- `Label = Close(T+2) / Open(T+1) - 1`

## Common Mistakes

| Mistake | Correct Approach |
|---------|-----------------|
| Using current index constituents for historical backtest | Use point-in-time constituents from `tushare.index_weight` |
| ZScore without winsorization | Always winsorize BEFORE standardizing |
| Applying PE filter on negative-earnings stocks | Handle negative PE: set to NaN or exclude |
| Using total market cap without log transform | Always use log(市值) for neutralization |
| Ignoring T+1 in return labels | Label = Close(T+2) / Open(T+1) - 1 |
| Forward-filling factor values for missing data | Set missing factor values to NaN; do not fill |
| Testing factor only in-sample | Walk-forward validation is mandatory |
| Single-point DCF valuation | Use sensitivity grid (WACC × growth rate) |
| Presenting gross-of-cost returns | Always show net-of-cost alongside gross |
| Claiming "alpha" from in-sample IC | Out-of-sample walk-forward is mandatory |

## Lot Size

- Minimum trade unit: **100 shares** (1 lot / 1手)
- All orders must be rounded to the nearest 100 shares
- Round **down** when buying (avoid over-allocation)
- This constraint affects portfolio construction for small accounts

## Market Calendar

- Trading days: Monday–Friday, excluding public holidays
- Trading hours: 9:30–11:30, 13:00–15:00 (Beijing time, UTC+8)
- Auction periods: 9:15–9:25 (opening), 14:57–15:00 (closing)
- Use an A-share trading calendar (e.g., `exchange_cal` from Tushare) to skip non-trading days in backtests
