# Stock Pool Design — 主题股票池策略

Date: 2026-05-18

## Background

当前量化流程缺少"股票池"环节，信号生成器直接在全市场扫描，导致噪音大、计算成本高。需要先定义"在哪些股票里找机会"，再让信号生成器在精选池内工作。

目标主题：**机器人、AI 硬件、AI 应用**。

## Design Principles

1. **轻起步** — 先手动 + Agent 辅助，不搞全自动
2. **借数据** — 用现有 MCP connector（akshare 概念板块、tushare 财报），不新增数据源
3. **可迭代** — Phase 1 只做发现 + 初筛，后续再加 thesis tracking、自动调仓

## Step 1: 主题定义

对每个主题做一次 **价值链梳理**，理解价值在哪里聚集。

### 输入

- 主题名称（如"机器人"）
- 相关概念板块代码（可从 akshare 查询）

### 流程

1. **价值链拆解** — 把主题拆成产业链环节，标注每个环节的价值聚集程度
2. **标的识别** — 列出各环节的关键公司，标注类型：
   - 纯正标的（核心业务就是该主题）
   - 概念股（沾边但营收占比低）
   - 二阶受益（不直接相关但受益于产业链扩张，如机器人主题里的轴承厂商）
3. **市场格局** — top 3 市占率、进入壁垒简评

### 输出格式

```json
{
  "theme": "机器人",
  "value_chain": [
    {
      "stage": "核心零部件",
      "value_density": "高",
      "companies": [
        {"code": "300124.SZ", "name": "汇川技术", "type": "pure_play", "note": "伺服龙头"},
        {"code": "002472.SZ", "name": "双环传动", "type": "second_order", "note": " RV减速器"}
      ]
    }
  ]
}
```

### 频率

启动时做一次，每季度更新。

## Step 2: 股票发现 + 初筛

自动发现候选标的，用 scorecard 决定是否入池。

### 发现渠道（并行执行）

| 渠道 | 数据源 | 说明 |
|------|--------|------|
| 概念板块成分股 | akshare `stock_board_concept_cons` | 直接拉取"机器人""AI硬件"等概念板块成员 |
| 财报关键词 | tushare `income` + 管理层讨论 | 筛选主营业务描述中包含主题关键词的公司 |
| 产业链关联 | Step 1 价值链 | 从已识别的上下游公司扩展 |

### 初筛 Scorecard

每只候选股票过以下维度，全部通过才入池：

| 维度 | Pass 标准 | 数据源 |
|------|-----------|--------|
| 业务相关性 | 相关营收占比 > 20% 或被列入核心概念板块 | tushare 财报 / akshare 概念 |
| 流动性 | 近 20 日日均成交额 > 5000 万元 | akshare 行情 |
| 基本面 | 非 ST、非退市风险警示 | akshare 实时行情 |
| 估值合理性 | PE 不在历史 95%+ 分位（排除极端泡沫） | tushare 指标 |

### 输出格式

```json
{
  "theme": "机器人",
  "pool_date": "2026-05-18",
  "stocks": [
    {
      "code": "300124.SZ",
      "name": "汇川技术",
      "type": "pure_play",
      "scorecard": {
        "relevance": {"value": "35%", "pass": true},
        "liquidity": {"value": "120M", "pass": true},
        "fundamentals": {"value": "正常", "pass": true},
        "valuation": {"value": "PE 45x", "pass": true}
      },
      "bull": "伺服+变频器双龙头，人形机器人关节电机核心供应商",
      "bear": "传统工控业务占比仍高，机器人业务贡献有限"
    }
  ],
  "rejected": [
    {"code": "XXXXXX.SZ", "name": "...", "reason": "流动性不足"}
  ]
}
```

### 频率

每月运行一次，与 Step 1 的季度更新解耦。

## File Structure

```
skills/market-data/
  stock-pool/
    theme_define.py      # Step 1: 价值链梳理 + 标的识别
    stock_discover.py    # Step 2: 多渠道发现 + scorecard 初筛
```

两个文件，各自独立可运行，通过 JSON 文件传递数据。

## MCP Tools Used

- `akshare.stock_board_concept_cons` — 概念板块成分股
- `akshare.stock_zh_a_spot` — 实时行情（流动性、ST 判断）
- `akshare.stock_zh_a_hist` — 历史行情（成交额计算）
- `tushare.income` — 利润表（营收）
- `tushare.fina_indicator` — 财务指标（PE）
- `tushare.daily` — 日线数据

## Phase 2 (Deferred)

以下功能不在本次实现范围：

- Thesis tracking / 催化剂日历
- 自动调仓信号
- 多因子排序打分
- Priced-in 判断
- 价值链变化的自动监控

## Acceptance Criteria

1. 能对给定主题输出价值链分析 JSON
2. 能从概念板块 + 财报渠道发现候选标的
3. 候选标的通过 scorecard 后进入股票池
4. 股票池结果存储到 internal-store
5. 代码符合项目 4 层架构（L1 Skill）
