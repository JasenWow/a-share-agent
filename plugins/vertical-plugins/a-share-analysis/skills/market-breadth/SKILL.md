---
name: market-breadth
description: |
  Market breadth analysis, northbound capital flow, dragon-tiger list
  alerts, sector rotation, and market regime detection for A-share market.

  Triggers: "市场情绪", "market breadth", "北向资金", "板块轮动",
  "龙虎榜", "涨跌停统计", "market monitor"
---

# Market Breadth and Sentiment Monitoring

## Workflow

### Step 1: Market Breadth Indicators

| Indicator | Source | Calculation |
|-----------|--------|-------------|
| 上涨/下跌家数比 | AKShare daily | count(up) / count(down) |
| 涨停/跌停家数 | AKShare | count(limit_up) / count(limit_down) |
| 新高/新低家数 | AKShare | 52-week high/low count |
| 全A等权收益 | Calculate | equal-weighted return of all A-shares |

### Step 2: Northbound Capital Flow

Fetch via AKShare:
- 当日净流入额 (daily net flow)
- 沪股通/深股通分拆
- 累计净流入趋势
- 前10大活跃个股

**Signal interpretation:**
- 连续3日大幅净流入 → 市场情绪偏多
- 连续3日大幅净流出 → 警惕

### Step 3: Dragon-Tiger List (龙虎榜)

Fetch via AKShare:
- 今日上榜个股
- 买方/卖方席位分析
- 机构 vs 游资 vs 散户占比
- 异常信号：机构净买入 > 5000万

### Step 4: Sector Rotation Map

Calculate sector performance:
- 申万一级31个行业
- 近1周/1月/3月收益率
- 成交额变化率
- 生成热力图数据

### Step 5: Market Regime Detection

Simple rule-based classification:

| Regime | Conditions |
|--------|-----------|
| 牛市 (Bull) | 沪深300 > MA60, 上涨家数 > 60%, 北向连续流入 |
| 熊市 (Bear) | 沪深300 < MA60, 下跌家数 > 60%, 北向连续流出 |
| 震荡 (Range) | Neither bull nor bear conditions met |
| 危机 (Crisis) | 单日跌幅 > 3%, 跌停 > 100家, VIX飙升 |

### Step 6: Output

**Markdown Report:**
- 市场宽度仪表盘
- 北向资金流向
- 龙虎榜异常信号
- 板块轮动排名
- 市场状态判断
- 操作建议（NOT投资建议）

**Excel File:**
- Sheet 1: 市场宽度数据
- Sheet 2: 板块排名
- Sheet 3: 龙虎榜明细
- File: `./out/market_<date>.xlsx`
