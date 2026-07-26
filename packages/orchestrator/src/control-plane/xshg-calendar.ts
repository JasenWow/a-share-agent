/**
 * FileBackedSessionExpander — production SessionExpander backed by a
 * precomputed XSHG trading-calendar JSON fixture.
 *
 * The fixture (`xshg-calendar.json`) is generated from
 * `exchange_calendars` (Python) covering 2020–2026. Keeping it as a
 * static file means the control plane has zero runtime Python
 * dependency for calendar operations — trading-day lookups are O(log n)
 * binary searches in-memory.
 *
 * To refresh the calendar (e.g. extend beyond 2026), regenerate:
 *   cd python && uv run python -c "
 *     import exchange_calendars as xc, json
 *     cal = xc.get_calendar('XSHG')
 *     dates = [s.strftime('%Y-%m-%d') for s in cal.sessions_in_range('2020-01-01','2026-12-31')]
 *     json.dump(dates, open('../packages/orchestrator/src/control-plane/xshg-calendar.json','w'))
 *   "
 */

import calendarData from "./xshg-calendar.json"
import type { SessionExpander } from "./session-expander"

const SORTED_SESSIONS: string[] = (calendarData as string[]).slice().sort()

/**
 * Binary search for the index of `target` in SORTED_SESSIONS.
 * Returns -1 if not found.
 */
function binarySearch(arr: string[], target: string): number {
  let lo = 0
  let hi = arr.length - 1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    const cmp = arr[mid]!.localeCompare(target)
    if (cmp === 0) return mid
    if (cmp < 0) lo = mid + 1
    else hi = mid - 1
  }
  return -1
}

/**
 * Find the largest index i where arr[i] <= target.
 * Returns -1 if no element is <= target.
 */
function floorIndex(arr: string[], target: string): number {
  let lo = 0
  let hi = arr.length - 1
  let result = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (arr[mid]! <= target) {
      result = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return result
}

export class FileBackedSessionExpander implements SessionExpander {
  private readonly sessions: string[]

  constructor(sessions?: string[]) {
    this.sessions = sessions ?? SORTED_SESSIONS
  }

  expand(startSession: string, endSession: string): string[] {
    const startIdx = binarySearch(this.sessions, startSession)
    const endIdx = binarySearch(this.sessions, endSession)
    if (startIdx === -1) {
      throw new Error(`'${startSession}' is not a trading session`)
    }
    if (endIdx === -1) {
      throw new Error(`'${endSession}' is not a trading session`)
    }
    if (startIdx > endIdx) {
      throw new Error(`start '${startSession}' is after end '${endSession}'`)
    }
    return this.sessions.slice(startIdx, endIdx + 1)
  }
}

/**
 * FileBackedSessionResolver — resolves the most recent trading session
 * at or before `now`. Used by the scheduler to pick the target session
 * for a cron fire.
 *
 * If `now` is before the first known session, throws.
 */
export class FileBackedSessionResolver {
  private readonly sessions: string[]

  constructor(sessions?: string[]) {
    this.sessions = sessions ?? SORTED_SESSIONS
  }

  resolve(now: Date): string {
    const nowStr = now.toISOString().slice(0, 10)
    const idx = floorIndex(this.sessions, nowStr)
    if (idx === -1) {
      throw new Error(`No trading session at or before ${nowStr}`)
    }
    return this.sessions[idx]!
  }
}

export { SORTED_SESSIONS as XSHG_SESSIONS }