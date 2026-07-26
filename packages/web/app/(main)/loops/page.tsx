"use client"

import useSWR from "swr"
import { getLoopsHistory, getLoopsHistoryKey } from "@/api-clients/orchestration"
import { HistoryPanel } from "@/components/orchestration/history-panel"
import { Card } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"

/**
 * /loops — historical view of orchestrator work (done / failed / retrying).
 *
 * Answers "is the system working over time?" via by-tracker and by-day
 * aggregation, plus a scrollable item list. Polls every 5s — less
 * time-sensitive than the live /orchestration three-state view.
 */
export default function LoopsPage() {
  const { data, error, isLoading } = useSWR(getLoopsHistoryKey(), getLoopsHistory, {
    refreshInterval: 5000,
    revalidateOnFocus: false,
  })

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 p-4 md:p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Loops</h1>
        <p className="text-sm text-muted-foreground">
          Historical run results across all trackers — trends and per-day throughput.
        </p>
      </header>

      {error && !data && (
        <Card className="border-red-500/40 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-300">
          <div className="font-medium">Orchestrator unreachable</div>
          <div className="mt-1 text-xs">
            Is the orchestrator server running on the expected port?{" "}
            <code className="rounded bg-red-500/10 px-1 py-0.5">
              {process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:3010"}
            </code>
          </div>
          <div className="mt-1 text-xs opacity-80">{String(error)}</div>
        </Card>
      )}

      {isLoading && !data ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading history...
        </div>
      ) : data ? (
        <HistoryPanel payload={data} />
      ) : null}
    </div>
  )
}
