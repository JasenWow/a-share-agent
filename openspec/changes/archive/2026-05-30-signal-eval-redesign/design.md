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
    6. 更新净值
```

关键点：
- **用 train+test 的全部历史评估因子值**（ranking 需要时间序列算 Ts_Mean 等），但**只在 test period 做 backtest**
- 每次调仓日，取因子在当日的截面排名，选 top-N
- 基准 = 等权持有全部标的
- 净值归一化为 1.0 起始

## D2: metrics.py — 评估指标

```python
def compute_backtest_metrics(equity: np.ndarray, benchmark: np.ndarray) -> dict:
    """计算完整评估指标"""
    return {
        "annualized_return": ...,    # 年化收益
        "annualized_volatility": ...,  # 年化波动率
        "sharpe_ratio": ...,         # 夏普比率 (rf=0)
        "max_drawdown": ...,         # 最大回撤
        "max_drawdown_duration": ..., # 最大回撤持续天数
        "calmar_ratio": ...,         # 年化/最大回撤
        "win_rate": ...,             # 日度胜率
        "excess_return": ...,        # 超额收益 (vs benchmark)
        "information_ratio": ...,    # 超额收益/跟踪误差
        "total_trades": ...,         # 总交易次数
        "avg_holding_period": ...,   # 平均持仓天数
    }

def compute_factor_metrics(ic_series: np.ndarray, n_stocks: int) -> dict:
    """因子层面的统计检验"""
    return {
        "mean_ic": ...,
        "ic_std": ...,
        "icir": ...,
        "t_stat": ...,             # t = mean / (std / sqrt(n))
        "is_significant": ...,      # |t| > 2
        "ic_positive_pct": ...,     # IC > 0 的期数占比
        "n_periods": ...,
    }
```

## D3: fitness.py — 显著性过滤

在 `template_search` 中替换 `abs(result["ic"]) >= min_ic`：

```python
def is_significant(ic_series: np.ndarray, min_periods: int = 20) -> bool:
    """双条件: |ICIR| > 2/sqrt(T) 且 |t-stat| > 2"""
    clean = ic_series[~np.isnan(ic_series)]
    if len(clean) < min_periods:
        return False
    mean, std = np.mean(clean), np.std(clean)
    if std < 1e-12:
        return False
    t_stat = mean / (std / np.sqrt(len(clean)))
    return abs(t_stat) > 2.0
```

`evaluate_candidate` 返回增加 `t_stat`、`is_significant` 字段。

## D4: ranker.py — 方向翻转 + 量因子限权

```python
# 方向翻转
sign = 1.0 if factor["ic"] >= 0 else -1.0
composite += weight * sign * zscore

# 量因子限权: 识别纯 volume 因子
is_volume_only = "$volume" in expr and "$close" not in expr
max_vol_weight = 0.3 * total_non_vol_weight  # 量权重 ≤ 非量权重的 30%
if is_volume_only:
    weight = min(weight, max_vol_weight)
```

Signal 分类阈值从硬编码改为分位数：
```python
score_p75 = np.percentile(composite, 75)
momentum_median = np.median(momentum)
```

## D5: templates.py — 价格动量基线

在"动量趋势"方向增加不带 Rank 的模板：

```python
"price_momentum_raw": [
    "($close / Delay($close, {W}) - 1)",           # N日涨幅
    "($close - Ts_Min($close, {W})) / ($close - Ts_Max($close, {W}))",  # 位置
]
```

窗口: [5, 10, 20, 60]

## D6: run_mining.py — Train/Test + 回测集成

Pipeline 改为：

```python
def run_mining_pipeline(...):
    # 1. Fetch data
    # 2. Train/Test split
    split_idx = int(T * 0.7)
    
    # 3. Template search (train only)
    # 4. GP refinement (train only, optional)
    
    # 5. Validation: filter by test-set IC
    for factor in discovered_factors:
        test_ic = compute_ic_on_test(factor, test_arrays)
        if sign(test_ic) != sign(factor["train_ic"]):
            mark_deprecated(factor)
    
    # 6. Ranking (all data, latest date)
    # 7. Backtest (test period only)
    bt_result = run_backtest(factors, data_arrays, test_start=split_idx)
    
    # 8. Generate report with backtest
```

CLI 新增参数：
- `--test-ratio 0.3` — 测试集比例
- `--top-n 5` — 回测持仓数
- `--rebalance 5` — 调仓频率
- `--commission 0.003` — 手续费率

## D7: report.py — 回测报告

报告增加：
1. **因子统计表**：train IC / test IC / t-stat / 显著性 / 因子类型
2. **回测绩效**：年化、夏普、回撤、胜率
3. **净值曲线**（ASCII chart）
4. **标的排名 + 实际近期涨跌幅**
5. **与基线对比**：等权 / 简单动量

## Data Flow (end-to-end)

```
Input: --concept 机器人 --start-date 2024-01-01

Step 1: fetch 28 stocks, 482 days OHLCV
Step 2: split train[0:337] / test[337:482]

Step 3: template_search (train)
  420 candidates → 40 significant → sorted by fitness

Step 4: validation (test)
  40 factors → compute test IC → 15 survive (IC same sign)

Step 5: ranking (all data, latest row)
  15 factors → direction-aware zscore → composite score
  → stock rank list

Step 6: backtest (test period)
  config: top-5, weekly rebalance, 0.3% commission
  → equity curve, trades, metrics

Step 7: baselines
  baseline 1: equal-weight all 28 stocks
  baseline 2: simple 20d momentum strategy

Step 8: report
  factors table with train/test IC
  backtest metrics vs baselines
  stock ranking with actual price change
  ASCII equity curve
```
