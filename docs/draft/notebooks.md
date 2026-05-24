# Jupyter Notebook Conventions

> Standards for creating and running Jupyter notebooks in this project. Notebooks are self-contained analysis units that access MCP data connectors via HTTP. Every notebook must be independently executable.

## Directory Structure

All notebooks live at the project root under `notebooks/`.

```
notebooks/
├── factor-analysis.ipynb
├── backtest-report.ipynb
├── portfolio-review.ipynb
└── market-monitor.ipynb
```

Naming convention: `{name}.ipynb` where `name` is lowercase-kebab-case. No spaces, no special characters.

## Data Access

Notebooks access MCP servers via HTTP POST to the streamable HTTP endpoint.

### Internal Store (port 8002)

```
http://localhost:8002/mcp
```

Request format:

```json
{
  "tool": "<tool_name>",
  "arguments": {
    "param1": "value1",
    "param2": 42
  }
}
```

Response is a JSON array. Empty array means no data. Each item is a dict.

### Connection Check

At the top of every notebook, check that the MCP server is reachable:

```python
import requests

MCP_URL = "http://localhost:8002/mcp"

def check_mcp_server():
    try:
        resp = requests.post(MCP_URL, json={"tool": "list_experiments", "arguments": {}}, timeout=5)
        if resp.status_code == 200:
            return True
    except Exception:
        return False

if not check_mcp_server():
    print("Warning: Internal Store MCP server not reachable at", MCP_URL)
    print("Start it with: uvicorn mcp-servers.internal-store.server:mcp_app --port 8002")
```

## Available MCP Tools

The internal-store server exposes 9 tools. All tool calls use the same HTTP POST pattern.

### 1. query_cache

Query local cache data. Returns cached data if not expired.

| Parameter | Type | Description |
|-----------|------|-------------|
| source | str | Data source name ("akshare" or "tushare") |
| tool_name | str | MCP tool name |
| params | dict | Parameters dict used in original query |

```python
resp = requests.post(MCP_URL, json={
    "tool": "query_cache",
    "arguments": {"source": "akshare", "tool_name": "stock_zh_a_hist", "params": {"symbol": "000001"}}
}).json()
```

### 2. list_backtest_results

List all recorded backtest results.

| Parameter | Type | Description |
|-----------|------|-------------|
| limit | int | Maximum number of results to return (default: 20) |

```python
resp = requests.post(MCP_URL, json={
    "tool": "list_backtest_results",
    "arguments": {"limit": 10}
}).json()
```

### 3. get_portfolio

Get current portfolio state.

| Parameter | Type | Description |
|-----------|------|-------------|
| name | str | Portfolio name (default: "default") |

```python
resp = requests.post(MCP_URL, json={
    "tool": "get_portfolio",
    "arguments": {"name": "default"}
}).json()
```

### 4. record_experiment

Record an experiment run for the Meta-Agent.

| Parameter | Type | Description |
|-----------|------|-------------|
| name | str | Experiment name |
| strategy | dict | Strategy configuration dict |
| params | dict | Strategy parameters dict |
| result | dict | Result metrics dict (final_nav, sharpe, max_drawdown) |

```python
resp = requests.post(MCP_URL, json={
    "tool": "record_experiment",
    "arguments": {
        "name": "momentum-2024q1",
        "strategy": {"type": "momentum", "lookback": 20},
        "params": {"threshold": 0.05},
        "result": {"final_nav": 1.23, "sharpe": 1.8, "max_drawdown": 0.12}
    }
}).json()
```

### 5. list_experiments

List all recorded experiments. No parameters.

```python
resp = requests.post(MCP_URL, json={
    "tool": "list_experiments",
    "arguments": {}
}).json()
```

### 6. get_best_strategies

Get top-k strategies ordered by final_nav descending.

| Parameter | Type | Description |
|-----------|------|-------------|
| top_k | int | Number of top strategies to return (default: 5) |

```python
resp = requests.post(MCP_URL, json={
    "tool": "get_best_strategies",
    "arguments": {"top_k": 5}
}).json()
```

### 7. record_transition

Record a state transition for RL-based strategies.

| Parameter | Type | Description |
|-----------|------|-------------|
| experiment_id | int | ID of the experiment this transition belongs to |
| state | dict | Current state dict |
| strategy | dict | Action/strategy dict |
| reward | dict | Reward dict |
| next_state | dict | Resulting state dict |

```python
resp = requests.post(MCP_URL, json={
    "tool": "record_transition",
    "arguments": {
        "experiment_id": 1,
        "state": {"date": "2024-01-01", "positions": []},
        "strategy": {"action": "buy", "stock": "000001"},
        "reward": {"return": 0.02},
        "next_state": {"date": "2024-01-02", "positions": ["000001"]}
    }
}).json()
```

### 8. record_episode_summary

Record an episode summary for simulation runs.

| Parameter | Type | Description |
|-----------|------|-------------|
| period | str | Period identifier (e.g., "2024Q1") |
| initial_capital | float | Starting capital |
| final_nav | float | Final NAV (net asset value) |
| sharpe | float | Sharpe ratio |
| max_drawdown | float | Maximum drawdown |

```python
resp = requests.post(MCP_URL, json={
    "tool": "record_episode_summary",
    "arguments": {
        "period": "2024Q1",
        "initial_capital": 1000000.0,
        "final_nav": 1.15,
        "sharpe": 1.5,
        "max_drawdown": 0.08
    }
}).json()
```

### 9. list_episode_summaries

List all episode summaries. No parameters.

```python
resp = requests.post(MCP_URL, json={
    "tool": "list_episode_summaries",
    "arguments": {}
}).json()
```

## Kernel Specification

Every notebook must specify the Python 3 kernel with these required packages:

| Package | Purpose |
|---------|---------|
| pandas | Data manipulation |
| requests | HTTP calls to MCP servers |
| plotly | Interactive charts (saved as static HTML for portability) |

At the top of each notebook, verify packages are available:

```python
import sys
import subprocess

required = ["pandas", "requests", "plotly"]
missing = []
for pkg in required:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)

if missing:
    print(f"Installing missing packages: {missing}")
    subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])
```

## Execution for CI

Run notebooks headlessly with nbconvert:

```bash
jupyter nbconvert --execute --ExecutePreprocessor.timeout=120 notebooks/factor-analysis.ipynb
```

The `--execute` flag runs the notebook from top to bottom. `--ExecutePreprocessor.timeout=120` sets a 120-second timeout per cell to prevent hangs.

To execute and save output inline:

```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/factor-analysis.ipynb
```

## Validation Rules

Every notebook must handle these cases gracefully:

### Empty Data

When MCP returns an empty list, display a clear message instead of crashing:

```python
data = resp.json()
if not data or data == []:
    print("No data returned. Check that the MCP server is running and data exists.")
elif isinstance(data, list) and len(data) > 0 and "error" in data[0]:
    print("MCP error:", data[0]["error"])
else:
    # proceed with data
    df = pd.DataFrame(data)
```

### MCP Server Unavailable

If the connection check fails at startup, do not proceed with analysis. Display instructions:

```python
if not check_mcp_server():
    print("=" * 60)
    print("MCP server not available.")
    print("Start internal-store server:")
    print("  uvicorn mcp-servers.internal-store.server:mcp_app --port 8002")
    print("=" * 60)
```

## Independent Execution

Each notebook must be self-contained. No inter-notebook dependencies.

- Do not import code from other notebooks.
- Do not rely on outputs from previous notebook runs.
- Do not share state between notebooks.
- All data must be fetched fresh via MCP tools within the notebook itself.

If multiple notebooks need shared logic, extract it to a Python script under `scripts/` and call it via `subprocess` or import it directly.

## Output Formatting

- Use `display()` for rich output in Jupyter.
- Save interactive Plotly charts as HTML files for portability: `fig.write_html("output.html")`.
- Use pandas `display()` options for consistent table formatting:

```python
pd.set_option("display.max_columns", 20)
pd.set_option("display.width", 120)
pd.set_option("display.max_rows", 50)
```