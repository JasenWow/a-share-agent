"use client"

import type { AgentEvent, AgentEventKind } from "@aquan/core"
import { Card } from "@/components/ui/card"

/**
 * EventTimeline — renders one work item's agent events as a vertical
 * timeline, ordered ascending by time. Each kind gets a distinct glyph
 * + tone so tool calls, messages, turn boundaries, and errors are
 * visually separable at a glance.
 *
 * Pure presentational — the parent page owns SWR polling.
 */
export function EventTimeline({ events }: { events: AgentEvent[] }) {
  if (events.length === 0) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">
        No events recorded yet. Events appear as the agent runs.
      </Card>
    )
  }
  return (
    <Card className="p-4">
      <div className="space-y-1.5">
        {events.map((e, i) => (
          <EventRow key={`${e.at}-${i}`} event={e} />
        ))}
      </div>
    </Card>
  )
}

const KIND_META: Record<AgentEventKind, { glyph: string; tone: string; label: string }> = {
  message: { glyph: "●", tone: "text-blue-600 dark:text-blue-400", label: "message" },
  tool_call: { glyph: "🔧", tone: "text-violet-600 dark:text-violet-400", label: "tool_call" },
  tool_result: { glyph: "✅", tone: "text-emerald-600 dark:text-emerald-400", label: "tool_result" },
  thinking: { glyph: "💭", tone: "text-slate-500 dark:text-slate-400", label: "thinking" },
  error: { glyph: "✖", tone: "text-red-600 dark:text-red-400", label: "error" },
  turn_end: { glyph: "↩", tone: "text-amber-600 dark:text-amber-400", label: "turn_end" },
  blocked: { glyph: "⏸", tone: "text-orange-600 dark:text-orange-400", label: "blocked" },
}

function EventRow({ event }: { event: AgentEvent }) {
  const meta = KIND_META[event.kind] ?? { glyph: "·", tone: "", label: event.kind }
  // Show only the time portion (HH:MM:SS) for compactness; the date is
  // implicit (all events in a run share the same day in practice).
  const time = event.at.slice(11, 19) || event.at
  return (
    <div className="flex items-start gap-2 text-xs">
      <span className={`mt-0.5 w-4 shrink-0 text-center ${meta.tone}`} title={event.at}>
        {meta.glyph}
      </span>
      <span className="w-20 shrink-0 font-mono text-muted-foreground">{time}</span>
      <span className={`w-24 shrink-0 font-medium ${meta.tone}`}>{meta.label}</span>
      <span className="min-w-0 flex-1 break-words text-foreground/90">
        {event.detail ?? ""}
        {event.tokens ? (
          <span className="ml-2 text-[10px] text-muted-foreground">
            {event.tokens.total ?? "?"} tok
          </span>
        ) : null}
      </span>
    </div>
  )
}
