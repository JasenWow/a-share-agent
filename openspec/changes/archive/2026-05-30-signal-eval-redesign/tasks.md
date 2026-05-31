---
archived-with: 2026-05-30-signal-eval-redesign
status: final
---
# Tasks: signal-eval-redesign

## T1: metrics.py — 评估指标模块 ✅
- [x] `compute_backtest_metrics(equity, benchmark)` → 年化/夏普/回撤/胜率/IR 等
- [x] `compute_factor_metrics(ic_series, n_stocks)` → IC/ICIR/t-stat/显著性

## T2: backtest.py — 回测引擎 ✅
- [x] `BacktestConfig` dataclass (top_n, rebalance_days, commission, slippage)
- [x] `BacktestResult` dataclass (equity_curve, benchmark_curve, trades, metrics)
- [x] `run_backtest()` — 调仓: 因子排名→选 top-N→等权建仓→扣手续费→更新净值
- [x] 方向感知 zscore (负 IC → sign=-1) + 量因子限权 30%
- [x] 基准: 等权持有全部标的

## T3: fitness.py — 显著性过滤 ✅
- [x] 新增 `is_significant(ic_series, min_periods)` 函数
- [x] `evaluate_candidate` 返回增加 t_stat, is_significant 字段
- [x] `template_search` 用显著性过滤替换 `abs(ic) >= min_ic`

## T4: templates.py — 价格动量基线模板 ✅
- [x] 新增 `price_momentum_raw` 类别（不带 Rank 的原始涨幅/位置）
- [x] 窗口覆盖 [5, 10, 20, 60]

## T5: ranker.py — 方向翻转 + 量因子限权 ✅
- [x] zscore 按因子 IC 符号翻转（负 IC → sign=-1）
- [x] 纯 volume 因子权重上限（≤ 非量权重 30%）
- [x] Signal 分类改用分位数阈值替代硬编码 0.5

## T6: run_mining.py — Train/Test Split + 回测集成 ✅
- [x] 按 ratio (默认 0.3) 时间切分 data_arrays
- [x] template_search 只在 train 上运行
- [x] OOS validation: test set IC 同号过滤
- [x] 集成 backtest.py 在 test period 运行回测
- [x] CLI 参数 `--test-ratio`, `--top-n`, `--rebalance`, `--commission`
- [x] JSON 序列化 ndarray→list

## T7: report.py — 回测报告 ✅
- [x] 因子表增加 train/test IC、t-stat、显著性标注
- [x] 回测绩效区块（年化/夏普/回撤 vs 基准）
- [x] ASCII 净值曲线
- [x] 标的排名

## T8: 端到端验证 ✅
- [x] 机器人概念 28 只跑完整 pipeline
- [x] 33/33 测试通过
- [x] 回测诚实反映：ann=-19.4%, sharpe=-0.59, max_dd=-26.4%
- [x] 3/10 因子通过 OOS 验证（全为量因子）
