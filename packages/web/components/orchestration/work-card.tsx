"use client"

import Link from "next/link"
import type { TrackedWork } from "@aquan/core"
import { Card } from "@/components/ui/card"

/**
 * One card per TrackedWork. Shows id, state dot, turn progress,
 * last event/message, and error (if any). The whole card is a link to
 * the work-item detail page (/orchestration/<id>), which renders the
 * full event timeline.
 *
 * Cards are intentionally compact — the dashboard polls every 2s and
 * renders dozens of these.
 */
export function WorkCard({ work }: { work: TrackedWork }) {
  return (
    <Link href={`/orchestration/${encodeURIComponent(work.id)}`} className="block">
      <Card className="cursor-pointer p-3 text-sm transition-colors hover:bg-accent">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <StateDot state={work.state} />
              <span className="truncate font-mono text-xs text-muted-foreground" title={work.id}>
                {work.id}
              </span>
            </div>
            <div className="mt-1 truncate font-medium" title={work.title}>
              {work.title}
            </div>
            {work.lastMessage && (
              <div className="mt-1 line-clamp-2 text-xs text-muted-foreground" title={work.lastMessage}>
                {work.lastMessage}
              </div>
            )}
            {work.error && (
              <div className="mt-1 line-clamp-2 rounded bg-red-500/10 p-1 text-xs text-red-600 dark:text-red-300" title={work.error}>
                {work.error}
              </div>
            )}
          </div>
          <div className="shrink-0 text-right text-[10px] text-muted-foreground">
            {typeof work.turnCount === "number" && <div>turn {work.turnCount}</div>}
            {work.startedAt && <div>{formatTime(work.startedAt)}</div>}
            {work.lastEventAt && <div title={work.lastEventAt}>↻ {formatTime(work.lastEventAt)}</div>}
          </div>
        </div>
      </Card>
    </Link>
  )
}

function StateDot({ state }: { state: TrackedWork["state"] }) {
  const color = dotColor(state)
  return (
    <span
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${color}`}
      aria-label={state}
      title={state}
    />
  )
}

function dotColor(state: TrackedWork["state"]): string {
  switch (state) {
    case "running":
      return "bg-blue-500 animate-pulse"
    case "retrying":
      return "bg-amber-500"
    case "blocked":
      return "bg-red-500"
    case "done":
      return "bg-emerald-500"
    case "failed":
      return "bg-red-700"
    case "pending":
    default:
      return "bg-slate-400"
  }
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  } catch {
    return iso
  }
}
