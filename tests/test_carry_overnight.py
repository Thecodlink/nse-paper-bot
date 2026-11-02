import pandas as pd

import config
import main


def _frame(closes, opens=None, start="2026-11-02 09:15"):
    idx = pd.date_range(start, periods=len(closes), freq="5min")
    opens = opens or closes
    return pd.DataFrame({"Open": opens, "High": [c + 1 for c in closes],
                         "Low": [c - 1 for c in closes], "Close": closes,
                         "Volume": [1000] * len(closes)}, index=idx)


def _state_with_pos():
    return {"cash": 4000.0, "starting_cash": 5000.0,
            "positions": [{"symbol": "ABC", "qty": 2, "entry": 100.0, "stop": 90.0,
                           "target": 120.0, "costs_buy": 1.0, "time": "t", "reason": "r"}],
            "trades": [], "daily_pnl": {}, "size_multiplier": 1.0}


def test_manage_exits_does_not_square_off_when_carrying(monkeypatch):
    # Real clock is past SQUARE_OFF_FROM in the evening test runs; with
    # CARRY_OVERNIGHT on, the 15:15 'close' trigger must NOT fire.
    monkeypatch.setattr(config, "CARRY_OVERNIGHT", True)
    st = _state_with_pos()
    main.manage_exits(st, {"ABC": _frame([101.0, 102.0])})
    assert len(st["positions"]) == 1


def test_manage_exits_squares_off_when_not_carrying(monkeypatch):
    monkeypatch.setattr(config, "CARRY_OVERNIGHT", False)
    if config.now_ist().time() < config.SQUARE_OFF_FROM:
        # Before 15:15 the close trigger cannot fire either way; the
        # companion test above covers the carry branch. Skip cleanly.
        import pytest
        pytest.skip("close trigger only fires after 15:15")
    st = _state_with_pos()
    main.manage_exits(st, {"ABC": _frame([101.0, 102.0])})
    assert len(st["positions"]) == 0


def test_eod_snapshot_marks_and_equity():
    st = _state_with_pos()
    snap = main.eod_snapshot(st, {"ABC": _frame([110.0])})
    assert snap is not None
    row = snap["positions"][0]
    assert row["mark"] == 110.0
    assert row["unrealised_pnl"] == round((110.0 - 100.0) * 2 - 1.0, 2)
    assert snap["equity_est"] == 4000.0 + 220.0
    assert st["positions"][0]["last_mark"] == 110.0
    assert st["positions"][0]["mark_date"] == str(config.today_ist())


def test_eod_snapshot_falls_back_to_entry_without_frame():
    st = _state_with_pos()
    snap = main.eod_snapshot(st, {})
    assert snap["positions"][0]["mark_source"] == "entry_fallback"
    assert snap["positions"][0]["mark"] == 100.0


def test_record_gaps_measures_overnight_gap():
    st = _state_with_pos()
    pos = st["positions"][0]
    today = str(config.today_ist())
    pos["last_mark"] = 100.0
    pos["mark_date"] = "2026-10-30"  # a previous session
    frame = _frame([97.5], opens=[97.0], start=f"{today} 09:15")
    main.record_gaps(st, {"ABC": frame})
    assert pos["gap_at_open"]["pct"] == -3.0
    assert pos["gap_at_open"]["prev_mark"] == 100.0
    # Idempotent within the day:
    pos["gap_at_open"]["pct"] = 0.0
    main.record_gaps(st, {"ABC": frame})
    assert pos["gap_at_open"]["pct"] == 0.0
