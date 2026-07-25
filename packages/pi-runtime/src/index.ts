/**
 * @aquan/pi-runtime — Pi agent-runtime adapter for the orchestrator.
 *
 * Public API:
 *   import { PiRuntime } from "@aquan/pi-runtime"
 *   const runtime = new PiRuntime({ provider: "zai", model: "glm-4.5-air" })
 *   const orch = new Orchestrator({ runtime, trackers })
 *
 * Stage 1 (2026-07-25): backed by the real @earendil-works/pi-agent-core
 * SDK, running in-process. See
 * docs/superpowers/specs/2026-07-25-pi-runtime-integration-design.md.
 */

export { PiRuntime } from "./runtime"
export type { PiRuntimeOptions } from "./config"
export { DEFAULT_MODEL, DEFAULT_PROVIDER, resolvePiRuntimeOptions } from "./config"

export { PiSession } from "./session"
export type { PiSessionOptions } from "./session"

export { NullToolRegistration } from "./tools"
export type { ToolRegistration } from "./tools"

export { translatePiEvent, translatePiEvents } from "./events"
