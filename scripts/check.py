#!/usr/bin/env python3
"""
Environment check script — verify all dependencies and configuration are ready.

Usage:
  python scripts/check.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def check_python_packages() -> list[str]:
    """Check Python package dependencies."""
    issues = []
    required = ["akshare", "tushare", "pandas", "openpyxl", "mcp", "fastapi"]
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            issues.append(f"MISSING: {pkg} (pip install {pkg})")
    return issues


def check_mcp_servers() -> list[str]:
    """Check MCP configuration files."""
    issues = []
    mcp_config = ROOT / ".mcp.json"
    if not mcp_config.exists():
        issues.append("MISSING: .mcp.json at project root")
        return issues

    with open(mcp_config) as f:
        config = json.load(f)

    required_servers = ["akshare", "tushare", "internal-store"]
    servers = config.get("mcpServers", {})
    for srv in required_servers:
        if srv not in servers:
            issues.append(f"MISSING: MCP server '{srv}' in .mcp.json")
        elif servers[srv].get("type") != "http":
            issues.append(f"WARN: MCP server '{srv}' type should be 'http'")

    return issues


def check_plugin_structure() -> list[str]:
    """Check plugin directory structure."""
    issues = []

    # Check vertical plugins (5 verticals: market-data, equity-research, trading-strategy, simulation, market-monitor)
    verticals = ["market-data", "equity-research", "trading-strategy", "simulation", "market-monitor"]
    verticals_dir = ROOT / "plugins" / "vertical-plugins"
    for vp_name in verticals:
        vp = verticals_dir / vp_name
        if not vp.exists():
            issues.append(f"MISSING: vertical plugin {vp}")
            continue
        for required in [".claude-plugin", ".mcp.json", "skills", "commands"]:
            if not (vp / required).exists():
                issues.append(f"MISSING: {vp / required}")

    # Check agent plugins (5 agents: equity-researcher, strategy-analyst, portfolio-manager, market-monitor, meta-strategist)
    agents = [
        "equity-researcher",
        "strategy-analyst",
        "portfolio-manager",
        "market-monitor",
        "meta-strategist",
    ]
    ap = ROOT / "plugins" / "agent-plugins"
    for agent in agents:
        agent_dir = ap / agent
        if not agent_dir.exists():
            issues.append(f"MISSING: agent plugin {agent_dir}")
            continue
        for required in [".claude-plugin", "agents"]:
            if not (agent_dir / required).exists():
                issues.append(f"MISSING: {agent_dir / required}")

    return issues


def check_mcp_servers_code() -> list[str]:
    """Check MCP server directories."""
    issues = []
    servers = ["akshare-server", "tushare-server", "internal-store"]
    for srv in servers:
        srv_dir = ROOT / "mcp-servers" / srv
        if not srv_dir.exists():
            issues.append(f"MISSING: MCP server directory {srv_dir}")
            continue
        if not (srv_dir / "server.py").exists():
            issues.append(f"MISSING: {srv_dir / 'server.py'}")
        if not (srv_dir / "pyproject.toml").exists():
            issues.append(f"MISSING: {srv_dir / 'pyproject.toml'}")
    return issues


def check_boundary_rules() -> list[str]:
    """Check architectural boundary rules (R1-R6)."""
    issues = []
    plugins_dir = ROOT / "plugins"

    # R1: MCP servers must not import plugins/ code
    mcp_dir = ROOT / "mcp-servers"
    if mcp_dir.exists():
        for srv_dir in mcp_dir.iterdir():
            if not srv_dir.is_dir():
                continue
            for py_file in srv_dir.rglob("*.py"):
                content = py_file.read_text(errors="ignore")
                if "plugins" in content and ("import" in content or "from" in content):
                    for line in content.splitlines():
                        stripped = line.strip()
                        if ("from plugins" in stripped or "import plugins" in stripped) and not stripped.startswith("#"):
                            issues.append(f"R1 VIOLATION: {py_file.relative_to(ROOT)} imports plugins code: {stripped}")

    # R6: MCP servers should not contain domain logic keywords
    domain_keywords = [
        "winsorize",
        "neutralize",
        "factor_cal",
        "backtest",
        "portfolio_optimize",
        "screen_stocks",
        "market_breadth",
    ]
    if mcp_dir.exists():
        for srv_dir in mcp_dir.iterdir():
            if not srv_dir.is_dir():
                continue
            for py_file in srv_dir.rglob("*.py"):
                content = py_file.read_text(errors="ignore").lower()
                for kw in domain_keywords:
                    if kw in content and "def " in content:
                        issues.append(f"R6 WARNING: {py_file.relative_to(ROOT)} may contain domain logic ({kw}) — consider moving to skill scripts/")
                        break

    # R4: No cross-server imports
    server_names = ["akshare_server", "tushare_server", "internal_store"]
    if mcp_dir.exists():
        for srv_dir in mcp_dir.iterdir():
            if not srv_dir.is_dir():
                continue
            for py_file in srv_dir.rglob("*.py"):
                content = py_file.read_text(errors="ignore")
                for other in server_names:
                    if other.replace("_", "-") != srv_dir.name:
                        if f"from mcp_servers.{other}" in content or f"import mcp_servers.{other}" in content:
                            issues.append(f"R4 VIOLATION: {py_file.relative_to(ROOT)} imports from {other}")

    return issues


def check_data_dir() -> list[str]:
    """Check data directory."""
    issues = []
    data_dir = ROOT / "data"
    if not data_dir.exists():
        issues.append(f"MISSING: {data_dir} (will be auto-created on first run)")
    return issues


def check_env_vars() -> list[str]:
    """Check environment variables."""
    import os

    issues = []
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        issues.append("WARN: TUSHARE_TOKEN not set (optional for AKShare-only mode)")
    return issues


def main():
    print("A-Share Agents Environment Check")
    print("=" * 50)

    all_issues = []

    checks = [
        ("Python Packages", check_python_packages),
        ("MCP Configuration", check_mcp_servers),
        ("Plugin Structure", check_plugin_structure),
        ("MCP Server Code", check_mcp_servers_code),
        ("Boundary Rules", check_boundary_rules),
        ("Data Directory", check_data_dir),
        ("Environment Variables", check_env_vars),
    ]

    for name, check_fn in checks:
        print(f"\n[{name}]")
        issues = check_fn()
        all_issues.extend(issues)
        if issues:
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("  OK")

    print(f"\n{'=' * 50}")
    if all_issues:
        print(f"Found {len(all_issues)} issue(s). Fix before proceeding.")
        sys.exit(1)
    else:
        print("All checks passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
