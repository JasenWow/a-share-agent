---
name: stock-pool
description: |
  构建主题股票池：价值链梳理 → 多渠道标的发现 → Scorecard 量化初筛。
  输出 Markdown 表格 + JSON 结构化数据。

  Triggers: "构建股票池", "机器人概念股", "AI硬件标的",
  "主题选股", "stock pool", "股票池", "主题股", "概念股筛选"
---

# Stock Pool — 主题股票池构建

## CRITICAL: A-Share Rules (READ FIRST)

1. **A-share exclusion** — ST/*ST、停牌、上市不满 1 年、退市风险，发现阶段最先过滤
2. **Data source priority** — Tushare MCP (financials/indicators) > AKShare MCP (quotes/concepts) > NEVER web search
3. **Pure play first** — scorecard 中 pure_play 优先级高于 concept 和 second_order

---

## Overview

**Core Philosophy:** "定义先行，发现其后，筛选兜底。"

本 skill 构建主题股票池，帮助投资者围绕特定产业主题（如机器人、AI 硬件、低空经济）系统化地发现和筛选投资标的。

---

## Step 1: Theme Definition

**Agent-driven reasoning.** 不需要脚本，Agent 基于知识和 MCP 数据完成。

### 1.1 价值链拆解

把主题拆成 3-6 个产业链环节，每个环节标注：
- **价值聚集度** — 高/中/低，判断该环节是否是价值链中最赚钱的部分
- **壁垒** — 技术壁垒、资金壁垒、牌照壁垒等简评

### 1.2 标的识别

每个环节列出 2-5 家关键公司，标注类型：
- `pure_play` — 核心业务就是该主题（相关营收占比 > 30%）
- `concept` — 沾边但主营占比 < 20%，弹性大但确定性低
- `second_order` — 间接受益（供应链、上游材料等）

### 1.3 市场格局

- Top 3 市占率
- 进入壁垒简评
- TAM 和增长预期

### 输出格式

按 `references/value-chain-template.md` 输出 JSON。

### 确认门控

展示价值链分析结果给用户。**必须用户确认后才进 Step 2。** 如果用户有修改意见，先更新价值链再继续。

---

## Step 2: Stock Discovery + Scorecard Screening

### 2.1 多渠道标的发现（顺序执行，避免 rate limit）

| Channel | Source | Description |
|---------|--------|-------------|
| THS 概念板块 | `scripts/discover_concept_stocks.py` | 爬取 10jqka.com.cn 概念板块成分股 |
| 财报关键词 | `akshare.stock_financial_report_sina` | 筛选主营描述含主题关键词的公司 |
| 价值链扩展 | Step 1 输出 | 从已识别的上下游公司扩展 |

**去重** — 合并各渠道结果，按 code 去重。

**注意：** Eastmoney APIs (`stock_board_concept_cons_em`) 全天不稳定，若 MCP 调用失败，改用 `scripts/discover_concept_stocks.py` 的 THS 爬虫通道。

### 2.2 数据预取

对每只候选股票，通过以下方式获取数据：
- **实时行情** — `akshare.stock_zh_a_spot_em` 或腾讯 `qt.gtimg.cn` fallback
- **20 日成交额** — `akshare.stock_zh_a_hist` + `(成交量 × 最新价)` 估算
- **PE_TTM** — 腾讯行情数据 `f39` 字段
- **营收占比** — 来自 Step 1 标注；若未标注则默认 0%（concept 类需人工确认）

> **Tushare rate limit 警告：** `concept_detail` 和 `fina_indicator` 限频 1次/分钟，避免批量调用。

将所有数据汇总为一个候选 JSON 文件，格式如下：

```json
{
  "theme": "机器人",
  "candidates": [
    {
      "code": "300124.SZ",
      "name": "汇川技术",
      "type": "pure_play",
      "is_st": false,
      "avg_turnover_20d": 120000000,
      "pe_ttm": 45.2,
      "pe_percentile": 62,
      "revenue_share_pct": 35
    }
  ]
}
```

保存到 `./out/pool_candidates_{theme}.json`。

### 2.3 Scorecard 筛选

调用 scorecard 脚本：

```bash
uv run python plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py \
  --input ./out/pool_candidates_{theme}.json \
  --output ./out/stock-pool-{theme}-{date}.json \
  --min-liquidity 50000000 \
  --pe-percentile-cap 95
```

**Scorecard 规则：**

| 维度 | Pass 标准 |
|------|-----------|
| 业务相关性 | 营收占比 >= 20% 或 type = pure_play |
| 流动性 | 近 20 日日均成交额 >= 5000 万 |
| 基本面 | 非 ST、非退市风险 |
| 估值合理性 | PE 历史分位 <= 95% |

### 2.4 最终输出

**Markdown 表格：**

```markdown
| 排名 | 代码 | 名称 | 类型 | 流动性 | PE | 估值分位 | Bull | Bear |
|------|------|------|------|--------|-----|---------|------|------|
| 1 | 300124.SZ | 汇川技术 | pure_play | 1.2亿 | 45.2x | 62% | 伺服龙头... | 传统工控占比高... |
```

- Bull/Bear 论点由 Agent 基于价值链分析和基本面数据撰写
- 排序规则：pure_play > concept > second_order，同类型按流动性降序

**JSON 文件：** scorecard 输出即最终 JSON，保存到 `./out/stock-pool-{theme}-{date}.json`

**Internal Store：** 调用 `internal-store.record_experiment` 存储结果：
- `name`: `stock-pool-{theme}`
- `strategy`: Step 1 价值链 JSON
- `params`: 筛选参数（min_liquidity, pe_percentile_cap）
- `result`: scorecard 输出 JSON

---

## Workflow

### Step 1: Theme Definition (Agent-driven, no script)

Agent analyzes the user-specified theme using domain knowledge and MCP data:
1. Break theme into 3-6 value chain stages with value density labels
2. Identify 2-5 key companies per stage, tag as `pure_play`/`concept`/`second_order`
3. Summarize market landscape (TAM, growth rate, top players)
4. **Confirmation gate:** present value chain JSON to user, proceed only after approval

Output: JSON per `references/value-chain-template.md`.

### Step 2: Stock Discovery + Scorecard Screening

**Parallel discovery:**
1. `akshare.stock_board_concept_cons` — pull concept board members
2. `tushare.income` + `tushare.fina_indicator` — filter by revenue keywords
3. Value chain extension from Step 1

**Data fetching per candidate:**
- `akshare.stock_zh_a_spot` — ST status, price, PE
- `akshare.stock_zh_a_hist` — 20-day avg turnover
- `tushare.fina_indicator` — PE_TTM, historical percentile

**Scorecard filtering** (calls `scripts/scorecard.py`):
```bash
uv run python plugins/.../stock-pool/scripts/scorecard.py \
  --input ./out/pool_candidates_{theme}.json \
  --output ./out/stock-pool-{theme}-{date}.json \
  --min-liquidity 50000000 --pe-percentile-cap 95
```

**Final output:** Markdown table + JSON file + internal-store record.

---

## Guardrails

1. **Never skip A-share exclusion rules** — ST, suspended, <1yr listed, delisted stocks must be filtered before any other logic
2. **Never use web search for financial data** — use only MCP data sources with audit trail
3. **Confirmation gate required before Step 2** — value chain analysis must be approved by user
4. **Do not modify scorecard thresholds without user confirmation** — defaults are 50M liquidity / 95th PE percentile
5. **Scorecard script has no network calls** — it only reads pre-fetched JSON, data must be collected via MCP first
6. **revenue_share_pct is required for concept stocks** — pure_play exception applies only if type is explicitly marked

---

## Quality Checklist

- [ ] 所有 A 股排除规则已应用（ST、停牌、上市不满 1 年）
- [ ] 每只入池股票有 bull/bear 论点
- [ ] rejected 列表每项有明确原因
- [ ] 每个数据字段标注 MCP 数据源
- [ ] JSON 输出格式与 value-chain-template 一致
- [ ] scorecard.py 通过所有单元测试
