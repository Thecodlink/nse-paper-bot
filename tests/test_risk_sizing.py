import datetime as dt

import config
import risk

MORNING = dt.datetime(2026, 11, 3, 10, 0, tzinfo=config.IST())


def test_spec_case_risk_cap_binds_not_margin():
    # Spec 0.1 acceptance: Rs 5,000 equity / entry Rs 500 / SL distance
    # Rs 10 -> qty must be <= 3 (risk cap: 5000*0.0075/10 = 3.75 -> 3),
    # NOT 4 (the old 45%-of-cash formula gave 2250/500 = 4).
    assert risk.position_size(5000.0, 500.0, 490.0) == 3


def test_risk_cap_binds_in_intraday_leverage_too(monkeypatch):
    monkeypatch.setattr(config, "MAX_LEVERAGE", 5.0)
    # Margin would allow 50; risk still caps at 3.
    assert risk.position_size(5000.0, 500.0, 490.0) == 3


def test_margin_cap_binds_when_stop_is_tight(monkeypatch):
    # Stop Rs 1 away: risk would allow 37, swing margin allows 10.
    assert risk.position_size(5000.0, 500.0, 499.0) == 10
    monkeypatch.setattr(config, "MAX_LEVERAGE", 5.0)
    assert risk.position_size(5000.0, 500.0, 499.0) == 37


def test_zero_when_risk_rounds_down():
    # Stop Rs 100 away: 37.5 / 100 -> 0.
    assert risk.position_size(5000.0, 500.0, 400.0) == 0


def test_equity_includes_open_positions_at_last_price():
    state = {"cash": 2740.0, "positions": [{"symbol": "ABC", "qty": 5, "entry": 452.0}]}
    assert risk.equity_from_state(state) == 5000.0  # entry as last-price fallback
    assert risk.equity_from_state(state, prices={"ABC": 500.0}) == 5240.0
    assert risk.deployed_notional(state) == 2260.0


def test_second_position_sized_off_equity_not_residual_cash():
    # After position 1 (notional Rs 2,260), cash is Rs 2,740. The old
    # code sized position 2 off Rs 2,740; risk sizing uses equity
    # Rs 5,000, so the same setup gets the same risk size (3), subject
    # to remaining margin (5000-2260=2740 -> 5): min(3, 5) = 3.
    state = {"cash": 2740.0, "positions": [{"symbol": "ABC", "qty": 5, "entry": 452.0}]}
    qty = risk.position_size(risk.equity_from_state(state), 500.0, 490.0,
                             deployed=risk.deployed_notional(state))
    assert qty == 3


def test_size_multiplier_halves_risk():
    assert risk.position_size(5000.0, 500.0, 490.0, multiplier=0.5) == 1


def test_check_uses_risk_sizing(fresh_state):
    # ATR chosen so levels() gives a Rs 10 stop distance (1.5 x ATR).
    ok, why, qty, sl, tp = risk.check(fresh_state, "ABC", 500.0, 10.0 / 1.5, now=MORNING)
    assert ok, why
    assert qty == 3
    assert sl == 490.0
    assert tp > 500.0
