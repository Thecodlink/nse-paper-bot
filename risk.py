"""Risk gate. Paper only.

Hard rule (Phase spec): after 2 consecutive losing days, position size is
HALVED for the next day. Tracked in state:
  state["daily_pnl"]                {date_str: net_pnl_for_that_day}
  state["consecutive_losing_days"]  trailing losing-day streak (int)
  state["size_multiplier"]          1.0 normally, 0.5 after a >=2-day losing streak
A winning (or flat) day resets the streak and restores the multiplier to 1.0.
"""
import config


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


def equity_from_state(state, prices=None):
    """Equity = cash + sum(open position qty x last price).

    `prices` maps symbol -> last known price; positions without a live
    price fall back to their entry price (last price the bot recorded).
    Sizing off equity, never off residual cash: the old code sized
    position 2 off what was left after position 1 (Rs 2,740 -> a
    Rs 1,233 position, 55% of the first position's size).
    """
    prices = prices or {}
    total = float((state or {}).get("cash", config.CAPITAL))
    for p in (state or {}).get("positions", []):
        last = prices.get(p["symbol"], p.get("entry", 0))
        total += float(p.get("qty", 0)) * float(last or 0)
    return total


def deployed_notional(state):
    """Notional already deployed in open positions (at entry prices)."""
    return sum(float(p.get("qty", 0)) * float(p.get("entry", 0))
               for p in (state or {}).get("positions", []))


def position_size(equity, entry, stop, deployed=0.0, multiplier=None):
    """Risk-based position size (Phase 0 rewrite).

        risk_amount = EQUITY * RISK_PER_TRADE        (x size multiplier)
        qty_risk    = floor(risk_amount / |entry - stop|)
        qty_margin  = floor((EQUITY * MAX_LEVERAGE - deployed) / entry)
        qty         = max(0, min(qty_risk, qty_margin))

    The legacy formula was min(0.45 * cash, 5 * cash) // price: the
    leverage term could never bind, so MIS_LEVERAGE was dead code and
    every position was a flat 45% of residual cash regardless of how
    far away its stop was.
    """
    if entry <= 0 or stop <= 0 or equity <= 0:
        return 0
    sl_distance = abs(entry - stop)
    if sl_distance <= 0:
        return 0
    if multiplier is None:
        multiplier = config.DEFAULT_SIZE_MULTIPLIER
    risk_amount = equity * config.RISK_PER_TRADE * float(multiplier)
    qty_risk = int(risk_amount // sl_distance)
    margin_room = equity * float(config.MAX_LEVERAGE) - float(deployed)
    qty_margin = int(margin_room // entry) if margin_room > 0 else 0
    qty = max(0, min(qty_risk, qty_margin))
    if qty == 0 and qty_margin >= 1 and sl_distance <= config.QTY_FLOOR_MAX_OVERRUN * risk_amount:
        # Granularity floor: one share, with the risk overrun bounded
        # at QTY_FLOOR_MAX_OVERRUN x the risk budget. Without this,
        # qty floors to 0 and silently kills the top of the universe
        # (e.g. risk Rs 37.50 vs a Rs 44.86 stop distance on a
        # Rs 1,400 name -> 0 shares, no log, no trade, ever).
        qty = 1
    return qty


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
    sl, tp = levels(entry, atr)
    if sl >= entry or tp <= entry:
        return False, "bad SL/TP", 0, 0, 0
    equity = equity_from_state(state)
    qty = position_size(equity, entry, sl, deployed=deployed_notional(state),
                        multiplier=size_multiplier(state))
    if qty <= 0:
        return False, "size rounds to 0 at this capital/risk", 0, 0, 0
    return True, "ok", qty, sl, tp


def trail_stop(pos, price, atr):
    """Trail only up, only after +1xATR profit."""
    if price >= pos["entry"] + config.TRAIL_ATR * atr:
        new = tick_round(price - config.SL_ATR * atr)
        return max(pos["stop"], new)
    return pos["stop"]
