/**
 * TradingCalendar — system boundary around exchange_calendars (XSHG).
 *
 * Tests inject a fake implementation. Production wires the real
 * Python-backed (or in-process Node) calendar. The control plane
 * only depends on this interface.
 */

export interface TradingCalendar {
  /** Whether the given YYYY-MM-DD is a trading session in this calendar. */
  isTradingSession(date: string): boolean
  /** Display name, e.g. "XSHG". */
  readonly exchange: string
}

/** A static, hand-curated calendar for tests. */
export class StaticTradingCalendar implements TradingCalendar {
  readonly exchange: string
  private readonly sessions: Set<string>

  constructor(exchange: string, sessions: string[]) {
    this.exchange = exchange
    this.sessions = new Set(sessions)
  }

  isTradingSession(date: string): boolean {
    return this.sessions.has(date)
  }
}