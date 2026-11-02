"""Phase 1.5 diagnostics (d1-d8) for the swing backtest.

Analysis only - no strategy code, no re-tuning. Reads the committed
sweep CSV, the cached candidate pools and the bar cache; re-runs
portfolio assemblies (cheap - extraction is cached) where per-fold or
per-trade resolution is needed.

  python diagnose.py --out reports/

Sections follow the user's d1-d8 order in the file, but d5
(benchmark verification) is computed first because the headline
verdict leans on it.
"""
import argparse
import logging
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

import backtest
import config

log = logging.getLogger("diagnose")

SECTORS = {
    "Financials": ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "BANKBARODA", "PNB", "CANBK", "FEDERALBNK", "IDFCFIRSTB", "INDUSINDBK", "YESBANK", "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "SHRIRAMFIN", "MUTHOOTFIN", "LICHSGFIN", "JIOFIN", "HDFCLIFE", "ICICIPRULI", "SBILIFE", "MFSL"],
    "IT": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "MPHASIS", "OFSS", "PERSISTENT", "NAUKRI"],
    "Energy & Power": ["RELIANCE", "ONGC", "IOC", "BPCL", "GAIL", "PETRONET", "NTPC", "POWERGRID", "TATAPOWER", "COALINDIA"],
    "Metals & Mining": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "SAIL"],
    "Auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "TVSMOTOR", "ASHOKLEY", "MOTHERSON", "EXIDEIND", "BALKRISIND"],
    "Pharma & Health": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "AUROPHARMA", "LUPIN", "ZYDUSLIFE", "BIOCON", "GLENMARK", "ALKEM", "TORNTPHARM", "APOLLOHOSP"],
    "FMCG & Consumer": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "GODREJCP", "COLPAL", "TATACONSUM", "UBL", "JUBLFOOD", "TRENT", "TITAN", "PAGEIND"],
    "Cement & Building": ["ULTRACEMCO", "GRASIM", "AMBUJACEM", "ACC", "SRF", "PIDILITIND", "BERGEPAINT", "ASIANPAINT", "POLYCAB", "HAVELLS", "VOLTAS"],
    "Capital Goods & Infra": ["LT", "SIEMENS", "ABB", "CUMMINSIND", "BHEL", "BEL", "ADANIPORTS", "CONCOR"],
    "Telecom": ["BHARTIARTL", "IDEA"],
    "Realty & Services": ["DLF", "INDHOTEL", "IRCTC", "ADANIENT"],
    "Chemicals": ["UPL"],
}
SYM2SECTOR = {s: sec for sec, syms in SECTORS.items() for s in syms}


def refined_reason(c):
    """Split the extractor's coarse 'stop' into initial-stop vs
    trailing-stop using the candidate's own stop/target levels."""
    if c["exit_reason"] == "window_end":
        return "window_end"
    tol = max(0.10, 0.001 * c["entry_raw"])
    if c["exit_raw"] >= c["target"] - tol:
        return "target"
    if c["exit_raw"] <= c["stop"] + tol:
        return "stop"
    return "trail"


def expectancy_pct(trades):
    """Mean per-trade return % of notional (trades carry qty/entry/net)."""
    vals = [t["net_pnl"] / (t["qty"] * t["entry"]) * 100 for t in trades if t["qty"] * t["entry"] > 0]
    return float(np.mean(vals)) if vals else 0.0


class _PoolUnpickler(pickle.Unpickler):
    """Pools were pickled by backtest.py running as __main__, so the
    Variant/Config classes resolve to __main__ there; remap them to
    the backtest module's classes here."""
    def find_class(self, module, name):
        if name in ("Variant", "Config"):
            return getattr(backtest, name)
        return super().find_class(module, name)


def load_pools(mode="swing"):
    import glob
    files = sorted(glob.glob(os.path.join(backtest.CACHE_ROOT, f"pools_{mode}_*.pkl")))
    with open(files[-1], "rb") as fh:
        return _PoolUnpickler(fh).load()


def parse_picks(report_path):
    with open(report_path) as fh:
        txt = fh.read()
    line = next(l for l in txt.splitlines() if l.startswith("Fold picks:"))
    picks = []
    for m in re.finditer(r"(\d{4}-\d{2}-\d{2}): (rsi\d+-\d+_sl[\d.]+_tp[\d.]+_risk[\d.]+_maxpos\d+)", line):
        picks.append((m.group(1), m.group(2)))
    return picks


def label_to_config(label):
    m = re.match(r"rsi(\d+)-(\d+)_sl([\d.]+)_tp([\d.]+)_risk([\d.]+)_maxpos(\d+)", label)
    v = backtest.Variant(int(m.group(1)), int(m.group(2)), float(m.group(3)), float(m.group(4)))
    return backtest.Config(v, float(m.group(5)), int(m.group(6)))


# ------------------------------------------------------------------ d5

def d5_benchmark(bars, folds):
    """Per-fold NIFTYBEES buy-and-hold, rebuilt from raw bars (not the
    report aggregate), plus the chained path and full-span return."""
    df = bars[backtest.BENCHMARK]
    rows = []
    for i, f in enumerate(folds):
        lo, hi = f["test"]
        w = df[(df.index >= lo) & (df.index < hi)]
        if len(w) < 2:
            continue
        o, c = float(w["Open"].iloc[0]), float(w["Close"].iloc[-1])
        rows.append({"fold": i + 1, "from": str(w.index[0].date()), "to": str(w.index[-1].date()),
                     "open": o, "close": c, "ret_pct": round((c / o - 1) * 100, 2)})
    out = pd.DataFrame(rows)
    if len(out):
        chained = float(np.prod(1 + out["ret_pct"] / 100) - 1) * 100
        first_o = float(df[(df.index >= folds[0]["test"][0])]["Open"].iloc[0])
        last_hi = folds[-1]["test"][1]
        last_c = float(df[df.index < last_hi]["Close"].iloc[-1])
        out.attrs["chained"] = round(chained, 2)
        out.attrs["full_span"] = round((last_c / first_o - 1) * 100, 2)
        out.attrs["mean_fold"] = round(float(out["ret_pct"].mean()), 2)
    return out


# ------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="swing")
    ap.add_argument("--out", default="reports/")
    ap.add_argument("--report", default="reports/swing_backtest_2026-11-02.md")
    ap.add_argument("--sweep", default="reports/sweep_swing_2026-11-02.csv")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    bars = backtest.load_all(a.mode, list(config.SYMBOLS) + [backtest.BENCHMARK])
    pools = load_pools(a.mode)
    sweep = pd.read_csv(a.sweep)
    cal = sorted(bars[backtest.BENCHMARK].index)
    folds = backtest.make_folds(cal, start_from=pd.Timestamp("2023-01-01"))
    picks = parse_picks(a.report)
    L = []
    L.append("# Phase 1.5 diagnosis - swing rule core (2026-11-02)")
    L.append("")
    L.append("Analysis of the Phase 1 sweep. No re-tuning, no new strategy code. "
             "Candidate-level sections use the extraction pools (every trade the entry "
             "rule generated, before portfolio assembly); config-level sections use "
             "portfolio assemblies over the cached pools.")
    L.append("")

    # ---- d5 first (the headline leans on it) ----
    bench = d5_benchmark(bars, folds)
    L.append("## d5 - Benchmark verification (per-fold NIFTYBEES)")
    L.append("")
    L.append(bench.to_markdown(index=False))
    L.append("")
    L.append(f"Arithmetic mean of fold returns: {bench.attrs['mean_fold']}% per fold. "
             f"Chained (compounded) across the 13 windows: {bench.attrs['chained']}%. "
             f"Full-span (first test open -> last test close): {bench.attrs['full_span']}%. "
             f"The report's +0.36% was total P&L / (Rs 5,000 x 13 folds) AFTER swing costs "
             f"(~Rs 17/fold of costs on a fractional-unit benchmark) - i.e. the mean fold "
             f"return net of costs. The windows are consecutive and non-overlapping, so "
             f"the per-fold rows show exactly which parts of the index path they covered.")
    L.append("")

    # ---- candidate population ----
    cand_rows = []
    for v, pool in pools.items():
        for c in pool:
            cand_rows.append({**c, "variant": v, "reason_r": refined_reason(c),
                              "gross_ret_pct": (c["exit_raw"] / c["entry_raw"] - 1) * 100,
                              "hold_bars": None})
    cand = pd.DataFrame(cand_rows)
    log.info("candidates: %d", len(cand))

    # ---- d1 ----
    d1 = cand["reason_r"].value_counts(normalize=True).mul(100).round(1)
    d1n = cand["reason_r"].value_counts()
    L.append("## d1 - Exit-reason distribution (all candidate trades, all 36 variants)")
    L.append("")
    L.append("| Exit | Count | % |")
    L.append("|---|---|---|")
    for r in ["stop", "trail", "target", "window_end"]:
        if r in d1n:
            L.append(f"| {r} | {int(d1n[r])} | {d1[r]} |")
    L.append("")
    by_sl = cand.groupby([cand["variant"].map(lambda v: v.sl_atr), "reason_r"]).size().unstack(fill_value=0)
    by_sl_pct = (by_sl.T / by_sl.sum(axis=1)).T.mul(100).round(1)
    L.append("By stop multiple (share of exits, %):")
    L.append("")
    L.append(by_sl_pct.to_markdown())
    L.append("")

    # ---- d2 ----
    log.info("d2: computing MFE on stopped candidates...")
    nb = bars[backtest.BENCHMARK]
    stopped = cand[cand["reason_r"].isin(["stop", "trail"])].copy()
    mfe_vals = []
    by_sym = {s: bars[s] for s in stopped["symbol"].unique() if s in bars}
    pos_cache = {}
    for _, c in stopped.iterrows():
        df = by_sym.get(c["symbol"])
        if df is None:
            mfe_vals.append(np.nan); continue
        key = c["symbol"]
        if key not in pos_cache:
            pos_cache[key] = {d: i for i, d in enumerate(df.index)}
        pos = pos_cache[key]
        i0, i1 = pos.get(c["entry_date"]), pos.get(c["exit_date"])
        if i0 is None or i1 is None or c["atr"] <= 0:
            mfe_vals.append(np.nan); continue
        hi = float(df["High"].iloc[i0:i1 + 1].max())
        mfe_vals.append((hi - c["entry_raw"]) / c["atr"])
    stopped["mfe_atr"] = mfe_vals
    ok = stopped.dropna(subset=["mfe_atr"])
    frac1 = float((ok["mfe_atr"] >= 1.0).mean()) if len(ok) else 0.0
    frac05 = float((ok["mfe_atr"] >= 0.5).mean()) if len(ok) else 0.0
    pure_stop = ok[ok["reason_r"] == "stop"]
    frac1s = float((pure_stop["mfe_atr"] >= 1.0).mean()) if len(pure_stop) else 0.0
    L.append("## d2 - MFE before stop (were stopped trades ever winning?)")
    L.append("")
    L.append(f"Stopped/trailing-stopped candidates analysed: {len(ok)} "
             f"(of {len(stopped)}; rest lacked bar alignment).")
    L.append(f"- Had >= 1.0 x ATR favourable excursion before dying: **{frac1*100:.1f}%**")
    L.append(f"- Had >= 0.5 x ATR favourable excursion: {frac05*100:.1f}%")
    L.append(f"- Initial-stop exits only: >= 1.0 x ATR excursion in {frac1s*100:.1f}%")
    L.append(f"- Median MFE of stopped trades: {float(ok['mfe_atr'].median()):.2f} x ATR")
    L.append("")

    # ---- d3 + d4: per-fold assemblies (zero-cost for gross, costed for net) ----
    log.info("d3: zero-cost assemblies for all 432 configs x %d folds...", len(folds))
    gross_rows = []
    cfg_objs = {c.label(): c for c in backtest.all_configs()}
    for label, cfg in cfg_objs.items():
        pool = pools[cfg.variant]
        tot_trades, pos_folds = [], 0
        fold_net = 0.0
        for f in folds:
            lo, hi = f["test"]
            tr, _ = backtest.assemble(pool, cfg, lo, hi, bars, False, a.mode, calendar=[])
            tot_trades.extend(tr)
            net = sum(t["net_pnl"] for t in tr)
            fold_net += net
            if net > 0:
                pos_folds += 1
        gross_rows.append({"config": label, "trades": len(tot_trades),
                            "gross_exp_pct": round(expectancy_pct(tot_trades), 3),
                            "gross_win_rate": round(float(np.mean([t["net_pnl"] > 0 for t in tot_trades])), 3) if tot_trades else 0.0,
                            "gross_net_pct": round(fold_net / (config.CAPITAL * len(folds)) * 100, 2),
                            "pos_folds": pos_folds})
    gross = pd.DataFrame(gross_rows)
    costed = sweep[sweep["run"] == "costed"][["config", "net_return_pct", "median_cost_pct_of_target"]]
    gross = gross.merge(costed, on="config", how="left", suffixes=("", "_costed"))
    gross = gross.sort_values("gross_exp_pct", ascending=False)
    alive = gross[(gross["trades"] >= 100) & (gross["pos_folds"] >= 8) & (gross["gross_exp_pct"] > 0)]
    L.append("## d3 - Gross-expectancy ranking (zero-cost, per config)")
    L.append("")
    L.append("Top 15 by gross expectancy per trade (% of notional, before ALL costs):")
    L.append("")
    L.append("| Config | Trades | Gross exp %/trade | Gross win% | Gross net% | +folds | Costed net% |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in gross.head(15).iterrows():
        L.append(f"| {r['config']} | {int(r['trades'])} | {r['gross_exp_pct']} | {r['gross_win_rate']*100:.1f} | "
                 f"{r['gross_net_pct']} | {int(r['pos_folds'])}/13 | {r['net_return_pct']} |")
    L.append("")
    L.append(f"Median gross expectancy across the 432: {gross['gross_exp_pct'].median():.3f}%/trade. "
             f"Configs gross-positive at all: {int((gross['gross_exp_pct'] > 0).sum())}/432. "
             f"Configs meeting the d3 life test (gross-positive AND >=100 trades AND >=8/13 positive folds): "
             f"**{len(alive)}**.")
    L.append("")

    # WF path: per-fold (d4) + exact gross/costed decomposition
    L.append("## d4 - Walk-forward-selected path, per fold")
    L.append("")
    L.append("| Fold test from | Picked config | Trades | Gross exp % | Net Rs (costed) | Costs Rs |")
    L.append("|---|---|---|---|---|---|")
    wf_gross_trades, wf_cost_trades = [], []
    fold_by_date = {str(f["test_start"].date()): f for f in folds}
    for date_s, label in picks:
        cfg = label_to_config(label)
        f = fold_by_date[date_s]
        lo, hi = f["test"]
        trg, _ = backtest.assemble(pools[cfg.variant], cfg, lo, hi, bars, False, a.mode, calendar=[])
        trc, _ = backtest.assemble(pools[cfg.variant], cfg, lo, hi, bars, True, a.mode, calendar=[])
        wf_gross_trades.extend(trg); wf_cost_trades.extend(trc)
        L.append(f"| {date_s} | {label} | {len(trc)} | {expectancy_pct(trg):.3f} | "
                 f"{sum(t['net_pnl'] for t in trc):.0f} | {sum(t['costs'] for t in trc):.0f} |")
    g_exp = expectancy_pct(wf_gross_trades)
    c_exp = expectancy_pct(wf_cost_trades)
    avg_cost_pct = g_exp - c_exp
    L.append("")
    L.append(f"**WF path decomposition (per trade, % of notional): gross expectancy {g_exp:.3f}%, "
             f"cost drag {avg_cost_pct:.3f}%, costed expectancy {c_exp:.3f}%.** "
             f"Gross is {'positive' if g_exp > 0 else 'NEGATIVE'} before costs; "
             f"the gross edge is {abs(g_exp/avg_cost_pct):.2f}x the cost drag." if avg_cost_pct else "")
    L.append("")

    # ---- d6 ----
    nb_close = nb["Close"]
    dma200 = nb_close.rolling(200).mean().shift(1)
    regime = pd.Series(np.where(nb_close > dma200, "above", "below"), index=nb.index)
    regime_map = regime.to_dict()
    cand["regime"] = [regime_map.get(d, "unknown") for d in cand["entry_date"]]
    d6 = cand[cand["regime"].isin(["above", "below"])].groupby("regime")["gross_ret_pct"].agg(["count", "mean"])
    d6w = cand[cand["regime"].isin(["above", "below"])].groupby("regime")["gross_ret_pct"].apply(lambda s: float((s > 0).mean()))
    L.append("## d6 - Regime split (candidate gross return by NIFTY vs 200DMA at entry)")
    L.append("")
    L.append("| Regime | Trades | Gross exp %/trade | Win% |")
    L.append("|---|---|---|---|")
    for r in ["above", "below"]:
        if r in d6.index:
            L.append(f"| NIFTY {r} 200DMA | {int(d6.loc[r, 'count'])} | {d6.loc[r, 'mean']:.3f} | {d6w[r]*100:.1f} |")
    L.append("")

    # ---- d7 ----
    losses = cand[cand["gross_ret_pct"] < 0].copy()
    losses["gross_loss"] = -losses["gross_ret_pct"] * losses["entry_raw"]  # per-share loss proxy
    losses["sector"] = losses["symbol"].map(SYM2SECTOR).fillna("Other")
    sec = losses.groupby("sector")["gross_loss"].sum().sort_values(ascending=False)
    sec_pct = (sec / sec.sum() * 100).round(1)
    band = pd.cut(losses["entry_raw"], [0, 250, 500, 1000, 1500], labels=["<250", "250-500", "500-1000", "1000-1500"])
    pb_ = losses.groupby(band, observed=True)["gross_loss"].sum()
    pb_pct = (pb_ / pb_.sum() * 100).round(1)
    L.append("## d7 - Loss concentration (candidate-level gross losses)")
    L.append("")
    L.append("By sector (share of total gross loss, %; sector map is approximate):")
    L.append("")
    for s, v in sec_pct.items():
        L.append(f"- {s}: {v}")
    L.append("")
    L.append("By entry price band (share of total gross loss, %):")
    L.append("")
    for s, v in pb_pct.items():
        L.append(f"- Rs {s}: {v}")
    L.append("")
    L.append("Position size: at the live default (risk 1.5%, equity Rs 5,000) qty is set by the "
             "stop distance, so notional concentrates where ATR% is small; the sweep's own "
             "risk dimension is in d3 - higher risk multiples scale the loss, they do not "
             "change its sign (gross expectancy is size-invariant per trade).")
    L.append("")

    # ---- d8 ----
    L.append("## d8 - Marginal separation (one-line filters on the best variant family)")
    L.append("")
    ind = {s: backtest.add_signal_columns(bars[s]) for s in bars if s != backtest.BENCHMARK}
    full_cal = sorted({d for df in bars.values() for d in df.index})
    filters = {
        "REL_VOLUME>1.5": lambda d: d["REL_VOLUME"] > 1.5,
        "DIST_20D_HIGH_PCT>-2": lambda d: d["DIST_20D_HIGH_PCT"] > -2,
    }
    L.append("| Variant | Filter | Cand. trades | Gross exp %/trade | Assembled trades (risk .02/maxpos 2) | Gross exp % | Costed net% |")
    L.append("|---|---|---|---|---|---|---|")
    for v in [backtest.Variant(40, 70, 2.0, 8.0), backtest.Variant(40, 70, 1.5, 8.0)]:
        base_pool = pools[v]
        base_exp = float(np.mean([(c["exit_raw"] / c["entry_raw"] - 1) * 100 for c in base_pool]))
        cfg = backtest.Config(v, 0.02, 2)
        trg_all, trc_all = [], []
        for f in folds:
            lo, hi = f["test"]
            t1, _ = backtest.assemble(base_pool, cfg, lo, hi, bars, False, a.mode, calendar=[])
            t2, _ = backtest.assemble(base_pool, cfg, lo, hi, bars, True, a.mode, calendar=[])
            trg_all.extend(t1); trc_all.extend(t2)
        net_pct = sum(t["net_pnl"] for t in trc_all) / (config.CAPITAL * len(folds)) * 100
        L.append(f"| sl{v.sl_atr}_tp{v.tp_atr} | none | {len(base_pool)} | {base_exp:.3f} | {len(trg_all)} | "
                 f"{expectancy_pct(trg_all):.3f} | {net_pct:.2f} |")
        for name, fn in filters.items():
            pool_f = backtest.extract_pool_batch(ind, v, full_cal, extra_filter=fn)
            if not pool_f:
                L.append(f"| sl{v.sl_atr}_tp{v.tp_atr} | {name} | 0 | - | 0 | - | - |")
                continue
            fexp = float(np.mean([(c["exit_raw"] / c["entry_raw"] - 1) * 100 for c in pool_f]))
            tg, tc = [], []
            for f in folds:
                lo, hi = f["test"]
                t1, _ = backtest.assemble(pool_f, cfg, lo, hi, bars, False, a.mode, calendar=[])
                t2, _ = backtest.assemble(pool_f, cfg, lo, hi, bars, True, a.mode, calendar=[])
                tg.extend(t1); tc.extend(t2)
            net_pct_f = sum(t["net_pnl"] for t in tc) / (config.CAPITAL * len(folds)) * 100
            L.append(f"| sl{v.sl_atr}_tp{v.tp_atr} | {name} | {len(pool_f)} | {fexp:.3f} | {len(tg)} | "
                     f"{expectancy_pct(tg):.3f} | {net_pct_f:.2f} |")
    L.append("")

    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, "diagnosis_2026-11-02.md")
    with open(path, "w") as fh:
        fh.write("\n".join(L))
    print("\n".join(L))
    print(f"\nDiagnosis: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
