# Design: Factor Mining MVP

## 核心理念

**产业驱动、数据验证、自进化。**

不是全市场通用因子挖掘，而是在特定产业标的池上发现"这个产业里什么信号最有效"。

## 两个核心场景

### 场景 A：产业选股

```
用户: "AI 眼镜最近很火，帮我看看有哪些值得关注"
         ↓
stock-pool 拉出 AI 眼镜产业链标的（已有能力）
         ↓
对该标的池历史数据做因子挖掘
  → 模板搜索 + GP 微调
  → 找到对该产业最有效的量化信号
         ↓
用挖出的因子给池内股票打分排名
  → 近期表现好的 = 因子分数高的
  → 未来可能表现好的 = 因子信号正在转强的
         ↓
输出排名报告
```

### 场景 B：持仓评估

```
用户: "帮我看看我的持仓" → 输入持仓列表
         ↓
识别持仓所属产业/行业
         ↓
加载该产业当前有效因子
         ↓
逐只打分 + 整体诊断
  → 哪些健康、哪些转弱
  → 集中度、相关性风险
         ↓
输出持仓评估报告
```

## 因子挖掘机制：混合三层

```
Layer 1: 方向约束
  用户选择产业方向 → 系统映射到搜索参数（字段、算子、窗口范围）
  MVP: 预设方向（低波动、动量、量价、均值回归、综合），自动应用到标的池

Layer 2: 模板搜索（确定性枚举）
  预定义因子模板 × 字段组合 × 窗口参数 → 网格搜索
  每个候选在该标的池上评估 IC/ICIR → 排序取 Top-N

Layer 3: GP 微调（进化搜索）
  以 Layer 2 的 Top-N 作为种子种群
  GP 在种子基础上交叉/变异，进一步优化
  输出最终因子集合
```

### 模板示例

```
趋势类:   Rank($X / Ts_Mean($X, {W}))
动量类:   Rank(Delta($X, {W}))
波动类:   Rank(-1 * Ts_Std($X, {W}))
量价类:   Ts_Corr($X, $Y, {W})
回归类:   Rank(($X - Ts_Mean($X, {W})) / Ts_Std($X, {W}))
强度类:   Rank(Ts_Sum(Sign(Delta($X, 1)), {W}))
```

### 关键区别：产业池 vs 全市场

| 维度 | 全市场因子挖掘 | 产业池因子挖掘 |
|------|--------------|--------------|
| 股票范围 | 沪深300/500 | stock-pool 产出的产业标的（可能 20-80 只） |
| 数据获取 | Qlib 统一 | AKShare/Tushare 按标的拉取 |
| 因子适用性 | 通用 | 对该产业可能特别有效 |
| 样本量 | 大（300+） | 小（20-80） |
| 统计显著性 | 容易达标 | 需要更长的回看期、更稳健的评估 |

### 小样本问题的处理

产业标的池可能只有 20-50 只股票，IC 计算不够稳定：
- 增加时间维度：用更长的时间窗口（至少 1 年日频 IC 序列）
- 降低通过门槛：产业因子 IC > 0.02 即可（而非全市场的 0.03）
- 强调 ICIR > 单次 IC（稳定性比绝对值重要）

## 因子生命周期

```
挖掘 → 注册(active) → 持续评估 → 淘汰(deprecated) / 保留
                ↑                         |
                └── 定期重新挖掘 ──────────┘
```

- 每个因子注册时记录：产业、挖掘日期、IC/ICIR、表达式
- 后台可定期重算因子 IC，连续 N 期低于阈值 → 标记 deprecated
- 下次挖掘时自动排除已淘汰的因子方向

## 数据流

```
AKShare/Tushare MCP
  → 获取标的池内每只股票的日频价量数据
  → 对齐为 (T, N) ndarray（T=交易日, N=标的数）
  → 计算前向收益 forward_returns
         ↓
模板搜索 + GP 微调
  → 对每个候选因子表达式：
    evaluator.evaluate_expression_vec(expr, data_arrays) → factor_values (T,N)
    fitness.compute_ic_series(factor_values, forward_returns) → ic_series
    fitness.compute_fitness(ic_series, turnover) → fitness_score
         ↓
Top-K 因子注册到 factor_library（internal-store MCP）
         ↓
用有效因子给当前标的位置打分 → 排名报告
```

## 与现有系统的集成

```
stock-pool (已有)          factor-mining (本次 MVP)
─────────────────          ─────────────────────────
Step 1: 价值链分析          
Step 2: 标的发现            
Step 3: scorecard 粗筛     
                           Step 4: 因子挖掘（新增）
                             - 在标的池上搜索有效信号
                           Step 5: 因子排名（新增）
                             - 用因子给标的打分
                           Step 6: 报告输出（新增）
                             - 排名 + 因子解读
```

持仓评估是独立入口，复用同样的因子打分逻辑。

## 文件变更

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `factor-mining/scripts/run_mining.py` | **新建** | 因子挖掘 pipeline 主入口：数据获取 → 模板搜索 → GP 微调 → 注册 |
| `factor-mining/scripts/templates.py` | **新建** | 因子模板定义 + 枚举搜索逻辑 |
| `factor-mining/scripts/ranker.py` | **新建** | 标的评分排名 + 持仓评估 |
| `factor-mining/scripts/report.py` | **新建** | 排名报告 + 持仓评估报告生成 |
| `factor-mining/scripts/gp_engine.py` | 修改 | 接受种子种群参数，明确 data_arrays 接口 |
| `factor-mining/scripts/fitness.py` | 修改 | 小样本友好的 IC 计算 |
| `factor-mining/scripts/mine_factors.py` | 修改 | 适配新 pipeline，metrics 真实化 |
| `factor-mining/scripts/data_fetcher.py` | 修改 | 添加按标的列表获取数据的能力 |
| `factor-mining/SKILL.md` | 修改 | 更新为产业驱动模式 |
| `equity-research/commands/stock-pool.md` | 修改 | 添加因子评分步骤 |
| `market-data/commands/factor.md` | 修改 | 添加 mine + evaluate 子命令 |
| `factor-mining/test_run_mining.py` | **新建** | Pipeline 集成测试 |
| `factor-mining/test_ranker.py` | **新建** | 评分排名测试 |
