# Cost Audit — Phase 0 (Nov 2, 2026)

Question: can a trade in this system make money after the full Indian
cost stack, at Rs 5,000 capital? Measured, not argued.

## Inputs (all measured or from the code itself)

- Representative entry price Rs 500 (universe filter is Rs 100–1500).
- ATR measured Nov 2, 2026 with the bot's own `data.py` + `indicators.py`
  on 14 liquid NIFTY names via Yahoo Finance:
  - **Daily ATR% median 2.136%** (mean 2.276%, range 1.81–3.62%)
  - **5-min ATR% median 0.166%** (mean 0.185%, range 0.13–0.39%)
    → TP at 2.5 x ATR = **0.41%**, matching the rebuild spec's ~0.43%.
- Costs computed by `paper_broker.cost_breakdown` / `round_trip_cost_estimate`
  (the same functions the live bot and the tests use).
- Sizing computed by the rewritten `risk.position_size`
  (RISK_PER_TRADE 0.0075, equity = cash + open positions at last price).
- Break-even win rate = net_loss / (net_win + net_loss), where
  net_win = qty x TP distance − round-trip cost and
  net_loss = qty x SL distance + round-trip cost.
- Figures exclude slippage (applied separately in `fill_price`, 0.1%
  per side = +0.2% of notional round-trip); the with-slippage
  cost-of-target is given where it changes the picture.

## Results

| Scenario | Qty (sized) | Notional | RT cost | RT % of position | TP distance | Cost % of TP | Net win | Net loss | Break-even win rate |
|---|---|---|---|---|---|---|---|---|---|
| **Legacy intraday** (old 45%-of-cash sizing, Rs 20 stack, 5-min ATR) | 4 | Rs 2,000 | Rs 47.92 | 2.40% | 0.41% | **577%** | **−Rs 39.62** | Rs 52.90 | **>100% (impossible)** |
| **Intraday mode, new** (risk sizing, real 5x leverage, Rs 20 stack, 5-min ATR) | 30 | Rs 15,000 | Rs 52.60 | 0.35% | 0.41% | 84.5% | Rs 9.65 | Rs 89.95 | **90.3%** |
| **Swing mode, new — DEFAULT** (risk sizing, 1x, Rs 0-brokerage delivery stack, daily ATR) | 2 | Rs 1,000 | Rs 14.17 | 1.42% | 5.34% | **26.5%** (30.3% incl. slippage) | Rs 39.23 | Rs 46.21 | **54.1%** |

Reference points:

- Swing round-trip cost on a full Rs 5,000 position (10 @ Rs 500):
  Rs 22.55 = **0.451%** (buy Rs 5.35 + sell Rs 17.20; the sell side is
  dominated by the Rs 12 DP charge). Spec test (< 0.6%): passes, and is
  asserted in `tests/test_paper_broker_costs.py`.
- Legacy intraday incl. slippage: RT Rs 51.92, cost = **627%** of the
  TP distance. The spec's 542% / Rs 50.19 used a Rs 2,250 position at a
  slightly different entry; same conclusion.
- Higher-ATR swing name (ATR% 3.0%): qty falls to 1 (wider stop →
  smaller risk size), so the fixed Rs 12 DP charge spreads over one
  share: cost = 34.9% of TP, break-even 59.3%. At Rs 5,000, the DP
  charge — not brokerage — is the binding fixed cost in swing mode.
- Sensitivity (NOT a config change): at TP_ATR 4 with the median daily
  ATR, swing cost = 16.6% of TP and break-even win rate = 39.4%.
  Whether TP_ATR moves is a Phase 1 backtest question
  (sweep set is {3, 4, 6}); Phase 0 does not tune it.

## Verdict

1. **Legacy intraday was mathematically dead**: a trade that hit its
   target still lost Rs 39.62. No win rate fixes a negative win.
   Root cause confirmed in code: `min(0.45 x cash, 5 x cash)` made
   MIS_LEVERAGE dead code; that formula is deleted.
2. **Intraday mode, even fixed, needs a 90.3% win rate** at the median
   5-minute ATR. It stays available behind `MODE = "intraday"` but
   nobody should expect it to survive Phase 1's backtest.
3. **Swing mode is the first configuration in this project whose
   winning trade makes money**: break-even win rate 54.1% at the
   shipped TP_ATR 2.5. Its cost is 26.5% of the TP distance —
   just above the 25% target band, and the gap is the fixed Rs 12 DP
   charge at tiny position sizes, not brokerage. The Phase 1 sweep
   (TP_ATR ∈ {3, 4, 6}) is exactly the lever that decides this, with
   evidence instead of intuition.

## What Phase 0 changed to get here

- `risk.position_size()` rewritten: risk-based
  (qty = min(floor(equity x 0.0075 / SL distance),
  floor((equity x MAX_LEVERAGE − deployed) / entry))), sized off
  EQUITY (cash + open positions), never residual cash. Spec case:
  Rs 5,000 / entry Rs 500 / SL Rs 10 → qty 3, not 4 (test-asserted).
- `config.MODE` = "swing" default ("intraday" legacy preserved);
  MAX_LEVERAGE 1.0 swing / 5.0 intraday; swing cost constants
  (Rs 0 brokerage, STT 0.1% both sides, DP Rs 12/scrip on sell)
  behind `ZERO_BROKERAGE`; `paper_broker.cost_breakdown(..., model=)`.
- Every entry now stores `cost_pct_of_target` (+ estimated round-trip
  cost) on the position and the closed trade, logs it, and sends a
  Telegram COST WARNING when it exceeds 25% — proven live in the
  simulated day (warning fired at 39% on a qty-1 test position).
- Dead code removed: `state.pull_state_branch()` (always silently
  failed) and `inputs.mode == 'once'` in jobA's `if:` in trade.yml.
- Tests: `tests/` (24 tests, pytest), ruff in `requirements-dev.txt`;
  pytest green, ruff clean on all Phase-0-touched files.

## Known scope limits (later phases, not hidden)

- Live scheduling/gates are still the intraday ones (Job A/B windows,
  14:45 entry cutoff, 15:15 square-off). In swing mode those gates are
  wrong-shaped; reshaping the live path is Phase 2/7 work, after the
  Phase 1 backtester exists. Phase 0 fixed the books only.
- Repo-wide `ruff check` still reports pre-existing findings in
  untouched legacy files (data.py, brain.py, etc.). Not bundled into
  Phase 0 (one concern per commit); BLE001 is ignored project-wide in
  pyproject.toml because blind-except-and-log is the deliberate
  never-crash pattern (hard constraint 4).
