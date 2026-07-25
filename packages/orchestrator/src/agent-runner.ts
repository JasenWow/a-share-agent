/**
 * AgentRunner — execute a single WorkItem through the agent runtime.
 *
 * Owns the per-WorkItem turn loop (the innermost of the three layers
 * described in the orchestration vision):
 *   - turn 1: initial prompt built from the WorkItem
 *   - turn 2..N: continuation guidance
 *   - stops on: done | blocked | max turns | fatal error
 *
 * Hardening (2026-07-25): mirrors pi-dispatch's `maxStalledCount: 0`.
 * A turn that throws is treated as a fatal infra failure for this
 * attempt — we do NOT silently retry the same turn. The RetryPolicy
 * at the orchestrator layer decides whether to start a fresh attempt,
 * and only for infra errors (agent "done"/"blocked" never retry).
 */

import type { AgentEvent, RunState, TrackedWork } from "@aquan/core"
import type { AgentRuntime, AgentSession, TurnResult } from "./runtime"
import {
  buildContinuationPrompt,
  buildInitialPrompt,
  buildInitialPromptParts,
} from "./prompt-builder"

export interface RunOpts {
  /** Max turns per WorkItem attempt (default 20, matches Symphony). */
  maxTurns?: number
}

export interface RunOutcome {
  state: RunState
  events: AgentEvent[]
  turnCount: number
  message?: string
  error?: string
  /**
   * "infra" if the run failed due to runtime/transport error → eligible
   * for retry per RetryPolicy. "agent" if the agent itself returned
   * done/blocked/failed → not retried. Mirrors pi-dispatch rule.
   */
  failureKind?: "infra" | "agent"
}

/** Execute one WorkItem attempt. Returns the final state + collected events. */
export async function runWork(
  runtime: AgentRuntime,
  work: TrackedWork,
  opts: RunOpts = {},
): Promise<RunOutcome> {
  const maxTurns = opts.maxTurns ?? 20
  // Build the two-slot prompt so runtimes that separate system/user slots
  // (PiRuntime) can isolate untrusted content per hardening iron rule 1.
  // The legacy single-string form is used for runTurn continuation inputs.
  const parts = buildInitialPromptParts(work)
  const prompt = buildInitialPrompt(work)

  let session: AgentSession
  try {
    session = await runtime.startSession({
      workspacePath: work.workspace?.path ?? "(in-memory)",
      workId: work.id,
      prompt,
      systemPrompt: parts.system,
    })
  } catch (err) {
    return {
      state: "failed",
      events: [],
      turnCount: 0,
      error: err instanceof Error ? err.message : String(err),
      failureKind: "infra",
    }
  }

  const events: AgentEvent[] = []
  let turnCount = 0
  let lastResult: TurnResult | undefined

  try {
    for (let turn = 1; turn <= maxTurns; turn++) {
      const turnPrompt = turn === 1 ? prompt : buildContinuationPrompt(turn, maxTurns)
      // Hardening: a turn throwing is fatal for this attempt. Do not
      // catch-and-retry-in-loop — that would silently burn the turn budget.
      lastResult = await session.runTurn(turnPrompt)
      events.push(...lastResult.events)
      turnCount = turn

      if (lastResult.kind === "done") break
      if (lastResult.kind === "blocked") break
      // "continue" -> loop again
    }
  } catch (err) {
    // Infra failure (transport, runtime crash, etc.). Return immediately
    // with failureKind="infra" so RetryPolicy can decide.
    return {
      state: "failed",
      events,
      turnCount,
      error: err instanceof Error ? err.message : String(err),
      failureKind: "infra",
    }
  } finally {
    try {
      await runtime.stopSession(session)
    } catch {
      // stopSession failures are best-effort; don't mask the original outcome.
    }
  }

  const state: RunState =
    lastResult?.kind === "blocked"
      ? "blocked"
      : lastResult?.kind === "done"
        ? "done"
        : "done" // reached maxTurns without explicit done
  return {
    state,
    events,
    turnCount,
    message: lastResult?.message,
    error: lastResult?.error,
    // done/blocked/maxTurns are all "agent" decisions — not eligible for retry.
    failureKind: state === "failed" ? "agent" : undefined,
  }
}
