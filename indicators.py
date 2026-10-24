"""Indicators: pandas-ta-classic if available, else pure pandas fallback.

Stack-test lesson (verified): the pandas-ta-classic fork installs ONLY as
``pandas_ta_classic`` -- ``import pandas_ta`` fails with ModuleNotFoundError.
Do not add a pandas_ta fallback.
"""
import pandas as pd, numpy as np
try:
    import pandas_ta_classic as pta  # pandas-ta-classic, import name is pandas_ta_classic
except Exception:
    pta = None

def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def rsi(close, n=14):
    d = close.diff(); up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    out = 100 - 100/(1+rs)
    return out.where(dn!=0, 100.0).where(up!=0, 50.0) if False else out.fillna(100.0)
def atr(df, n=14):
    h,l,c = df["High"], df["Low"], df["Close"]; pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()
def macd(close):
    m = ema(close,12)-ema(close,26); sig = ema(m,9); return m, sig, m-sig
def vwap(df):
    """VWAP requires a DatetimeIndex (stack-test trap: pandas-ta's vwap fails
    on a RangeIndex with 'RangeIndex object has no attribute to_period').
    NEVER reset_index() before calling this -- keep the DatetimeIndex."""
    if "Volume" not in df: return pd.Series(index=df.index, dtype=float)
    if pta is not None and isinstance(df.index, pd.DatetimeIndex):
        try:
            v = pta.vwap(high=df["High"], low=df["Low"], close=df["Close"], volume=df["Volume"])
            if v is not None: return v
        except Exception:
            pass  # fall through to the pure-pandas calculation below
    tp = (df["High"]+df["Low"]+df["Close"])/3
    return (tp*df["Volume"]).cumsum() / df["Volume"].cumsum().replace(0, np.nan)

def add_indicators(df):
    """df needs Open/High/Low/Close/Volume. Returns df with indicator columns."""
    if df is None or len(df)==0: return df
    df = df.copy()  # copy preserves the index -- do NOT reset_index (VWAP needs DatetimeIndex)
    df["EMA9"]=ema(df["Close"],9); df["EMA21"]=ema(df["Close"],21); df["EMA50"]=ema(df["Close"],50)
    df["RSI14"]=rsi(df["Close"]); df["ATR14"]=atr(df)
    m,s,h = macd(df["Close"]); df["MACD"]=m; df["MACD_SIGNAL"]=s; df["MACD_HIST"]=h
    # VWAP: intraday if index is intraday else rolling session approx = cumulative
    try: df["VWAP"]=vwap(df)
    except Exception: df["VWAP"]=np.nan
    vol_ma = df["Volume"].rolling(20).mean() if "Volume" in df else np.nan
    df["REL_VOLUME"]=df["Volume"]/vol_ma if "Volume" in df else np.nan
    hi20 = df["High"].rolling(20).max(); lo20 = df["Low"].rolling(20).min()
    df["DIST_20D_HIGH_PCT"]=(df["Close"]-hi20)/hi20*100
    df["DIST_20D_LOW_PCT"]=(df["Close"]-lo20)/lo20.replace(0,np.nan)*100
    df["ATR_PCT"]=df["ATR14"]/df["Close"]
    return df

def latest(df):
    if df is None or len(df)==0: return {}
    r = df.iloc[-1]
    return {k: (float(r[k]) if k in r and pd.notna(r[k]) else None) for k in
            ["Close","EMA9","EMA21","EMA50","RSI14","ATR14","ATR_PCT","MACD","MACD_HIST","VWAP","REL_VOLUME","DIST_20D_HIGH_PCT","DIST_20D_LOW_PCT"]}
