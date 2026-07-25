/**
 * AgentRuntime — abstraction over the underlying agent backend
 * (Pi, Codex, etc). The orchestrator only knows this interface.
 *
 * Phase 5: interface only. The Pi-backed implementation lives in
 * @aquan/pi-runtime. A stub implementation is provided for tests.
 */

import type { AgentEvent } from "@aquan/core"

export interface TurnResult {
  /** "continue" = work still active, run another turn. */
  kind: "continue" | "done" | "blocked"
  /** Events observed during this turn. */
  events: AgentEvent[]
  /** Final message if the turn produced one. */
  message?: string
  /** Error if the turn failed. */
  error?: string
}

export interface AgentRuntime {
  /** Start a new session for the given workspace + work id. */
  startSession(opts: {
    workspacePath: string
    workId: string
    prompt: string
    /**
     * Trusted system prompt for runtimes that separate system/user slots
     * (e.g. PiRuntime). When omitted, runtimes should derive a sensible
     * default from `prompt` or use their own persona.
     */
    systemPrompt?: string
  }): Promise<AgentSession>

  /** Stop a previously started session, releasing resources. */
  stopSession(session: AgentSession): Promise<void>
}

export interface AgentSession {
  readonly sessionId: string
  readonly workspacePath: string

  /** Run a single turn. The first turn uses the session's initial prompt;
   *  continuation turns receive guidance built by the caller. */
  runTurn(prompt: string): Promise<TurnResult>
}

/**
 * StubRuntime — a no-op runtime used by tests and during early bootstrap.
 * It immediately reports each turn as "done" with no events.
 */
export class StubRuntime implements AgentRuntime {
  async startSession(opts: { workspacePath: string; workId: string; prompt: string }): Promise<AgentSession> {
    return {
      sessionId: `stub-${opts.workId}`,
      workspacePath: opts.workspacePath,
      runTurn: async () => ({ kind: "done", events: [] }),
    }
  }

  async stopSession(): Promise<void> {
    // no-op
  }
}
