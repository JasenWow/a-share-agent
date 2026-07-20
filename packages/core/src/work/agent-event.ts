/**
 * AgentEvent — the stream of events emitted by an agent runtime (Pi)
 * during a turn. The orchestrator records these and the dashboard
 * surfaces the latest one.
 */

import type { TradingDate } from "../types/market"

/** Coarse event categories the UI groups on. */
export type AgentEventKind =
  | "message" // assistant produced text
  | "tool_call" // agent invoked a tool
  | "tool_result" // tool returned a value
  | "thinking" // reasoning-only step (no external effect)
  | "error" // runtime or tool error
  | "turn_end" // turn completed normally
  | "blocked" // agent requests human input

export interface AgentEvent {
  /** When the event was emitted (ISO8601). */
  at: string
  kind: AgentEventKind
  /** Free-form payload — message text, tool name, error detail, etc. */
  detail?: string
  /** Token usage if the runtime reports it. */
  tokens?: {
    input?: number
    output?: number
    total?: number
  }
}

/** Aggregated token counts for a run, computed from the event stream. */
export interface RunTokens {
  input: number
  output: number
  total: number
}

/** A single observation the orchestrator stores per trading day. */
export interface DailyObservation {
  date: TradingDate
  source: "free-exploration" | "sedimentation"
  summary: string
  highlights?: string[]
}
