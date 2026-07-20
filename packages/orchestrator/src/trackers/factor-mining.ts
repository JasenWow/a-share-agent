/**
 * FactorMiningTracker — sedimentation work source.
 *
 * Pulls pending factor-mining hypotheses from the internal-store MCP
 * server and surfaces them as WorkItems. Phase 5 stub: returns empty
 * until the factor-mining backlog schema is finalized.
 */

import type { WorkItem } from "@aquan/core"
import type { Tracker, AgentToolSpec } from "./tracker"

export class FactorMiningTracker implements Tracker {
  readonly name = "factor-mining"

  async fetchByStates(): Promise<WorkItem[]> {
    // TODO(phase-5-followup): query internal-store MCP for pending hypotheses.
    return []
  }

  async fetchById(): Promise<WorkItem | undefined> {
    return undefined
  }

  async updateState(): Promise<void> {
    // TODO(phase-5-followup): write state back to internal-store.
  }

  agentToolSpecs(): AgentToolSpec[] {
    // TODO(phase-5-followup): expose factor-mine, backtest, persist-experiment tools.
    return []
  }
}
