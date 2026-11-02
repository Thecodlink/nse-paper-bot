import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def _no_journal_writes(monkeypatch):
    """Tests must not write the real journal.db."""
    import journal
    monkeypatch.setattr(journal, "log_trade", lambda *a, **k: None)
    monkeypatch.setattr(journal, "log_decision", lambda *a, **k: None)


@pytest.fixture
def fresh_state():
    return {"cash": 5000.0, "starting_cash": 5000.0, "positions": [], "trades": [],
            "equity_curve": [], "heartbeat": None, "heartbeat_date": None,
            "decisions": [], "daily_pnl": {}, "consecutive_losing_days": 0,
            "size_multiplier": 1.0}
