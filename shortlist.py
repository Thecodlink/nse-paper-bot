"""Shortlist filter: price 100-1500, avg vol >500k, ATR% >1%, exclude T2T.
Result is capped at the TOP 20 by score (Phase spec)."""
import logging, config
from indicators import add_indicators
log = logging.getLogger("shortlist")


def build_shortlist(daily_data: dict):
    out = []
    for sym, df in (daily_data or {}).items():
        if sym in config.T2T_EXCLUSIONS:
            continue
        try:
            if df is None or len(df) < 30:
                continue
            d = add_indicators(df)
            last = d.iloc[-1]
            price = float(last["Close"])
            avgvol = float(df["Volume"].tail(20).mean())
            atrp = float(last["ATR_PCT"]) if last["ATR_PCT"] == last["ATR_PCT"] else 0
            if config.PRICE_MIN <= price <= config.PRICE_MAX and avgvol > config.MIN_AVG_VOLUME and atrp > config.MIN_ATR_PCT:
                # Score: liquidity x volatility -- both are required properties,
                # so rank by their product (higher = more tradable intraday).
                score = avgvol * atrp
                out.append({"symbol": sym, "price": price, "avg_volume": avgvol,
                            "atr": float(last["ATR14"]), "atr_pct": atrp, "score": score})
        except Exception as e:
            log.warning("shortlist %s: %s", sym, e)
    out.sort(key=lambda x: x["score"], reverse=True)
    top_n = getattr(config, "SHORTLIST_TOP_N", 20)
    out = out[:top_n]
    log.info("shortlist: %d passed (top %d kept) of %d symbols", len(out), top_n, len(daily_data or {}))
    return out
