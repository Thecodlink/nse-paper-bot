import config
import paper_broker


def test_swing_round_trip_on_5000_position_under_0_6_pct():
    # Spec 0.3 acceptance: swing round-trip cost on a Rs 5,000 position
    # (10 shares @ Rs 500) must be < 0.6% of the position.
    buy = paper_broker.cost_breakdown("BUY", 10, 500.0, model="swing")
    sell = paper_broker.cost_breakdown("SELL", 10, 500.0, model="swing")
    rt = buy["total"] + sell["total"]
    assert rt / 5000.0 < 0.006


def test_swing_model_components():
    buy = paper_broker.cost_breakdown("BUY", 10, 500.0, model="swing")
    sell = paper_broker.cost_breakdown("SELL", 10, 500.0, model="swing")
    assert buy["brokerage"] == 0.0 and sell["brokerage"] == 0.0
    assert buy["stt"] == 5.0 and sell["stt"] == 5.0  # 0.1% both sides
    assert sell["dp_charge"] == config.DP_CHARGE_PER_SCRIP == 12.0
    assert buy["dp_charge"] == 0.0
    assert buy["model"] == "swing"


def test_intraday_model_unchanged():
    buy = paper_broker.cost_breakdown("BUY", 10, 500.0, model="intraday")
    sell = paper_broker.cost_breakdown("SELL", 10, 500.0, model="intraday")
    assert buy["brokerage"] == 20.0 and sell["brokerage"] == 20.0
    assert buy["stt"] == 0.0
    assert sell["stt"] == 1.25  # 0.025% sell-side only
    assert sell["dp_charge"] == 0.0


def test_default_model_follows_config():
    # Default MODE is swing with ZERO_BROKERAGE on.
    assert paper_broker.cost_breakdown("BUY", 1, 100.0)["model"] == "swing"


def test_cost_pct_of_target_intraday_legacy_blowout():
    # Legacy geometry: Rs 2,250 position (5 @ Rs 450), TP distance
    # 0.43% -> target gain ~Rs 9.68 against ~Rs 50 round-trip cost.
    entry, qty = 450.0, 5
    target = entry * 1.0043
    pct = paper_broker.cost_pct_of_target(qty, entry, entry * 0.997, target, model="intraday")
    assert pct is not None and pct > 4.0  # >400% of target


def test_buy_stores_cost_pct_of_target(fresh_state):
    pos, _cb = paper_broker.buy(fresh_state, "ABC", 3, 500.0, 490.0, 525.0,
                               "test", "2026-11-03T10:00:00+05:30")
    assert pos["cost_model"] == "swing"
    assert pos["cost_pct_of_target"] is not None
    # Swing RT cost ~Rs 16 on a 3 x Rs 25 = Rs 75 target gain.
    assert 0 < pos["cost_pct_of_target"] < 0.35
    assert pos["est_round_trip_cost"] > 0
    # Swing cash floor is 0: cash must not be negative after the buy.
    assert fresh_state["cash"] > 0


def test_sell_keeps_cost_model_and_pct(fresh_state):
    pos, _ = paper_broker.buy(fresh_state, "ABC", 3, 500.0, 490.0, 525.0,
                              "test", "2026-11-03T10:00:00+05:30")
    trade, _ = paper_broker.sell(fresh_state, pos, 525.0, "target", "2026-11-04T10:00:00+05:30")
    assert trade["cost_pct_of_target"] == pos["cost_pct_of_target"]
    assert fresh_state["positions"] == []
