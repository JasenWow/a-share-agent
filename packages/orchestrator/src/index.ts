/**
 * @aquan/orchestrator — Symphony-like work orchestration engine.
 *
 * Public API:
 *   import { Orchestrator, MemoryTracker, StubRuntime, startOrchestratorServer } from "@aquan/orchestrator"
 *
 * Phase 5: skeleton. The poll-run-record loop, in-memory state store,
 * and HTTP presenter are implemented. Pi runtime integration + real
 * trackers arrive in follow-up specs.
 */

export { Orchestrator } from "./orchestrator"
export type { OrchestratorOpts } from "./orchestrator"

export { runWork } from "./agent-runner"
export type { RunOpts, RunOutcome } from "./agent-runner"

export { StateStore } from "./state-store"

export { statePayload } from "./presenter"
export type { StatePayload } from "./presenter"

export { startOrchestratorServer } from "./http"

export type {
  AgentRuntime,
  AgentSession,
  TurnResult,
} from "./runtime"
export { StubRuntime } from "./runtime"

export {
  buildInitialPrompt,
  buildContinuationPrompt,
} from "./prompt-builder"

export { LocalWorkspaceManager } from "./workspace"
export type { WorkspaceManager } from "./workspace"

export type { Tracker, AgentToolSpec } from "./trackers/tracker"
export { MemoryTracker } from "./trackers/tracker"
export { FactorMiningTracker } from "./trackers/factor-mining"
export { FreeExplorationTracker } from "./trackers/free-exploration"
