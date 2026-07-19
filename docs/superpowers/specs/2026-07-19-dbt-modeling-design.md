# dbt 建模（DWD/DWS/ADS）设计

**日期**: 2026-07-19
**状态**: Approved
**关联**: 路线图 `2026-07-19-data-loop-roadmap-design.md` 子项目 ❶。前置：ODS 地基 `2026-07-18-data-warehouse-foundation-design.md`。

---

## 0. 背景与范围

ODS 层已完成（equity_daily / index_constituents / financial_income），数据是贴源最小标准化的。本期在 ODS 之上建 DWD/DWS/ADS，让数据可分析。

**范围**（路线图 §3 ❶）：
- 装 dbt-duckdb，建 dbt 项目骨架（`a-share-agents/dbt/`）
- DWD 层：明细宽表
- DWS 层：轻度汇总
- ADS 层：应用表
- dbt tests + dbt docs

**不在范围**：实验数据入仓（❷）、语义层（❸）、复权算法等业务转换。

---

## 1. 技术方案

### 1.1 dbt 连接方式（方案 A）

dbt 直接连现有 `data/warehouse/meta.db`（ETL 写入实例）。DWD/DWS/ADS 在同一实例建为 view/table。DWD 通过 `{{ source('ods','ods_equity_daily') }}` 引用 ODS 视图。

理由：DuckDB 嵌入式无需分库；单实例最简单；后续 chat-database adapter 也连同一文件。

### 1.2 表清单（MVP）

| 层 | 表名 | 来源 | 内容 |
|---|---|---|---|
| DWD | `dwd_equity_daily` | `ods_equity_daily` | 标准化日线 + 派生（日收益/vwap/是否涨停） |
| DWD | `dwd_financial_quarterly` | `ods_financial_income` | 财务宽表（利润表展开 + 派生毛利率/净利率） |
| DWS | `dws_equity_monthly` | `dwd_equity_daily` | 月度 OHLCV + 月收益 |
| DWS | `dws_factor_daily` | `dwd_equity_daily` | 每日因子值（动量 20d / 波动率 20d / 换手） |
| ADS | `ads_strategy_returns` | `dws_equity_monthly` | 简单策略净值序列（等权 Top-N 动量） |

> 注：路线图 §3 ❶ 提到的 `dws_industry_monthly` 因缺行业映射数据推迟；本期用 `dws_equity_monthly` + `dws_factor_daily` 替代，覆盖 DWS 价值。

### 1.3 种子数据策略

当前 ODS 是**空占位视图**（init.py 建的，无真实 Parquet 数据，因为没启动 MCP server 跑 ETL）。为了让 dbt 能真正跑通验证，本期提供种子数据：

- 在 `dbt/seeds/` 放 3 个 CSV（mini 版，20-50 行）：`seed_equity_daily.csv`、`seed_financial_income.csv`、`seed_index_constituents.csv`
- 建 dbt model `stg_ods_equity_daily`：在真实数据存在时 `SELECT * FROM source(ods, ...)`；种子模式时从 seed 拷贝到 ODS 表
- 通过 dbt variable `use_seeds` 切换

**简化**：MVP 阶段**直接用 seed 当 ODS 源**（不走 source 引用）。真实 ETL 跑过后再切回 source。这样 dbt run 立即可验证，不被外部依赖阻塞。

---

## 2. dbt 项目结构

```
dbt/
├── dbt_project.yml          # 项目配置
├── profiles.yml             # DuckDB 连接（gitignore）
├── .gitignore               # 忽略 target/ logs/ profiles.yml
├── packages.yml             # dbt-utils 等包（可选，本期不引）
├── models/
│   ├── staging/
│   │   └── stg_equity_daily.sql       # 从 seed/source 标准化
│   │   └── stg_financial_income.sql
│   ├── dwd/
│   │   ├── dwd_equity_daily.sql
│   │   └── dwd_financial_quarterly.sql
│   ├── dws/
│   │   ├── dws_equity_monthly.sql
│   │   └── dws_factor_daily.sql
│   ├── ads/
│   │   └── ads_strategy_returns.sql
│   └── schema.yml           # sources + 模型文档 + tests
├── seeds/
│   ├── seed_equity_daily.csv
│   ├── seed_financial_income.csv
│   └── seed_index_constituents.csv
├── macros/
│   └── (空，本期不用)
└── tests/
    └── (空，generic tests 用 schema.yml)
```

### 2.1 分层 materialization 策略

| 层 | materialized | 理由 |
|---|---|---|
| staging | view | 轻包装，零成本 |
| DWD | table | 派生计算物化，避免重复算 |
| DWS | table | 聚合结果物化 |
| ADS | table | 应用层物化 |

---

## 3. 验收标准

- [ ] `dbt deps` 成功（如有 packages.yml）
- [ ] `dbt seed` 把 3 个 CSV 装入
- [ ] `dbt run` 全 model 成功
- [ ] `dbt test` 全 generic test 通过（非空、唯一、关系完整性）
- [ ] `dbt docs generate` 生成文档
- [ ] 至少 5 个 model：2 DWD + 2 DWS + 1 ADS
- [ ] 能 `SELECT * FROM dws_factor_daily LIMIT 5` 查到真实动量/波动率因子值
- [ ] `scripts/check.py` 通过（新增 dbt 检查可选）
