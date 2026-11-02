import config


def test_default_mode_is_swing():
    assert config.MODE == "swing"


def test_swing_leverage_and_brokerage_flags():
    # Swing: no leverage, zero-brokerage cost model.
    assert config.MAX_LEVERAGE == 1.0
    assert config.ZERO_BROKERAGE is True


def test_risk_constants():
    # 0.015 per the Nov 2 Phase 1 amendment (was 0.0075 in Phase 0):
    # the flat Rs 12 DP charge needs a larger position to dilute.
    assert config.RISK_PER_TRADE == 0.015
    assert config.COST_TARGET_WARN_PCT == 0.25
    assert config.QTY_FLOOR_MAX_OVERRUN == 2.0


def test_positions_and_carry():
    assert config.MAX_POSITIONS == 3
    # Swing mode carries overnight; intraday would not.
    assert config.CARRY_OVERNIGHT is True


def test_swing_cost_constants():
    assert config.BROKERAGE_PER_ORDER_SWING == 0.0
    assert config.DP_CHARGE_PER_SCRIP == 12.0
    assert config.STT_DELIVERY_PCT == 0.001


def test_intraday_cost_stack_preserved():
    assert config.BROKERAGE_PER_ORDER == 20.0
    assert config.STT_SELL_PCT == 0.00025
