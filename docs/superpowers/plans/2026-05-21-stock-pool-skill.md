# Stock Pool Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a theme-based stock pool skill under the equity-research vertical, aligned with the Anthropic financial-analysis skill pattern.

**Architecture:** SKILL.md defines the two-step workflow (theme definition → discovery + scorecard). Agent executes Step 1 (value chain analysis) via reasoning. Step 2 uses MCP tools for data fetching and calls `scorecard.py` for deterministic filtering. No new MCP tools.

**Tech Stack:** Python 3.10+, argparse, json, dataclasses. Tests via pytest. Follows existing plugin patterns from `factor-screen` and `financial-analysis` skills.

**Spec:** `docs/superpowers/specs/2026-05-20-stock-pool-skill-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `plugins/vertical-plugins/equity-research/commands/stock-pool.md` | Slash command entry point |
| Create | `plugins/vertical-plugins/equity-research/skills/stock-pool/SKILL.md` | Full workflow definition |
| Create | `plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py` | Pure filter logic, reads JSON, outputs JSON |
| Create | `plugins/vertical-plugins/equity-research/skills/stock-pool/references/value-chain-template.md` | Value chain output template |
| Create | `tests/test_stock_pool_scorecard.py` | Unit tests for scorecard.py |
| Create | `tests/fixtures/scorecard_candidates.json` | Test fixture for scorecard input |
| Modify | `plugins/vertical-plugins/equity-research/.claude-plugin/plugin.json` | Add stock-pool to skills list |
| Modify | `plugins/vertical-plugins/equity-research/AGENTS.md` | Add stock-pool to skills table |

---

### Task 1: scorecard.py — Data Models + Filter Logic

**Files:**
- Create: `plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py`

- [ ] **Step 1: Write failing tests for scorecard filter logic**

Create `tests/test_stock_pool_scorecard.py`:

```python
"""Tests for stock-pool scorecard filter logic."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SCRIPT = Path("plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py")
FIXTURES = Path("tests/fixtures")


def _run_scorecard(input_data: dict, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as inf:
        json.dump(input_data, inf, ensure_ascii=False)
        inf_path = inf.name
    out_path = inf_path + ".out.json"
    cmd = [sys.executable, str(SCRIPT), "--input", inf_path, "--output", out_path]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        with open(out_path) as f:
            result.output_data = json.load(f)
    return result


@pytest.fixture
def sample_candidates():
    return {
        "theme": "机器人",
        "candidates": [
            {
                "code": "300124.SZ",
                "name": "汇川技术",
                "type": "pure_play",
                "is_st": False,
                "avg_turnover_20d": 120_000_000,
                "pe_ttm": 45.2,
                "pe_percentile": 62,
                "revenue_share_pct": 35,
            },
            {
                "code": "000001.SZ",
                "name": "平安银行",
                "type": "concept",
                "is_st": False,
                "avg_turnover_20d": 300_000_000,
                "pe_ttm": 5.2,
                "pe_percentile": 30,
                "revenue_share_pct": 5,
            },
            {
                "code": "688001.SZ",
                "name": "ST某股",
                "type": "concept",
                "is_st": True,
                "avg_turnover_20d": 80_000_000,
                "pe_ttm": 100.0,
                "pe_percentile": 98,
                "revenue_share_pct": 10,
            },
        ],
    }


class TestScorecardPass:
    def test_pure_play_passes_all_dimensions(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        passed = result.output_data["passed"]
        codes = [s["code"] for s in passed]
        assert "300124.SZ" in codes

    def test_passed_stock_has_all_scorecard_dimensions(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        stock = next(s for s in result.output_data["passed"] if s["code"] == "300124.SZ")
        sc = stock["scorecard"]
        for dim in ("relevance", "liquidity", "fundamentals", "valuation"):
            assert dim in sc
            assert "pass" in sc[dim]
            assert "value" in sc[dim]


class TestScorecardReject:
    def test_st_stock_rejected(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        rejected = result.output_data["rejected"]
        codes = [s["code"] for s in rejected]
        assert "688001.SZ" in codes

    def test_concept_low_relevance_rejected(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        rejected = result.output_data["rejected"]
        codes = [s["code"] for s in rejected]
        assert "000001.SZ" in codes

    def test_rejected_has_reason(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        rejected = result.output_data["rejected"]
        for r in rejected:
            assert "reason" in r
            assert len(r["reason"]) > 0


class TestScorecardOutput:
    def test_output_has_theme_and_date(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        assert result.output_data["theme"] == "机器人"
        assert "pool_date" in result.output_data

    def test_passed_count(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        assert len(result.output_data["passed"]) == 1

    def test_rejected_count(self, sample_candidates):
        result = _run_scorecard(sample_candidates)
        assert result.returncode == 0
        assert len(result.output_data["rejected"]) == 2


class TestScorecardCustomThresholds:
    def test_custom_liquidity_threshold(self, sample_candidates):
        # Set very high threshold so even the liquid stock fails
        result = _run_scorecard(sample_candidates, ["--min-liquidity", "999999999"])
        assert result.returncode == 0
        assert len(result.output_data["passed"]) == 0

    def test_custom_pe_percentile_cap(self, sample_candidates):
        # Set very low cap so most stocks fail valuation
        result = _run_scorecard(sample_candidates, ["--pe-percentile-cap", "10"])
        assert result.returncode == 0
        # Only concept with pe_percentile=30 fails; pure_play with 62 already fails
        rejected_codes = [s["code"] for s in result.output_data["rejected"]]
        assert "300124.SZ" in rejected_codes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stock_pool_scorecard.py -v`
Expected: FAIL — `ModuleNotFoundError` or `FileNotFoundError` (script does not exist yet)

- [ ] **Step 3: Write scorecard.py implementation**

Create `plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py`:

```python
"""Stock pool scorecard filter — pure logic, no I/O except CLI argparse/json file read/write."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


def check_relevance(candidate: dict) -> tuple[bool, str]:
    revenue_pct = candidate.get("revenue_share_pct", 0)
    stock_type = candidate.get("type", "")
    if stock_type == "pure_play" or revenue_pct >= 20:
        return True, f"{revenue_pct}%"
    return False, f"{revenue_pct}% (需≥20%或pure_play)"


def check_liquidity(candidate: dict, min_liquidity: float) -> tuple[bool, str]:
    turnover = candidate.get("avg_turnover_20d", 0)
    wan = turnover / 10000
    yi = turnover / 100000000
    display = f"{yi:.1f}亿" if yi >= 1 else f"{wan:.0f}万"
    if turnover >= min_liquidity:
        return True, display
    min_display = f"{min_liquidity / 100000000:.1f}亿" if min_liquidity >= 100000000 else f"{min_liquidity / 10000:.0f}万"
    return False, f"{display} (需≥{min_display})"


def check_fundamentals(candidate: dict) -> tuple[bool, str]:
    if candidate.get("is_st", False):
        return False, "ST/退市风险"
    return True, "正常"


def check_valuation(candidate: dict, pe_percentile_cap: int) -> tuple[bool, str]:
    pe = candidate.get("pe_ttm")
    pct = candidate.get("pe_percentile", 0)
    if pe is None:
        return True, "PE无数据(跳过)"
    display = f"PE {pe:.1f}x (分位 {pct}%)"
    if pct > pe_percentile_cap:
        return False, f"{display} (分位>{pe_percentile_cap}%)"
    return True, display


def score_stock(candidate: dict, min_liquidity: float, pe_percentile_cap: int) -> dict:
    checks = {
        "relevance": check_relevance(candidate),
        "liquidity": check_liquidity(candidate, min_liquidity),
        "fundamentals": check_fundamentals(candidate),
        "valuation": check_valuation(candidate, pe_percentile_cap),
    }
    scorecard = {}
    failed_reasons = []
    for dim, (passed, value) in checks.items():
        scorecard[dim] = {"value": value, "pass": passed}
        if not passed:
            failed_reasons.append(f"{dim}: {value}")

    result = {
        "code": candidate["code"],
        "name": candidate["name"],
        "type": candidate.get("type", ""),
        "scorecard": scorecard,
    }

    if failed_reasons:
        result["reason"] = "; ".join(failed_reasons)
    return result


def run_scorecard(input_path: str, output_path: str, min_liquidity: float, pe_percentile_cap: int) -> None:
    with open(input_path) as f:
        data = json.load(f)

    passed = []
    rejected = []

    for candidate in data.get("candidates", []):
        result = score_stock(candidate, min_liquidity, pe_percentile_cap)
        if "reason" in result:
            rejected.append({
                "code": result["code"],
                "name": result["name"],
                "reason": result["reason"],
            })
        else:
            passed.append(result)

    output = {
        "theme": data.get("theme", ""),
        "pool_date": date.today().isoformat(),
        "passed": passed,
        "rejected": rejected,
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Stock pool scorecard filter")
    parser.add_argument("--input", required=True, help="Path to candidate JSON file")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument("--min-liquidity", type=float, default=50_000_000, help="Min 20-day avg turnover (CNY)")
    parser.add_argument("--pe-percentile-cap", type=int, default=95, help="Max PE historical percentile")
    args = parser.parse_args()
    run_scorecard(args.input, args.output, args.min_liquidity, args.pe_percentile_cap)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stock_pool_scorecard.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Create test fixture file**

Create `tests/fixtures/scorecard_candidates.json`:

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
    },
    {
      "code": "000001.SZ",
      "name": "平安银行",
      "type": "concept",
      "is_st": false,
      "avg_turnover_20d": 300000000,
      "pe_ttm": 5.2,
      "pe_percentile": 30,
      "revenue_share_pct": 5
    },
    {
      "code": "688001.SZ",
      "name": "ST某股",
      "type": "concept",
      "is_st": true,
      "avg_turnover_20d": 80000000,
      "pe_ttm": 100.0,
      "pe_percentile": 98,
      "revenue_share_pct": 10
    }
  ]
}
```

- [ ] **Step 6: Commit**

```bash
git add plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py tests/test_stock_pool_scorecard.py tests/fixtures/scorecard_candidates.json
git commit -m "feat(stock-pool): add scorecard filter with tests"
```

---

### Task 2: references/value-chain-template.md

**Files:**
- Create: `plugins/vertical-plugins/equity-research/skills/stock-pool/references/value-chain-template.md`

- [ ] **Step 1: Create the template file**

```markdown
---
name: value-chain-template
description: Output format template for Step 1 theme value chain analysis
---

# 价值链分析输出模板

Agent 在 Step 1 结束时按此 JSON 格式输出价值链分析结果。

## JSON Schema

```json
{
  "theme": "主题名称",
  "analysis_date": "YYYY-MM-DD",
  "value_chain": [
    {
      "stage": "产业链环节名称",
      "value_density": "高|中|低",
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

## Type Definitions

| Type | Definition |
|------|-----------|
| `pure_play` | 主题相关营收占比 > 30%，或被市场公认为该主题核心标的 |
| `concept` | 概念板块成员但主营占比 < 20%，弹性大但确定性低 |
| `second_order` | 供应链受益，不直接面对终端市场 |

## Example: 机器人

```json
{
  "theme": "机器人",
  "analysis_date": "2026-05-21",
  "value_chain": [
    {
      "stage": "核心零部件",
      "value_density": "高",
      "barrier": "精密加工技术壁垒高，国产替代空间大",
      "companies": [
        {
          "code": "300124.SZ",
          "name": "汇川技术",
          "type": "pure_play",
          "market_position": "伺服龙头，国内市占率前三",
          "note": "人形机器人关节电机核心供应商"
        },
        {
          "code": "002472.SZ",
          "name": "双环传动",
          "type": "second_order",
          "market_position": "RV减速器国内领先",
          "note": "工业机器人+人形机器人双线布局"
        }
      ]
    },
    {
      "stage": "整机制造",
      "value_density": "中",
      "barrier": "系统集成能力要求高，但竞争加剧",
      "companies": [
        {
          "code": "300015.SZ",
          "name": "埃斯顿",
          "type": "pure_play",
          "market_position": "国产工业机器人龙头",
          "note": "全产业链布局，伺服+本体+集成"
        }
      ]
    }
  ],
  "market_landscape": {
    "total_addressable_market": "约 800 亿",
    "growth_rate": "CAGR 25%+",
    "key_players": ["汇川技术", "埃斯顿", "绿的谐波"]
  }
}
```
```

- [ ] **Step 2: Commit**

```bash
git add plugins/vertical-plugins/equity-research/skills/stock-pool/references/value-chain-template.md
git commit -m "feat(stock-pool): add value chain template reference"
```

---

### Task 3: SKILL.md — Workflow Definition

**Files:**
- Create: `plugins/vertical-plugins/equity-research/skills/stock-pool/SKILL.md`

- [ ] **Step 1: Create SKILL.md**

```markdown
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

### 2.1 多渠道标的发现（并行执行）

| Channel | MCP Tool | Description |
|---------|----------|-------------|
| 概念板块成分股 | `akshare.stock_board_concept_cons` | 拉取相关概念板块成员 |
| 财报关键词 | `tushare.income` + `tushare.fina_indicator` | 筛选主营描述含主题关键词的公司 |
| 价值链扩展 | Step 1 输出 | 从已识别的上下游公司扩展 |

**去重** — 合并三个渠道的结果，按 code 去重。

### 2.2 数据预取

对每只候选股票，通过 MCP 工具获取以下数据：
- `akshare.stock_zh_a_spot` — ST 状态、实时行情
- `akshare.stock_zh_a_hist` — 近 20 日成交额（计算日均）
- `tushare.fina_indicator` — PE_TTM、PE 历史分位
- Step 1 标注的 revenue_share_pct

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
| 业务相关性 | 营收占比 ≥ 20% 或 type = pure_play |
| 流动性 | 近 20 日日均成交额 ≥ 5000 万 |
| 基本面 | 非 ST、非退市风险 |
| 估值合理性 | PE 历史分位 ≤ 95% |

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

## Quality Checklist

- [ ] 所有 A 股排除规则已应用（ST、停牌、上市不满 1 年）
- [ ] 每只入池股票有 bull/bear 论点
- [ ] rejected 列表每项有明确原因
- [ ] 每个数据字段标注 MCP 数据源
- [ ] JSON 输出格式与 value-chain-template 一致
- [ ] scorecard.py 通过所有单元测试
```

- [ ] **Step 2: Commit**

```bash
git add plugins/vertical-plugins/equity-research/skills/stock-pool/SKILL.md
git commit -m "feat(stock-pool): add SKILL.md workflow definition"
```

---

### Task 4: Command Entry + Plugin Metadata Update

**Files:**
- Create: `plugins/vertical-plugins/equity-research/commands/stock-pool.md`
- Modify: `plugins/vertical-plugins/equity-research/.claude-plugin/plugin.json`
- Modify: `plugins/vertical-plugins/equity-research/AGENTS.md`

- [ ] **Step 1: Create command file**

Create `plugins/vertical-plugins/equity-research/commands/stock-pool.md`:

```markdown
---
description: "构建主题股票池：价值链梳理、标的发现、量化初筛"
argument-hint: "[主题名称，如：机器人、AI硬件、低空经济]"
---

Load the `stock-pool` skill and build a themed stock pool for the specified theme.

If no theme specified, ask the user which theme to analyze. Examples: 机器人、AI硬件、低空经济、半导体、新能源车.

The skill will guide through value chain analysis, stock discovery, and scorecard screening.
```

- [ ] **Step 2: Update plugin.json**

The current file at `plugins/vertical-plugins/equity-research/.claude-plugin/plugin.json` contains:

```json
{
  "name": "equity-research",
  "version": "0.1.0",
  "description": "Equity research: financial analysis for A-share stocks",
  "skills": ["financial-analysis"],
  "mcp_dependencies": ["akshare", "tushare", "internal-store"]
}
```

Change `"skills": ["financial-analysis"]` to `"skills": ["financial-analysis", "stock-pool"]`.

- [ ] **Step 3: Update AGENTS.md**

The current skills table in `plugins/vertical-plugins/equity-research/AGENTS.md` contains:

```markdown
## Skills

| Skill | Purpose |
|-------|---------|
| `financial-analysis` | Deep financial analysis and valuation |
```

Add a row:

```markdown
| `stock-pool` | 主题股票池构建：价值链分析、标的发现、量化初筛 |
```

Also update the structure diagram to include stock-pool under skills/.

- [ ] **Step 4: Commit**

```bash
git add plugins/vertical-plugins/equity-research/commands/stock-pool.md plugins/vertical-plugins/equity-research/.claude-plugin/plugin.json plugins/vertical-plugins/equity-research/AGENTS.md
git commit -m "feat(stock-pool): add command entry, update plugin metadata"
```

---

### Task 5: Integration Verification

**Files:**
- No new files

- [ ] **Step 1: Run all scorecard tests**

Run: `uv run pytest tests/test_stock_pool_scorecard.py -v`
Expected: All 10 tests PASS

- [ ] **Step 2: Test scorecard CLI with fixture file**

Run: `uv run python plugins/vertical-plugins/equity-research/skills/stock-pool/scripts/scorecard.py --input tests/fixtures/scorecard_candidates.json --output ./out/test_scorecard.json`
Expected: Exit code 0, file `./out/test_scorecard.json` created with passed/rejected results

- [ ] **Step 3: Verify plugin structure**

Run: `uv run python scripts/validate.py`
Expected: No errors related to stock-pool skill

- [ ] **Step 4: Run linter**

Run: `uv run ruff check plugins/vertical-plugins/equity-research/skills/stock-pool/ tests/test_stock_pool_scorecard.py`
Expected: No errors

- [ ] **Step 5: Clean up test output**

Run: `rm -f ./out/test_scorecard.json`

- [ ] **Step 6: Final commit (if any lint fixes needed)**

```bash
git add -A
git commit -m "chore: stock-pool integration verification"
```
```
