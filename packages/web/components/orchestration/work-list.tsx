"use client"

import type { RunState, TrackedWork } from "@aquan/core"
import { WorkCard } from "./work-card"

/**
 * Grouped list of TrackedWork by state. The "live" states (running /
 * retrying / blocked) come first, then pending, then the terminal
 * states are hidden behind a collapsible section so the page doesn't
 * drown in old work.
 *
 * Each section header shows the count + state label. Empty sections
 * are collapsed to a single line.
 */
export function WorkList({
  running,
  retrying,
  blocked,
  pending,
  recent,
}: {
  running: TrackedWork[]
  retrying: TrackedWork[]
  blocked: TrackedWork[]
  pending: TrackedWork[]
  recent: TrackedWork[]
}) {
  return (
    <div className="space-y-4">
      <Section title="Running" works={running} tone="text-blue-600 dark:text-blue-300" />
      <Section title="Retrying" works={retrying} tone="text-amber-600 dark:text-amber-300" />
      <Section title="Blocked" works={blocked} tone="text-red-600 dark:text-red-300" />
      <Section title="Pending" works={pending} tone="text-slate-600 dark:text-slate-300" />
      <Section title="Recent" works={recent} tone="text-slate-500" collapsible />
    </div>
  )
}

function Section({
  title,
  works,
  tone,
  collapsible = false,
}: {
  title: string
  works: TrackedWork[]
  tone: string
  collapsible?: boolean
}) {
  if (works.length === 0) {
    return (
      <div className="text-xs text-muted-foreground">
        <span className={tone}>{title}</span> · 0
      </div>
    )
  }
  return (
    <details open={!collapsible} className="group">
      <summary className={`cursor-pointer select-none text-sm font-medium ${tone}`}>
        {title} <span className="text-muted-foreground">· {works.length}</span>
      </summary>
      <div className="mt-2 grid grid-cols-1 gap-2 group-open:grid">
        {works.map((w) => (
          <WorkCard key={w.id} work={w} />
        ))}
      </div>
    </details>
  )
}

/** Helper for the parent if it wants a single RunState's slice. */
export function worksByState(works: TrackedWork[], state: RunState): TrackedWork[] {
  return works.filter((w) => w.state === state)
}
