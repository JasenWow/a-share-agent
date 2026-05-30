# Tasks: Factor Mining MVP

## Phase 1: 基础设施 — 数据获取 + 模板搜索

- [x] T1: 重构 `data_fetcher.py` — 添加 `fetch_pool_data()` 函数，按标的列表从 AKShare/Tushare 获取日频价量，输出对齐的 (T, N) ndarray
- [x] T2: 新建 `templates.py` — 定义因子模板集合（趋势、动量、波动、量价、均值回归、强度），实现模板枚举搜索（模板 × 字段 × 窗口 → 候选表达式列表）
- [x] T3: 重构 `gp_engine.py` — `run_evolution()` 显式接受 `data_arrays` + `forward_returns_2d`，支持 `seed_individuals` 种子种群参数

## Phase 2: Pipeline 主入口

- [x] T4: 新建 `run_mining.py` — 产业因子挖掘 pipeline：接收标的池 + 方向 → 获取数据 → 模板搜索(Layer 2) → GP微调(Layer 3) → 注册因子
- [x] T5: 修复 `mine_factors.py` — metrics 从评估结果真实提取，移除零值占位；适配新的 pipeline 流程

## Phase 3: 评分 + 报告

- [x] T6: 新建 `ranker.py` — 标的评分排名：用因子给标的打分，区分"当前最强"和"信号转强"；持仓评估：逐只打分 + 集中度/相关性诊断
- [x] T7: 新建 `report.py` — 生成 Markdown 报告：产业选股排名报告、持仓评估报告

## Phase 4: 命令入口 + 技能更新

- [x] T8: 更新 `factor.md` 命令 — 添加 `mine`（产业因子挖掘）和 `evaluate`（持仓评估）子命令
- [x] T9: 更新 `SKILL.md` — 重写为产业驱动模式，更新输入/输出/工作流说明

## Phase 5: 测试

- [x] T10: 新建 `test_templates.py` — 模板枚举 + 搜索测试
- [x] T11: 新建 `test_ranker.py` — 评分排名 + 持仓评估测试
- [x] T12: 运行全部测试（33/33 通过），确保不回归
