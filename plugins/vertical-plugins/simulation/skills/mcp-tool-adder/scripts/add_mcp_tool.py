from pathlib import Path
import subprocess
import json

DOMAIN_KEYWORDS = ["backtest", "portfolio_optimize", "screen_stocks", "market_breadth", "factor_cal", "winsorize", "neutralize", "portfolio", "backtest"]

MCP_TOOL_TEMPLATE = '''
@mcp.tool()
def {tool_name}({params}) -> list[dict]:
    """
    {description}

    Args:
{param_docs}    """
    try:
        df = {upstream_call}
        return df_to_json(df)
    except Exception as e:
        return [{{"error": str(e), "tool": "{tool_name}"}}]

'''

def validate_tool_code(tool_code: str) -> tuple[bool, str]:
    """Check tool code doesn't contain domain logic keywords."""
    for kw in DOMAIN_KEYWORDS:
        if f"def {kw}" in tool_code.lower() or f"{kw}(" in tool_code.lower():
            return False, f"Domain keyword '{kw}' found in tool code"
    return True, "valid"

def add_tool_to_server(server_name: str, tool_name: str, params: str, description: str, upstream_call: str) -> bool:
    """Add a new tool to an existing MCP server. Only internal-store allowed."""
    if server_name != "internal-store":
        return False

    server_path = Path(f"mcp-servers/{server_name}/server.py")
    if not server_path.exists():
        return False

    content = server_path.read_text()

    existing_funcs = [line.strip() for line in content.split('\n') if line.strip().startswith('def ')]
    for func in existing_funcs:
        func_name = func.split('(')[0].replace('def ', '').strip()
        if func_name == tool_name:
            return False

    valid, reason = validate_tool_code(upstream_call)
    if not valid:
        return False

    param_list = ", ".join(params.split(", ")) if params else ""
    param_docs = "\n".join([f"        {p.split(':')[0].strip()}: Description." for p in params.split(", ") if p])

    tool_code = MCP_TOOL_TEMPLATE.format(
        tool_name=tool_name,
        params=param_list,
        description=description,
        param_docs=param_docs or "        # Add parameter descriptions",
        upstream_call=upstream_call
    )

    asgi_marker = "# --- ASGI App ---"
    if asgi_marker in content:
        content = content.replace(asgi_marker, tool_code + "\n\n" + asgi_marker)
    else:
        content += "\n" + tool_code

    server_path.write_text(content)

    result = subprocess.run(
        ["uv", "run", "python", "scripts/check.py"],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        return False

    return True

def update_server_readme(server_name: str, tool_name: str, description: str) -> bool:
    """Update server README with new tool."""
    readme_path = Path(f"mcp-servers/{server_name}/README.md")
    if not readme_path.exists():
        return False

    content = readme_path.read_text()
    new_entry = f"\n| `{tool_name}` | New tool | {description} |"

    if f"| `{tool_name}` |" in content:
        return False

    content = content.replace("| Tool Name |", f"| Tool Name |\n| `{tool_name}` | New tool | {description} |")
    readme_path.write_text(content)
    return True