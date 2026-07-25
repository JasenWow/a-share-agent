/**
 * PiSession — AgentSession implementation backed by a real Pi SDK Agent.
 *
 * Lifecycle:
 *   - One PiSession owns one Agent (1:1).
 *   - runTurn(prompt) calls agent.prompt(prompt) + waitForIdle(), letting
 *     the SDK drive its internal turn loop. We do NOT loop externally
 *     (orchestrator's outer for-loop sees a single "done" and exits).
 *   - maxTurns is enforced via an AbortController: we count turn_end
 *     events in the subscriber and abort() when the cap is reached.
 *     This mirrors pi-dispatch's hard-stop philosophy.
 *
 * Why not the SDK's shouldStopAfterTurn hook:
 *   - Current AgentOptions does not expose loopConfig in the public .d.ts
 *   - AbortController is more portable and gives us synchronous control
 */

import type { AgentEvent as AquanAgentEvent } from "@aquan/core"
import type { AgentEvent as PiAgentEvent, Agent } from "@earendil-works/pi-agent-core"
import type { AgentSession, TurnResult } from "@aquan/orchestrator"
import { contentText } from "@earendil-works/pi-ai"
import { translatePiEvent } from "./events"

export interface PiSessionOptions {
  /** A constructed Pi SDK Agent (PiRuntime creates this). */
  agent: Agent
  /** Stable id for this session (used by dashboard + logs). */
  sessionId: string
  /** Per-session workspace path (informational; SDK does not enforce). */
  workspacePath: string
  /** Hard cap on turns per runTurn() call. */
  maxTurnsPerRun: number
}

export class PiSession implements AgentSession {
  readonly sessionId: string
  readonly workspacePath: string
  private readonly agent: Agent
  private readonly maxTurnsPerRun: number

  constructor(opts: PiSessionOptions) {
    this.agent = opts.agent
    this.sessionId = opts.sessionId
    this.workspacePath = opts.workspacePath
    this.maxTurnsPerRun = opts.maxTurnsPerRun
  }

  async runTurn(prompt: string): Promise<TurnResult> {
    const events: AquanAgentEvent[] = []
    let turnCount = 0
    let aborted = false

    const unsubscribe = this.agent.subscribe((event: PiAgentEvent) => {
      const translated = translatePiEvent(event)
      if (translated) events.push(translated)

      if (event.type === "turn_end") {
        turnCount += 1
        if (turnCount >= this.maxTurnsPerRun) {
          // Hard stop: do not let the SDK start another turn.
          aborted = true
          this.agent.abort()
        }
      }
    })

    try {
      await this.agent.prompt(prompt)
      await this.agent.waitForIdle()
    } catch (err) {
      // An abort we initiated surfaces as an error; treat as normal stop.
      if (aborted) {
        return {
          kind: "done",
          events,
          message: `[pi-runtime] hit maxTurnsPerRun=${this.maxTurnsPerRun}`,
        }
      }
      return {
        kind: "done",
        events,
        error: err instanceof Error ? err.message : String(err),
      }
    } finally {
      unsubscribe()
    }

    // Extract the final assistant message text (if any).
    const messages = this.agent.state.messages
    const lastMessage = messages.length > 0 ? messages[messages.length - 1] : undefined
    const messageText = lastMessage ? extractText(lastMessage) : undefined

    return {
      kind: "done",
      events,
      message: messageText,
    }
  }
}

function extractText(message: unknown): string | undefined {
  if (!message || typeof message !== "object") return undefined
  const msg = message as { content?: unknown }
  // contentText takes the content field (array of blocks), not the whole message.
  const content = msg.content
  if (typeof content === "string") return content.length > 0 ? content : undefined
  if (!Array.isArray(content)) return undefined
  try {
    const text = contentText(content as never)
    return typeof text === "string" && text.length > 0 ? text : undefined
  } catch {
    return undefined
  }
}
