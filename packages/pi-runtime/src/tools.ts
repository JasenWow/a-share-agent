/**
 * MCP tool exposure to the Pi agent.
 *
 * The orchestrator's trackers declare which tools their WorkItems need
 * (via Tracker.agentToolSpecs()). The pi-runtime is responsible for
 * registering those tools with the Pi SDK so the agent can invoke them
 * during a turn.
 *
 * Phase 5: stub. The concrete registration lands once the Pi SDK's
 * tool-registration API is verified.
 */

import type { AgentToolSpec } from "@aquan/orchestrator"

/** Registered tools for a single Pi session. */
export interface ToolRegistration {
  specs: AgentToolSpec[]
  /** Invoke a registered tool by name. */
  invoke(name: string, args: Record<string, unknown>): Promise<unknown>
}

/** No-op tool registration used during bootstrap. */
export class NullToolRegistration implements ToolRegistration {
  constructor(readonly specs: AgentToolSpec[] = []) {}

  async invoke(): Promise<unknown> {
    throw new Error("NullToolRegistration: no tools are wired up yet")
  }
}
