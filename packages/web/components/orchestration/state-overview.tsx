"use client"

import { Card } from "@/components/ui/card"
import type { RunState } from "@aquan/core"
import { RUN_STATE_META } from "@aquan/core"

/**
 * Row of state-count cards at the top of the /orchestration page.
 *
 * Each card shows the count for one RunState. Color comes from
 * RUN_STATE_META[state].tone (defined in @aquan/core so the dashboard
 * and orchestrator agree on the palette).
 */
export function StateOverview({ counts }: { counts: Record<RunState, number> }) {
  const order: RunState[] = ["running", "retrying", "blocked", "pending", "done", "failed"]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {order.map((state) => {
        const meta = RUN_STATE_META[state]
        const value = counts[state] ?? 0
        return (
          <Card
            key={state}
            className={`${toneRingClass(meta.tone)} ${toneTextClass(meta.tone)} p-4`}
          >
            <div className="text-xs font-medium uppercase tracking-wide opacity-70">
              {meta.label}
            </div>
            <div className="mt-1 text-3xl font-semibold tabular-nums">{value}</div>
          </Card>
        )
      })}
    </div>
  )
}

function toneRingClass(tone: string): string {
  switch (tone) {
    case "info":
      return "border-l-4 border-l-blue-500"
    case "warning":
      return "border-l-4 border-l-amber-500"
    case "danger":
      return "border-l-4 border-l-red-500"
    case "success":
      return "border-l-4 border-l-emerald-500"
    case "muted":
    default:
      return "border-l-4 border-l-slate-400"
  }
}

function toneTextClass(tone: string): string {
  switch (tone) {
    case "info":
      return "text-blue-600 dark:text-blue-300"
    case "warning":
      return "text-amber-600 dark:text-amber-300"
    case "danger":
      return "text-red-600 dark:text-red-300"
    case "success":
      return "text-emerald-600 dark:text-emerald-300"
    case "muted":
    default:
      return "text-slate-600 dark:text-slate-300"
  }
}
