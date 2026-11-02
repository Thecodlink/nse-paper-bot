# Phase 1.5 diagnosis - swing rule core (2026-11-02)

Analysis of the Phase 1 sweep. No re-tuning, no new strategy code. Candidate-level sections use the extraction pools (every trade the entry rule generated, before portfolio assembly); config-level sections use portfolio assemblies over the cached pools.

## d5 - Benchmark verification (per-fold NIFTYBEES)

|   fold | from       | to         |   open |   close |   ret_pct |
|-------:|:-----------|:-----------|-------:|--------:|----------:|
|      1 | 2024-01-08 | 2024-03-20 | 242    |  241.58 |     -0.17 |
|      2 | 2024-03-21 | 2024-06-06 | 243.8  |  252.98 |      3.77 |
|      3 | 2024-06-07 | 2024-08-20 | 253.88 |  275.83 |      8.65 |
|      4 | 2024-08-21 | 2024-10-30 | 275.95 |  272.16 |     -1.37 |
|      5 | 2024-10-31 | 2025-01-13 | 273.99 |  258.4  |     -5.69 |
|      6 | 2025-01-14 | 2025-03-25 | 260.95 |  264.73 |      1.45 |
|      7 | 2025-03-26 | 2025-06-10 | 264.1  |  281.39 |      6.55 |
|      8 | 2025-06-11 | 2025-08-20 | 281.75 |  282.52 |      0.27 |
|      9 | 2025-08-21 | 2025-11-04 | 284.99 |  289.59 |      1.61 |
|     10 | 2025-11-06 | 2026-01-15 | 290.4  |  290.66 |      0.09 |
|     11 | 2026-01-16 | 2026-04-01 | 291.89 |  257.45 |    -11.8  |
|     12 | 2026-04-02 | 2026-06-16 | 256.99 |  271.67 |      5.71 |
|     13 | 2026-06-17 | 2026-08-26 | 272.8  |  277.02 |      1.55 |

Arithmetic mean of fold returns: 0.82% per fold. Chained (compounded) across the 13 windows: 9.27%. Full-span (first test open -> last test close): 14.47%. The report's +0.36% was total P&L / (Rs 5,000 x 13 folds) AFTER swing costs (~Rs 17/fold of costs on a fractional-unit benchmark) - i.e. the mean fold return net of costs. The windows are consecutive and non-overlapping, so the per-fold rows show exactly which parts of the index path they covered.

## d1 - Exit-reason distribution (all candidate trades, all 36 variants)

| Exit | Count | % |
|---|---|---|
| stop | 26408 | 16.8 |
| trail | 108216 | 68.9 |
| target | 21451 | 13.7 |
| window_end | 931 | 0.6 |

By stop multiple (share of exits, %):

|   variant |   stop |   target |   trail |   window_end |
|----------:|-------:|---------:|--------:|-------------:|
|       1.5 |   20.5 |      8.6 |    70.5 |          0.4 |
|       2   |   14.9 |     14.8 |    69.6 |          0.6 |
|       2.5 |   12.4 |     21.6 |    65.1 |          0.9 |

## d2 - MFE before stop (were stopped trades ever winning?)

Stopped/trailing-stopped candidates analysed: 134624 (of 134624; rest lacked bar alignment).
- Had >= 1.0 x ATR favourable excursion before dying: **57.3%**
- Had >= 0.5 x ATR favourable excursion: 74.5%
- Initial-stop exits only: >= 1.0 x ATR excursion in 2.9%
- Median MFE of stopped trades: 1.22 x ATR

## d3 - Gross-expectancy ranking (zero-cost, per config)

Top 15 by gross expectancy per trade (% of notional, before ALL costs):

| Config | Trades | Gross exp %/trade | Gross win% | Gross net% | +folds | Costed net% |
|---|---|---|---|---|---|---|
| rsi35-65_sl2.5_tp8.0_risk0.02_maxpos2 | 93 | 1.568 | 41.9 | 1.08 | 7/13 | -1.41 |
| rsi35-65_sl2.5_tp8.0_risk0.015_maxpos2 | 93 | 1.568 | 41.9 | 0.93 | 6/13 | -1.42 |
| rsi40-70_sl2.5_tp8.0_risk0.01_maxpos2 | 92 | 1.268 | 42.4 | 0.68 | 7/13 | -1.49 |
| rsi40-70_sl2.5_tp8.0_risk0.015_maxpos2 | 91 | 1.265 | 40.7 | 0.28 | 6/13 | -1.99 |
| rsi40-70_sl2.5_tp8.0_risk0.02_maxpos2 | 91 | 1.265 | 40.7 | 0.44 | 6/13 | -2.01 |
| rsi35-65_sl2.5_tp8.0_risk0.01_maxpos2 | 95 | 1.252 | 43.2 | 0.56 | 7/13 | -1.65 |
| rsi45-75_sl2.5_tp3.0_risk0.01_maxpos2 | 128 | 1.25 | 44.5 | 0.94 | 8/13 | -2.02 |
| rsi35-65_sl2.0_tp3.0_risk0.015_maxpos2 | 153 | 1.207 | 41.8 | 2.53 | 9/13 | -1.51 |
| rsi35-65_sl2.0_tp3.0_risk0.02_maxpos2 | 153 | 1.207 | 41.8 | 3.49 | 9/13 | -1.02 |
| rsi45-75_sl2.5_tp4.0_risk0.01_maxpos2 | 110 | 1.188 | 41.8 | 0.78 | 6/13 | -1.77 |
| rsi35-65_sl2.0_tp3.0_risk0.01_maxpos2 | 155 | 1.177 | 41.9 | 1.82 | 8/13 | -1.94 |
| rsi45-75_sl2.5_tp3.0_risk0.02_maxpos2 | 127 | 1.173 | 44.1 | 1.43 | 7/13 | -1.93 |
| rsi45-75_sl2.5_tp3.0_risk0.015_maxpos2 | 127 | 1.173 | 44.1 | 0.76 | 7/13 | -2.53 |
| rsi45-75_sl2.5_tp4.0_risk0.005_maxpos2 | 112 | 1.122 | 41.1 | 0.9 | 7/13 | -1.59 |
| rsi45-75_sl2.5_tp4.0_risk0.015_maxpos2 | 110 | 1.093 | 41.8 | 1.03 | 5/13 | -1.77 |

Median gross expectancy across the 432: 0.339%/trade. Configs gross-positive at all: 391/432. Configs meeting the d3 life test (gross-positive AND >=100 trades AND >=8/13 positive folds): **89**.

## d4 - Walk-forward-selected path, per fold

| Fold test from | Picked config | Trades | Gross exp % | Net Rs (costed) | Costs Rs |
|---|---|---|---|---|---|
| 2024-01-08 | rsi45-75_sl1.5_tp6.0_risk0.02_maxpos5 | 35 | 1.417 | -94 | 523 |
| 2024-03-21 | rsi45-75_sl1.5_tp6.0_risk0.015_maxpos5 | 31 | 2.567 | 128 | 443 |
| 2024-06-07 | rsi45-75_sl1.5_tp3.0_risk0.02_maxpos3 | 17 | 2.106 | -230 | 258 |
| 2024-08-21 | rsi35-65_sl1.5_tp8.0_risk0.02_maxpos5 | 32 | -1.312 | -1240 | 467 |
| 2024-10-31 | rsi35-65_sl2.5_tp8.0_risk0.02_maxpos3 | 14 | -1.463 | -567 | 200 |
| 2025-01-14 | rsi40-70_sl1.5_tp8.0_risk0.02_maxpos2 | 13 | 1.017 | -47 | 209 |
| 2025-03-26 | rsi35-65_sl2.5_tp8.0_risk0.02_maxpos3 | 7 | 2.195 | -28 | 100 |
| 2025-06-11 | rsi35-65_sl2.5_tp6.0_risk0.015_maxpos2 | 8 | -3.927 | -537 | 117 |
| 2025-08-21 | rsi45-75_sl2.5_tp8.0_risk0.01_maxpos2 | 7 | -1.448 | -121 | 99 |
| 2025-11-06 | rsi40-70_sl1.5_tp8.0_risk0.02_maxpos2 | 13 | 2.517 | 697 | 232 |
| 2026-01-16 | rsi40-70_sl2.5_tp4.0_risk0.02_maxpos2 | 12 | 0.201 | -255 | 178 |
| 2026-04-02 | rsi40-70_sl2.5_tp4.0_risk0.02_maxpos2 | 9 | 1.963 | 37 | 131 |
| 2026-06-17 | rsi40-70_sl2.5_tp4.0_risk0.02_maxpos2 | 7 | -2.404 | -398 | 106 |

**WF path decomposition (per trade, % of notional): gross expectancy 0.668%, cost drag 2.133%, costed expectancy -1.465%.** Gross is positive before costs; the gross edge is 0.31x the cost drag (costs are ~3.2x the edge).

## d6 - Regime split (candidate gross return by NIFTY vs 200DMA at entry)

| Regime | Trades | Gross exp %/trade | Win% |
|---|---|---|---|
| NIFTY above 200DMA | 99696 | 0.534 | 42.2 |
| NIFTY below 200DMA | 57197 | -0.163 | 36.2 |

## d7 - Loss concentration (candidate-level gross losses)

By sector (share of total gross loss, %; sector map is approximate):

- Financials: 25.2
- FMCG & Consumer: 12.4
- Pharma & Health: 11.8
- IT: 8.8
- Energy & Power: 8.4
- Cement & Building: 8.0
- Capital Goods & Infra: 6.6
- Metals & Mining: 6.6
- Realty & Services: 5.5
- Auto: 3.0
- Chemicals: 1.7
- Other: 1.1
- Telecom: 1.0

By entry price band (share of total gross loss, %):

- Rs <250: 5.5
- Rs 250-500: 14.5
- Rs 500-1000: 34.0
- Rs 1000-1500: 46.0

Position size: at the live default (risk 1.5%, equity Rs 5,000) qty is set by the stop distance, so notional concentrates where ATR% is small; the sweep's own risk dimension is in d3 - higher risk multiples scale the loss, they do not change its sign (gross expectancy is size-invariant per trade).

## d8 - Marginal separation (one-line filters on the best variant family)

| Variant | Filter | Cand. trades | Gross exp %/trade | Assembled trades (risk .02/maxpos 2) | Gross exp % | Costed net% |
|---|---|---|---|---|---|---|
| sl2.0_tp8.0 | none | 3758 | 0.347 | 122 | 1.059 | -1.01 |
| sl2.0_tp8.0 | REL_VOLUME>1.5 | 2137 | -0.067 | 135 | -0.353 | -5.80 |
| sl2.0_tp8.0 | DIST_20D_HIGH_PCT>-2 | 2387 | 0.055 | 126 | 0.114 | -3.52 |
| sl1.5_tp8.0 | none | 5718 | 0.189 | 185 | 0.921 | -1.06 |
| sl1.5_tp8.0 | REL_VOLUME>1.5 | 2529 | -0.124 | 196 | -0.526 | -9.65 |
| sl1.5_tp8.0 | DIST_20D_HIGH_PCT>-2 | 3120 | 0.072 | 180 | 0.183 | -4.81 |

## Reading (added on delivery, Nov 2)

- **The exit engine is the trailing stop, not the initial stop.** 68.9% of all candidate trades exit by trail, 16.8% by initial stop, 13.7% by target, 0.6% by window end. Initial-stop exits were almost never "noise-stopped" (only 2.9% had ever been up 1xATR). Trailing exits typically died after +1.22xATR median favourable excursion - the 1xATR trail cuts the middle of the distribution off before TP, which is the measured form of the Phase 1 report's capped avg_win.
- **The regime split is the strongest separation in the whole diagnosis** (d6): +0.534%/trade gross above the 200DMA vs -0.163% below it, on ~157k candidate trades. Nothing else tested separates this cleanly.
- **The "missing triggers" do not separate** (d8): REL_VOLUME > 1.5 and DIST_20D_HIGH_PCT > -2 both make gross expectancy WORSE on the best variant family. The unused indicators are not the missing event, at least not as entry filters on this rule.
- **Corrections to the Phase 1 report's framing** (both verified in d5/d4): (1) NIFTYBEES was not flat - it compounded +9.27% chained across the test windows (+14.47% full-span); the +0.36% headline was a per-fold-reset, cost-diluted mean. No assembly bug, but the wrong number to lead with. (2) The WF path's -1.47%/trade is its COSTED expectancy; gross expectancy is +0.67%/trade and the cost drag is 2.13%/trade. The conclusion is unchanged - no config is costed-profitable and the new gate is not met - but the decomposition matters: a small gross edge exists (~+0.34%/trade median across configs), concentrated in wide-stop/wide-target corners (sl2.5/tp8, sl2.0/tp3) and in above-200DMA regimes. It is roughly 3x too small for the Rs 5,000 cost structure.
- **Gate check (Phase 1.5 gate): NOT met by anything tested.** Best costed net (-1.01%) < benchmark; best PF < 1.2; no config positive in >= 8/13 folds after costs. d3's formal life test (gross-positive, >=100 trades, >=8/13 gross-positive folds) is passed by 89 configs - so an h1 test (regime gate on the existing rule) is justified by the user's decision rule, and is the cheapest next experiment. Nothing else is authorised by the data: d8 kills the indicator-filter route, and re-tuning the 432 was explicitly ruled out.
