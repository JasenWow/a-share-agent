"""Trading-day utilities (T+1, holidays, business-day arithmetic).

Phase 1: thin placeholder wrapping exchange_calendars. Concrete helpers
(previous_trading_day, is_trading_day, n_trading_days_ago) will be added
as migrating code requires them.
"""

from __future__ import annotations

# Lazy import: exchange_calendars is heavy and optional during early migration.
_DEFAULT_EXCHANGE = "XSHG"  # Shanghai Stock Exchange; covers both SH and SZ trading days.


def _calendar(exchange: str = _DEFAULT_EXCHANGE):
    """Return an exchange_calendars calendar handle (lazy-loaded)."""
    import exchange_calendars as xcals

    return xcals.get_calendar(exchange)
