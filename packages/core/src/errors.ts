/**
 * Aquan error hierarchy.
 *
 * All aquan-specific exceptions extend AquanError so callers can catch
 * the entire family with one clause. Subclasses live with the code that
 * raises them; only the base is defined here.
 */

export class AquanError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message)
    this.name = "AquanError"
  }
}

/** Raised when a tracker cannot find a WorkItem. */
export class WorkItemNotFound extends AquanError {
  constructor(workId: string) {
    super(`WorkItem not found: ${workId}`)
    this.name = "WorkItemNotFound"
  }
}

/** Raised when an agent runtime rejects or fails a turn. */
export class AgentRuntimeError extends AquanError {
  constructor(message: string, cause?: unknown) {
    super(message, cause)
    this.name = "AgentRuntimeError"
  }
}
