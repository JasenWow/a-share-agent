"use client"

import useSWR from "swr"
import {
  getOrchestrationSchedules,
  getOrchestrationSchedulesKey,
  getOrchestrationState,
  getOrchestrationStateKey,
  triggerTick,
} from "@/api-clients/orchestration"
import { StateOverview } from "@/components/orchestration/state-overview"
import { WorkList } from "@/components/orchestration/work-list"
import { SchedulerPanel } from "@/components/orchestration/scheduler-panel"
import { SpendPanel } from "@/components/orchestration/spend-panel"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "sonner"

/**
 * /orchestration — Symphony-style three-state dashboard.
 *
 * Polls the orchestrator server every 2s for state and every 5s for
 * schedules. Layout:
 *   - Top:    state count cards (running / retrying / blocked / ...)
 *   - Middle: left = work lists grouped by state, right = spend + scheduler panels
 *   - Bottom: manual tick button (dev tool — fires orchestrator.tick() once)
 *
 * The orchestrator server lives on :3010 by default; override with
 * NEXT_PUBLIC_ORCHESTRATOR_URL. If it's down, SWR surfaces a friendly
 * "unreachable" banner instead of crashing.
 */
export default function OrchestrationPage() {
  const {
    data: state,
    error: stateError,
    isLoading: stateLoading,
    mutate: mutateState,
  } = useSWR(getOrchestrationStateKey(), getOrchestrationState, {
    refreshInterval: 2000,
    revalidateOnFocus: false,
  })

  const { data: sched, mutate: mutateSched } = useSWR(
    getOrchestrationSchedulesKey(),
    getOrchestrationSchedules,
    { refreshInterval: 5000, revalidateOnFocus: false },
  )

  async function onManualTick() {
    try {
      const outcome = await triggerTick()
      toast.success(`Tick ran ${outcome.ran} work item(s)`)
      mutateState()
      mutateSched()
    } catch (e) {
      toast.error(`Tick failed: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 p-4 md:p-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Orchestration</h1>
          <p className="text-sm text-muted-foreground">
            Live view of agent work items across all trackers.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onManualTick} disabled={stateLoading}>
          Run tick now
        </Button>
      </header>

      {stateError && !state && (
        <Card className="border-red-500/40 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-300">
          <div className="font-medium">Orchestrator unreachable</div>
          <div className="mt-1 text-xs">
            Is the orchestrator server running on the expected port?
            {" "}
            <code className="rounded bg-red-500/10 px-1 py-0.5">
              {process.env.NEXT_PUBLIC_ORCHESTRATOR_URL || "http://localhost:3010"}
            </code>
          </div>
          <div className="mt-1 text-xs opacity-80">{String(stateError)}</div>
        </Card>
      )}

      {stateLoading && !state ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading orchestrator state...
        </div>
      ) : state ? (
        <>
          <StateOverview counts={state.counts} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
            <div className="space-y-4">
              <WorkList
                running={state.running}
                retrying={state.retrying}
                blocked={state.blocked}
                pending={state.pending}
                recent={state.recent}
              />
            </div>
            <aside className="space-y-4">
              <SpendPanel spend={state.spend} />
              <SchedulerPanel
                schedules={sched?.schedules ?? state.schedules ?? []}
                running={sched?.running ?? false}
              />
              <Card className="p-3 text-[10px] text-muted-foreground">
                <div>generatedAt: {state.generatedAt}</div>
                <div>polling: 2s (state) · 5s (schedules)</div>
              </Card>
            </aside>
          </div>
        </>
      ) : null}
    </div>
  )
}
