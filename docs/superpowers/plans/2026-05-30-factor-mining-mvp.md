---
change: factor-mining-mvp
design-doc: docs/superpowers/specs/2026-05-30-factor-mining-mvp-design.md
base-ref: 2f7239195ab8d036fedeb77d46bc48cc847227f2
---

# Implementation Plan: Factor Mining MVP

## Overview

产业驱动的因子挖掘 + 标的评分系统。在特定产业标的池上自动发现有效量化信号，用于选股排名和持仓评估。

## Tasks

### T1: 新建 `templates.py` — 因子模板定义 + 枚举搜索
- 定义 6 类因子模板（趋势、动量、波动、量价、均值回归、强度）
- 实现 `enumerate_candidates(templates, fields, windows)` 生成所有候选表达式
- 实现 `template_search(candidates, data_arrays, forward_returns)` 评估并排序
- **Commit:** `feat(factor-mining): add factor template search engine`

### T2: 重构 `data_fetcher.py` — 按标的列表获取数据
- 添加 `fetch_pool_data(codes, start_date, end_date)` 函数
- 从 AKShare 获取日频 OHLCV，对齐为 (T, N) ndarray
- 添加同步包装 `fetch_pool_data_sync()`
- **Commit:** `feat(factor-mining): add pool data fetcher for stock lists`

### T3: 重构 `gp_engine.py` — 接口重构 + 种子种群
- `run_evolution()` 显式接受 `data_arrays` + `forward_returns_2d`（替代 kwargs）
- 新增 `seed_individuals` 参数支持种子种群注入
- **Commit:** `refactor(factor-mining): explicit data interface + seed population for GP engine`

### T4: 修改 `fitness.py` — 小样本适配
- `evaluate_expression()` 中 forward return horizon 可配置
- IC 门槛参数化（产业池 0.02 vs 全市场 0.03）
- **Commit:** `refactor(factor-mining): small-sample IC thresholds`

### T5: 修改 `mine_factors.py` — 适配新 pipeline
- metrics 从评估结果真实提取，移除零值占位
- 适配 `run_evolution()` 新接口
- **Commit:** `refactor(factor-mining): real metrics from evaluation results`

### T6: 新建 `run_mining.py` — Pipeline 主入口
- 接收标的池 + 方向参数
- 流程：获取数据 → 模板搜索(Layer 2) → GP微调(Layer 3) → 注册因子
- 输出挖掘结果 JSON
- **Commit:** `feat(factor-mining): end-to-end mining pipeline`

### T7: 新建 `ranker.py` — 标的评分 + 持仓评估
- `rank_stocks(factors, data_arrays)` — 用因子给标的打分排名
- 识别"当前最强"和"信号转强"标的
- `evaluate_portfolio(holdings, factors, data_arrays)` — 持仓诊断
- **Commit:** `feat(factor-mining): stock ranking and portfolio evaluation`

### T8: 新建 `report.py` — 报告生成
- `generate_mining_report()` — 产业选股排名报告（Markdown）
- `generate_portfolio_report()` — 持仓评估报告（Markdown）
- **Commit:** `feat(factor-mining): ranking and portfolio reports`

### T9: 更新命令入口 + SKILL.md
- 修改 `factor.md` 添加 mine/evaluate 子命令
- 重写 `SKILL.md` 为产业驱动模式
- **Commit:** `docs(factor-mining): update commands and skill for industry-driven mode`

### T10: 测试
- 新建 `test_templates.py` — 模板枚举 + 搜索测试
- 新建 `test_run_mining.py` — Pipeline 集成测试（mock 数据）
- 新建 `test_ranker.py` — 评分排名测试
- 确保现有测试不回归
- **Commit:** `test(factor-mining): add tests for templates, pipeline, and ranker`
