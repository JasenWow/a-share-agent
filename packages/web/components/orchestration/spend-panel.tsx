"use client"

import { Card } from "@/components/ui/card"
import type { SpendPayload } from "@/api-clients/orchestration"

/**
 * Spend/budget panel — shows current counters against each cap with a
 * progress bar for the binding window. Caps of `null` mean unlimited
 * (bar is hidden for those windows).
 *
 * The orchestrator counts job starts (pi-dispatch model), not tokens,
 * so the labels say "jobs" not "$" or "tokens".
 */
export function SpendPanel({ spend }: { spend?: SpendPayload }) {
  if (!spend) {
    return (
      <Card className="p-4">
        <h3 className="mb-2 text-sm font-semibold">Spend</h3>
        <div className="text-xs text-muted-foreground">No SpendGuard wired into the orchestrator.</div>
      </Card>
    )
  }

  return (
    <Card className="p-4">
      <h3 className="mb-3 text-sm font-semibold">Spend (jobs)</h3>
      <div className="space-y-3 text-xs">
        <SpendRow label="Today" count={spend.daily} cap={spend.dailyCap} dayStart={spend.dayStart} />
        <SpendRow label="This week" count={spend.weekly} cap={spend.weeklyCap} dayStart={spend.weekStart} />
        <SpendRow label="This month" count={spend.monthly} cap={spend.monthlyCap} dayStart={spend.monthStart} />
      </div>
    </Card>
  )
}

function SpendRow({
  label,
  count,
  cap,
  dayStart,
}: {
  label: string
  count: number
  cap: number | null
  dayStart: string
}) {
  const isUnlimited = cap === null
  const pct = isUnlimited ? 0 : Math.min(100, Math.round((count / cap) * 100))
  const barColor =
    pct >= 100 ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-blue-500"
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums">
          <span className="font-medium">{count}</span>
          {isUnlimited ? (
            <span className="ml-1 text-muted-foreground">/ ∞</span>
          ) : (
            <span className="ml-1 text-muted-foreground">/ {cap}</span>
          )}
        </span>
      </div>
      {!isUnlimited && (
        <div className="h-1.5 w-full overflow-hidden rounded bg-muted">
          <div
            className={`h-full transition-all ${barColor}`}
            style={{ width: `${pct}%` }}
            aria-label={`${pct}% of cap used`}
          />
        </div>
      )}
      <div className="mt-0.5 text-[10px] text-muted-foreground">
        window since {formatDate(dayStart)}
      </div>
    </div>
  )
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  } catch {
    return iso
  }
}
