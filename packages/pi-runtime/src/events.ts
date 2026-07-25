/**
 * Pi SDK AgentEvent → @aquan/core AgentEvent translator.
 *
 * The Pi SDK emits a typed event stream during a run (see
 * `AgentEvent` in @earendil-works/pi-agent-core). The orchestrator's
 * `AgentEventKind` is coarser, so this module drops noisy events
 * (turn_start, agent_start, tool_execution_update) and collapses
 * related ones (message_start/update/end all → "message").
 *
 * See docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md
 * section 5 for the translation table rationale.
 */

import type { AgentEvent as AquanAgentEvent, AgentEventKind } from "@aquan/core"
import { contentText } from "@earendil-works/pi-ai"
import type { AgentEvent as PiAgentEvent } from "@earendil-works/pi-agent-core"

/**
 * Translate a Pi SDK lifecycle event into the orchestrator's coarser shape.
 * Returns `null` for events we choose not to surface (agent_start, turn_start,
 * tool_execution_update) so the caller can skip them without a sentinel.
 */
export function translatePiEvent(raw: PiAgentEvent, at = new Date().toISOString()): AquanAgentEvent | null {
  switch (raw.type) {
    case "message_start":
    case "message_update":
    case "message_end": {
      const text = extractMessageText(raw.message)
      if (!text && raw.type !== "message_end") return null // drop empty incremental updates
      return {
        at,
        kind: "message",
        detail: text || undefined,
      }
    }

    case "tool_execution_start": {
      return {
        at,
        kind: "tool_call",
        detail: raw.toolName,
      }
    }

    case "tool_execution_end": {
      const summary = summarizeToolResult(raw.result)
      return {
        at,
        kind: "tool_result",
        detail: raw.isError ? `error in ${raw.toolName}: ${summary}` : `${raw.toolName}: ${summary}`,
      }
    }

    case "turn_end":
    case "agent_end": {
      return {
        at,
        kind: "turn_end",
      }
    }

    // Intentionally dropped — too noisy to surface on the dashboard.
    case "agent_start":
    case "turn_start":
    case "tool_execution_update":
      return null

    default: {
      // Unknown event types become errors so they're visible on the dashboard
      // and we notice when the SDK adds something we should handle.
      return {
        at,
        kind: "error",
        detail: `unhandled pi event: ${(raw as { type: string }).type}`,
      }
    }
  }
}

/** Filter + map in one pass: returns only non-null translations. */
export function translatePiEvents(raws: PiAgentEvent[], at?: string): AquanAgentEvent[] {
  const out: AquanAgentEvent[] = []
  for (const r of raws) {
    const t = translatePiEvent(r, at)
    if (t) out.push(t)
  }
  return out
}

/** Internal: best-effort extraction of plain text from a Pi AgentMessage. */
function extractMessageText(message: unknown): string {
  if (!message || typeof message !== "object") return ""
  const msg = message as { content?: unknown }
  // contentText takes the content field (array of blocks), not the whole message.
  const content = msg.content
  if (typeof content === "string") return content
  if (!Array.isArray(content)) return ""
  try {
    const text = contentText(content as never)
    return typeof text === "string" ? text : ""
  } catch {
    return ""
  }
}

/** Internal: produce a short, dashboard-readable summary of a tool result. */
function summarizeToolResult(result: unknown): string {
  if (result == null) return "(null)"
  if (typeof result === "string") return truncate(result, 200)
  if (typeof result === "object") {
    try {
      return truncate(JSON.stringify(result), 200)
    } catch {
      return "(unserializable object)"
    }
  }
  return truncate(String(result), 200)
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max)}…`
}

// Re-export the kind enum for callers that want to switch on it.
export type { AgentEventKind } from "@aquan/core"
