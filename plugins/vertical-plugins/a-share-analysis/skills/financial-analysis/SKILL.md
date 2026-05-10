---
name: financial-analysis
description: |
  Deep financial analysis of a single A-share stock covering three statements,
  key ratios, DuPont decomposition, and industry comparison.

  Triggers: "分析这只股票", "research stock", "财务分析", "个股研究",
  "analyze 600519", "deep dive on"
---

# Single Stock Financial Analysis

## CRITICAL: A-Share Financial Reporting Conventions

- A-share annual reports follow Chinese Accounting Standards (CAS)
- Key differences from US GAAP: 非经常性损益处理、商誉减值、关联交易披露
- Fiscal year ends Dec 31 for all A-share companies
- Quarterly reports: Q1 (before Apr 30), Q2/H1 (before Aug 31),
  Q3 (before Oct 31), Annual (before Apr 30 of next year)
- **Always check report date vs today** — stale financials are unreliable

---

## Workflow

### Step 1: Identify Stock

Parse user input for stock identifier:
- 6-digit code (e.g., 600519, 000001)
- Stock name (e.g., 贵州茅台, 平安银行)
- Resolve to unified code via MCP data source

### Step 2: Fetch Financial Data

| Data | Source | Period |
|------|--------|--------|
| Income Statement (利润表) | Tushare income | Last 5 years + last 4 quarters |
| Balance Sheet (资产负债表) | Tushare balancesheet | Last 5 years |
| Cash Flow (现金流量表) | Tushare cashflow | Last 5 years |
| Financial Indicators | Tushare fina_indicator | Last 5 years |
| Industry Classification | Tushare stock_basic | 申万一级 |
| Real-time Quote | AKShare spot | Current |

### Step 3: Financial Statement Analysis

**利润表 (Income Statement):**
- Revenue trend (YoY, QoQ)
- Gross margin evolution
- Net margin evolution
- Non-recurring items impact (非经常性损益占比)
- 关联交易占比 (if available)

**资产负债表 (Balance Sheet):**
- Asset composition (fixed vs current)
- Liability structure (short-term vs long-term)
- Goodwill as % of net assets (商誉/净资产 — flag if >30%)
- Accounts receivable turnover days
- Inventory turnover days

**现金流量表 (Cash Flow Statement):**
- Operating cash flow vs net income (earnings quality)
- Free cash flow trend
- Capex / depreciation ratio

### Step 4: Key Ratios Calculation

| Category | Ratios |
|----------|--------|
| 盈利能力 | ROE, ROA, 毛利率, 净利率, EBITDA margin |
| 偿债能力 | 资产负债率, 流动比率, 速动比率, 利息保障倍数 |
| 运营效率 | 应收周转天数, 存货周转天数, 总资产周转率 |
| 成长性 | 营收YoY, 净利润YoY, 扣非净利润YoY |

### Step 5: DuPont Decomposition

```
ROE = 净利率 × 资产周转率 × 权益乘数
    = (净利/营收) × (营收/总资产) × (总资产/净资产)
```

Identify which driver is contributing most to ROE changes.

### Step 6: Industry Comparison

Fetch same metrics for 申万一级 industry peers:
- Rank target stock within industry for each metric
- Calculate percentile rank
- Highlight outliers (top/bottom quartile)

### Step 7: Format Output

**Markdown Report:**
- 公司概况 (basic info, market cap, industry)
- 财务摘要 (5-year trend tables)
- 三表分析 (key observations per statement)
- 比率分析 (table with industry comparison)
- DuPont分解 (tree diagram)
- 结论与关注点 (bullet points, NOT investment advice)

**Excel File:**
- Sheet 1: 原始数据 (raw financial data)
- Sheet 2: 比率计算 (computed ratios with formulas)
- Sheet 3: 行业对比 (industry comparison)
- File: `./out/research_<code>_<date>.xlsx`

---

## Guardrails

- Mark all non-recurring items clearly
- Flag goodwill > 30% of net assets with warning
- Flag accounts receivable growth > revenue growth with warning
- If financial data is > 3 months stale, warn user
- Never provide investment advice — output is factual analysis only
