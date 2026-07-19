# 指标语义层（Metric Semantic Layer）

子项目 ❸ — 统一量化指标定义，避免"同名异义"。

## 设计

**轻量 YAML catalog + Python 编译器**，不引入新服务。

| 备选 | 不选的理由 |
|---|---|
| dbt Semantic Layer | 需 dbt Cloud 付费；MetricFlow 对 DuckDB 兼容差 |
| Cube.dev | 需独立部署，与"单仓库最小化服务"原则冲突 |

## 指标清单（10 个）

**因子评价（5 个）**：`ic_1d`, `ic_20d`, `icir`, `turnover_monthly`, `ir_rank`
**策略/回测评价（5 个）**：`sharpe_annualized`, `max_drawdown`, `annual_return`, `win_rate`, `calmar_ratio`

每个指标在 `metrics.yml` 定义：`name`, `formula`, `description`, `unit`, `category`, `source_table`, `dimensions`。

## 用法

```python
from metrics import compile_query, list_metrics, describe_metric

# 列出所有指标
for m in list_metrics():
    print(m["name"], m["description"])

# 查询"动量因子在 csi300 的 ICIR"
sql = compile_query(
    metric="icir",
    dimensions=["factor_name"],
    filters={"universe": "csi300", "factor_name": "momentum_20d"},
)
# SELECT name, avg(ic) / nullif(stddev(ic), 0) AS icir
# FROM ods_factor_experiments
# WHERE universe = 'csi300' AND name = 'momentum_20d'
# GROUP BY name

# 在 DuckDB 执行（由 chat-database adapter / CLI 负责）
# conn.execute(sql).fetchall()
```

## 消费方

| 消费方 | 怎么用 |
|---|---|
| chat-database agent (❹) | agent 调 `compile_query()` 生成 SQL，再走 DuckDB adapter 执行 |
| 未来仪表板 (❺) | 直接调 `compile_query()` 或读 YAML 渲染下拉选项 |
| Meta-Agent (❻) | 基于统一口径查询历史实验，做推荐 |

## 扩展指标

1. 在 `metrics.yml` 的 `metrics:` 下加新条目
2. 必填字段：`name`, `formula`, `description`, `unit`, `category`, `source_table`, `dimensions`
3. `formula` 是 DuckDB SQL 片段（会被原样嵌入 SELECT）
4. `dimensions` 是允许 GROUP BY / WHERE 的字段白名单
5. 若维度名与列名不同（如 `factor_name` → 列 `name`），在 `compile_query` 的 `_col()` 加映射

## 测试

```bash
uv run pytest metrics/test_metrics.py -v
# 16 tests
```
