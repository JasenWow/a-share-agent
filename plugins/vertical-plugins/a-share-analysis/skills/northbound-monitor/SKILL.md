---
name: northbound-monitor
description: |
  A-share northbound capital flow monitoring and analysis. Track daily
  net flows from HKEx to Shanghai/Shenzhen exchanges via Stock Connect,
  compute trend metrics, and generate structured Markdown reports.

  Triggers: "北向资金", "northbound flow", "沪股通净流入", "深股通",
  "北向资金流向", "northbound capital", "沪深港通资金", "/market"
---

# A-Share Northbound Capital Flow Monitor

## Overview

This skill monitors and analyzes northbound capital flows through the
Shanghai-HK and Shenzhen-HK Stock Connect programs. It fetches real-time
or daily net flow data, computes cumulative trend metrics, and generates
Markdown reports for market sentiment analysis.

**Core Philosophy:** "Flows speak louder than prices."

---

## Workflow

### Step 1: Fetch Northbound Flow Data

Call AKShare tool `stock_hsgt_north_net_flow_in_em` with no parameters:

```
mcp__akshare__stock_hsgt_north_net_flow_in_em()
```

The tool returns JSON in this format:
```json
{
  "data": [
    {
      "日期": "20240520",
      "沪股通": "1234.56",
      "深股通": "567.89",
      "当日净流入": "1802.45",
      "近5日累计": "8901.23",
      "近20日累计": "34567.89"
    }
  ],
  "count": 1
}
```

If data is empty or count is 0, return graceful message and exit.

### Step 2: Parse JSON and Extract Fields

Parse the returned JSON and extract these fields for each date entry:

| Field | Type | Description |
|-------|------|-------------|
| 日期 | string | Trading date (YYYYMMDD) |
| 沪股通 | float | Shanghai Connect net flow (million CNY) |
| 深股通 | float | Shenzhen Connect net flow (million CNY) |
| 当日净流入 | float | Total daily net flow |
| 近5日累计 | float | 5-day cumulative net flow |
| 近20日累计 | float | 20-day cumulative net flow |

Convert string values to float for metric computation.
Format date strings to readable format (YYYY-MM-DD).

### Step 3: Compute Trend Metrics

Compute the following metrics from parsed data:

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| 当日净流入 | from data | Today's total net flow (million CNY) |
| 沪股通占比 | 沪股通 / 当日净流入 × 100% | Shanghai vs Shenzhen split |
| 深股通占比 | 深股通 / 当日净流入 × 100% | Shenzhen vs Shanghai split |
| 趋势判断 | Compare recent days' signs | 连续流入/流出天数 (consecutive up/down days) |

**Trend Direction Logic:**
- If consecutive days have same sign (all positive or all negative), trend = "连续X日净流入" or "连续X日净流出"
- If signs alternate, trend = "震荡态势"

### Step 4: Generate Markdown Report

Assemble the output as a Markdown report:

```markdown
# 北向资金流向报告 | Northbound Capital Flow Report

**报告日期 | Report Date:** YYYY-MM-DD

---

## 今日资金流向 | Today's Flow

| 指标 | 金额（亿元）|
|-----|------------|
| 当日净流入 | +XX.XX |
| 沪股通 | +XX.XX (XX%) |
| 深股通 | +XX.XX (XX%) |

---

## 累计净流入 | Cumulative Flow

| 周期 | 金额（亿元）|
|-----|------------|
| 近5日累计 | +XXX.XX |
| 近20日累计 | +XXX.XX |

---

## 趋势分析 | Trend Analysis

- **趋势判断:** 连续X日净流入 / 连续X日净流出 / 震荡态势
- **市场情绪:** 积极（持续流入）/ 谨慎（流出扩大）/ 中性

---

## 风险提示 | Risk Notes

- 数据存在T+1延迟，仅供参考
- 非交易日无数据更新
- 大额流入/流出可能受政策或事件驱动，需结合基本面判断
```

---

## Guardrails

- **T+1数据延迟:** 北向资金数据为T+1披露，报告中需注明"数据仅供参考，不构成投资建议"
- **非交易日处理:** 若返回数据为空或count=0，返回"今日暂无北向资金数据（可能为非交易日）"并退出
- **数据新鲜度:** 检查返回数据日期是否为最近交易日，若数据超过2个交易日需提示数据延迟
- **金额单位:** AKShare返回单位为万元，需转换为亿元（除以10000）并保留2位小数
- **除以零保护:** 计算沪股通/深股通占比时，若当日净流入为0，跳过百分比计算
- **仅使用AKShare:** 禁止使用Tushare工具获取北向资金数据

---

## Output Format Specification

1. **报告标题:** 使用中英双语标题
2. **数据表格:** Markdown表格，金额单位为"亿元"，正数显示为绿色（+），负数显示为红色（-）
3. **趋势判断:** 明确标注连续流入/流出天数和市场情绪
4. **风险提示:** 固定包含风险提示区块，作为报告结尾
5. **空数据处理:** 返回单行消息，不生成完整报告

(End of file - total 138 lines)
