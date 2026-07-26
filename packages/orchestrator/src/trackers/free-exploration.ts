/**
 * FreeExplorationTracker — emits one daily market-observation WorkItem.
 *
 * The orchestrator polls `fetchByStates(["pending", "retrying"])` on every
 * tick (cron-driven or manual). This tracker ensures today's observation
 * task exists in an in-memory map and returns it iff its current state is
 * in the requested set, giving exactly one fresh observation per day:
 *
 *   - First tick of the day → item created as "pending" → returned → run
 *   - After a successful run → updateState("done") → no longer returned
 *   - After a failure       → updateState("retrying") → returned next tick
 *
 * State is in-memory (free-exploration is ephemeral by design). A process
 * restart regenerates today's observation, which is acceptable. Idempotency
 * within a run is by date-stamped id (`free-exploration-YYYY-MM-DD`), so
 * the orchestrator's persistent store also dedupes across restarts for
 * the same date.
 */

import type { WorkItem, RunState } from "@aquan/core"
import type { Tracker, AgentToolSpec } from "./tracker"

interface TrackedItem {
  item: WorkItem
  state: RunState
  error?: string
}

export class FreeExplorationTracker implements Tracker {
  readonly name = "free-exploration"

  private items = new Map<string, TrackedItem>()

  async fetchByStates(states: RunState[]): Promise<WorkItem[]> {
    this.ensureToday()
    const out: WorkItem[] = []
    for (const v of this.items.values()) {
      if (states.includes(v.state)) out.push(v.item)
    }
    return out
  }

  async fetchById(id: string): Promise<WorkItem | undefined> {
    this.ensureToday()
    return this.items.get(id)?.item
  }

  async updateState(id: string, state: RunState, error?: string): Promise<void> {
    const existing = this.items.get(id)
    if (!existing) return
    this.items.set(id, { ...existing, state, error })
  }

  agentToolSpecs(): AgentToolSpec[] {
    // The agent invokes A-share market data via the `aquan stock` CLI
    // (quotes / kline / indices / concepts). The Pi runtime wires the
    // actual CLI-backed tools; these specs advertise them for inspection.
    return [
      {
        name: "stock",
        description: "A-share market data via `aquan stock <action>` (quotes, kline, indices, concepts, ...).",
        inputSchema: {
          type: "object",
          properties: {
            action: { type: "string", description: "stock subcommand action, e.g. quote / kline / index" },
          },
          required: ["action"],
        },
      },
    ]
  }

  /** Create today's observation task if it doesn't exist yet. */
  private ensureToday(): void {
    const today = todayLocalDate()
    const id = `free-exploration-${today}`
    if (this.items.has(id)) return
    this.items.set(id, {
      item: {
        id,
        title: `Daily market observation — ${today}`,
        type: "free-exploration",
        description:
          "Scan today's A-share market: pull the major indices (上证, 深证, 创业板) " +
          "and a few hot-concept boards via the `aquan stock` CLI, then summarize " +
          "breadth, leaders, laggards, and anything worth a deeper look tomorrow. " +
          "Keep the writeup under 200 words.",
        labels: ["daily", "observation"],
        createdAt: new Date().toISOString(),
      },
      state: "pending",
    })
  }
}

/** Local-time YYYY-MM-DD (en-CA locale yields ISO order). */
function todayLocalDate(): string {
  return new Date().toLocaleDateString("en-CA")
}
