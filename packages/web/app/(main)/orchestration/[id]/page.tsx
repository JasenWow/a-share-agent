"use client"

import { useParams, useRouter } from "next/navigation"
import useSWR from "swr"
import {
  getOrchestrationWork,
  getOrchestrationWorkEvents,
  getOrchestrationWorkEventsKey,
  getOrchestrationWorkKey,
} from "@/api-clients/orchestration"
import { EventTimeline } from "@/components/orchestration/event-timeline"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"

/**
 * /orchestration/[id] — single work-item detail with its event timeline.
 *
 * Polls the work item (3s) and its events (3s) so you can watch the agent
 * work in real time. Reached by clicking any WorkCard on the orchestration
 * dashboard or the loops history view.
 */
export default function WorkDetailPage() {
  const params = useParams<{ id: string }>()
  const router = useRouter()
  const id = decodeURIComponent(params.id)

  const {
    data: work,
    error: workError,
    isLoading: workLoading,
  } = useSWR(getOrchestrationWorkKey(id), () => getOrchestrationWork(id), {
    refreshInterval: 3000,
    revalidateOnFocus: false,
  })

  const { data: eventsPayload } = useSWR(
    getOrchestrationWorkEventsKey(id),
    () => getOrchestrationWorkEvents(id),
    { refreshInterval: 3000, revalidateOnFocus: false },
  )

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 p-4 md:p-6">
      <header className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          ← Back
        </Button>
        <div className="min-w-0">
          <h1 className="truncate font-mono text-lg font-semibold" title={id}>
            {id}
          </h1>
          {work && (
            <p className="text-xs text-muted-foreground">
              state: <span className="font-medium">{work.state}</span>
              {work.turnCount != null && <> · turn {work.turnCount}</>}
              {work.attempt != null && <> · attempt {work.attempt}</>}
              {work.lastEventAt && <> · last {work.lastEventAt.slice(11, 19)}</>}
            </p>
          )}
        </div>
      </header>

      {workError && !work && (
        <Card className="border-red-500/40 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-300">
          Work item not found, or the orchestrator is unreachable.
        </Card>
      )}

      {workLoading && !work ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Loading work item...
        </div>
      ) : work ? (
        <>
          {work.lastMessage && (
            <Card className="p-4 text-sm">
              <div className="mb-1 text-xs font-medium text-muted-foreground">Last message</div>
              <div className="whitespace-pre-wrap break-words">{work.lastMessage}</div>
            </Card>
          )}
          {work.error && (
            <Card className="border-red-500/40 bg-red-500/5 p-4 text-sm text-red-600 dark:text-red-300">
              <div className="mb-1 text-xs font-medium">Error</div>
              <div className="whitespace-pre-wrap break-words">{work.error}</div>
            </Card>
          )}

          <div>
            <h2 className="mb-2 text-sm font-medium">
              Event timeline{eventsPayload ? ` (${eventsPayload.count})` : ""}
            </h2>
            <EventTimeline events={eventsPayload?.events ?? []} />
          </div>
        </>
      ) : null}
    </div>
  )
}
