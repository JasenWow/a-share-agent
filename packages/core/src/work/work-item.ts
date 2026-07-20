/**
 * WorkItem — the unit of work the orchestrator schedules and tracks.
 *
 * Maps to Symphony's `Issue` concept but is work-type agnostic:
 * a sedimentation task (factor mining) and a free-exploration task
 * (market observation) both produce a WorkItem.
 */

/** The two work types the system runs. */
export type WorkType = "sedimentation" | "free-exploration"

/**
 * RunState — lifecycle of a WorkItem inside the orchestrator.
 * Modeled on Symphony's three-state view (running / retrying / blocked)
 * plus terminal states.
 */
export type RunState =
  | "pending" // queued, not yet picked up
  | "running" // agent is actively working
  | "retrying" // failed, waiting before next attempt
  | "blocked" // agent needs human input or external dependency
  | "done" // finished successfully
  | "failed" // exhausted retries or unrecoverable error

/** A single WorkItem as scheduled by a tracker. */
export interface WorkItem {
  /** Stable unique id (e.g. "factor-mine-2026-07-20-momentum"). */
  id: string
  /** Human-readable label for dashboard display. */
  title: string
  /** Which work family this belongs to. */
  type: WorkType
  /** Full prompt or task description handed to the agent. */
  description: string
  /** Tracker-specific priority (lower = higher). */
  priority?: number
  /** Labels for filtering on the dashboard. */
  labels?: string[]
  /** Where to find / how to do the work (repo path, MCP tool, etc.). */
  workspace?: {
    path: string
    host?: string
  }
  /** When the tracker created this WorkItem (ISO8601). */
  createdAt: string
}

/** WorkItem plus its current run state — what the dashboard renders. */
export interface TrackedWork extends WorkItem {
  state: RunState
  /** Current attempt number (1 = first try). */
  attempt: number
  /** Session id assigned by the agent runtime. */
  sessionId?: string
  /** Number of agent turns completed in the current attempt. */
  turnCount?: number
  /** When the current run started (ISO8601). */
  startedAt?: string
  /** When the last agent event was observed (ISO8601). */
  lastEventAt?: string
  /** Last event type from the agent (e.g. "tool_call", "message"). */
  lastEvent?: string
  /** Humanized last message from the agent. */
  lastMessage?: string
  /** When the run entered its current state (ISO8601). */
  stateChangedAt?: string
  /** Most recent error if state is retrying/blocked/failed. */
  error?: string
}
