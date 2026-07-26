"use client"

import type { HistoryPayload, HistoryBucket } from "@/api-clients/orchestration"
import { Card } from "@/components/ui/card"
import { WorkCard } from "./work-card"

/**
 * HistoryPanel — the /loops view body. Renders three sections:
 *   1. Totals strip (done / failed / retrying)
 *   2. Aggregation: by tracker + by day (bar-chart-ish)
 *   3. Scrollable item list (reuses WorkCard)
 *
 * Pure presentational — the parent page owns SWR polling and passes the
 * payload in.
 */
export function HistoryPanel({ payload }: { payload: HistoryPayload }) {
  const trackerRows = Object.entries(payload.byTracker).sort((a, b) => b[1].total - a[1].total)
  const dayRows = Object.entries(payload.byDay)
    .sort((a, b) => b[0].localeCompare(a[0]))
    .slice(0, 14) // last 2 weeks
  const maxDayTotal = Math.max(1, ...dayRows.map(([, b]) => b.total))

  return (
    <div className="space-y-4">
      {/* Totals */}
      <Card className="flex items-center gap-6 p-4 text-sm">
        <TotalChip label="Done" value={payload.totals.done} tone="text-emerald-600 dark:text-emerald-400" />
        <TotalChip label="Failed" value={payload.totals.failed} tone="text-red-600 dark:text-red-400" />
        <TotalChip label="Retrying" value={payload.totals.retrying} tone="text-amber-600 dark:text-amber-400" />
        <div className="ml-auto text-xs text-muted-foreground">
          total {payload.totals.total} · {payload.items.length} shown
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* By tracker */}
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-medium">By tracker</h3>
          {trackerRows.length === 0 ? (
            <p className="text-xs text-muted-foreground">No history yet.</p>
          ) : (
            <div className="space-y-2">
              {trackerRows.map(([name, b]) => (
                <BucketRow key={name} label={name} bucket={b} max={Math.max(1, b.total)} />
              ))}
            </div>
          )}
        </Card>

        {/* By day */}
        <Card className="p-4">
          <h3 className="mb-3 text-sm font-medium">By day (last 14)</h3>
          {dayRows.length === 0 ? (
            <p className="text-xs text-muted-foreground">No dated history yet.</p>
          ) : (
            <div className="space-y-1.5">
              {dayRows.map(([day, b]) => (
                <div key={day} className="flex items-center gap-2 text-xs">
                  <span className="w-24 font-mono text-muted-foreground">{day}</span>
                  <div className="relative h-4 flex-1 rounded bg-muted">
                    <div
                      className="h-4 rounded bg-primary/40"
                      style={{ width: `${(b.total / maxDayTotal) * 100}%` }}
                    />
                  </div>
                  <span className="w-24 text-right tabular-nums text-muted-foreground">
                    {b.done} done{b.failed > 0 ? ` · ${b.failed} fail` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Item list */}
      <Card className="p-4">
        <h3 className="mb-3 text-sm font-medium">History (newest first)</h3>
        {payload.items.length === 0 ? (
          <p className="text-xs text-muted-foreground">No items match the current filters.</p>
        ) : (
          <div className="max-h-[600px] space-y-2 overflow-y-auto pr-1">
            {payload.items.map((w) => (
              <WorkCard key={w.id} work={w} />
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function TotalChip({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex flex-col">
      <span className={`text-2xl font-semibold tabular-nums ${tone}`}>{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

function BucketRow({ label, bucket, max }: { label: string; bucket: HistoryBucket; max: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-32 truncate font-mono text-muted-foreground" title={label}>
        {label}
      </span>
      <div className="relative h-4 flex-1 rounded bg-muted">
        <div className="h-4 rounded bg-primary/40" style={{ width: `${(bucket.total / max) * 100}%` }} />
      </div>
      <span className="w-32 text-right tabular-nums text-muted-foreground">
        {bucket.done} done · {bucket.failed} fail{bucket.retrying > 0 ? ` · ${bucket.retrying} retry` : ""}
      </span>
    </div>
  )
}
