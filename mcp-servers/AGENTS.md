# MCP Servers

**Scope:** The only Python packages in this project. 4 independent servers, no cross-server imports.

## SERVERS

| Server | Port | Purpose | Key Dependencies |
|--------|------|---------|-----------------|
| akshare-server | 8000 | Realtime data (free, no auth) | akshare, mcp, pandas, fastapi |
| tushare-server | 8001 | Historical data (requires TUSHARE_TOKEN) | tushare, mcp, pandas, fastapi |
| internal-store | 8002 | Cache layer, query results | pyarrow, mcp, pandas, fastapi |
| bilibili-server | — | Bilibili data (not verified) | bilibili-api-python, mcp |

## STRUCTURE

```
mcp-servers/
├── akshare-server/
│   ├── server.py          # FastMCP app, 9 @mcp.tool() functions
│   ├── pyproject.toml
│   ├── test_server.py
│   └── README.md
├── tushare-server/
├── internal-store/
└── bilibili-server/
```

## TOOL PATTERN

```python
@mcp.tool()
def tool_name(param: str) -> list[dict]:
    """Docstring is mandatory — becomes tool description for agents."""
    try:
        df = external_api_call(param)
        return df_to_json(df)  # max 5000 rows, NaN → "NaN" string
    except Exception as e:
        return [{"error": str(e), "tool": "tool_name", "params": {"param": param}}]
```

## ANTI-PATTERNS

- **Never** `return None` from a tool — return `[]` or error dict
- **Never** raise unhandled exceptions — catch and return error dicts
- **Never** hardcode credentials — tokens from env vars only
- **Never** web search for financial data — Tushare → AKShare → user-provided
- **Never** import another MCP server's code (R4)

## CONVENTIONS

- Stock codes: always 6-digit strings, `000001.SZ` not `1`
- Tushare codes include suffix (`.SZ`, `.SH`), AKShare codes are bare
- Dates: `YYYYMMDD` strings for API calls, `datetime` only for calculations
- `df_to_json()` converts DataFrames consistently
- `logging` instead of `print()` in production
- Max 5000 rows per tool response