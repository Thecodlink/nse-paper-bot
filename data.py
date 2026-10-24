"""Data: Yahoo Finance only (primary), fallback jugaad-data -> nsepython.
Research/paper only. Degrades gracefully: returns empty, logs, never crashes caller."""
import time, logging, datetime as dt
import pandas as pd
import config
log = logging.getLogger("data")
_daily_cache = {}   # symbol -> df, cached for session
_last_source = "none"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def _session():
    try:
        from curl_cffi import requests as creq
        s = creq.Session(impersonate="chrome")
        s.headers.update({"User-Agent": UA}); return s
    except Exception as e:
        log.warning("curl_cffi unavailable (%s), default session", e); return None

def _backoff(fn):
    delay=1
    for attempt in range(4):
        try:
            out = fn()
            if out is not None and not (isinstance(out, pd.DataFrame) and out.empty): return out
            log.warning("empty result attempt %d", attempt)
        except Exception as e:
            log.warning("fetch error attempt %d: %s", attempt, e)
            if "429" in str(e): pass
        time.sleep(delay); delay*=2  # 1,2,4,8
    return None

def fetch_batched(tickers, period="5d", interval="5m"):
    """ONE batched yf.download for ALL tickers - never per-symbol bulk loops."""
    global _last_source
    import yfinance as yf
    sess = _session()
    ytickers = [f"{t}.NS" if not t.endswith(".NS") else t for t in tickers]
    def _do():
        kwargs = dict(tickers=" ".join(ytickers), period=period, interval=interval, group_by="ticker", auto_adjust=False, threads=True, progress=False)
        if sess is not None:
            try: return yf.download(**kwargs, session=sess)
            except TypeError: return yf.download(**kwargs)
        return yf.download(**kwargs)
    raw = _backoff(_do)
    if raw is None: return {}
    _last_source="yfinance"
    out={}
    for t, yt in zip(tickers, ytickers):
        try:
            df = raw[yt] if yt in raw else raw
            df = df.dropna(how="all")
            if not df.empty: out[t]=df
        except Exception: continue
    return out

def fetch_daily_cached(symbols):
    """Daily candles cached for whole session."""
    missing=[s for s in symbols if s not in _daily_cache]
    if missing:
        res = fetch_batched(missing, period="6mo", interval="1d")
        _daily_cache.update(res)
        if len(res)<len(missing): _fallback_daily(missing)
    return {s:_daily_cache[s] for s in symbols if s in _daily_cache}

def _fallback_daily(symbols):
    global _last_source
    for src, fn in (("jugaad-data", _jugaad), ("nsepython", _nsepython)):
        for s in symbols:
            if s in _daily_cache: continue
            try:
                df=fn(s)
                if df is not None and not df.empty: _daily_cache[s]=df; _last_source=src; log.info("fallback %s used for %s", src, s)
            except Exception as e: log.warning("fallback %s %s failed: %s", src, s, e)

def _jugaad(symbol):
    # Preferred: pip package `jugaad-data` (in requirements.txt, imported normally).
    # Fallback: a local git clone of jugaad-py/jugaad-data on sys.path (stack-test
    # lesson: the clone alone is NOT importable until it is pip-installed or on PYTHONPATH).
    try:
        from jugaad_data.nse import stock_df
    except ImportError:
        import sys, os
        for cand in ("jugaad-data", "jugaad_data", "../jugaad-data"):
            if os.path.isdir(cand): sys.path.insert(0, cand)
        from jugaad_data.nse import stock_df
    to_d=config.today_ist(); from_d=to_d-dt.timedelta(days=180)
    df=stock_df(symbol=symbol, from_date=from_d, to_date=to_d, series="EQ")
    return df.rename(columns={"OPEN":"Open","HIGH":"High","LOW":"Low","CLOSE":"Close","VOLUME":"Volume"}) if df is not None else None

def _nsepython(symbol):
    from nsepython import equity_history
    df=equity_history(symbol, "EQ", str(config.today_ist()-dt.timedelta(days=180)), str(config.today_ist()))
    return df

def fetch_intraday(symbols):
    return fetch_batched(symbols, period="5d", interval="5m")

def last_source(): return _last_source

def is_stale(df, max_minutes=None):
    max_minutes = max_minutes or config.STALE_DATA_MINUTES
    try:
        last = df.index[-1]
        if getattr(last, "tzinfo", None) is None: last = pd.Timestamp(last).tz_localize("Asia/Kolkata")
        age = (pd.Timestamp.now(tz="Asia/Kolkata") - last).total_seconds()/60
        return age > max_minutes, age
    except Exception:
        return True, None
