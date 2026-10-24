"""Risk gate. Paper only.

Hard rule (Phase spec): after 2 consecutive losing days, position size is
HALVED for the next day. Tracked in state:
  state["daily_pnl"]                {date_str: net_pnl_for_that_day}
  state["consecutive_losing_days"]  trailing losing-day streak (int)
  state["size_multiplier"]          1.0 normally, 0.5 after a >=2-day losing streak
A winning (or flat) day resets the streak and restores the multiplier to 1.0.
"""
import datetime as dt, config


def tick_round(x):
    return round(round(x / 0.05) * 0.05, 2)


def size_multiplier(state):
    """Current size multiplier from state (defaults to 1.0)."""
    try:
        m = float((state or {}).get("size_multiplier", config.DEFAULT_SIZE_MULTIPLIER))
        return m if m > 0 else config.DEFAULT_SIZE_MULTIPLIER
    except Exception:
        return config.DEFAULT_SIZE_MULTIPLIER


def update_day_close(state, date_str, day_pnl):
    """Record a day's net P&L and update the losing-streak / size multiplier.

    Unit-testable, no I/O. Returns (consecutive_losing_days, size_multiplier).
    Recomputing the streak from the ordered daily_pnl dict makes repeated
    calls for the same date idempotent.
    """
    daily = state.setdefault("daily_pnl", {})
    daily[str(date_str)] = float(day_pnl)
    streak = 0
    for d in sorted(daily.keys(), reverse=True):
        if float(daily[d]) < 0:
            streak += 1
        else:
            break
    state["consecutive_losing_days"] = streak
    threshold = getattr(config, "CONSECUTIVE_LOSING_DAYS_THRESHOLD", 2)
    state["size_multiplier"] = (
        config.HALVED_SIZE_MULTIPLIER if streak >= threshold else config.DEFAULT_SIZE_MULTIPLIER
    )
    return state["consecutive_losing_days"], state["size_multiplier"]


def position_size(cash, price, multiplier=None):
    if price <= 0:
        return 0
    if multiplier is None:
        multiplier = config.DEFAULT_SIZE_MULTIPLIER
    budget = min(config.MAX_CAPITAL_PCT * cash, config.MIS_LEVERAGE * cash)  # min(45% cash, 5x MIS limit per spec)
    budget *= float(multiplier)
    # Note: 45% cash is the binding constraint; qty floored
    return int(budget // price)


def levels(entry, atr):
    return tick_round(entry - config.SL_ATR * atr), tick_round(entry + config.TP_ATR * atr)


def check(state, symbol, entry, atr, now=None):
    """Returns (ok, reason, qty, stop, target)"""
    now = now or config.now_ist()
    if now.time() >= config.NO_NEW_TRADES_AFTER:
        return False, "no new trades after 14:45", 0, 0, 0
    positions = state.get("positions", [])
    if len(positions) >= config.MAX_POSITIONS:
        return False, "max 2 positions", 0, 0, 0
    if any(p["symbol"] == symbol for p in positions):
        return False, "already holding", 0, 0, 0
    if not atr or atr <= 0:
        return False, "no ATR / no stop calculable", 0, 0, 0
    cash = float(state.get("cash", config.CAPITAL))
    qty = position_size(cash, entry, multiplier=size_multiplier(state))
    if qty <= 0:
        return False, "size rounds to 0 at this capital/price", 0, 0, 0
    sl, tp = levels(entry, atr)
    if sl >= entry or tp <= entry:
        return False, "bad SL/TP", 0, 0, 0
    return True, "ok", qty, sl, tp


def trail_stop(pos, price, atr):
    """Trail only up, only after +1xATR profit."""
    if price >= pos["entry"] + config.TRAIL_ATR * atr:
        new = tick_round(price - config.SL_ATR * atr)
        return max(pos["stop"], new)
    return pos["stop"]
