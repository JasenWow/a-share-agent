/**
 * SessionExpander — expand a [start, end] trading-session range into the
 * ordered list of trading sessions it contains.
 *
 * The control plane depends on this interface, not on any concrete
 * calendar. Tests inject a static expander; production wires the XSHG
 * calendar (PR3-B candidate). Backfill scope validation and admission
 * both consume the expanded list.
 */

export interface SessionExpander {
  /**
   * Expand an inclusive [startSession, endSession] range into the ordered
   * list of trading sessions (YYYY-MM-DD, ascending).
   *
   * Both bounds must be trading sessions in the underlying calendar; if a
   * bound is not a trading session, implementations should throw.
   */
  expand(startSession: string, endSession: string): string[]
}

/** Hand-curated expander for deterministic tests. */
export class StaticSessionExpander implements SessionExpander {
  private readonly sessions: string[]

  constructor(sessions: string[]) {
    this.sessions = [...sessions].sort()
  }

  expand(startSession: string, endSession: string): string[] {
    const startIdx = this.sessions.indexOf(startSession)
    const endIdx = this.sessions.indexOf(endSession)
    if (startIdx === -1) {
      throw new Error(`StaticSessionExpander: '${startSession}' is not a known trading session`)
    }
    if (endIdx === -1) {
      throw new Error(`StaticSessionExpander: '${endSession}' is not a known trading session`)
    }
    if (startIdx > endIdx) {
      throw new Error(
        `StaticSessionExpander: start '${startSession}' is after end '${endSession}'`,
      )
    }
    return this.sessions.slice(startIdx, endIdx + 1)
  }
}