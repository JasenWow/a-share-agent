# Comet Design Handoff

- Change: signal-eval-redesign
- Phase: design
- Mode: compact
- Context hash: d55114d9316c4db9fe546d831c31d9ce8f3d61ddfd29828d57ee85551b603129

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/signal-eval-redesign/proposal.md

- Source: openspec/changes/signal-eval-redesign/proposal.md
- Lines: 1-42
- SHA256: 24d067d1116608800fc47fa9b07a62d49e95afa61ba7681b65284cb20e2b1f15

```md
# Proposal: 因子挖掘完整评估体系（含回测）

## Problem

当前 pipeline 挖掘出因子后直接排名出报告，**没有任何验证手段**。用户看到"强势延续"的股票实际在暴跌，系统毫无纠错能力。

具体问题：
1. **排名与实际走势脱节**：成交活跃 ≠ 股价强，负 IC 因子方向没翻转
2. **无统计显著性门槛**：28 只股票上 IC=0.035 纯噪音照样入选
3. **无样本外验证**：全部数据用于因子搜索，过拟合不可避免
4. **无回测**：不知道按因子排名建仓到底能不能赚钱

## Goals

构建 **因子挖掘 → 排名 → 回测 → 评估** 完整闭环：

1. **回测引擎**：按因子排名模拟建仓（多 top-N / 空 bottom-N），定期调仓，输出净值曲线
2. **评估指标体系**：年化收益、夏普比率、最大回撤、超额收益、胜率、换手率
3. **Train/Test 分离**：因子在训练集挖掘，在测试集验证
4. **统计显著性过滤**：ICIR 和 t-stat 双重检验
5. **方向感知排名**：负 IC 因子翻转 zscore，量因子限权
6. **对比基线**：等权基准、简单动量基线

## Scope

### 新增文件
- `backtest.py` — 回测引擎
- `metrics.py` — 评估指标计算

### 修改文件
- `fitness.py` — 增加显著性检验
- `ranker.py` — 方向翻转 + 量因子限权
- `run_mining.py` — train/test split + 回测集成
- `report.py` — 回测结果报告
- `templates.py` — 增加价格动量基线模板

## Non-goals
- 不做复杂的交易成本/滑点模型（MVP 用固定千三手续费）
- 不做杠杆/融资融券
- 不改 GP 引擎
- 不加基本面因子
- 不做 Web 可视化（纯 CLI + Markdown 报告）
```

## openspec/changes/signal-eval-redesign/design.md

- Source: openspec/changes/signal-eval-redesign/design.md
- Lines: 1-246
- SHA256: d565457849c6f579167dc1a019fecbedd9b2f1f4e7f4d5868f4b8d62ef82734c

[TRUNCATED]

```md
# Design: 因子挖掘完整评估体系

## Architecture

```
                    ┌─────────────────┐
                    │   Stock Pool     │
                    │  (28 stocks)     │
                    └────────┬────────┘
                             │ fetch OHLCV (482 days)
                             ▼
                    ┌─────────────────┐
                    │  Train/Test Split │  70/30 by time
                    │  train: 0~337d   │
                    │  test:  337~482d │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐
    │  Factor Mining   │            │  Validation     │
    │  (train set)     │            │  (test set)     │
    │  template_search │            │  IC 同号？      │
    │  + GP refine     │            │  显著性？       │
    └────────┬────────┘            └────────┬────────┘
             │ 过滤: significant + OOS valid  │
             └──────────────┬─────────────────┘
                            ▼
                   ┌─────────────────┐
                   │  Ranking Engine  │  方向感知 + 量因子限权
                   │  (latest data)   │
                   └────────┬────────┘
                            ▼
              ┌─────────────┴──────────────┐
              ▼                             ▼
    ┌─────────────────┐           ┌─────────────────┐
    │  Backtest Engine │           │  Baselines       │
    │  top-N long      │           │  等权基准         │
    │  rebalance weekly│           │  简单动量策略     │
    └────────┬────────┘           └────────┬────────┘
             │                              │
             └──────────────┬───────────────┘
                            ▼
                   ┌─────────────────┐
                   │  Metrics        │  年化/夏普/回撤/胜率
                   │  + Report       │  Markdown 输出
                   └─────────────────┘
```

## D1: backtest.py — 回测引擎

### 核心接口

```python
@dataclass
class BacktestConfig:
    top_n: int = 5           # 做多 top-N
    bottom_n: int = 0        # 做空 bottom-N (A股MVP=0)
    rebalance_days: int = 5  # 调仓频率（交易日）
    commission: float = 0.003  # 单边手续费
    slippage: float = 0.001   # 滑点

@dataclass
class BacktestResult:
    equity_curve: np.ndarray    # (T,) 净值曲线
    benchmark_curve: np.ndarray # (T,) 基准净值
    trades: list[dict]          # 交易记录
    metrics: dict               # 评估指标
    period_returns: np.ndarray  # (T,) 每期收益
```

### 回测逻辑

```
for each rebalance_date in test_set:
    1. 用因子排名所有标的
    2. 选 top-N 作为持仓
    3. 计算与上期持仓的差异 → 交易
    4. 扣手续费
    5. 按等权计算当日组合收益
```

Full source: openspec/changes/signal-eval-redesign/design.md

## openspec/changes/signal-eval-redesign/tasks.md

- Source: openspec/changes/signal-eval-redesign/tasks.md
- Lines: 1-52
- SHA256: 613b04be6e6e0a7ec0f8291556ff5e062ca8586547161a57a122c1250955d269

```md
# Tasks: signal-eval-redesign

## T1: metrics.py — 评估指标模块
- [ ] `compute_backtest_metrics(equity, benchmark)` → 年化/夏普/回撤/胜率/IR 等
- [ ] `compute_factor_metrics(ic_series, n_stocks)` → IC/ICIR/t-stat/显著性
- [ ] 单元测试

## T2: backtest.py — 回测引擎
- [ ] `BacktestConfig` dataclass (top_n, rebalance_days, commission, slippage)
- [ ] `BacktestResult` dataclass (equity_curve, benchmark_curve, trades, metrics)
- [ ] `run_backtest(factors, data_arrays, config, test_start_idx)` 核心逻辑
- [ ] 调仓: 因子排名→选 top-N→等权建仓→扣手续费→更新净值
- [ ] 基准: 等权持有全部标的
- [ ] 单元测试

## T3: fitness.py — 显著性过滤
- [ ] 新增 `is_significant(ic_series, min_periods)` 函数
- [ ] `evaluate_candidate` 返回增加 t_stat, is_significant 字段
- [ ] `template_search` 用显著性过滤替换 `abs(ic) >= min_ic`
- [ ] 更新测试

## T4: templates.py — 价格动量基线模板
- [ ] "动量趋势"方向增加不带 Rank 的原始价格动量模板
- [ ] 窗口覆盖 [5, 10, 20, 60]
- [ ] 更新测试

## T5: ranker.py — 方向翻转 + 量因子限权
- [ ] zscore 按因子 IC 符号翻转（负 IC → sign=-1）
- [ ] 纯 volume 因子权重上限（≤ 非量权重 30%）
- [ ] Signal 分类改用分位数阈值替代硬编码 0.5
- [ ] 更新测试

## T6: run_mining.py — Train/Test Split + 回测集成
- [ ] 按 ratio (默认 0.3) 时间切分 data_arrays
- [ ] template_search 只在 train 上运行
- [ ] 新增 validation 步骤：test set IC 同号过滤
- [ ] 集成 backtest.py 在 test period 运行回测
- [ ] CLI 参数 `--test-ratio`, `--top-n`, `--rebalance`, `--commission`
- [ ] 更新测试

## T7: report.py — 回测报告
- [ ] 因子表增加 train/test IC、t-stat、显著性标注
- [ ] 回测绩效区块（年化/夏普/回撤 vs 基准）
- [ ] ASCII 净值曲线
- [ ] 标的排名附带实际近期涨跌幅
- [ ] 更新测试

## T8: 端到端验证
- [ ] 用机器人概念跑完整 pipeline
- [ ] 验证回测净值曲线为正（或至少理解为何为负）
- [ ] 验证排名与 test period 实际涨跌幅正相关
- [ ] 所有测试通过
```

