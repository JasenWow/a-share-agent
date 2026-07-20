/**
 * Tracker — source of WorkItems for the orchestrator.
 *
 * A tracker knows how to discover work the system should do. Different
 * work types plug in different trackers:
 * - sedimentation (factor mining, strategy hypothesis testing)
 * - free-exploration (market observation, opportunity scan)
 *
 * Modeled on Symphony's Tracker behaviour but tracker-implementation
 * agnostic.
 */

import type { WorkItem, RunState } from "@aquan/core"

export interface Tracker {
  /** Human-readable name for logging and dashboard display. */
  readonly name: string

  /** Discover WorkItems in the given states. */
  fetchByStates(states: RunState[]): Promise<WorkItem[]>

  /** Fetch a specific WorkItem by id. */
  fetchById(id: string): Promise<WorkItem | undefined>

  /**
   * Update a WorkItem's state after a run completes / retries / blocks.
   * Trackers that persist state (e.g. a database-backed one) write here.
   */
  updateState(id: string, state: RunState, error?: string): Promise<void>

  /**
   * Return agent tool specs this tracker's WorkItems need. The runtime
   * uses these to expose the right tools to the agent. Empty by default.
   */
  agentToolSpecs(): AgentToolSpec[]
}

/** Spec for a tool the agent can call during a turn. */
export interface AgentToolSpec {
  name: string
  description: string
  /** JSON schema for the tool's arguments. */
  inputSchema: Record<string, unknown>
}

/**
 * MemoryTracker — minimal in-memory implementation used for tests and
 * bootstrapping. Real trackers (factor-mining, free-exploration) build
 * on this contract.
 */
export class MemoryTracker implements Tracker {
  readonly name = "memory"
  private items = new Map<string, WorkItem & { state: RunState; error?: string }>()

  seed(items: Array<WorkItem & { state?: RunState }>): void {
    for (const item of items) {
      this.items.set(item.id, { ...item, state: item.state ?? "pending" })
    }
  }

  async fetchByStates(states: RunState[]): Promise<WorkItem[]> {
    return [...this.items.values()].filter((i) => states.includes(i.state))
  }

  async fetchById(id: string): Promise<WorkItem | undefined> {
    const found = this.items.get(id)
    return found ? { ...found } : undefined
  }

  async updateState(id: string, state: RunState, error?: string): Promise<void> {
    const existing = this.items.get(id)
    if (!existing) throw new Error(`MemoryTracker: unknown id ${id}`)
    this.items.set(id, { ...existing, state, error })
  }

  agentToolSpecs(): AgentToolSpec[] {
    return []
  }
}
