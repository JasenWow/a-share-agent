# Testing

> Unit, integration, and E2E testing conventions for this project. Read before adding or changing tests.

## Unit Tests

- **Framework**: `pytest` + `pytest-mock`
- **Naming**: `test_*.py` in the same directory as the source file (co-located)
- **Style**: prefer table-driven tests — one `cases` list with subtests via `pytest.param` or a `@pytest.mark.parametrize` loop.
- **Command**: `pytest` (runs all non-integration tests by default)

### Pattern

```python
# mcp-servers/akshare-server/test_server.py
import pytest
from server import df_to_json, stock_zh_a_spot

class TestDfToJson:
    @pytest.mark.parametrize("input_data,expected", [
        ({"a": [1, 2], "b": [3, 4]}, 2),
        ({"a": [float("nan")]}, 1),  # NaN preserved as string "NaN"
    ])
    def test_row_count(self, input_data, expected):
        import pandas as pd
        df = pd.DataFrame(input_data)
        result = df_to_json(df)
        assert len(result) == expected
```

## MCP Server Integration Tests

Integration tests verify that MCP tools return correctly shaped data from real or mock APIs.

- **Marker**: `@pytest.mark.integration`
- **Command**: `pytest -m integration`
- **Requirement**: MCP servers must be running on localhost ports 8000–8002

### Pattern: Real API

```python
import pytest
import httpx

@pytest.mark.integration
class TestAkShareServer:
    BASE = "http://localhost:8000/mcp"

    async def test_stock_zh_a_spot_returns_list(self):
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.BASE,
                json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            )
        assert resp.status_code == 200
        tools = resp.json().get("result", {}).get("tools", [])
        assert any(t["name"] == "stock_zh_a_spot" for t in tools)
```

### Pattern: Mock API

For unit-testing MCP tools without hitting external APIs:

```python
import pytest
from unittest.mock import patch
import pandas as pd
from server import stock_zh_a_spot

class TestStockZhASpotMocked:
    @patch("server.ak.stock_zh_a_spot_em")
    def test_returns_list_of_dicts(self, mock_func):
        mock_func.return_value = pd.DataFrame({
            "代码": ["000001", "600519"],
            "名称": ["平安银行", "贵州茅台"],
            "最新价": [10.5, 1800.0],
        })
        result = stock_zh_a_spot()
        assert len(result) == 2
        assert result[0]["代码"] == "000001"

    @patch("server.ak.stock_zh_a_spot_em")
    def test_filters_by_symbol(self, mock_func):
        mock_func.return_value = pd.DataFrame({
            "代码": ["000001", "600519"],
            "名称": ["平安银行", "贵州茅台"],
        })
        result = stock_zh_a_spot(symbol="600519")
        assert len(result) == 1
        assert result[0]["代码"] == "600519"
```

## Agent E2E Tests

End-to-end tests verify that agents produce correct outputs given sample inputs. Because agents depend on MCP data, E2E tests use recorded (fixture) responses instead of live API calls.

- **Marker**: `@pytest.mark.e2e`
- **Command**: `pytest -m e2e`
- **Fixtures**: `tests/fixtures/` — JSON files containing recorded MCP tool responses

### Pattern

```python
import pytest
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

@pytest.mark.e2e
class TestStockScreener:
    def test_screen_low_pe_high_roe(self):
        """Verify stock-screener filters and ranks correctly."""
        # Load fixture data (simulated MCP response)
        spot_data = json.loads(
            (FIXTURES / "akshare_spot_50stocks.json").read_text()
        )
        fina_data = json.loads(
            (FIXTURES / "tushare_fina_indicator_sample.json").read_text()
        )

        # ... exercise screening logic with fixture data ...
        # Assert expected filtering and ranking behavior
```

## Testing Rules by Component

### MCP Servers

| Rule | Detail |
|------|--------|
| Every `@mcp.tool()` function gets at least one test | Cover happy path and at least one error case |
| Test `df_to_json()` helper | NaN handling, row truncation, empty DataFrame |
| Test with mock API | Mock `akshare` / `tushare` calls; verify response shape |
| Integration test against live server | At least one test that calls the running server |

### Skills

| Rule | Detail |
|------|--------|
| SKILL.md is valid | `scripts/check.py` validates structure (trigger conditions, inputs, outputs, steps) |
| Examples parse correctly | Input/output examples in `examples/` match the defined schema |
| Workflow is complete | Every step in SKILL.md has a corresponding test case |

### Agents

| Rule | Detail |
|------|--------|
| Guardrails hold | Test that excluded stocks (ST, suspended, <1yr) are filtered |
| Citation mandate | Test that output includes data source and timestamp |
| A-share constraints | Test that T+1, price limits, lot size rules are respected |

### Scripts

| Rule | Detail |
|------|--------|
| `check.py` | Test each check function independently |
| `sync-agent-skills.py` | Test sync with a fixture plugin directory |

## Test Commands

```bash
pytest                         # Unit tests only (excludes integration/e2e)
pytest -m integration          # Integration tests (requires MCP servers running)
pytest -m e2e                  # End-to-end tests (uses fixture data)
pytest --cov=mcp_servers       # Coverage report for MCP servers
pytest -x                      # Stop on first failure
pytest -v                      # Verbose output
```

## Coverage Targets

| Component | Target | Rationale |
|-----------|--------|-----------|
| MCP Servers | 80% | Core data layer — must be reliable |
| Utility scripts | 70% | Important but less critical |
| Agent prompt logic | 60% | Hard to test LLM behavior; focus on guardrail enforcement |
| Skill definitions | Validation only | SKILL.md is Markdown — check structure, not execution |

## Fixture Management

- Store fixture files in `tests/fixtures/`
- Name format: `{source}_{tool}_{description}.json`
  - Example: `akshare_spot_50stocks.json`, `tushare_fina_indicator_sample.json`
- Include a `README.md` in `tests/fixtures/` describing each fixture
- Regenerate fixtures when upstream API response shapes change
