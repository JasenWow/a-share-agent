export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:3001"

/**
 * Orchestrator server URL — where the agent orchestration engine exposes
 * /api/v1/state, /api/v1/schedules, /api/v1/spend. Separate from the main
 * API server because the orchestrator is a different process (Bun.serve
 * on :3010). Override with NEXT_PUBLIC_ORCHESTRATOR_URL.
 */
export const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:3010"
