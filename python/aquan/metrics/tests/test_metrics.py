"""Tests for the metric semantic layer (sub-project ❸)."""

import pytest

from aquan.metrics import (
    compile_query,
    describe_metric,
    list_dimensions,
    list_metrics,
)


def test_list_metrics_returns_at_least_10():
    """spec 要求至少 10 个核心指标。"""
    metrics = list_metrics()
    assert len(metrics) >= 10, f"only {len(metrics)} metrics defined, need >= 10"


def test_list_metrics_by_category():
    factor_metrics = list_metrics(category="factor_evaluation")
    strategy_metrics = list_metrics(category="strategy_evaluation")
    assert len(factor_metrics) >= 4
    assert len(strategy_metrics) >= 4
    # 两类不重叠
    factor_names = {m["name"] for m in factor_metrics}
    strategy_names = {m["name"] for m in strategy_metrics}
    assert not (factor_names & strategy_names)


def test_each_metric_has_required_fields():
    """每个指标必须有 name/formula/description/unit/category/source_table/dimensions。"""
    required = {"name", "formula", "description", "unit", "category", "source_table", "dimensions"}
    for m in list_metrics():
        missing = required - set(m.keys())
        assert not missing, f"metric {m.get('name')} missing: {missing}"


def test_describe_metric_found():
    spec = describe_metric("icir")
    assert spec["name"] == "icir"
    assert "avg(ic)" in spec["formula"]


def test_describe_metric_not_found():
    with pytest.raises(KeyError, match="Unknown metric"):
        describe_metric("does_not_exist")


def test_compile_query_no_dimensions():
    """无 dimensions：返回标量 SQL。"""
    sql = compile_query("icir")
    assert "SELECT avg(ic) / nullif(stddev(ic), 0) AS icir" in sql
    assert "FROM ods_factor_experiments" in sql
    assert "GROUP BY" not in sql


def test_compile_query_with_dimensions():
    sql = compile_query("icir", dimensions=["universe", "factor_name"])
    assert "SELECT universe, name, avg(ic)" in sql  # factor_name → name 列映射
    assert "GROUP BY universe, name" in sql


def test_compile_query_with_filters():
    sql = compile_query(
        "icir",
        dimensions=["factor_name"],
        filters={"universe": "csi300", "factor_name": "momentum_20d"},
    )
    assert "WHERE universe = 'csi300' AND name = 'momentum_20d'" in sql
    assert "GROUP BY name" in sql


def test_compile_query_with_numeric_filter():
    sql = compile_query(
        "sharpe_annualized",
        filters={"strategy_name": "momentum_top2"},
    )
    assert "name = 'momentum_top2'" in sql


def test_compile_query_with_list_filter():
    sql = compile_query(
        "icir",
        filters={"universe": ["csi300", "csi500"]},
    )
    assert "universe IN ('csi300', 'csi500')" in sql


def test_compile_query_limit():
    sql = compile_query("icir", limit=10)
    assert sql.endswith("LIMIT 10")


def test_compile_query_rejects_unknown_dimension():
    with pytest.raises(KeyError, match="not allowed"):
        compile_query("icir", dimensions=["bogus_dim"])


def test_compile_query_rejects_unknown_filter():
    with pytest.raises(KeyError, match="not allowed"):
        compile_query("icir", filters={"bogus_filter": "x"})


def test_list_dimensions_returns_dictionary():
    dims = list_dimensions()
    assert len(dims) >= 4
    names = {d["name"] for d in dims}
    assert "universe" in names
    assert "factor_name" in names


def test_factor_and_strategy_metrics_use_correct_tables():
    """因子评价指标来自 factor 表，策略评价指标来自 backtest 表。"""
    for m in list_metrics(category="factor_evaluation"):
        assert m["source_table"] in ("ods_factor_experiments", "dws_factor_daily"), m
    for m in list_metrics(category="strategy_evaluation"):
        assert m["source_table"] in ("ods_backtest_runs", "dwd_equity_daily"), m


def test_metrics_names_are_unique():
    names = [m["name"] for m in list_metrics()]
    assert len(names) == len(set(names)), f"duplicate metric names: {names}"
