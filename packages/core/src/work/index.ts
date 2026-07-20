/**
 * Work domain — types for orchestration: WorkItem, RunState, AgentEvent.
 *
 * This module is the contract between:
 * - trackers (produce WorkItems)
 * - orchestrator (manages RunState)
 * - pi-runtime (emits AgentEvents)
 * - web dashboard (renders TrackedWork)
 *
 * Kept dependency-free so all four layers can import it without cycles.
 */

export * from "./work-item"
export * from "./agent-event"
