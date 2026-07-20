/**
 * Pi SDK event -> @aquan/core AgentEvent translator.
 *
 * Phase 5: interface only. Concrete mapping lands once the Pi SDK's
 * event surface is verified against upstream docs.
 */

import type { AgentEvent, AgentEventKind } from "@aquan/core"

/** Opaque shape of a Pi SDK event — pinned when the SDK is integrated. */
export interface PiRawEvent {
  type: string
  payload?: unknown
  timestamp?: string
}

/** Map a raw Pi event to the orchestrator's AgentEvent shape. */
export function translatePiEvent(raw: PiRawEvent): AgentEvent {
  return {
    at: raw.timestamp ?? new Date().toISOString(),
    kind: classifyPiEvent(raw.type),
    detail: typeof raw.payload === "string" ? raw.payload : JSON.stringify(raw.payload ?? ""),
  }
}

function classifyPiEvent(type: string): AgentEventKind {
  if (type.includes("message")) return "message"
  if (type.includes("tool_call") || type.includes("tool.call")) return "tool_call"
  if (type.includes("tool_result") || type.includes("tool.result")) return "tool_result"
  if (type.includes("think") || type.includes("reason")) return "thinking"
  if (type.includes("error")) return "error"
  if (type.includes("blocked")) return "blocked"
  if (type.includes("turn_end") || type.includes("end")) return "turn_end"
  return "message"
}
