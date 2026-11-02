"""Paper broker: fills at NEXT candle open +/- 0.1% slippage, full Indian cost stack itemised.
Paper only - no broker API, no real orders ever.

Cost models (Phase 0):
- "intraday" (legacy): Rs 20/order brokerage, STT 0.025% sell-side only.
- "swing": Rs 0 brokerage (ZERO_BROKERAGE), STT 0.1% BOTH sides
  (delivery), DP charge Rs 12 per scrip on sell.
Default model comes from config (ZERO_BROKERAGE / MODE); callers may
pass model= explicitly (backtests do).
"""
import logging

import config
import journal

log = logging.getLogger("paper_broker")


def _default_model():
    return "swing" if getattr(config, "ZERO_BROKERAGE", False) else "intraday"


def cost_breakdown(side, qty, price, model=None):
    model = model or _default_model()
    turnover = qty * price
    if model == "swing":
        brokerage = config.BROKERAGE_PER_ORDER_SWING
        stt = turnover * config.STT_DELIVERY_PCT  # delivery: both sides
        dp = config.DP_CHARGE_PER_SCRIP if side == "SELL" else 0.0
    else:
        brokerage = config.BROKERAGE_PER_ORDER
        stt = turnover * config.STT_SELL_PCT if side == "SELL" else 0.0
        dp = 0.0
    txn = turnover * config.EXCHANGE_TXN_PCT
    sebi = turnover * (config.SEBI_PER_CRORE / 1e7)
    stamp = turnover * config.STAMP_BUY_PCT if side == "BUY" else 0.0
    gst = config.GST_PCT * (brokerage + txn + sebi)
    total = brokerage + stt + txn + sebi + stamp + gst + dp
    return {"brokerage": round(brokerage, 2), "stt": round(stt, 2),
            "exchange_txn": round(txn, 2), "sebi": round(sebi, 2),
            "stamp_duty": round(stamp, 2), "gst": round(gst, 2),
            "dp_charge": round(dp, 2), "model": model,
            "total": round(total, 2), "turnover": round(turnover, 2)}


def fill_price(next_open, side):
    return round(next_open * (1 + config.SLIPPAGE_PCT) if side == "BUY" else next_open * (1 - config.SLIPPAGE_PCT), 2)


def round_trip_cost_estimate(qty, entry_price, target_price, model=None):
    """Estimated round-trip cost of a position entered at entry_price and
    exited at target_price, under the given cost model."""
    buy_cb = cost_breakdown("BUY", qty, entry_price, model=model)
    sell_cb = cost_breakdown("SELL", qty, target_price, model=model)
    return round(buy_cb["total"] + sell_cb["total"], 2)


def cost_pct_of_target(qty, entry_price, stop, target, model=None):
    """Round-trip cost as a fraction of the take-profit distance
    (qty x (target - entry)). None when there is no target distance.
    The Phase 0 target is < 0.25 (25%); the legacy intraday build
    measured 5.42 (542%)."""
    gain = (target - entry_price) * qty
    if gain <= 0:
        return None
    return round(round_trip_cost_estimate(qty, entry_price, target, model=model) / gain, 4)


def buy(state, symbol, qty, next_open, stop, target, reason, ts):
    price = fill_price(next_open, "BUY")
    cb = cost_breakdown("BUY", qty, price)
    gross = qty * price
    total_cost = gross + cb["total"]
    state["cash"] = round(state["cash"] - total_cost, 2)
    pct = cost_pct_of_target(qty, price, stop, target, model=cb["model"])
    pos = {"symbol": symbol, "qty": qty, "entry": price, "stop": stop, "target": target,
           "costs_buy": cb["total"], "time": str(ts), "reason": reason,
           "cost_model": cb["model"], "cost_pct_of_target": pct,
           "est_round_trip_cost": round_trip_cost_estimate(qty, price, target, model=cb["model"])}
    state["positions"].append(pos)
    log.info("BUY %s qty %d @ %.2f costs %.2f cost_pct_of_target=%s (model=%s)",
             symbol, qty, price, cb["total"], pct, cb["model"])
    # Leverage invariant (Phase 0.1): cash may only go negative by the
    # borrowed fraction, i.e. cash >= -EQUITY * (MAX_LEVERAGE - 1).
    # In swing (leverage 1.0) that floor is 0. Breach = logged warning,
    # never a raise (constraint: nothing raises into the trade loop).
    try:
        deployed = sum(p["qty"] * p["entry"] for p in state["positions"])
        equity_est = state["cash"] + deployed
        floor_cash = -equity_est * (float(config.MAX_LEVERAGE) - 1.0)
        if state["cash"] < floor_cash - 0.01:
            log.warning("CASH FLOOR BREACHED after BUY %s: cash %.2f < floor %.2f "
                        "(equity est %.2f, leverage %.1f)",
                        symbol, state["cash"], floor_cash, equity_est, float(config.MAX_LEVERAGE))
    except Exception as e:
        log.warning("cash floor check failed (ignored): %s", e)
    journal.log_trade(str(ts), symbol, "BUY", qty, price, gross, cb["total"], cb, -total_cost, reason)
    return pos, cb


def sell(state, pos, next_open, reason, ts):
    qty = pos["qty"]
    price = fill_price(next_open, "SELL")
    cb = cost_breakdown("SELL", qty, price, model=pos.get("cost_model"))
    gross = qty * price
    net = gross - cb["total"]
    state["cash"] = round(state["cash"] + net, 2)
    state["positions"] = [p for p in state["positions"] if p is not pos]
    buy_cost = pos.get("costs_buy", 0)
    pnl = net - (pos["entry"] * qty + buy_cost)
    trade = {"symbol": pos["symbol"], "qty": qty, "entry": pos["entry"], "exit": price, "gross": gross,
             "costs": round(cb["total"] + buy_cost, 2),
             "costs_sell": cb["total"], "net_pnl": round(pnl, 2), "reason": reason, "time": str(ts),
             "cost_pct_of_target": pos.get("cost_pct_of_target")}
    state.setdefault("trades", []).append(trade)
    journal.log_trade(str(ts), pos["symbol"], "SELL", qty, price, gross, cb["total"], cb, round(pnl, 2), reason)
    return trade, cb
