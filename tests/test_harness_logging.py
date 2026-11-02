import importlib.util
import os
import sqlite3

import pandas as pd
import pytest

import config
import journal
import main
import paper_broker


def _fresh_journal_module():
    """Load a second copy of journal.py (the autouse conftest stub
    replaced log_trade on the shared module object)."""
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "journal.py")
    spec = importlib.util.spec_from_file_location("journal_real", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_journal_schema_and_label_roundtrip(tmp_path, monkeypatch):
    db = str(tmp_path / "j.db")
    monkeypatch.setattr(config, "JOURNAL_DB", db)
    jr = _fresh_journal_module()
    jr.log_trade("2026-11-03 09:20", "ABC", "SELL", 2, 110.0, 220.0, 14.0,
                 {"total": 14.0}, 6.0, "target", label="edge_invalid",
                 mae_pct=-1.25, mfe_pct=4.5)
    c = sqlite3.connect(db)
    cols = [r[1] for r in c.execute("PRAGMA table_info(trades)").fetchall()]
    assert {"label", "mae_pct", "mfe_pct"} <= set(cols)
    row = c.execute("SELECT symbol, label, mae_pct, mfe_pct FROM trades").fetchone()
    assert row == ("ABC", "edge_invalid", -1.25, 4.5)
    c.close()


def test_buy_initialises_mae_mfe_and_labels(monkeypatch, fresh_state):
    calls = []
    monkeypatch.setattr(journal, "log_trade", lambda *a, **k: calls.append((a, k)))
    pos, _ = paper_broker.buy(fresh_state, "ABC", 2, 100.0, 95.0, 115.0, "test", "2026-11-03 09:20")
    assert pos["mae_pct"] == 0.0 and pos["mfe_pct"] == 0.0
    assert calls and calls[0][1].get("label") == "edge_invalid"
    assert config.LIVE_LABEL == "edge_invalid"


def test_sell_records_mae_mfe_and_label(monkeypatch, fresh_state):
    calls = []
    monkeypatch.setattr(journal, "log_trade", lambda *a, **k: calls.append((a, k)))
    pos, _ = paper_broker.buy(fresh_state, "ABC", 2, 100.0, 95.0, 115.0, "test", "2026-11-03 09:20")
    pos["mae_pct"] = -2.5
    pos["mfe_pct"] = 6.25
    trade, _ = paper_broker.sell(fresh_state, pos, 112.0, "target", "2026-11-05 15:10")
    assert trade["mae_pct"] == -2.5 and trade["mfe_pct"] == 6.25
    assert trade["label"] == "edge_invalid"
    sell_call = calls[-1][1]
    assert sell_call.get("mae_pct") == -2.5 and sell_call.get("mfe_pct") == 6.25
    assert sell_call.get("label") == "edge_invalid"


def test_manage_exits_updates_mae_mfe(monkeypatch):
    monkeypatch.setattr(config, "CARRY_OVERNIGHT", True)  # no square-off interference
    st = {"cash": 4000.0, "starting_cash": 5000.0,
          "positions": [{"symbol": "ABC", "qty": 2, "entry": 100.0, "stop": 90.0,
                         "target": 130.0, "costs_buy": 1.0,
                         "time": "2026-11-03 09:20:00", "reason": "r",
                         "mae_pct": 0.0, "mfe_pct": 0.0}],
          "trades": [], "daily_pnl": {}, "size_multiplier": 1.0}
    idx = pd.date_range("2026-11-03 09:15", periods=3, freq="5min")
    df = pd.DataFrame({"Open": [101.0, 104.0, 103.0], "High": [102.0, 108.0, 104.0],
                       "Low": [99.0, 97.0, 101.0], "Close": [101.0, 103.0, 102.0],
                       "Volume": [1000] * 3, "ATR14": [2.0] * 3}, index=idx)
    main.manage_exits(st, {"ABC": df})
    pos = st["positions"][0]  # no exit: 102 within stop/target
    assert pos["mfe_pct"] == pytest.approx(8.0)   # high 108 vs entry 100
    assert pos["mae_pct"] == pytest.approx(-3.0)  # low 97 vs entry 100
