"""Kronos forecast. Loads NeoQuasar/Kronos-small ONCE (lazy singleton).
Research only. If unavailable returns None - never fakes a probability.
Optional ensemble (Chronos/TimesFM/Moirai) research only, remove if commercial, default OFF.

UP-PROBABILITY -- CORRECT METHOD (stack-test verified, Oct 24):
``KronosPredictor.predict(sample_count=N)`` returns ONE path averaged over
its N samples, so the fraction of paths closing above entry is NOT
recoverable from a single call with sample_count=10. To get the real
fraction we loop ``predict(sample_count=1)`` N=10 times independently and
count how many final closes are above entry.

COST WARNING: measured on this 2-CPU box, ~5.8s per single path, i.e.
~58s per symbol for 10 paths (57.7s for 10 paths on RELIANCE daily).
Kronos must therefore run ONLY on the final 2-5 candidates that survive
all the cheap filters (price / volume / ATR / RSI / EMA / sentiment) --
never on the full shortlist, or the 5-minute cycle overruns.
"""
import logging, sys, os, time
import numpy as np, config
log = logging.getLogger("kronos")
_predictor = None
_tried = False


def _load():
    global _predictor, _tried
    if _predictor is not None or _tried:
        return _predictor
    _tried = True
    try:
        if os.path.isdir("Kronos"):
            sys.path.insert(0, "Kronos")
        from model import Kronos, KronosTokenizer, KronosPredictor  # from shiyu-coder/Kronos clone
        tok = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        try:
            model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        except Exception:
            model = Kronos.from_pretrained("NeoQuasar/Kronos-mini")
        _predictor = KronosPredictor(model, tok, max_context=512)
        log.info("Kronos loaded (once, singleton)")
    except Exception as e:
        log.warning("Kronos unavailable, forecasts disabled: %s", e)
        _predictor = None
    return _predictor


def _final_close(result):
    """Final Close of one predicted path (DataFrame, or list of DataFrames)."""
    if isinstance(result, (list, tuple)):
        result = result[0]
    return float(result["Close"].iloc[-1])


def up_probability(df, entry=None, symbol=None):
    """df OHLCV with DatetimeIndex. Returns float in [0,1] or None.

    Loops predict(sample_count=1) KRONOS_SAMPLE_COUNT times and returns the
    fraction of paths whose final close is above entry. Logs timing because
    this is the most expensive call in the cycle (~58s/symbol on 2 CPU).
    """
    p = _load()
    if p is None or df is None or len(df) < 50:
        return None
    try:
        import pandas as pd
        d = df.tail(config.KRONOS_LOOKBACK).copy()
        x_df = d[["Open", "High", "Low", "Close", "Volume"]].copy()
        if "Amount" not in x_df:
            x_df["Amount"] = x_df["Close"] * x_df["Volume"]
        x_ts = pd.Series(d.index)
        entry = float(entry or d["Close"].iloc[-1])
        future = pd.date_range(d.index[-1], periods=config.KRONOS_PRED_LEN + 1, freq="5min")[1:]
        n = int(config.KRONOS_SAMPLE_COUNT)
        t0 = time.time()
        above = 0
        completed = 0
        for _ in range(n):
            y_df = p.predict(df=x_df, x_timestamp=x_ts, y_timestamp=pd.Series(future),
                             pred_len=config.KRONOS_PRED_LEN, T=config.KRONOS_T,
                             top_p=config.KRONOS_TOP_P, sample_count=1, verbose=False)
            completed += 1
            if _final_close(y_df) > entry:
                above += 1
        elapsed = time.time() - t0
        prob = above / completed if completed else None
        log.info("Kronos %s: %d/%d paths above entry %.2f -> up_prob=%s in %.1fs (%.1fs/path)",
                 symbol or "?", above, completed, entry, prob, elapsed,
                 elapsed / completed if completed else 0.0)
        return float(prob) if prob is not None else None
    except Exception as e:
        log.warning("Kronos forecast failed: %s", e)
        return None


# Optional ensemble stubs - research only, remove if commercial, default OFF
def chronos_up_prob(df): return None
def timesfm_up_prob(df): return None  # TimesFM weights non-commercial: research only
def moirai_up_prob(df): return None   # Moirai/uni2ts non-commercial: research only
