# Stock Pool Skill Design

Date: 2026-05-20

## Summary

构建主题股票池 skill，对齐 Anthropic `equity-research:idea-generation` 的 skill 模式。放在 `equity-research` vertical 下，采用 SKILL.md + Python 脚本混合方式。本次只做 stock-pool，thesis-track 留 Phase 2。

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Core positioning | Unified selection (screen + theme) | 覆盖因子筛选和主题选股两种场景 |
| Skill split | stock-pool (this) + thesis-track (Phase 2) | 对齐 Anthropic idea-generation + thesis-tracker |
| Execution mode | SKILL.md + Python script hybrid | Agent 推理 + scorecard 确定性逻辑可复现 |
| Vertical plugin | equity-research | 对齐 Anthropic idea-generation 归属 |
| Reference pattern | Anthropic financial-analysis | Command → Skill → References 分层 |

## File Structure

```
plugins/vertical-plugins/equity-research/
  commands/
    stock-pool.md                          # /stock-pool [主题名称]
  skills/
    stock-pool/
      SKILL.md                             # 完整工作流定义
      scripts/
        scorecard.py                       # Scorecard 量化筛选脚本
      references/
        value-chain-template.md            # 价值链分析输出模板
```

## Command Entry

`commands/stock-pool.md`:

```yaml
---
description: "构建主题股票池：价值链梳理、标的发现、量化初筛"
argument-hint: "[主题名称，如：机器人、AI硬件、低空经济]"
---
```

Command 是薄路由，加载 `stock-pool` skill 执行。

## SKILL.md Workflow

### Frontmatter

```yaml
---
name: stock-pool
description: |
  构建主题股票池：价值链梳理 → 多渠道标的发现 → Scorecard 量化初筛。
  输出 Markdown 表格 + JSON 结构化数据。

  Triggers: "构建股票池", "机器人概念股", "AI硬件标的",
  "主题选股", "stock pool", "股票池"
---
```

### Critical Rules (READ FIRST)

1. **A-share exclusion** — ST/*ST、停牌、上市不满 1 年、退市风险，发现阶段最先过滤
2. **Data source priority** — Tushare MCP (financials/indicators) > AKShare MCP (quotes/concepts) > NEVER web search
3. **Pure play first** — scorecard 中 pure_play 优先级高于 concept 和 second_order

### Step 1: Theme Definition (Agent-driven)

Input: theme name (from user argument or interactive prompt)

1. **Value chain breakdown** — split theme into 3-6 industry chain stages, label value density (高/中/低)
2. **Company identification** — list key companies per stage, label type:
   - `pure_play` — core business IS the theme (>30% revenue)
   - `concept` — tangentially related (<20% revenue)
   - `second_order` — indirect beneficiary (supply chain)
3. **Market landscape** — top 3 market share, entry barriers

Output: JSON per `references/value-chain-template.md` format.

**Confirmation gate** — present value chain analysis to user, proceed to Step 2 only after approval.

### Step 2: Stock Discovery + Scorecard Screening

**Discovery channels** (parallel):

| Channel | MCP Tool | Description |
|---------|----------|-------------|
| Concept board members | `akshare.stock_board_concept_cons` | Pull concept board constituents |
| Financial keywords | `tushare.income` + `fina_indicator` | Filter by revenue description keywords |
| Value chain extension | Step 1 output | Expand from identified upstream/downstream |

**Scorecard screening** — call `scripts/scorecard.py`:

| Dimension | Pass Criteria | Data Source |
|-----------|---------------|-------------|
| Business relevance | Revenue share > 20% OR core concept board member | tushare / akshare |
| Liquidity | 20-day avg turnover > 50M CNY | akshare |
| Fundamentals | Not ST, not delisting risk | akshare |
| Valuation sanity | PE not at 95%+ historical percentile | tushare |

**Final output**:
- Markdown table (rank, code, name, type, bull/bear thesis)
- JSON structure (full scorecard details, rejected list with reasons)
- Store to internal-store + local file `./out/stock-pool-{theme}-{date}.json`

### Quality Checklist

- [ ] All A-share exclusion rules applied
- [ ] Each stock in pool has bull/bear thesis
- [ ] Rejected stocks have explicit reasons
- [ ] Every field has data source citation (MCP source)
- [ ] JSON output matches value-chain-template format

## scorecard.py

### Interface

```bash
uv run python plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py \
  --input ./out/pool_candidates.json \
  --output ./out/pool_scorecard.json \
  --min-liquidity 50000000 \
  --pe-percentile-cap 95
```

### Input Format

```json
{
  "theme": "机器人",
  "candidates": [
    {"code": "300124.SZ", "name": "汇川技术", "type": "pure_play"},
    {"code": "002472.SZ", "name": "双环传动", "type": "second_order"}
  ]
}
```

### Internal Logic

1. Read candidate JSON from `--input`
2. For each stock, fetch data via MCP tools:
   - `akshare.stock_zh_a_spot` — ST status, current price
   - `akshare.stock_zh_a_hist` — 20-day avg turnover
   - `tushare.fina_indicator` — PE_TTM, ROE
3. Score each dimension, output pass/fail + reason
4. Aggregate and write to `--output`

### Output Format

```json
{
  "theme": "机器人",
  "pool_date": "2026-05-20",
  "passed": [
    {
      "code": "300124.SZ",
      "name": "汇川技术",
      "type": "pure_play",
      "scorecard": {
        "relevance": {"value": "35%", "pass": true},
        "liquidity": {"value": "1.2亿", "pass": true},
        "fundamentals": {"value": "正常", "pass": true},
        "valuation": {"value": "PE 45x (分位 62%)", "pass": true}
      }
    }
  ],
  "rejected": [
    {"code": "XXXXXX.SZ", "name": "...", "reason": "流动性不足：日均 3200 万"}
  ]
}
```

### Data Source in Script

scorecard.py calls MCP tools directly (not via Agent). It uses the existing MCP server endpoints configured in `.mcp.json`. The script imports `mcp` client or uses HTTP calls to localhost:8000/8001/8002.

## Data Storage

No new MCP tools. Use existing internal-store:

- **Write**: `record_experiment(name="stock-pool-{theme}", strategy=theme_definition, params=screening_params, result=pool_result)`
- **Read**: `list_experiments()` filtered by name prefix `stock-pool-`
- **File backup**: JSON written to `./out/stock-pool-{theme}-{date}.json`

## references/value-chain-template.md

```json
{
  "theme": "string",
  "analysis_date": "YYYY-MM-DD",
  "value_chain": [
    {
      "stage": "产业链环节名称",
      "value_density": "高/中/低",
      "barrier": "壁垒简述",
      "companies": [
        {
          "code": "000000.SZ",
          "name": "公司名称",
          "type": "pure_play | concept | second_order",
          "market_position": "市场地位描述",
          "note": "补充说明"
        }
      ]
    }
  ],
  "market_landscape": {
    "total_addressable_market": "xxx 亿",
    "growth_rate": "CAGR xx%",
    "key_players": ["公司A", "公司B", "公司C"]
  }
}
```

Type definitions:
- `pure_play` — theme revenue > 30% OR widely recognized as core theme stock
- `concept` — concept board member but main business < 20%, high elasticity but low certainty
- `second_order` — supply chain beneficiary, not directly facing end market

## Relationship with factor-screen

`factor-screen` (under `market-data` vertical) is an independent multi-factor screening skill. `stock-pool` may suggest using factor-screen for pre-filtering in Step 2, but does not hard-depend on it. Both skills run independently.

## Acceptance Criteria

1. `/stock-pool 机器人` triggers skill, outputs value chain analysis JSON
2. Value chain confirmed → auto-enters Step 2, discovers candidates via multiple channels
3. `scorecard.py` runs independently, outputs pass/reject JSON from candidate input
4. Final pool includes Markdown table + JSON file
5. Code follows 4-layer architecture boundary (L1 Skill, no cross-layer references)

## Phase 2 (Deferred)

| Feature | Description |
|---------|-------------|
| thesis-track skill | Investment thesis tracking, independent skill in equity-research |
| Auto-rebalance | Periodic pool refresh + entry/exit triggers |
| Multi-factor ranking | Rank pool stocks by factor scores |
| Value chain monitoring | Auto-detect industry chain changes |
| Catalyst calendar | Aligned with Anthropic catalyst-calendar |
