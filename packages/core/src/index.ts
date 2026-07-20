/**
 * @aquan/core — shared types, errors, constants, and utils.
 *
 * The dependency-free foundation of the aquan TS codebase. Everything
 * else (server, web, orchestrator, pi-runtime) may depend on core;
 * core depends on nothing internal.
 *
 * Composition:
 * - types/      domain type definitions (market, backtest, ai, auth, ...)
 * - work/       orchestration types (WorkItem, RunState, AgentEvent)
 * - constants/  AI providers, ports, run-state display metadata
 * - errors.ts   AquanError hierarchy
 * - utils/      pure date/id helpers
 */

export * from "./types"
export * from "./work"
export * from "./constants"
export * from "./errors"
export * from "./utils"
