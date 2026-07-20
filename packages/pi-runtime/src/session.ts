/**
 * PiSession — AgentSession implementation backed by the Pi SDK.
 *
 * Phase 5: skeleton. runTurn is stubbed to return immediately; the
 * concrete Pi SDK calls land once the upstream API surface is verified.
 */

import type { AgentSession, TurnResult } from "@aquan/orchestrator"
import type { ToolRegistration } from "./tools"

export interface PiSessionOptions {
  workId: string
  workspacePath: string
  initialPrompt: string
  tools: ToolRegistration
}

export class PiSession implements AgentSession {
  readonly sessionId: string
  readonly workspacePath: string
  private readonly initialPrompt: string
  private readonly tools: ToolRegistration
  private turnCount = 0

  constructor(opts: PiSessionOptions) {
    this.sessionId = `pi-${opts.workId}`
    this.workspacePath = opts.workspacePath
    this.initialPrompt = opts.initialPrompt
    this.tools = opts.tools
  }

  async runTurn(prompt: string): Promise<TurnResult> {
    this.turnCount++
    // TODO(phase-5-followup): hand off to pi-agent-core.
    // For now, signal "done" immediately so the orchestrator's turn loop
    // exits cleanly during bootstrap.
    void this.initialPrompt
    void this.tools
    void prompt
    return {
      kind: "done",
      events: [],
      message: "[pi-runtime stub] turn completed",
    }
  }
}
