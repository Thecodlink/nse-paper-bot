import datetime as dt

import config
import risk

MORNING = dt.datetime(2026, 11, 3, 10, 0, tzinfo=config.IST())


def test_phase0_spec_case_at_original_risk(monkeypatch):
    # Original Phase 0.1 acceptance case at RISK_PER_TRADE 0.0075:
    # Rs 5,000 / entry Rs 500 / SL distance Rs 10 -> 3 (risk cap binds),
    # NOT 4 (the old 45%-of-cash formula gave 2250/500 = 4).
    monkeypatch.setattr(config, "RISK_PER_TRADE", 0.0075)
    assert risk.position_size(5000.0, 500.0, 490.0) == 3


def test_current_default_risk(monkeypatch):
    # At the amended default 0.015: risk budget Rs 75 -> 7 shares,
    # swing margin (10) does not bind.
    assert config.RISK_PER_TRADE == 0.015
    assert risk.position_size(5000.0, 500.0, 490.0) == 7


def test_risk_cap_binds_in_intraday_leverage_too(monkeypatch):
    monkeypatch.setattr(config, "MAX_LEVERAGE", 5.0)
    # Margin would allow 50; risk still caps at 7.
    assert risk.position_size(5000.0, 500.0, 490.0) == 7


def test_margin_cap_binds_when_stop_is_tight(monkeypatch):
    # Stop Rs 1 away: risk would allow 75; swing margin allows 10,
    # intraday 5x margin allows 50 - margin binds in both modes.
    assert risk.position_size(5000.0, 500.0, 499.0) == 10
    monkeypatch.setattr(config, "MAX_LEVERAGE", 5.0)
    assert risk.position_size(5000.0, 500.0, 499.0) == 50


def test_qty_floor_one_share_with_bounded_overrun():
    # Stop Rs 100 away: risk 75/100 -> 0 by the plain formula, but one
    # share risks Rs 100 <= 2x the Rs 75 budget, so the floor gives 1.
    assert risk.position_size(5000.0, 500.0, 400.0) == 1


def test_qty_floor_refuses_unbounded_overrun():
    # Stop Rs 200 away: one share risks Rs 200 > 2x budget Rs 150 -> 0.
    assert risk.position_size(5000.0, 500.0, 300.0) == 0


def test_qty_floor_respects_margin():
    # Equity Rs 400 cannot margin even 1 share at Rs 500 (swing 1x).
    assert risk.position_size(400.0, 500.0, 490.0) == 0


def test_equity_includes_open_positions_at_last_price():
    state = {"cash": 2740.0, "positions": [{"symbol": "ABC", "qty": 5, "entry": 452.0}]}
    assert risk.equity_from_state(state) == 5000.0  # entry as last-price fallback
    assert risk.equity_from_state(state, prices={"ABC": 500.0}) == 5240.0
    assert risk.deployed_notional(state) == 2260.0


def test_second_position_sized_off_equity_not_residual_cash():
    # After position 1 (notional Rs 2,260), cash is Rs 2,740. The old
    # code sized position 2 off Rs 2,740 (45% -> Rs 1,233). Risk sizing
    # uses EQUITY Rs 5,000: risk allows 7, remaining margin
    # (5000-2260=2740 -> 5) binds -> 5. Off residual cash the old code
    # gave 2 shares at this price; equity sizing gives 5.
    state = {"cash": 2740.0, "positions": [{"symbol": "ABC", "qty": 5, "entry": 452.0}]}
    qty = risk.position_size(risk.equity_from_state(state), 500.0, 490.0,
                             deployed=risk.deployed_notional(state))
    assert qty == 5


def test_size_multiplier_halves_risk():
    # 0.5 multiplier: risk budget Rs 37.50 -> 37.5/10 = 3.
    assert risk.position_size(5000.0, 500.0, 490.0, multiplier=0.5) == 3


def test_check_uses_risk_sizing(fresh_state):
    # ATR chosen so levels() gives a Rs 10 stop distance (1.5 x ATR).
    ok, why, qty, sl, tp = risk.check(fresh_state, "ABC", 500.0, 10.0 / 1.5, now=MORNING)
    assert ok, why
    assert qty == 7
    assert sl == 490.0
    assert tp > 500.0
