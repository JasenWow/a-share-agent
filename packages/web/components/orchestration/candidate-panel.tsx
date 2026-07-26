"use client"

import { useState } from "react"
import useSWR from "swr"
import {
  getCandidatesKey,
  getCandidates,
  promoteCandidate,
  rejectCandidate,
} from "@/api-clients/orchestration"
import type { CandidateFactor } from "@/api-clients/orchestration"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { toast } from "sonner"

/**
 * CandidatePanel — the human half of the half-automatic feedback loop.
 *
 * Shows factor candidates the agent has persisted (status='candidate'),
 * with Promote (→ active) and Reject (→ rejected) actions. Polls every
 * 5s; promote/reject revalidates immediately. Embeds in the /orchestration
 * page's right aside.
 */
export function CandidatePanel() {
  const { data, mutate } = useSWR(getCandidatesKey(), getCandidates, {
    refreshInterval: 5000,
    revalidateOnFocus: false,
  })
  const [busyId, setBusyId] = useState<number | null>(null)

  async function onPromote(c: CandidateFactor) {
    setBusyId(c.id)
    try {
      const res = await promoteCandidate(c.id)
      if (res.ok) {
        toast.success(`Promoted "${c.name}" to active`)
        mutate()
      } else {
        toast.error(`Promote failed: ${res.error ?? "unknown"}`)
      }
    } catch (e) {
      toast.error(`Promote failed: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setBusyId(null)
    }
  }

  async function onReject(c: CandidateFactor) {
    setBusyId(c.id)
    try {
      const res = await rejectCandidate(c.id)
      if (res.ok) {
        toast.success(`Rejected "${c.name}"`)
        mutate()
      } else {
        toast.error(`Reject failed: ${res.error ?? "unknown"}`)
      }
    } catch (e) {
      toast.error(`Reject failed: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setBusyId(null)
    }
  }

  const candidates = data?.candidates ?? []
  const source = data?.source ?? "unavailable"

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-medium">
          Candidates
          {candidates.length > 0 && (
            <Badge variant="secondary" className="ml-2">
              {candidates.length}
            </Badge>
          )}
        </h3>
        {source === "unavailable" && (
          <span className="text-[10px] text-muted-foreground">internal-store offline</span>
        )}
      </div>

      {candidates.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          {source === "unavailable"
            ? "Connect internal-store to review agent-produced factors."
            : "No candidates awaiting review."}
        </p>
      ) : (
        <div className="space-y-2">
          {candidates.map((c) => (
            <div key={c.id} className="rounded border p-2 text-xs">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium" title={c.name}>
                    {c.name}
                  </div>
                  <div className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground" title={c.expression}>
                    {c.expression}
                  </div>
                  <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                    {typeof c.ic === "number" && <span>ic {c.ic.toFixed(3)}</span>}
                    {typeof c.icir === "number" && <span>icir {c.icir.toFixed(2)}</span>}
                    {typeof c.confidence === "number" && (
                      <span>conf {c.confidence.toFixed(2)}</span>
                    )}
                    {c.universe && <span>{c.universe}</span>}
                  </div>
                  {c.rationale && (
                    <div className="mt-1 line-clamp-2 text-[10px] italic text-muted-foreground" title={c.rationale}>
                      “{c.rationale}”
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-2 flex gap-1.5">
                <Button
                  size="sm"
                  className="h-6 px-2 text-[11px]"
                  onClick={() => onPromote(c)}
                  disabled={busyId !== null}
                >
                  Promote
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  className="h-6 px-2 text-[11px]"
                  onClick={() => onReject(c)}
                  disabled={busyId !== null}
                >
                  Reject
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
