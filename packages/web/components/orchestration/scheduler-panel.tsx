"use client"

import { Card } from "@/components/ui/card"
import type { ScheduleStatusPayload } from "@/api-clients/orchestration"

/**
 * Scheduler status panel — one row per ScheduleSpec showing the cron
 * expression, fire count, error count, and last error.
 *
 * Shows whether the scheduler is running (green dot) or stopped.
 * When the orchestrator isn't started yet, the panel says so instead of
 * showing an empty table.
 */
export function SchedulerPanel({
  schedules,
  running,
}: {
  schedules: ScheduleStatusPayload[]
  running: boolean
}) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Schedules</h3>
        <SchedulerRunningBadge running={running} />
      </div>
      {schedules.length === 0 ? (
        <div className="text-xs text-muted-foreground">
          No schedules registered. The orchestrator is not started, or no cron jobs have been added.
        </div>
      ) : (
        <div className="space-y-2">
          {schedules.map((s, i) => (
            <div
              key={`${s.spec.name ?? "schedule"}-${i}`}
              className="flex items-center justify-between gap-3 border-b border-border/50 pb-2 text-xs last:border-0 last:pb-0"
            >
              <div className="min-w-0">
                <div className="truncate font-mono text-[11px]">
                  {s.spec.name ?? s.spec.cron}
                </div>
                <div className="truncate font-mono text-[10px] text-muted-foreground">
                  {s.spec.cron}
                  {s.spec.trackers && s.spec.trackers.length > 0 && (
                    <span className="ml-1 opacity-70">→ {s.spec.trackers.join(", ")}</span>
                  )}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="tabular-nums">
                  fired <span className="font-medium">{s.fireCount}</span>
                  {" · "}
                  <span className={s.errorCount > 0 ? "font-medium text-red-500" : "text-muted-foreground"}>
                    {s.errorCount} err
                  </span>
                </div>
                {s.lastError && (
                  <div className="line-clamp-1 max-w-[18ch] text-[10px] text-red-500" title={s.lastError}>
                    {s.lastError}
                  </div>
                )}
                {s.lastFireAt && !s.lastError && (
                  <div className="text-[10px] text-muted-foreground">{timeAgo(s.lastFireAt)}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

function SchedulerRunningBadge({ running }: { running: boolean }) {
  if (running) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-300">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" />
        running
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-500/10 px-2 py-0.5 text-[10px] font-medium text-slate-500">
      stopped
    </span>
  )
}

function timeAgo(iso: string): string {
  try {
    const then = new Date(iso).getTime()
    const now = Date.now()
    const sec = Math.max(0, Math.floor((now - then) / 1000))
    if (sec < 60) return `${sec}s ago`
    const min = Math.floor(sec / 60)
    if (min < 60) return `${min}m ago`
    const hr = Math.floor(min / 60)
    if (hr < 24) return `${hr}h ago`
    return `${Math.floor(hr / 24)}d ago`
  } catch {
    return iso
  }
}
