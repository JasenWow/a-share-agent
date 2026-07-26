/**
 * @aquan/orchestrator — Symphony-like work orchestration engine.
 *
 * Public API:
 *   import { Orchestrator, MemoryTracker, StubRuntime, startOrchestratorServer } from "@aquan/orchestrator"
 *
 * Phase 5: skeleton. The poll-run-record loop, in-memory state store,
 * and HTTP presenter are implemented.
 * Hardening (2026-07-25): SpendGuard + ConcurrencyGate bound what an
 * agent run can do before any provider call. See hardening spec.
 */

export { Orchestrator } from "./orchestrator"
export type { OrchestratorOpts, TickOutcome, TickOptions } from "./orchestrator"

export { runWork } from "./agent-runner"
export type { RunOpts, RunOutcome } from "./agent-runner"

export { StateStore } from "./state-store"
export type { IStateStore } from "./state-store"
export { SqliteStateStore } from "./sqlite-store"
export type { SqliteStateStoreOptions } from "./sqlite-store"

export { statePayload } from "./presenter"
export type { StatePayload } from "./presenter"

export { startOrchestratorServer } from "./http"
export type { OrchestratorHttpOptions } from "./http"

// Internal-store reader (read-only view of factor_library for dedup + dashboard)
export { InternalStoreReader } from "./internal-store-reader"
export type { CandidateFactor } from "./internal-store-reader"

export type {
  AgentRuntime,
  AgentSession,
  TurnResult,
} from "./runtime"
export { StubRuntime } from "./runtime"

export {
  buildInitialPrompt,
  buildInitialPromptParts,
  buildContinuationPrompt,
} from "./prompt-builder"
export type { PromptParts } from "./prompt-builder"

export { LocalWorkspaceManager } from "./workspace"
export type { WorkspaceManager } from "./workspace"

// Hardening exports
export { SpendGuard, ConcurrencyGate } from "./policy"
export type { SpendCheckResult, SpendRejectReason, SpendStats } from "./policy"
export { PersistedSpendGuard } from "./persisted-spend-guard"

// Scheduling exports (Stage 3)
export { Scheduler } from "./scheduler"
export type { ScheduleSpec, SchedulerLogger } from "./scheduler"

export type { Tracker, AgentToolSpec } from "./trackers/tracker"
export { MemoryTracker } from "./trackers/tracker"
export { FactorMiningTracker } from "./trackers/factor-mining"
export { FreeExplorationTracker } from "./trackers/free-exploration"
