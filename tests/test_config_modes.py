import config


def test_default_mode_is_swing():
    assert config.MODE == "swing"


def test_swing_leverage_and_brokerage_flags():
    # Swing: no leverage, zero-brokerage cost model.
    assert config.MAX_LEVERAGE == 1.0
    assert config.ZERO_BROKERAGE is True


def test_risk_constants():
    assert config.RISK_PER_TRADE == 0.0075
    assert config.COST_TARGET_WARN_PCT == 0.25


def test_swing_cost_constants():
    assert config.BROKERAGE_PER_ORDER_SWING == 0.0
    assert config.DP_CHARGE_PER_SCRIP == 12.0
    assert config.STT_DELIVERY_PCT == 0.001


def test_intraday_cost_stack_preserved():
    assert config.BROKERAGE_PER_ORDER == 20.0
    assert config.STT_SELL_PCT == 0.00025
