# A-Share Agents

A-share quantitative analysis Agent system built on MCP (Model Context Protocol) data connectors and a plugin architecture.

## Architecture

```
Agent Layer → Skill Layer → Connector Layer (MCP Servers)
```

- **6 Agents**: stock-screener, equity-researcher, factor-analyst, backtester, portfolio-manager, market-monitor
- **7 Skills**: factor-screen, financial-analysis, factor-research, backtest-engine, portfolio-optimize, market-breadth, xlsx-author
- **3 MCP Servers**: AKShare (realtime), Tushare (high-quality historical), Internal Store (cache)

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   cp .env.example .env
   # Edit .env and add your TUSHARE_TOKEN
   ```

3. Start MCP servers:
   ```bash
   uvicorn mcp-servers/akshare-server/server:mcp_app --port 8000 &
   TUSHARE_TOKEN=xxx uvicorn mcp-servers/tushare-server/server:mcp_app --port 8001 &
   uvicorn mcp-servers/internal-store/server:mcp_app --port 8002 &
   ```

4. Run environment check:
   ```bash
   python scripts/check.py
   ```

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/screen` | Multi-factor stock screening | `/screen 沪深300 PE<20 ROE>15` |
| `/research` | Deep financial analysis | `/research 600519` |
| `/factor` | Factor research and validation | `/factor momentum` |
| `/backtest` | Strategy backtesting | `/backtest 沪深300动量策略` |
| `/optimize` | Portfolio optimization | `/optimize HRP` |
| `/market` | Market breadth monitoring | `/market 北向资金` |

## Project Structure

```
a-share-agents/
├── plugins/
│   ├── agent-plugins/       # 6 agent plugins
│   └── vertical-plugins/    # A-share analysis skill pack
├── mcp-servers/             # MCP data connectors
├── scripts/                 # Dev tooling
├── managed-agent-cookbooks/ # Managed agent deployments
├── contributing/            # Contributing guidelines
└── docs/                    # Design documents
```

## Contributing

See `contributing/README.md` for full guidelines.

## License

Private project — not for redistribution.
