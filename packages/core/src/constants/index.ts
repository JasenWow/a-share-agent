/**
 * Project-wide constants — ports, default paths, well-known names,
 * plus AI provider catalog (migrated from the original shared package).
 *
 * Centralized so server, orchestrator, and pi-runtime don't disagree
 * about where to find things.
 */

// Re-export the AI provider catalog from the original chat-database/shared.
export * from "./ai-providers"

/** Default MCP server ports (must match python/aquan/core/config.py). */
export const MCP_PORTS = {
  akshare: 8000,
  tushare: 8001,
  internalStore: 8002,
  qlib: 8003,
} as const

/** Default API server port (chat-database Hono server). */
export const SERVER_PORT = 3001

/** RunState display metadata for the dashboard. */
export const RUN_STATE_META = {
  pending: { label: "Pending", tone: "muted" },
  running: { label: "Running", tone: "info" },
  retrying: { label: "Retrying", tone: "warning" },
  blocked: { label: "Blocked", tone: "danger" },
  done: { label: "Done", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
} as const
