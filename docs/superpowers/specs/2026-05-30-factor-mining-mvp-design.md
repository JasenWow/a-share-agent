---
comet_change: factor-mining-mvp
role: technical-design
canonical_spec: openspec
---

# Factor Mining MVP — 产业驱动的量化选股系统

**Date:** 2026-05-30
**Change:** factor-mining-mvp

---

## 1. 设计目标

构建产业驱动的因子挖掘 + 标的评分系统，服务于两个场景：

1. **产业选股**：对一个产业标的池自动发现有效量化信号，排名推荐
2. **持仓评估**：对用户持仓用产业因子诊断健康度

核心原则：**不是全市场通用因子挖掘，而是在特定产业标的上发现"这个产业里什么信号最有效"。**

---

## 2. 架构设计

### 2.1 整体流程

```
┌──────────────────────────────────────────────────────────────┐
│                      用户交互层                               │
│  /factor mine <产业主题>         /factor evaluate <持仓列表>  │
└──────────────┬──────────────────────────┬────────────────────┘
               ↓                          ↓
┌──────────────────────┐    ┌──────────────────────────┐
│  stock-pool (已有)    │    │  持仓列表 (用户输入)       │
│  价值链 → 标的池       │    │  [300124, 002475, ...]   │
└──────────┬───────────┘    └──────────┬───────────────┘
           ↓                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    数据获取层                                  │
│  AKShare/Tushare MCP → 日频价量 → (T, N) ndarray 对齐        │
└──────────────────────────┬───────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│                   因子挖掘层 (三层)                            │
│                                                              │
│  Layer 1: 方向约束 — 预设方向映射搜索参数                      │
│  Layer 2: 模板搜索 — 枚举模板×字段×窗口，评估 IC/ICIR         │
│  Layer 3: GP 微调  — Top-N 作种子，DEAP 进化优化              │
│                                                              │
│  评估引擎: evaluator.py (向量化) + fitness.py (IC/ICIR)       │
└──────────────────────────┬───────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│                   输出层                                      │
│  因子注册 → factor_library (internal-store MCP)              │
│  标的排名 → Markdown 报告                                     │
│  持仓诊断 → 评估报告                                         │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 模板搜索 (Layer 2)

**模板 = 带空格的因子公式，系统自动枚举填空。**

```python
TEMPLATES = {
    "trend": [
        "Rank($X / Ts_Mean($X, {W}))",                  # 价格/均线位置
        "Rank(Delta($X, {W}) / Ts_Std($X, {W}))",      # 标准化动量
    ],
    "momentum": [
        "Rank(Delta($X, {W}))",                          # 绝对动量
        "Rank(Ts_Sum(Sign(Delta($X, 1)), {W}))",        # 上涨天数占比
    ],
    "volatility": [
        "Rank(-1 * Ts_Std($X, {W}))",                   # 低波动
        "Rank(Ts_Mean($X, {W1}) / Ts_Std($X, {W2}))",   # 波动调整
    ],
    "volume_price": [
        "Ts_Corr($X, $Y, {W})",                          # 量价相关性
        "Rank($X / Ts_Sum($Y, {W}))",                    # 量价比
    ],
    "mean_reversion": [
        "Rank(($X - Ts_Mean($X, {W})) / Ts_Std($X, {W}))",  # Z-score
        "Rank(-1 * Abs($X / Ts_Mean($X, {W}) - 1))",        # 偏离度反转
    ],
}
```

搜索空间 = 模板 × 字段($close, $volume, ...) × 窗口(5, 10, 20, 60)。
例如 12 个模板 × 4 字段 × 4 窗口 = 192 个候选，秒级完成。

### 2.3 GP 微调 (Layer 3)

以 Layer 2 Top-N 结果作为种子种群（非随机初始化）：
- 在种子基础上交叉、变异
- 搜索空间小，收敛快
- 子代可追溯父模板

需要重构 `gp_engine.py`：
- `run_evolution()` 显式接受 `data_arrays` + `forward_returns_2d`
- 新增 `seed_individuals` 参数支持种子种群注入

### 2.4 小样本适配

产业标的池通常 20-80 只股票：
- IC 通过门槛降低至 0.02（vs 全市场 0.03）
- 强调 ICIR > IC（稳定性优先）
- 时间窗口至少 1 年（~250 交易日 × 20-80 只 = 足够统计量）
- forward return horizon 默认 5 日

---

## 3. 评分排名

### 3.1 标的评分

用挖出的因子给标的打分：

```python
for each factor in active_factors:
    factor_values = evaluate_expression_vec(factor.expression, data_arrays)
    # 取最新一期的因子值
    latest_values = factor_values[-1]
    # ZScore 标准化
    zscore = (latest_values - mean) / std
    # 加权（用因子 ICIR 作权重）
    scores[i] += factor.icir * zscore
```

排名输出：
- **当前最强**：综合分数最高的
- **信号转强**：近 5 日分数变化最大的（正在启动）

### 3.2 持仓评估

对用户持仓列表：
- 识别所属行业/产业
- 加载该产业有效因子
- 逐只打分 + 额外诊断：
  - 行业集中度（所有持仓是否在同一行业）
  - 因子相关性（持仓之间是否高度同质）
  - 回撤位置（距近期高点多远）

---

## 4. 因子生命周期

```
         注册(active)
            ↓
     定期重算 IC/ICIR
            ↓
   ┌────────┴─────────┐
   ↓                  ↓
持续有效          连续N期低于阈值
(保留 active)      ↓
               淘汰(deprecated)
                   ↓
              下次挖掘时排除该方向
```

通过 internal-store MCP 的 `register_factor` / `list_factors` / `deprecate_factor` 管理。

---

## 5. 数据流详细设计

### 5.1 数据获取

```
输入: 标的代码列表 ["300124.SZ", "002472.SZ", ...]
         ↓
AKShare MCP: stock_zh_a_hist → 每只标的日频 OHLCV
Tushare MCP: daily → 补充复权数据
         ↓
按交易日历对齐 → 缺失日填 NaN
         ↓
输出: data_arrays = {
  "$close": (T, N) ndarray,
  "$open":  (T, N) ndarray,
  "$volume": (T, N) ndarray,
  ...
}
forward_returns: (T, N) ndarray  # close[t+5]/close[t] - 1
```

### 5.2 GP 评估回调

```python
def _evaluate(ind):
    expr_str = individual_to_expression(ind)
    try:
        factor_values = evaluate_expression_vec(expr_str, data_arrays)
        ic_series = compute_ic_series(factor_values, forward_returns)
        turnover = compute_turnover(rank(factor_values))
        fitness = compute_fitness(ic_series, turnover)
    except:
        fitness = -999.0
    return (fitness,)
```

---

## 6. 文件变更清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `factor-mining/scripts/run_mining.py` | 新建 | Pipeline 主入口 |
| `factor-mining/scripts/templates.py` | 新建 | 因子模板 + 枚举搜索 |
| `factor-mining/scripts/ranker.py` | 新建 | 标的评分 + 持仓评估 |
| `factor-mining/scripts/report.py` | 新建 | 报告生成 |
| `factor-mining/scripts/gp_engine.py` | 修改 | 接口重构 + 种子种群 |
| `factor-mining/scripts/fitness.py` | 修改 | 小样本适配 |
| `factor-mining/scripts/mine_factors.py` | 修改 | 适配新 pipeline |
| `factor-mining/scripts/data_fetcher.py` | 修改 | 按标的列表获取 |
| `factor-mining/SKILL.md` | 修改 | 重写为产业驱动模式 |
| `market-data/commands/factor.md` | 修改 | 添加子命令 |
| `factor-mining/test_run_mining.py` | 新建 | Pipeline 测试 |
| `factor-mining/test_ranker.py` | 新建 | 评分测试 |

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 产业标池样本小，IC 不稳定 | 降低门槛 + 强调 ICIR + 长时间窗口 |
| GP 生成的表达式在 evaluator 中语法不兼容 | try/except 降级为极低适应度 |
| 数据获取依赖 MCP 服务可用性 | 支持本地缓存 fallback |
| 因子过拟合 | 样本外验证 + ICIR 稳定性检查 |
