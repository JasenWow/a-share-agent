/**
 * AgentRunner — execute a single WorkItem through the agent runtime.
 *
 * Owns the per-WorkItem turn loop (the innermost of the three layers
 * described in the orchestration vision):
 *   - turn 1: initial prompt built from the WorkItem
 *   - turn 2..N: continuation guidance
 *   - stops on: done | blocked | max turns | fatal error
 *
 * Mirrors Symphony's AgentRunner.do_run_codex_turns shape but with
 * a pluggable AgentRuntime instead of hard-coded Codex.
 */

import type { TrackedWork, RunState, AgentEvent } from "@aquan/core"
import type { AgentRuntime, AgentSession, TurnResult } from "./runtime"
import { buildInitialPrompt, buildContinuationPrompt } from "./prompt-builder"

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
}

/** Execute one WorkItem attempt. Returns the final state + collected events. */
export async function runWork(
  runtime: AgentRuntime,
  work: TrackedWork,
  opts: RunOpts = {},
): Promise<RunOutcome> {
  const maxTurns = opts.maxTurns ?? 20
  const prompt = buildInitialPrompt(work)

  const session: AgentSession = await runtime.startSession({
    workspacePath: work.workspace?.path ?? "(in-memory)",
    workId: work.id,
    prompt,
  })

  const events: AgentEvent[] = []
  let turnCount = 0
  let lastResult: TurnResult | undefined

  try {
    for (let turn = 1; turn <= maxTurns; turn++) {
      const turnPrompt = turn === 1 ? prompt : buildContinuationPrompt(turn, maxTurns)
      lastResult = await session.runTurn(turnPrompt)
      events.push(...lastResult.events)
      turnCount = turn

      if (lastResult.kind === "done") break
      if (lastResult.kind === "blocked") break
      // "continue" -> loop again
    }
  } catch (err) {
    return {
      state: "failed",
      events,
      turnCount,
      error: err instanceof Error ? err.message : String(err),
    }
  } finally {
    await runtime.stopSession(session)
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
  }
}
