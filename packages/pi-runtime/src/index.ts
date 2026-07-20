/**
 * @aquan/pi-runtime — Pi agent-runtime adapter for the orchestrator.
 *
 * Public API:
 *   import { PiRuntime } from "@aquan/pi-runtime"
 *   const runtime = new PiRuntime({ workspaceRoot: ".worktrees" })
 *   const orch = new Orchestrator({ runtime, trackers })
 *
 * Phase 5: skeleton. Pi SDK calls land in a follow-up spec.
 */

export { PiRuntime } from "./runtime"
export type { PiRuntimeOptions } from "./runtime"

export { PiSession } from "./session"
export type { PiSessionOptions } from "./session"

export { NullToolRegistration } from "./tools"
export type { ToolRegistration } from "./tools"

export { translatePiEvent } from "./events"
export type { PiRawEvent } from "./events"
