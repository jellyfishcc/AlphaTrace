"""Historical test fixture only; never imported by production modules."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

BEIJING = timezone(timedelta(hours=8))
FIXTURE_DATE = '2026-11-02'

@contextmanager
def fixed_price_clock(instant=None):
    instant = instant or datetime(2026, 11, 2, 12, tzinfo=BEIJING)
    if instant.tzinfo is None:
        raise ValueError('test clock requires timezone')
    with patch('tracelab.cost_budget.VERIFIED_DATE', FIXTURE_DATE), patch('tracelab.cost_budget.datetime', wraps=datetime) as clock:
        clock.now.side_effect = lambda tz=None: instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
        yield clock
