# Comet Design Handoff

- Change: factor-mining-mvp
- Phase: design
- Mode: compact
- Context hash: e9526f9c7fe45244c58578271430335f93dc35b1482f4145d0b7105776c4e713

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/factor-mining-mvp/proposal.md

- Source: openspec/changes/factor-mining-mvp/proposal.md
- Lines: 1-43
- SHA256: d2f1e3fa083a68d329d40da4666bf67234d5782748a982500b08f72f83c6b58a

```md
# Proposal: Factor Mining MVP

## Problem

项目需要一个**产业驱动的量化选股能力**：在一个快速爆发的产业集群标的上，自动发现"什么量化信号最能预测超额收益"，并用它给标的排名、给持仓体检。

现有的 stock-pool 技能已覆盖"价值链分析 → 标的发现 → 基础筛选"，但缺少精细化量化评估：
- scorecard 只看 4 个粗粒度维度（相关性、流动性、ST、估值分位），无法区分池内好坏
- 没有自进化的因子发现机制——评分维度和权重依赖人工硬编码
- 没有持仓评估能力

## Goals

构建一个**产业标的因子挖掘 + 评分**系统：

1. **产业因子挖掘**：在特定产业标的池的历史数据上，自动搜索最有效的量化信号（模板搜索 + GP 微调）
2. **标的排名**：用挖出的因子给池内股票打分，识别"近期最强"和"信号正在转强（未来可能表现好）"的标的
3. **持仓评估**：对用户持仓用同样因子打分，诊断健康度、给出风险提示
4. **自进化**：因子持续跟踪表现，失效淘汰，定期重新挖掘

## Scope

### In Scope (MVP)
- 产业标的池的因子挖掘 pipeline（模板搜索 + GP 微调）
- 标的评分排名（基于挖出的因子）
- 持仓评估报告
- 因子生命周期管理（注册、评估、淘汰）
- 价量数据源（AKShare + Tushare，MVP 不扩展到基本面数据）

### Out of Scope (MVP)
- LLM 自动假设翻译（MVP 用户选择预设方向）
- 基本面/另类数据因子（财务、产业链、北向资金等后续迭代）
- 产业间因子泛化验证
- 分布式并行挖掘
- Web UI / 可视化面板

## Success Criteria

1. 用户能对一个产业标的池运行因子挖掘，获得有效的排名信号
2. 挖出的因子在该标池上有统计学意义（IC/ICIR 达标）
3. 持仓评估能给出有意义的诊断结果
4. 因子可注册到 factor_library，支持后续查询和淘汰
5. 整个流程可通过命令行触发
```

## openspec/changes/factor-mining-mvp/design.md

- Source: openspec/changes/factor-mining-mvp/design.md
- Lines: 1-155
- SHA256: ec7f5aeba4eff64e721724538bd9af68cbbcd2521b09ae94a97ba50f23d51b0c

[TRUNCATED]

```md
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
```

Full source: openspec/changes/factor-mining-mvp/design.md

## openspec/changes/factor-mining-mvp/tasks.md

- Source: openspec/changes/factor-mining-mvp/tasks.md
- Lines: 1-28
- SHA256: 176ff1b6dfba92d855f93cf40d376ec30907512642167a32f60a3af651fa539c

```md
# Tasks: Factor Mining MVP

## Phase 1: 基础设施 — 数据获取 + 模板搜索

- [ ] T1: 重构 `data_fetcher.py` — 添加 `fetch_pool_data(codes, start_date, end_date)` 函数，按标的列表从 AKShare/Tushare 获取日频价量，输出对齐的 (T, N) ndarray
- [ ] T2: 新建 `templates.py` — 定义因子模板集合（趋势、动量、波动、量价、均值回归、强度），实现模板枚举搜索（模板 × 字段 × 窗口 → 候选表达式列表）
- [ ] T3: 重构 `gp_engine.py` — `run_evolution()` 显式接受 `data_arrays` + `forward_returns_2d`，支持 `seed_individuals` 种子种群参数

## Phase 2: Pipeline 主入口

- [ ] T4: 新建 `run_mining.py` — 产业因子挖掘 pipeline：接收标的池 + 方向 → 获取数据 → 模板搜索(Layer 2) → GP微调(Layer 3) → 注册因子
- [ ] T5: 修复 `mine_factors.py` — metrics 从评估结果真实提取，移除零值占位；适配新的 pipeline 流程

## Phase 3: 评分 + 报告

- [ ] T6: 新建 `ranker.py` — 标的评分排名：用因子给标的打分，区分"当前最强"和"信号转强"；持仓评估：逐只打分 + 集中度/相关性诊断
- [ ] T7: 新建 `report.py` — 生成 Markdown 报告：产业选股排名报告、持仓评估报告

## Phase 4: 命令入口 + 技能更新

- [ ] T8: 更新 `factor.md` 命令 — 添加 `mine`（产业因子挖掘）和 `evaluate`（持仓评估）子命令
- [ ] T9: 更新 `SKILL.md` — 重写为产业驱动模式，更新输入/输出/工作流说明

## Phase 5: 测试

- [ ] T10: 新建 `test_run_mining.py` — Pipeline 集成测试（mock 数据）
- [ ] T11: 新建 `test_ranker.py` — 评分排名 + 持仓评估测试
- [ ] T12: 运行全部现有测试，确保不回归
```

