/**
 * Presenter — project StateStore into HTTP response shapes.
 *
 * Mirrors Symphony's Presenter.state_payload: counts + per-state lists.
 * The dashboard consumes this verbatim.
 */

import type { TrackedWork } from "@aquan/core"
import type { StateStore } from "./state-store"

export interface StatePayload {
  generatedAt: string
  counts: {
    running: number
    retrying: number
    blocked: number
    pending: number
    done: number
    failed: number
  }
  running: TrackedWork[]
  retrying: TrackedWork[]
  blocked: TrackedWork[]
  pending: TrackedWork[]
  recent: TrackedWork[]
}

export function statePayload(store: StateStore): StatePayload {
  const all = store.listAll()
  return {
    generatedAt: new Date().toISOString(),
    counts: {
      running: count(all, "running"),
      retrying: count(all, "retrying"),
      blocked: count(all, "blocked"),
      pending: count(all, "pending"),
      done: count(all, "done"),
      failed: count(all, "failed"),
    },
    running: filter(all, "running"),
    retrying: filter(all, "retrying"),
    blocked: filter(all, "blocked"),
    pending: filter(all, "pending"),
    recent: all
      .slice()
      .sort((a, b) => (b.stateChangedAt ?? "").localeCompare(a.stateChangedAt ?? ""))
      .slice(0, 20),
  }
}

function count(items: TrackedWork[], state: TrackedWork["state"]): number {
  return items.filter((w) => w.state === state).length
}

function filter(items: TrackedWork[], state: TrackedWork["state"]): TrackedWork[] {
  return items.filter((w) => w.state === state)
}
