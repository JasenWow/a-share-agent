---
name: mcp-tool-adder
description: |
  Adds new MCP tools to existing servers based on data access patterns discovered during evolution.
  Triggers: "add MCP tool", "new data endpoint", "extend server"
---

# MCP Tool Adder

## Overview
Enables Meta-Agent Phase 3 to extend MCP servers with new tools when simulation reveals useful data patterns.

## Constraints (R6 Boundary)
- MCP servers must contain ONLY data access logic
- No domain/business logic in MCP tools
- New tools must follow FastMCP pattern (df_to_json, error handling)
- Must register new tool in server's README.md
- Only operates on internal-store server (not akshare or tushare)

## Process
1. Identify data access pattern from simulation
2. Validate tool code doesn't contain domain keywords
3. Write new @mcp.tool() function following server's pattern
4. Add to internal-store server
5. Update server's README.md tool table
6. Server restart required for tool registration