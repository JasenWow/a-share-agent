# dbt 建模（DWD/DWS/ADS）

基于 [dbt-duckdb](https://github.com/duckdb/dbt-duckdb) 在 ODS 之上建分层模型，让数据可分析。
spec：`docs/superpowers/specs/2026-07-19-dbt-modeling-design.md`
路线图：`docs/superpowers/specs/2026-07-19-data-loop-roadmap-design.md`（子项目 ❶，里程碑 M1）

## 快速开始

```bash
cd dbt
# 1. 配置 profiles.yml（首次）
cat > profiles.yml <<EOF
a_share_analytics:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ../data/warehouse/meta.db
      threads: 4
      extensions: [parquet]
EOF

# 2. 装种子 → 建模型 → 测试 → 文档（一站式）
uv run dbt seed --profiles-dir .
uv run dbt run --profiles-dir .
uv run dbt test --profiles-dir .
uv run dbt docs generate --profiles-dir .

# 3. 可视化文档
uv run dbt docs serve --profiles-dir .  # http://localhost:8080
```

## 分层结构

| 层 | 表 | 内容 |
|---|---|---|
| **staging**（view） | `stg_equity_daily` / `stg_financial_income` | 类型标准化、null 处理 |
| **DWD**（table） | `dwd_equity_daily` | 日线 + 派生（日收益/VWAP/涨停/日内动量） |
| | `dwd_financial_quarterly` | 财务宽表 + 派生（营业利润率/净利率，取最新修订） |
| **DWS**（table） | `dws_equity_monthly` | 个股月度 OHLCV + 月收益率 |
| | `dws_factor_daily` | 每日因子值（动量 20d / 波动率 20d / 换手代理） |
| **ADS**（table） | `ads_strategy_returns` | 简单策略净值序列（Top-2 动量等权，demo） |

物化在各 schema 下：`main_dwd.*` / `main_dws.*` / `main_ads.*` / `main_seed.*`

## 种子数据 vs 真实数据

**MVP 阶段**用种子（`seeds/*.csv`）当数据源，让 dbt 立即可验证。

**真实数据切换**：当 `scripts/etl/` 跑过真实 ETL 后，把 `staging/*.sql` 里的 `from {{ ref('seed_xxx') }}` 改为 `from source('ods', 'ods_xxx')`（需在 schema.yml 加 sources 声明）。

## 查询示例

```sql
-- 查最近动量因子值
SELECT trade_date, code, momentum_20d_pct, volatility_20d_pct
FROM main_dws.dws_factor_daily
ORDER BY trade_date DESC, momentum_20d_pct DESC LIMIT 10;

-- 查策略选股记录
SELECT * FROM main_ads.ads_strategy_returns ORDER BY year_month, momentum_rank;

-- 查财务派生指标
SELECT code, period, revenue, oper_margin_pct, net_margin_pct
FROM main_dwd.dwd_financial_quarterly ORDER BY code, period;
```

## 添加新 model

1. 在对应层目录建 `.sql`（dwd/dws/ads）
2. 用 `{{ ref('上层表') }}` 引用依赖
3. 在 `models/schema.yml` 加 model 声明 + tests
4. 跑 `dbt run` + `dbt test` 验证

## 后续扩展（路线图其他子项目）

- **❷ 实验入仓**：新加 `ods_factor_experiments` 等 source，建 `dwd_experiment_runs`
- **❸ 语义层**：在 DWS 之上用 dbt Semantic Layer / Cube.dev 定义 IC/Sharpe
- 切换到真实 ODS source（取消种子依赖）
