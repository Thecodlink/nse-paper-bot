"""Walk-forward backtester (Phase 1 - the gate).

Swing leg: daily bars. Intraday leg: 5-min bars, HARD LIMIT 60 days of
history - Yahoo Finance caps 5m data at 60 days, so a 3-year intraday
backtest is impossible on this data source (spec amendment, Nov 2,
2026). The intraday leg is therefore scoped to 60 days and labelled as
such wherever its numbers appear. Daily bars are unrestricted.

Method (no full-sample fitting, ever):
- Indicators and entry signals are computed once per symbol with the
  repo's own indicators.py (same code as live).
- Trade extraction (fills) runs through vectorbt Portfolio.from_signals
  per symbol: signals shift one bar and execute at the NEXT bar's Open;
  stops/targets are per-entry fractions derived from ATR at the signal
  bar; vectorbt's stop engine evaluates High/Low intrabar and fills a
  gap-through-stop at the bar's Open, not the stop price (verified on
  synthetic data, tests/test_backtest.py). Trailing uses vectorbt's
  sl_trail at the entry ATR distance - an approximation of the live
  ATR-recomputed trail, documented in the report.
- Portfolio assembly (shared Rs 5,000 equity, max positions, risk-based
  sizing off equity, exact repo cost stack via paper_broker) is done
  here, because vectorbt's fee model (% + flat) cannot express the
  Indian stack exactly (DP charge is sell-side only). Costs and
  slippage are applied at assembly with the SAME functions the live
  bot uses. Zero-cost runs skip both.
- Walk-forward: train 250 bars / test 50 bars, rolled by 50, on the
  NIFTYBEES reference calendar. Per-config metrics aggregate ONLY the
  test windows (each fold starts fresh at Rs 5,000). A separate
  walk-forward-selected line picks, per fold, the best config ON THE
  TRAIN WINDOW (after the cost filter) and reports its test result.
- Hard filter (spec amendment): a config whose median
  cost_pct_of_target exceeds 25% is discarded BEFORE ranking.

Not backtested (no honest historical inputs): Kronos forecasts,
FinBERT sentiment (no 2023 headline archive), the LLM brain. This
tests the rule core: shortlist filters + price>EMA21 + RSI band +
ATR stops/targets/trailing. Survivorship bias: SYMBOLS is today's
universe applied to 2023-2026 - results are flattered by it; noted,
not solved (spec amendment).

CLI:
  python backtest.py --mode swing --symbols all --from 2023-01-01 \
      --costs on --out reports/
"""
import argparse
import contextlib
import json
import logging
import math
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

import config
import paper_broker
import risk
from indicators import add_indicators

log = logging.getLogger("backtest")

CACHE_ROOT = os.path.join("data", "cache")
BENCHMARK = "NIFTYBEES"
WARMUP_START = "2022-01-01"

# Sweep grids (spec Phase 1 + Nov 2 amendments)
RISK_GRID = [0.005, 0.01, 0.015, 0.02]
SL_GRID = [1.5, 2.0, 2.5]
TP_GRID = [3.0, 4.0, 6.0, 8.0]
RSI_GRID = [(40, 70), (45, 75), (35, 65)]
MAXPOS_GRID = [2, 3, 5]


@dataclass(frozen=True)
class Variant:
    rsi_min: int
    rsi_max: int
    sl_atr: float
    tp_atr: float


@dataclass(frozen=True)
class Config:
    variant: Variant
    risk_per_trade: float
    max_positions: int

    def label(self):
        v = self.variant
        return (f"rsi{v.rsi_min}-{v.rsi_max}_sl{v.sl_atr}_tp{v.tp_atr}"
                f"_risk{self.risk_per_trade}_maxpos{self.max_positions}")


# ---------------------------------------------------------------- cache

def _cache_dir(mode):
    return os.path.join(CACHE_ROOT, "daily" if mode == "swing" else "intraday5m")


def _normalize(df):
    df = df.copy()
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(how="any")


def build_cache(mode, symbols, refresh=False):
    """Fetch bars into Parquet cache (never committed; see .gitignore).
    Daily: 5y from Yahoo. Intraday 5m: 60d - the Yahoo cap."""
    import data as data_mod
    os.makedirs(_cache_dir(mode), exist_ok=True)
    period, interval = ("5y", "1d") if mode == "swing" else ("60d", "5m")
    todo = [s for s in symbols
            if refresh or not os.path.exists(os.path.join(_cache_dir(mode), f"{s}.parquet"))]
    for i in range(0, len(todo), 25):
        chunk = todo[i:i + 25]
        got = data_mod.fetch_batched(chunk, period=period, interval=interval)
        for s in chunk:
            df = (got or {}).get(s)
            if df is None or len(df) == 0:
                log.warning("cache: no data for %s", s)
                continue
            out = _normalize(df)
            out = out[out.index >= pd.Timestamp(WARMUP_START)]
            out.insert(0, "symbol", s)
            out.to_parquet(os.path.join(_cache_dir(mode), f"{s}.parquet"))
        log.info("cache: %d/%d symbols written", min(i + 25, len(todo)), len(todo))
    return _cache_dir(mode)


def load_bars(symbol, mode):
    """Load one symbol's bars via DuckDB over the Parquet cache."""
    path = os.path.join(_cache_dir(mode), f"{symbol}.parquet")
    if not os.path.exists(path):
        return None
    import duckdb
    # DuckDB is the query layer over the Parquet cache (row-count /
    # integrity check here); pandas reads the frame back for index
    # fidelity.
    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{path}')").fetchone()[0]
    con.close()
    if not n:
        return None
    df = pd.read_parquet(path)
    if "symbol" in df.columns:
        df = df.drop(columns=["symbol"])
    df.index = pd.DatetimeIndex(df.index)
    return df


def load_all(mode, symbols):
    bars = {}
    for s in symbols:
        df = load_bars(s, mode)
        if df is not None and len(df) >= 60:
            bars[s] = df
    return bars


# ---------------------------------------------------------------- signals

def add_signal_columns(df):
    d = add_indicators(df)
    d["AVG_VOL20"] = d["Volume"].rolling(20).mean()
    return d


def entry_signals(d, rsi_min, rsi_max):
    """Live rule core on the signal bar (close): shortlist filters +
    price > EMA21 + RSI inside the band. One position per symbol is
    enforced by the extractor (vectorbt accumulate=False)."""
    sig = (
        (d["Close"] > d["EMA21"])
        & (d["RSI14"] > rsi_min) & (d["RSI14"] < rsi_max)
        & (d["ATR_PCT"] > config.MIN_ATR_PCT)
        & (d["Close"] >= config.PRICE_MIN) & (d["Close"] <= config.PRICE_MAX)
        & (d["AVG_VOL20"] > config.MIN_AVG_VOLUME)
    )
    return sig.fillna(False)


# ---------------------------------------------------------------- extraction (vectorbt)

def extract_candidates(symbol, d, variant):
    """Run vectorbt for one symbol/variant; return raw candidate trades
    (prices WITHOUT slippage/costs - assembly applies the exact stack).

    Signals at bar t execute at bar t+1's Open. sl/tp fractions are
    computed from ATR at the signal bar and placed at the execution
    bar. A trade still open at the series end is closed at the last
    Close with reason 'window_end'."""
    import vectorbt as vbt
    sig = entry_signals(d, variant.rsi_min, variant.rsi_max)
    if not sig.any():
        return []
    entries = sig.shift(1, fill_value=False)
    atr = d["ATR14"]
    open_ = d["Open"]
    sl_frac = (variant.sl_atr * atr).shift(1) / open_
    tp_frac = (variant.tp_atr * atr).shift(1) / open_
    avgvol = d["AVG_VOL20"]
    score = (avgvol * d["ATR_PCT"]).shift(1)
    # vectorbt scales order prices by close/price at the entry bar when
    # the two series differ, which corrupts exact stop/target levels.
    # Passing an adjusted close (the execution bar's close replaced by
    # its Open) makes fills exact: entry = next bar's Open, exits at
    # the precise stop/target/open levels (verified in tests). The
    # only side effect is the trailing-stop tracker sees the Open
    # instead of the Close on entry bars - a one-bar approximation.
    adj_close = d["Close"].copy()
    adj_close[entries] = open_[entries]
    pf = vbt.Portfolio.from_signals(
        adj_close, entries, price=adj_close, open=open_, high=d["High"], low=d["Low"],
        sl_stop=sl_frac, tp_stop=tp_frac, sl_trail=True,
        init_cash=1e12, size=1, size_type="amount", fees=0.0, slippage=0.0,
        freq="1D", accumulate=False)
    rec = pf.trades.records_readable
    out = []
    for _, r in rec.iterrows():
        entry_ts = pd.Timestamp(r["Entry Timestamp"])
        exit_ts = pd.Timestamp(r["Exit Timestamp"])
        entry_raw = float(r["Avg Entry Price"])
        i = d.index.get_loc(entry_ts)
        sig_i = max(i - 1, 0)
        sl_f = float(sl_frac.iloc[i]) if pd.notna(sl_frac.iloc[i]) else 0.0
        tp_f = float(tp_frac.iloc[i]) if pd.notna(tp_frac.iloc[i]) else 0.0
        exit_raw = float(r["Avg Exit Price"])
        status = str(r["Status"])
        if status.lower().startswith("open"):
            reason = "window_end"
        elif exit_raw <= entry_raw * (1 - sl_f) + 1e-9:
            reason = "stop"
        elif exit_raw >= entry_raw * (1 + tp_f) - 1e-9:
            reason = "target"
        else:
            reason = "stop"  # trailing stop sits above the initial stop
        out.append({
            "symbol": symbol,
            "signal_date": d.index[sig_i],
            "entry_date": entry_ts, "exit_date": exit_ts,
            "entry_raw": entry_raw, "exit_raw": exit_raw,
            "stop": round(entry_raw * (1 - sl_f), 2),
            "target": round(entry_raw * (1 + tp_f), 2),
            "atr": float(atr.iloc[sig_i]) if pd.notna(atr.iloc[sig_i]) else 0.0,
            "score": float(score.iloc[i]) if pd.notna(score.iloc[i]) else 0.0,
            "exit_reason": reason,
        })
    return out


# ---------------------------------------------------------------- assembly

@contextlib.contextmanager
def _cfg(**overrides):
    saved = {k: getattr(config, k) for k in overrides}
    for k, v in overrides.items():
        setattr(config, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


def assemble(cands, cfg, start, end, bars, costs_on, mode, calendar=None):
    """Shared-equity portfolio assembly over entries in [start, end).

    Candidates are raw (no slippage/costs). Applies, in entry order:
    settle matured positions -> equity/deployed from state -> risk
    sizing (repo risk.position_size) -> exact cost stack (repo
    paper_broker) -> exits from candidate records. Returns
    (trades, equity_points) where equity_points maps date -> equity
    for every bar date in [start, end] of the union calendar."""
    model = "swing" if mode == "swing" else "intraday"
    leverage = 1.0 if mode == "swing" else 5.0
    pool = [c for c in cands if start <= c["entry_date"] < end]
    pool.sort(key=lambda c: (c["entry_date"], -c["score"]))
    cash = config.CAPITAL
    open_pos = []  # dicts with exit_date, qty, entry_fill, symbol, cand, buy_cost
    trades = []

    def mark(symbol, when):
        df = bars.get(symbol)
        if df is None:
            return None
        idx = df.index[df.index <= when]
        return float(df["Close"].iloc[-1]) if len(idx) else None

    def settle(upto):
        nonlocal cash
        keep = []
        for p in open_pos:
            if p["exit_date"] < upto:
                cash = round(cash + p["settle_cash"], 2)
                trades.append(p["trade"])
            else:
                keep.append(p)
        open_pos[:] = keep

    with _cfg(RISK_PER_TRADE=cfg.risk_per_trade, MAX_LEVERAGE=leverage):
        for c in pool:
            settle(c["entry_date"])
            if len(open_pos) >= cfg.max_positions:
                continue
            if any(p["symbol"] == c["symbol"] for p in open_pos):
                continue
            equity = cash + sum(
                p["qty"] * (mark(p["symbol"], c["entry_date"]) or p["entry_fill"])
                for p in open_pos)
            deployed = sum(p["qty"] * p["entry_fill"] for p in open_pos)
            qty = risk.position_size(equity, c["entry_raw"], c["stop"], deployed=deployed)
            if qty <= 0:
                continue
            entry_fill = paper_broker.fill_price(c["entry_raw"], "BUY") if costs_on else c["entry_raw"]
            buy_cost = paper_broker.cost_breakdown("BUY", qty, entry_fill, model=model)["total"] if costs_on else 0.0
            cash = round(cash - (qty * entry_fill + buy_cost), 2)
            exit_fill = paper_broker.fill_price(c["exit_raw"], "SELL") if costs_on else c["exit_raw"]
            sell_cost = paper_broker.cost_breakdown("SELL", qty, exit_fill, model=model)["total"] if costs_on else 0.0
            net = qty * exit_fill - sell_cost - (qty * entry_fill + buy_cost)
            pct_target = (paper_broker.cost_pct_of_target(qty, entry_fill, c["stop"], c["target"], model=model)
                          if costs_on else 0.0)
            trade = {"symbol": c["symbol"], "entry_date": c["entry_date"], "exit_date": c["exit_date"],
                     "qty": qty, "entry": entry_fill, "exit": exit_fill, "stop": c["stop"],
                     "target": c["target"], "exit_reason": c["exit_reason"],
                     "costs": round(buy_cost + sell_cost, 2), "buy_cost": round(buy_cost, 2),
                     "sell_cost": round(sell_cost, 2), "net_pnl": round(net, 2),
                     "cost_pct_of_target": pct_target}
            open_pos.append({"symbol": c["symbol"], "qty": qty, "entry_fill": entry_fill,
                             "exit_date": c["exit_date"], "settle_cash": qty * exit_fill - sell_cost,
                             "trade": trade})
        settle(pd.Timestamp.max)

    # Equity curve over the window calendar (mark-to-market). The
    # caller passes the reference (benchmark) calendar slice; building
    # a union calendar per call would dominate the sweep's runtime.
    if calendar is None:
        calendar = sorted({dt for s, df in bars.items() for dt in df.index if start <= dt < end})
    cal = calendar
    eq_points = {}
    for dt_ in cal:
        eq = config.CAPITAL
        eq += sum(t["net_pnl"] for t in trades if t["exit_date"] <= dt_)
        for t in trades:
            if t["entry_date"] <= dt_ < t["exit_date"]:
                m = mark(t["symbol"], dt_)
                if m is not None:
                    eq += (m - t["entry"]) * t["qty"] - t["buy_cost"]
        eq_points[dt_] = round(eq, 2)
    return trades, eq_points


def _cal_slice(bars, lo, hi):
    df = bars.get(BENCHMARK)
    if df is None:
        return []
    idx = df.index[(df.index >= lo) & (df.index < hi)]
    return list(idx)


# ---------------------------------------------------------------- metrics

def metrics(trades, eq_points_list):
    """Aggregate metrics from pooled fold trades and per-fold equity
    curves (each fold's curve starts at CAPITAL)."""
    n = len(trades)
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    win_rate = len(wins) / n if n else 0.0
    avg_win = float(np.mean([t["net_pnl"] for t in wins])) if wins else 0.0
    avg_loss = abs(float(np.mean([t["net_pnl"] for t in losses]))) if losses else 0.0
    be_wr = (avg_loss / (avg_win + avg_loss)) if (avg_win + avg_loss) > 0 else 0.0
    gross_win = sum(t["net_pnl"] for t in wins)
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    total_pnl = sum(t["net_pnl"] for t in trades)
    folds = max(len(eq_points_list), 1)
    net_return = total_pnl / (config.CAPITAL * folds)
    # Drawdown + Sharpe from concatenated per-fold daily returns.
    rets = []
    max_dd = 0.0
    for eq in eq_points_list:
        if not eq:
            continue
        s = pd.Series(eq).sort_index()
        peak = s.cummax()
        max_dd = min(max_dd, float(((s - peak) / peak).min()))
        rets.extend((s.pct_change().dropna()).tolist())
    sharpe = 0.0
    if len(rets) > 5 and np.std(rets) > 0:
        sharpe = float(np.mean(rets) / np.std(rets) * math.sqrt(252))
    pcts = [t["cost_pct_of_target"] for t in trades if t.get("cost_pct_of_target") is not None]
    return {
        "trades": n, "win_rate": round(win_rate, 4), "break_even_win_rate": round(be_wr, 4),
        "avg_win_pct": round(float(np.mean([t["net_pnl"] / (t["qty"] * t["entry"]) * 100 for t in wins])), 3) if wins else 0.0,
        "avg_loss_pct": round(float(np.mean([t["net_pnl"] / (t["qty"] * t["entry"]) * 100 for t in losses])), 3) if losses else 0.0,
        "avg_win_rs": round(avg_win, 2), "avg_loss_rs": round(avg_loss, 2),
        "net_pnl": round(total_pnl, 2), "net_return_pct": round(net_return * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2), "sharpe": round(sharpe, 2),
        "profit_factor": round(pf, 2) if pf != float("inf") else None,
        "median_cost_pct_of_target": round(float(np.median(pcts)), 4) if pcts else None,
        "total_costs": round(sum(t["costs"] for t in trades), 2),
    }


def make_folds(calendar, train=250, test=50, start_from=None):
    """Walk-forward folds on the reference calendar:
    train [k*test, k*test+train), test = the next `test` bars."""
    dates = [d for d in calendar if start_from is None or d >= start_from]
    folds = []
    k = 0
    while True:
        tr_lo, tr_hi = k * test, k * test + train
        te_lo, te_hi = tr_hi, tr_hi + test
        if te_hi > len(dates):
            break
        folds.append({
            "train": (dates[tr_lo], dates[te_hi - 1] + pd.Timedelta(days=1)),
            "test": (dates[te_lo], dates[te_hi - 1] + pd.Timedelta(days=1)),
            "train_start": dates[tr_lo], "test_start": dates[te_lo],
        })
        k += 1
    return folds


def benchmark_returns(bars, folds):
    """NIFTYBEES buy-and-hold per fold: buy at the first test bar's
    Open with the full Rs 5,000 (fractional units - benchmark only),
    sell at the last test bar's Close. Swing cost stack applied."""
    df = bars.get(BENCHMARK)
    if df is None:
        return None
    total = 0.0
    for f in folds:
        lo, hi = f["test"]
        w = df[(df.index >= lo) & (df.index < hi)]
        if len(w) < 2:
            continue
        qty = config.CAPITAL / float(w["Open"].iloc[0])
        buy_c = paper_broker.cost_breakdown("BUY", qty, float(w["Open"].iloc[0]), model="swing")["total"]
        sell_px = float(w["Close"].iloc[-1])
        sell_c = paper_broker.cost_breakdown("SELL", qty, sell_px, model="swing")["total"]
        total += qty * sell_px - sell_c - (config.CAPITAL + buy_c)
    return {"net_pnl": round(total, 2),
            "net_return_pct": round(total / (config.CAPITAL * max(len(folds), 1)) * 100, 2),
            "folds": len(folds)}


def tear_sheet(rets, bench_series, out_html):
    """quantstats tearsheet from a returns series (best-effort)."""
    try:
        import quantstats as qs
        rets.index = pd.DatetimeIndex(rets.index)
        qs.reports.html(rets, benchmark=bench_series, output=out_html,
                        title="NSE Paper Bot - walk-forward selected (costed)")
        return out_html
    except Exception as e:
        log.warning("quantstats tearsheet failed (ignored): %s", e)
        return None


# ---------------------------------------------------------------- sweep

def all_configs():
    for rsi_min, rsi_max in RSI_GRID:
        for sl in SL_GRID:
            for tp in TP_GRID:
                v = Variant(rsi_min, rsi_max, sl, tp)
                for r in RISK_GRID:
                    for mp in MAXPOS_GRID:
                        yield Config(v, r, mp)


def run_wf_selection(mode, bars, folds, by_variant):
    """Per fold: pick the best config on the TRAIN window among those
    passing the cost filter (median cost_pct_of_target <= 0.25, from a
    costed train run), then take that config's TEST result.
    Returns (metrics, equity points of the stitched selection, picks)."""
    picks = []
    sel_trades, sel_eqs = [], []
    for f in folds:
        tr_lo, tr_hi = f["train"]
        te_lo, te_hi = f["test"]
        best = None
        for cfg in all_configs():
            pool = by_variant[cfg.variant]
            tr, _ = assemble(pool, cfg, tr_lo, tr_hi, bars, True, mode, calendar=[])
            if len(tr) < 5:
                continue
            m = metrics(tr, [])
            med = m["median_cost_pct_of_target"]
            if med is None or med > config.COST_TARGET_WARN_PCT:
                continue
            if best is None or m["net_pnl"] > best[1]["net_pnl"]:
                best = (cfg, m)
        if best is None:
            picks.append((str(f["test_start"].date()), None))
            continue
        cfg = best[0]
        tr, eq = assemble(by_variant[cfg.variant], cfg, te_lo, te_hi, bars, True, mode, calendar=_cal_slice(bars, te_lo, te_hi))
        sel_trades.extend(tr)
        sel_eqs.append(eq)
        picks.append((str(f["test_start"].date()), cfg.label()))
    return metrics(sel_trades, sel_eqs), sel_eqs, picks


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="swing", choices=["swing", "intraday"])
    ap.add_argument("--symbols", default="all")
    ap.add_argument("--from", dest="from_date", default="2023-01-01")
    ap.add_argument("--costs", default="on", choices=["on", "off"])
    ap.add_argument("--out", default="reports/")
    ap.add_argument("--refresh-cache", action="store_true")
    ap.add_argument("--selection-only", action="store_true",
                    help="skip the full sweep; run walk-forward selection only")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    symbols = list(config.SYMBOLS) if a.symbols == "all" else a.symbols.split(",")
    fetch_list = symbols + [BENCHMARK]
    build_cache(a.mode, fetch_list, refresh=a.refresh_cache)
    bars = load_all(a.mode, fetch_list)
    log.info("loaded bars for %d symbols", len(bars))
    if BENCHMARK not in bars:
        log.error("benchmark %s missing - cannot report", BENCHMARK)
        return 1
    cal = sorted(bars[BENCHMARK].index)
    folds = make_folds(cal, start_from=pd.Timestamp(a.from_date))
    log.info("%d walk-forward folds (train 250 / test 50)", len(folds))
    if not folds:
        log.error("no folds - not enough history")
        return 1
    bench = benchmark_returns(bars, folds)

    os.makedirs(a.out, exist_ok=True)
    stamp = str(config.today_ist())
    ind = {s: add_signal_columns(bars[s]) for s in bars if s != BENCHMARK}
    by_variant = {}
    for v in {c.variant for c in all_configs()}:
        pool = []
        for s, d in ind.items():
            pool.extend(extract_candidates(s, d, v))
        by_variant[v] = pool
        log.info("variant %s: %d candidates", v, len(pool))

    sel_metrics, sel_eqs, picks = run_wf_selection(a.mode, bars, folds, by_variant)

    sweep_rows = []
    if not a.selection_only:
        for costs_on, tag in ((True, "costed"), (False, "zero-cost")):
            res = {}
            for cfg in all_configs():
                fold_trades, fold_eqs = [], []
                for f in folds:
                    lo, hi = f["test"]
                    tr, eq = assemble(by_variant[cfg.variant], cfg, lo, hi, bars, costs_on, a.mode, calendar=_cal_slice(bars, lo, hi))
                    fold_trades.extend(tr)
                    fold_eqs.append(eq)
                res[cfg.label()] = (metrics(fold_trades, fold_eqs), cfg)
            for label, (m, cfg) in res.items():
                sweep_rows.append({"config": label, "run": tag, **m})
            log.info("sweep done: %s", tag)
    sweep_df = pd.DataFrame(sweep_rows)
    csv_path = os.path.join(a.out, f"sweep_{a.mode}_{stamp}.csv")
    if len(sweep_df):
        sweep_df.to_csv(csv_path, index=False)

    # Tearsheet for the WF-selected costed result: concatenate the
    # per-fold daily returns (each fold starts fresh at CAPITAL, so
    # stitching raw equity would fabricate a boundary return).
    fold_rets = []
    for eq in sel_eqs:
        if eq:
            s = pd.Series(eq).sort_index()
            fold_rets.append(s.pct_change().dropna())
    sel_rets = pd.concat(fold_rets).sort_index() if fold_rets else pd.Series(dtype=float)
    tear = tear_sheet(sel_rets, None, os.path.join(a.out, f"tearsheet_{a.mode}_{stamp}.html"))

    report = render_report(a, folds, bench, sweep_df, sel_metrics, picks, tear, csv_path)
    md_path = os.path.join(a.out, f"{a.mode}_backtest_{stamp}.md")
    with open(md_path, "w") as f:
        f.write(report)
    print(report)
    print(f"\nReport: {md_path}\nSweep CSV: {csv_path}\nTearsheet: {tear}")
    return 0


def render_report(a, folds, bench, sweep_df, sel_metrics, picks, tear, csv_path):
    stamp = str(config.today_ist())
    lines = []
    lines.append(f"# Backtest report - {a.mode} leg ({stamp})")
    lines.append("")
    lines.append("Walk-forward only: train 250 bars / test 50 bars, rolled by 50. "
                 "All metrics below aggregate TEST windows only; every fold starts "
                 "fresh at Rs 5,000. Fills at next bar open + slippage; stops/targets "
                 "on High/Low intrabar; gap-through-stop fills at the open "
                 "(vectorbt extraction, repo-exact cost stack at assembly).")
    lines.append("")
    if a.mode == "intraday":
        lines.append("**Scope limit: Yahoo Finance caps 5-minute data at 60 days. "
                     "This intraday leg covers 60 days ONLY - it is not a 3-year "
                     "backtest and must not be read as one.**")
        lines.append("")
    lines.append("**Survivorship bias**: the symbol universe is TODAY's SYMBOLS list "
                 "applied to history. Names that died or were dropped are absent, "
                 "which flatters results. Noted, not solved.")
    lines.append("")
    lines.append("**Not in this backtest** (no honest historical inputs): Kronos "
                 "forecasts, FinBERT sentiment (no headline archive), the LLM "
                 "brain. This tests the rule core only: shortlist filters + "
                 "price>EMA21 + RSI band + ATR stop/target/trailing.")
    lines.append("")
    lines.append(f"Folds: {len(folds)} | First test window: {folds[0]['test_start'].date()} | "
                 f"Benchmark NIFTYBEES buy-and-hold: net {bench['net_return_pct']}% over the same test windows.")
    lines.append("")
    lines.append("## Walk-forward selection (train-picked, cost-filtered)")
    lines.append("")
    lines.append("Per fold, the config with the best TRAIN net P&L among those with "
                 "median cost_pct_of_target <= 25% was applied to the test window.")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(sel_metrics, indent=1))
    lines.append("```")
    lines.append("")
    lines.append("Fold picks: " + "; ".join(f"{d}: {p or 'none passed filter'}" for d, p in picks))
    lines.append("")
    if len(sweep_df):
        costed = sweep_df[sweep_df["run"] == "costed"].copy()
        zero = sweep_df[sweep_df["run"] == "zero-cost"].set_index("config")
        costed["passes_cost_filter"] = costed["median_cost_pct_of_target"].fillna(1) <= config.COST_TARGET_WARN_PCT
        ranked = costed[costed["passes_cost_filter"]].sort_values("net_return_pct", ascending=False)
        lines.append("## Top costed configs that PASS the 25% cost filter")
        lines.append("")
        lines.append("| Config | Trades | Win% | BE win% | Net% | MaxDD% | Sharpe | PF | Cost% of TP | Zero-cost net% (same config) |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for _, r in ranked.head(15).iterrows():
            z = zero.loc[r["config"]] if r["config"] in zero.index else None
            lines.append(f"| {r['config']} | {int(r['trades'])} | {r['win_rate']*100:.1f} | "
                         f"{r['break_even_win_rate']*100:.1f} | {r['net_return_pct']} | {r['max_drawdown_pct']} | "
                         f"{r['sharpe']} | {r['profit_factor']} | {r['median_cost_pct_of_target']} | "
                         f"{(z['net_return_pct'] if z is not None else 'n/a')} |")
        lines.append("")
        best_zero = zero.sort_values("net_return_pct", ascending=False).head(5)
        lines.append("## Zero-cost view (does raw edge exist at all?)")
        lines.append("")
        lines.append("Best zero-cost configs by net return, with their costed result alongside:")
        lines.append("")
        lines.append("| Config | Zero-cost net% | Zero-cost trades | Costed net% | Costed BE win% |")
        lines.append("|---|---|---|---|---|")
        costed_idx = costed.set_index("config")
        for label, z in best_zero.iterrows():
            c = costed_idx.loc[label] if label in costed_idx.index else None
            lines.append(f"| {label} | {z['net_return_pct']} | {int(z['trades'])} | "
                         f"{(c['net_return_pct'] if c is not None else 'n/a')} | "
                         f"{(c['break_even_win_rate'] if c is not None else 'n/a')} |")
        lines.append("")
        n_pass = int(costed["passes_cost_filter"].sum())
        lines.append(f"Configs passing the cost filter: {n_pass} of {len(costed)}. "
                     f"Full sweep: `{csv_path}`.")
        lines.append("")
    if tear:
        lines.append(f"Tearsheet (WF-selected, costed): `{tear}`")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
