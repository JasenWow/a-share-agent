/**
 * FreeExplorationTracker — free-exploration work source.
 *
 * Generates one WorkItem per scheduled tick (e.g. end-of-trading-day)
 * asking the agent to observe the market and report findings. Phase 5
 * stub: returns empty until the cron schedule + observation schema land.
 */

import type { WorkItem } from "@aquan/core"
import type { Tracker, AgentToolSpec } from "./tracker"

export class FreeExplorationTracker implements Tracker {
  readonly name = "free-exploration"

  async fetchByStates(): Promise<WorkItem[]> {
    // TODO(phase-5-followup): emit a daily observation task when scheduled.
    return []
  }

  async fetchById(): Promise<WorkItem | undefined> {
    return undefined
  }

  async updateState(): Promise<void> {
    // Free-exploration tasks are ephemeral — no persisted state.
  }

  agentToolSpecs(): AgentToolSpec[] {
    // TODO(phase-5-followup): expose market-breadth, hot-concepts, northbound tools.
    return []
  }
}
