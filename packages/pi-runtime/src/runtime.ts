/**
 * PiRuntime — AgentRuntime backed by the Pi SDK.
 *
 * Phase 5: skeleton. startSession returns a PiSession; the Pi SDK
 * wiring (transport + extensions + state management) lands in a
 * follow-up spec.
 */

import type { AgentRuntime, AgentSession } from "@aquan/orchestrator"
import { PiSession } from "./session"
import { NullToolRegistration } from "./tools"

export interface PiRuntimeOptions {
  /** Workspace root under which per-WorkItem directories are created. */
  workspaceRoot: string
}

export class PiRuntime implements AgentRuntime {
  constructor(private readonly opts: PiRuntimeOptions) {}

  async startSession(args: {
    workspacePath: string
    workId: string
    prompt: string
  }): Promise<AgentSession> {
    // TODO(phase-5-followup): create the workspace dir, register tools,
    // attach Pi extensions, and return a session bound to pi-agent-core.
    return new PiSession({
      workId: args.workId,
      workspacePath: args.workspacePath,
      initialPrompt: args.prompt,
      tools: new NullToolRegistration(),
    })
  }

  async stopSession(): Promise<void> {
    // TODO(phase-5-followup): release Pi session / transport.
    void this.opts
  }
}
