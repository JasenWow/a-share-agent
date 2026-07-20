/**
 * PromptBuilder — turn an WorkItem into the agent's initial prompt,
 * and continuation prompts for follow-up turns.
 */

import type { WorkItem } from "@aquan/core"

/** Initial prompt for turn #1 of a run. */
export function buildInitialPrompt(work: WorkItem): string {
  const label = work.labels?.length ? `\nLabels: ${work.labels.join(", ")}` : ""
  return [
    `# Task: ${work.title}`,
    ``,
    work.description,
    ``,
    `Work type: ${work.type}`,
    `Workspace: ${work.workspace?.path ?? "(none)"}`,
    label,
  ]
    .filter((line) => line.length > 0)
    .join("\n")
}

/**
 * Continuation prompt for turns 2..N of a run. Mirrors Symphony's
 * continuation guidance: the previous turn finished normally but the
 * WorkItem is still active, so resume rather than restart.
 */
export function buildContinuationPrompt(turnNumber: number, maxTurns: number): string {
  return [
    `Continuation guidance:`,
    ``,
    `- The previous turn completed normally, but the WorkItem is still active.`,
    `- This is continuation turn #${turnNumber} of ${maxTurns}.`,
    `- Resume from the current workspace and prior turn context.`,
    `- Focus on the remaining work. Do not end the turn while the task is`,
    `  still active unless you are truly blocked.`,
  ].join("\n")
}
