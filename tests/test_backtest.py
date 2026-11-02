import pandas as pd
import pytest

import backtest

V = backtest.Variant(40, 70, 1.5, 3.0)


def _indicator_frame(closes, opens=None, highs=None, lows=None, n_atr=2.0):
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    opens = opens or list(closes)
    highs = highs or [c + 1 for c in closes]
    lows = lows or [c - 1 for c in closes]
    ema21 = [200.0] * n
    ema21[10] = 100.0  # signal ONLY at bar 10: Close 110 > EMA21 100 there
    return pd.DataFrame({
        "Open": opens, "High": highs, "Low": lows, "Close": closes,
        "Volume": [1_000_000] * n,
        "EMA21": ema21, "RSI14": [50.0] * n,
        "ATR14": [n_atr] * n, "ATR_PCT": [0.02] * n,
        "AVG_VOL20": [1_000_000.0] * n,
    }, index=idx)


def _base_closes():
    closes = [100.0] * 40
    closes[10] = 110.0   # signal bar (Close > EMA21, RSI in band)
    closes[11] = 106.0
    closes[12] = 112.0
    for i in range(13, 40):
        closes[i] = 112.0
    return closes


try:
    import vectorbt  # noqa: F401
    HAS_VBT = True
except Exception:
    HAS_VBT = False
vbt_only = pytest.mark.skipif(not HAS_VBT, reason="vectorbt not installed")


@vbt_only
def test_entry_fills_at_next_bar_open_not_signal_close():
    closes = _base_closes()
    opens = [100.0] * 40
    opens[11] = 105.0    # execution bar open
    opens[12] = 107.0
    highs = [c + 1 for c in closes]
    highs[12] = 115.0    # reaches target 105 + 3*ATR(2) = 111
    d = _indicator_frame(closes, opens=opens, highs=highs)
    cands = backtest.extract_candidates("AAA", d, V)
    assert len(cands) == 1
    c = cands[0]
    assert c["entry_raw"] == 105.0           # NOT the signal close 110
    assert c["entry_date"] == d.index[11]
    assert c["exit_raw"] == 111.0
    assert c["exit_reason"] == "target"


@vbt_only
def test_gap_through_stop_fills_at_open_not_stop_price():
    closes = _base_closes()
    opens = [100.0] * 40
    opens[11] = 105.0
    opens[12] = 95.0     # gaps below the 102 stop
    highs = [c + 1 for c in closes]
    highs[12] = 96.0
    lows = [c - 1 for c in closes]
    lows[12] = 94.0
    closes[12] = 95.0
    d = _indicator_frame(closes, opens=opens, highs=highs, lows=lows)
    cands = backtest.extract_candidates("AAA", d, V)
    assert len(cands) == 1
    assert cands[0]["exit_raw"] == 95.0      # the open, NOT 102
    assert cands[0]["exit_reason"] == "stop"


@vbt_only
def test_intrabar_wick_below_stop_stops_out():
    closes = _base_closes()
    opens = [100.0] * 40
    opens[11] = 105.0
    opens[12] = 106.0
    highs = [c + 1 for c in closes]
    highs[12] = 108.0    # below target 111
    lows = [c - 1 for c in closes]
    lows[12] = 101.0     # wick below stop 102, close recovers to 107
    closes[12] = 107.0
    d = _indicator_frame(closes, opens=opens, highs=highs, lows=lows)
    cands = backtest.extract_candidates("AAA", d, V)
    assert len(cands) == 1
    assert cands[0]["exit_raw"] == 102.0     # stop price on an intrabar wick
    assert cands[0]["exit_reason"] == "stop"


def test_folds_are_walk_forward():
    cal = list(pd.date_range("2023-01-01", periods=600, freq="B"))
    folds = backtest.make_folds(cal, start_from=cal[0])
    assert len(folds) == 7  # (600 - 250) / 50
    seen_tests = []
    for f in folds:
        assert f["train_start"] < f["test_start"]
        seen_tests.append((f["test"][0], f["test"][1]))
    for i in range(len(seen_tests) - 1):
        assert seen_tests[i][1] <= seen_tests[i + 1][0]  # disjoint, ordered


def _hand_candidate(sym, entry_d, exit_d, entry=100.0, exit_=115.0, stop=95.0, target=115.0):
    return {"symbol": sym, "signal_date": entry_d, "entry_date": entry_d,
            "exit_date": exit_d, "entry_raw": entry, "exit_raw": exit_,
            "stop": stop, "target": target, "atr": 2.0, "score": 1.0,
            "exit_reason": "target"}


def _bars_for(symbols):
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    return {s: pd.DataFrame({"Open": [100.0] * 60, "High": [101.0] * 60,
                             "Low": [99.0] * 60, "Close": [100.0] * 60,
                             "Volume": [1_000_000] * 60}, index=idx)
            for s in symbols}


def test_zero_cost_run_has_no_costs_and_beats_costed():
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    cands = [_hand_candidate("AAA", idx[5], idx[10])]
    bars = _bars_for(["AAA"])
    cfg = backtest.Config(V, 0.015, 2)
    tr_off, _ = backtest.assemble(cands, cfg, idx[0], idx[59], bars, False, "swing", calendar=list(idx))
    tr_on, _ = backtest.assemble(cands, cfg, idx[0], idx[59], bars, True, "swing", calendar=list(idx))
    assert len(tr_off) == len(tr_on) == 1
    assert tr_off[0]["costs"] == 0.0
    assert tr_on[0]["costs"] > 0
    assert tr_off[0]["net_pnl"] > tr_on[0]["net_pnl"]
    assert tr_on[0]["cost_pct_of_target"] is not None


def test_assemble_respects_max_positions_and_equity_sizing():
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    cands = [_hand_candidate(s, idx[5], idx[10]) for s in ("AAA", "BBB", "CCC")]
    bars = _bars_for(["AAA", "BBB", "CCC"])
    cfg = backtest.Config(V, 0.015, 2)
    tr, _ = backtest.assemble(cands, cfg, idx[0], idx[59], bars, True, "swing", calendar=list(idx))
    assert len(tr) == 2  # third candidate blocked by max_positions


def test_metrics_reports_break_even_win_rate():
    trades = [{"net_pnl": 100.0, "qty": 1, "entry": 100.0, "costs": 5.0, "cost_pct_of_target": 0.1},
              {"net_pnl": 100.0, "qty": 1, "entry": 100.0, "costs": 5.0, "cost_pct_of_target": 0.1},
              {"net_pnl": -100.0, "qty": 1, "entry": 100.0, "costs": 5.0, "cost_pct_of_target": 0.1}]
    m = backtest.metrics(trades, [])
    assert m["win_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert m["break_even_win_rate"] == pytest.approx(0.5, abs=1e-3)
    assert m["profit_factor"] == pytest.approx(2.0, abs=1e-6)
