# Backtest report - swing leg (2026-11-02)

Walk-forward only: train 250 bars / test 50 bars, rolled by 50. All metrics below aggregate TEST windows only; every fold starts fresh at Rs 5,000. Fills at next bar open + slippage; stops/targets on High/Low intrabar; gap-through-stop fills at the open (vectorbt extraction, repo-exact cost stack at assembly).

**Survivorship bias**: the symbol universe is TODAY's SYMBOLS list applied to history. Names that died or were dropped are absent, which flatters results. Noted, not solved.

**Not in this backtest** (no honest historical inputs): Kronos forecasts, FinBERT sentiment (no headline archive), the LLM brain. This tests the rule core only: shortlist filters + price>EMA21 + RSI band + ATR stop/target/trailing.

Folds: 13 | First test window: 2024-01-08 | Benchmark NIFTYBEES buy-and-hold: net 0.36% over the same test windows.

## Walk-forward selection (train-picked, cost-filtered)

Per fold, the config with the best TRAIN net P&L among those with median cost_pct_of_target <= 25% was applied to the test window.

```json
{
 "trades": 205,
 "win_rate": 0.3171,
 "break_even_win_rate": 0.4063,
 "avg_win_pct": 6.463,
 "avg_loss_pct": -5.146,
 "avg_win_rs": 86.16,
 "avg_loss_rs": 58.97,
 "net_pnl": -2656.13,
 "net_return_pct": -4.09,
 "max_drawdown_pct": -46.21,
 "sharpe": 0.22,
 "profit_factor": 0.68,
 "median_cost_pct_of_target": 0.0717,
 "total_costs": 3064.08
}
```

Fold picks: 2024-01-08: rsi45-75_sl1.5_tp6.0_risk0.02_maxpos5; 2024-03-21: rsi45-75_sl1.5_tp6.0_risk0.015_maxpos5; 2024-06-07: rsi45-75_sl1.5_tp3.0_risk0.02_maxpos3; 2024-08-21: rsi35-65_sl1.5_tp8.0_risk0.02_maxpos5; 2024-10-31: rsi35-65_sl2.5_tp8.0_risk0.02_maxpos3; 2025-01-14: rsi40-70_sl1.5_tp8.0_risk0.02_maxpos2; 2025-03-26: rsi35-65_sl2.5_tp8.0_risk0.02_maxpos3; 2025-06-11: rsi35-65_sl2.5_tp6.0_risk0.015_maxpos2; 2025-08-21: rsi45-75_sl2.5_tp8.0_risk0.01_maxpos2; 2025-11-06: rsi40-70_sl1.5_tp8.0_risk0.02_maxpos2; 2026-01-16: rsi40-70_sl2.5_tp4.0_risk0.02_maxpos2; 2026-04-02: rsi40-70_sl2.5_tp4.0_risk0.02_maxpos2; 2026-06-17: rsi40-70_sl2.5_tp4.0_risk0.02_maxpos2

## Top costed configs that PASS the 25% cost filter

| Config | Trades | Win% | BE win% | Net% | MaxDD% | Sharpe | PF | Cost% of TP | Zero-cost net% (same config) |
|---|---|---|---|---|---|---|---|---|---|
| rsi40-70_sl2.0_tp8.0_risk0.02_maxpos2 | 122 | 32.8 | 35.9 | -1.01 | -49.17 | -0.07 | 0.87 | 0.0456 | 2.66 |
| rsi35-65_sl2.0_tp3.0_risk0.02_maxpos2 | 153 | 37.2 | 39.8 | -1.02 | -48.87 | 0.12 | 0.9 | 0.1205 | 3.49 |
| rsi40-70_sl1.5_tp8.0_risk0.02_maxpos2 | 185 | 36.2 | 38.2 | -1.06 | -42.85 | 0.34 | 0.92 | 0.0359 | 5.06 |
| rsi45-75_sl2.0_tp8.0_risk0.02_maxpos2 | 121 | 33.1 | 36.9 | -1.2 | -49.17 | -0.15 | 0.84 | 0.0459 | 2.41 |
| rsi35-65_sl2.5_tp8.0_risk0.02_maxpos2 | 93 | 37.6 | 43.7 | -1.41 | -33.07 | -0.14 | 0.78 | 0.0568 | 1.08 |
| rsi35-65_sl2.5_tp8.0_risk0.015_maxpos2 | 93 | 35.5 | 43.0 | -1.42 | -23.13 | -0.09 | 0.73 | 0.0713 | 0.93 |
| rsi45-75_sl2.5_tp4.0_risk0.02_maxpos2 | 110 | 35.4 | 40.6 | -1.42 | -34.92 | 0.39 | 0.8 | 0.1108 | 1.58 |
| rsi40-70_sl2.0_tp8.0_risk0.015_maxpos2 | 122 | 32.8 | 38.8 | -1.46 | -46.04 | -0.21 | 0.77 | 0.0567 | 1.7 |
| rsi45-75_sl2.5_tp8.0_risk0.005_maxpos2 | 92 | 23.9 | 39.5 | -1.48 | -14.47 | -0.82 | 0.48 | 0.1697 | 0.45 |
| rsi40-70_sl2.5_tp8.0_risk0.01_maxpos2 | 92 | 28.3 | 38.1 | -1.49 | -22.0 | -0.57 | 0.64 | 0.098 | 0.68 |
| rsi35-65_sl2.0_tp3.0_risk0.015_maxpos2 | 153 | 35.9 | 40.8 | -1.51 | -43.78 | -0.03 | 0.81 | 0.1497 | 2.53 |
| rsi45-75_sl2.5_tp8.0_risk0.01_maxpos2 | 94 | 27.7 | 37.6 | -1.58 | -20.89 | -0.47 | 0.63 | 0.0927 | 0.6 |
| rsi45-75_sl2.0_tp8.0_risk0.015_maxpos2 | 121 | 33.1 | 39.7 | -1.61 | -46.04 | -0.29 | 0.75 | 0.0571 | 1.5 |
| rsi35-65_sl2.5_tp8.0_risk0.01_maxpos2 | 95 | 30.5 | 41.9 | -1.65 | -22.94 | -0.42 | 0.61 | 0.0991 | 0.56 |
| rsi40-70_sl2.5_tp6.0_risk0.01_maxpos2 | 93 | 29.0 | 41.0 | -1.77 | -26.69 | -0.2 | 0.59 | 0.1245 | 0.37 |

## Zero-cost view (does raw edge exist at all?)

Best zero-cost configs by net return, with their costed result alongside:

| Config | Zero-cost net% | Zero-cost trades | Costed net% | Costed BE win% |
|---|---|---|---|---|
| rsi40-70_sl1.5_tp8.0_risk0.02_maxpos3 | 5.17 | 266 | -2.6 | 0.3556 |
| rsi40-70_sl1.5_tp8.0_risk0.02_maxpos2 | 5.06 | 185 | -1.06 | 0.3823 |
| rsi45-75_sl1.5_tp4.0_risk0.02_maxpos2 | 3.94 | 213 | -3.09 | 0.4102 |
| rsi45-75_sl1.5_tp8.0_risk0.02_maxpos2 | 3.88 | 188 | -2.25 | 0.3768 |
| rsi40-70_sl1.5_tp8.0_risk0.02_maxpos5 | 3.76 | 356 | -5.58 | 0.3288 |

Configs passing the cost filter: 378 of 432. Full sweep: `reports/sweep_swing_2026-11-02.csv`.

Tearsheet (WF-selected, costed): `reports/tearsheet_swing_2026-11-02.html`

## Intraday leg — scope note

Not run. Yahoo Finance caps 5-minute history at 60 days, so the spec's 3-year intraday backtest is impossible on the current data source (Phase 1 amendment, Nov 2). If run, the intraday leg would cover 60 days ONLY and be labelled as such. The alternative — pulling 1-minute history from Upstox into the cache — needs an Upstox account opened by the user (no card, but a real signup). Swing leg was done first regardless, per instruction.

## Verdict (added on delivery, Nov 2)

- **Zero-cost is economically flat.** The single best zero-cost config made +5.17% in total across all 13 out-of-sample test windows (~650 trading days) on 266 trades — roughly Rs 1 of gross edge per trade. The median zero-cost config is far below that. There is no meaningful raw edge in the rule core to optimise costs against.
- **Costed, nothing survives: 0 of 432 configs are positive.** Best costed config: -1.01%. Median costed config: -4.88%. The hard cost filter passes 378 configs and every one of them still loses.
- **Walk-forward selection (the no-peeking number): -4.09% net**, realised win rate 31.7% vs break-even 40.6%, profit factor 0.68, total costs Rs 3,064 on 205 trades (~Rs 15/trade, matching the Phase 0 cost model).
- The NIFTYBEES benchmark returned +0.36% over the same test windows — a flat benchmark that still beat every costed configuration.
- Per the Phase 1 gate set by the user ("if the zero-cost run is flat, say so plainly and we stop before Phase 2"): **the zero-cost run is flat for practical purposes, and Phase 2 does not start on this evidence.** What this verdict covers: the rule core (shortlist filters + EMA21/RSI/ATR exits) in swing mode on today's universe, 2024-2026 out-of-sample. What it does NOT cover: the Kronos/FinBERT/LLM layers, which have no historical inputs and were excluded rather than faked.
