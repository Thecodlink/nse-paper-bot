# NSE Paper-Trading Bot — Full Report (Oct 24, 2026)

Status at the time of writing: **100% of the build and of everything that
can be tested while the market is closed.** The first real-market cycle
cannot be manufactured on a Saturday — it is scheduled for Monday 08:50 IST
(see "What Monday will prove" at the end). Everything below was verified
by a command, a log, or an API response, not by a green check alone.

## 1. What this bot is

A fully automated, PAPER-ONLY NSE intraday trading agent. No broker API,
no real orders, ever. Data from Yahoo Finance only. Virtual capital
Rs 5,000, intraday only, simulated 5x MIS leverage (Rs 25,000 buying
power). It runs itself on GitHub Actions — no laptop needed.

Repo (public): https://github.com/Thecodlink/nse-paper-bot

## 2. Repo and branches (Phase 0 — done)

- Repo: `Thecodlink/nse-paper-bot`, **public** (verified via API:
  `private: false`).
- Branch `main` — bot code, workflows, knowledge base.
  Latest commits at report time:
  - `cd0724ac` — initial bot, workflows, knowledge base (26 files)
  - `e50687c` — state commit-back fix (git identity + state.py fix)
  - `5378b18` — simulated trading-day test harness added (27 files)
- Branch `bot-state` — holds `state.json` (and, after the fix,
  `journal.db` when present). This is the bot's memory between runs.
- Push route: terminal/GitHub API via the user's GitHub credential,
  verified as `Thecodlink` (HTTP 200 on `GET /user`). No code was typed
  into the GitHub web editor.

## 3. Architecture — how a cycle works

Every 5 minutes, 08:50–15:40 IST, Mon–Fri, on NSE trading days:

1. Refresh 5-min candles for shortlisted symbols; daily candles cached
   all session (`data.py`).
2. Check open positions first: stop hit? target hit? trail triggered?
3. Exit on stop / target / trail / 15:15 forced close.
4. If under 2 positions and before 14:45: run the entry pipeline.
5. Write heartbeat + state, commit state to `bot-state`.
6. Log everything with reasoning (`journal.db` + `state.json`).

### Entry pipeline (all must pass, in order)

a. **Shortlist** from NIFTY500: price Rs 100–1500, avg daily volume
   > 500,000, ATR > 1% of price, not in circuit, not already held.
   Top 20 by score (liquidity × volatility).
b. **Verify chart**: EMA9/21/50, RSI14, MACD, ATR14, VWAP, relative
   volume. Discard if daily trend and 5-min trend disagree.
c. **Kronos forecast**: 400-candle lookback, predict next 12 candles,
   sample_count=10, T=1.0, top_p=0.9.
   `up_probability` = fraction of the 10 paths closing above entry.
   Required: **> 0.58**.
d. **Sentiment**: FinBERT on the last 50 headlines. Required: **>= 0**.
e. **Brain**: Groq screens → Gemini decides (bull case, bear case,
   verdict, playbook injected) → NVIDIA NIM argues the opposite side.
   Disagreement → SKIP. Bad JSON → retry ×3, then SKIP.
f. **Risk gate** (see §4).
g. **Execute (paper)**: fill at the NEXT candle's open, full cost stack.

### Risk rules (hard, not negotiable)

- Max 2 open positions, max 45% of capital per position.
- Stop loss: 1.5 × ATR below entry. Take profit: 2.5 × ATR above entry.
- Trailing stop: activates after +1 × ATR, trails at 1 × ATR.
- Never move a stop down. Force close everything at 15:15 IST.
- No new entries after 14:45 IST.
- **2 consecutive losing days → halve position size the next day**
  (`risk.update_day_close`, called at end-of-day; a winning/flat day
  resets the multiplier to 1.0).

### Cost model (applied to every simulated fill)

Brokerage Rs 20/order, STT 0.025% sell-side, exchange transaction
~0.00325%, GST 18% on brokerage+transaction, SEBI Rs 10/crore,
stamp duty 0.003% buy-side, slippage 0.1%. Total cost is logged per trade.

Worked example (from the local synthetic test, §7): BUY 2 @ Rs 1,001.00
cost Rs 23.74 → SELL @ Rs 1,098.90 cost Rs 24.24 → round-trip Rs 47.98,
net P&L +Rs 147.82 on that earlier synthetic trade. At Rs 5,000 capital
this is why the playbook enforces NO-TRADE/skip discipline: roughly a
+1.9–2% move on one 45% position (~Rs 2,250) is needed just to break even
after the fixed ~Rs 40 round trip.

### Data reliability (all implemented in `data.py`)

- `curl_cffi` session with Chrome TLS fingerprint passed to yfinance,
  plus a browser User-Agent.
- ONE batched `yf.download()` for all tickers, never per-symbol.
- Daily candles cached all session; only shortlisted symbols refreshed
  every 5 minutes.
- Exponential backoff on 429/empty: 1s, 2s, 4s, 8s.
- Fallback chain: yfinance → jugaad-data → nsepython, with the source
  used logged each cycle.
- Skip the cycle if data is older than 30 minutes.
- `DATA_DELAY_MINUTES = 15` in `config.py`: Yahoo NSE data is ~15 min
  delayed, so the newest received candle is treated as "now" and the
  whole clock is shifted accordingly.

### Messages (exact Telegram Markdown templates)

- BUY: `*BUY CONFIRMED*` — Stock | Qty | Time, Buy price | Amount,
  Stop | Target, Reason (Kronos prob, RSI, trend, sentiment, brain),
  Cash left.
- SELL: `*SELL CONFIRMED*` — Sell price | Gross | Costs | NET (pct%),
  Exit reason (stop/target/trail/close).
- 15:35: `*MARKET CLOSED - <date>*` — Open Rs 5000 | Close | P&L,
  Trades (win/loss) | Costs paid, Notes.
- `notify.py` is channel-agnostic: `CHANNELS = ["telegram"]`, each
  channel tried in try/except, a notify failure never blocks a trade.
  The Telegram token is read from the environment only and is never
  printed or logged (log lines record only "Telegram send ok/rejected"
  and character count, never the URL or token).

## 4. Stack (Phase 2 — done, with measured numbers)

All on the 2-CPU / 8-GB sandbox unless stated, Python 3.12.3 locally,
Python 3.11 in GitHub Actions (workflow pins 3.11).

| Component | Version / source | Verified |
|---|---|---|
| torch (CPU) | 2.14.1+cpu, CPU wheel | import + matmul OK, peak 222 MB |
| yfinance | 1.7.0 | live RELIANCE.NS fetch OK |
| curl_cffi | 0.16.3 | session passed to yfinance |
| pandas / numpy | 3.1.0 / 2.5.4 | imports OK (see note below) |
| pandas-ta-classic | 0.8.32 | import name is `pandas_ta_classic` only; `import pandas_ta` fails |
| transformers | 5.20.2 | FinBERT load+score OK |
| streamlit / plotly | 1.66.1 / 7.1.0 | dashboard HTTP 200 (see §7) |
| apscheduler | 3.11.3 | import OK |
| einops | 0.8.2 | **required by Kronos, missing from the original spec list** |
| nsepython | 2.101 | import OK (fallback data source) |
| jugaad-data | pip package | clone is NOT pip-importable; use the pip package or PYTHONPATH |

Models downloaded (safetensors only for FinBERT — the full snapshot is
1.7 GB / 515.9s because it ships TF/Flax/PyTorch-bin duplicates; the bot
fetches safetensors + tokenizer/config only):
- `NeoQuasar/Kronos-Tokenizer-base` ~16 MB
- `NeoQuasar/Kronos-small` 98,980,656 B
- `NeoQuasar/Kronos-mini` 16,440,776 B (fallback)
- `ProsusAI/finbert` safetensors 437,965,908 B

Measured performance (stack test, `~/workspace/nse-stack-test/STACK_REPORT.md`):
- Kronos-small, lookback 400, pred_len 12, T=1.0, top_p=0.9:
  **57.7s for 10 paths (~5.8s/path)**, peak 547 MB, up_probability 1.0
  on one RELIANCE daily sample (a single sample — NOT edge evidence).
- **Critical API fact**: `KronosPredictor.predict(sample_count=N)`
  returns ONE averaged path, not N paths. The specified up_probability
  is therefore computed by looping `predict(sample_count=1)` 10× and
  counting final closes above entry. The bot code does this
  (`kronos_forecast.py`); an older fallback that did not was deleted.
- **Consequence**: at ~58s/symbol, a 5-minute loop can Kronos-forecast
  at most ~5 symbols. The bot applies all cheap filters first and runs
  Kronos only on the final `KRONOS_MAX_CANDIDATES = 5` candidates.
- FinBERT: load+score 18.4s, peak 776 MB. Test headline about Reliance
  record profit scored pos 0.943 / sentiment +0.914.
- Highest single peak observed: ~941 MB (FinBERT snapshot downloader).
  Budget ~1.3 GB if Kronos+FinBERT run in one process — fine on
  GitHub Actions (16 GB), tight on this 8 GB box.
- Traps found and fixed in code: `ta.vwap()` crashes on a RangeIndex —
  never reset_index before VWAP, keep DatetimeIndex; Kronos pins older
  pandas/hub versions but ran fine on newer versions from local dirs.

LLM tiers (all free, no card) — with a lesson that repeated for every
provider: the listed/default model name is NOT always the callable one.
Each model below was verified with a live call before being locked in:

| Tier | Provider | Locked model (verified 200 OK) | Rejected |
|---|---|---|---|
| 1 screen | Groq | `qwen/qwen3.8-27b` | `llama-3.3-70b-versatile` → 404 model_not_found; account list has only 11 models. Bare urllib got Cloudflare 1010/403 — a browser User-Agent is required for the models list. |
| 2 decide | Gemini (google-genai SDK, thinking enabled) | `gemini-3.5-flash-lite` | `gemini-2.5-flash` and `2.5-flash-lite` → 404 "no longer available to new users"; `gemini-flash-latest` → 503 high demand. |
| 3 critique | NVIDIA NIM | `meta/llama-3.2-90b-vision-instruct` | `meta/llama-3.3-70b-instruct` → 410 gone; nemotron-70b, mistral-large-2, chatqa-70b, kimi-k2.6 → 404. |

Licences (research/paper-only scope, confirmed by the user):
FinBERT (CC BY-NC-SA), TimesFM weights, and Moirai/uni2ts may be used
because this bot is research/paper-only, not commercial. If it ever
goes commercial, those three must be removed/replaced. Kronos is MIT;
TradingAgents/Chronos are Apache-2.0. Ensemble flags for Chronos/TimesFM/
Moirai are OFF by default in `config.py`.

## 5. Bot files (Phase 3 — done)

`~/workspace/nse-paper-bot/` — 2,186 lines total across code, knowledge,
workflows, and docs:

| File | Job |
|---|---|
| `main.py` (163 lines) | Orchestrator + internal 5-min loop; modes jobA/jobB/watchdog/once/test-notify |
| `config.py` (105) | Symbols, thresholds, NSE 2026 holidays, DATA_DELAY_MINUTES=15 |
| `data.py` (108) | yfinance + curl_cffi + retry + cache + fallback chain + staleness |
| `shortlist.py` (33) | NIFTY500 filter, top 20 by score |
| `indicators.py` (62) | EMA9/21/50, RSI14, MACD, ATR14, VWAP, relative volume |
| `kronos_forecast.py` (98) | Per-path loop → up_probability |
| `sentiment.py` (91) | RSS headlines + FinBERT, last 50 headlines |
| `brain.py` (140) | Groq → Gemini → NIM, JSON-only output, bad-JSON retry ×3 |
| `risk.py` (91) | Position size, SL/TP levels, trail, losing-day halving |
| `paper_broker.py` (39) | Fill at next candle open, full cost stack |
| `state.py` (55) | state.json persistence, bot-state branch, retry ×3 |
| `journal.py` (22) | SQLite decision/trade journal |
| `notify.py` (111) | Telegram, channel-agnostic, never blocks a trade |
| `dashboard.py` (21) | Streamlit: equity curve, positions, trades, reasoning |
| `weekly_review.py` (21) | Friday review generator (see §8) |
| `sim_trading_day.py` (77) | Closed-market simulation harness (see §7) |
| `requirements.txt` (25) | Pinned/tested versions (see §4) |
| `README.md` (98) | Setup and operation notes |

Brain output format (JSON only):
`{"symbol","action","confidence","entry","stop","target","reasoning","veto_flag"}`
Reasoning style: bull case, then bear case, then verdict, citing real
numbers. Confidence 0.55–0.62 → say so, prefer SKIP. All five framework
checks → BUY; any two fail → SKIP.

## 6. Workflows (Phase 4 — done)

`.github/workflows/trade.yml` (143 lines, YAML parses):
- Triggers: cron `'20 3 * * 1-5'` = 08:50 IST Job A,
  `'25 9 * * 1-5'` = 14:55 IST Job B,
  `'0 4 * * 1-5'` = 09:30 IST watchdog, plus `workflow_dispatch`
  (modes jobA/jobB/watchdog/once/test-notify).
- Job A: timeout 355 min, internal loop every 300s, exits 14:50 IST.
- Job B: timeout 45 min, loop every 300s, exits 15:40 IST, runs
  end-of-day square-off + market-closed message.
- Watchdog: if no heartbeat for today, sends a Telegram alert and
  re-dispatches Job A.
- All jobs: ubuntu-latest, Python 3.11, pip cache, HF model cache,
  restore state from `bot-state`, commit state back every cycle,
  catch-up logic (started after 09:15 → straight to live cycle).
- Permissions: contents write, actions write. Actions verified enabled
  via API (`enabled: true, allowed_actions: all`).

`.github/workflows/review.yml` (36 lines): Friday 16:00 IST
(`'30 10 * * 5'`), restores journal/state from `bot-state`, runs
`weekly_review.py`, commits the review back to `main`.

### State commit-back bug found and fixed (Oct 24)

Symptom: two `workflow_dispatch` runs showed "completed / success",
all steps green including "Commit state back", yet `bot-state` stayed
at its initial commit with heartbeat 11:00.
Root cause (two parts):
1. Git identity was only configured in the commit-back step, AFTER the
   main run. `state.py`'s in-run commit therefore failed, and —
2. the old `state.py` checked only the PUSH returncode. A push of the
   unchanged HEAD returns 0, so it reported success while nothing moved.
   The workflow's `git checkout -B bot-state` then discarded the modified
   `state.json`, so the backup commit found "nothing to commit".
Fix (pushed in `e50687c`):
- Git identity is now configured immediately after checkout, BEFORE
  the run, in all three jobs.
- `state.py` now checks the commit returncode and that HEAD actually
  changed; a failed commit is logged as an error and the file is left
  modified for the backup step.
- The workflow backup step no longer does `checkout -B bot-state` or
  `pull --rebase`; it adds `state.json` + `journal.db`, and only
  commits+pushes (`HEAD:bot-state --force`) if there is actually a
  staged change. If `state.py` already pushed, it prints "nothing to
  commit" and does nothing — it can no longer revert the branch.
- `journal.db` is now also committed back, so the Friday review can
  actually read the week's journal (previously only `state.json` was
  committed, so the review would always have seen an empty journal).

## 7. Verification evidence (Phase 6 — as far as a Saturday allows)

| Check | Result |
|---|---|
| All Python files compile | `py_compile` OK, all files |
| `main.py --mode once` (Saturday) | Exit 0, correctly "Not a trading day — skip cycle" |
| `main.py --mode watchdog` | Exit 0, "heartbeat OK" |
| `main.py --mode test-notify` (local, no env) | Exit 0, prints the would-be Telegram message, never raises |
| Risk gate | Rs 5,000 / price 1,000 / ATR 20 → qty 2, SL 970, TP 1050 |
| Losing-day halving | qty 2 → ×0.5 qty 1 after 2 loss days → win resets ×1.0 |
| Brain bad-JSON retry | bad → SKIP; bad-then-good → BUY on retry 2 |
| Dashboard | Streamlit 1.66.1 (stack-test venv) → HTTP 200. System Python has no Streamlit installed, so the dashboard must be run from that venv or from Actions, not system Python. |
| Actions `once` runs (2×, before fix) | Both completed success, all steps green — but bot-state did NOT move (the bug in §6). This is why run status alone is never accepted as proof here. |
| Actions `test-notify` run (after secrets added) | Run `40070114581`, jobA success in ~68s (cached deps/models). **Log line, from the actual job log: `Telegram send ok (87 chars)`** at 06:26:04 UTC. In `notify.py` that line is only logged when Telegram's API returns `ok: true`, so the test message was accepted by Telegram for the configured chat. |
| Simulated trading day (market closed) | `sim_trading_day.py` — PASS. See below. |

### Simulated trading day — full pipeline, mocked inputs only

Because the market is closed, a real entry cannot be produced from live
data today. The simulation patches ONLY the inputs (forced trading day,
synthetic candles, sentiment +0.5, Kronos 0.72, brain BUY) and runs the
REAL risk, broker, state, and notify code untouched:

- Shortlist: 1 passed (SIMTEST, price ~1000, vol 800k–900k, ATR% >1%).
- CYCLE 1 BUY: `SIMTEST qty 2 entry 1031.03 stop 1007.50 target 1067.50`,
  cash Rs 5,000 → Rs 2,914.20, with the exact `*BUY CONFIRMED*` template
  (Kronos 0.72, RSI 69.3, price>EMA21, sentiment 0.50).
- CYCLE 2 SELL at target: exit 1067.43, gross 2134.86, costs 47.96,
  **NET +24.84 (1.19%)**, cash Rs 5,024.84, exact `*SELL CONFIRMED*`
  template, exit reason `target`.
- Real Kronos and real FinBERT are NOT in this simulation — their
  measured performance is in §4 (57.7s / 10 paths; FinBERT +0.914 on a
  Reliance profit headline). Replacing the mocked 0.72 with a live
  Kronos call is exactly what Monday's first cycle does.

## 8. Knowledge base (Phase 1 — done)

`knowledge/` (646 lines):
- `papers_digest.md` (151) — Kronos (arXiv 2508.02739), TradingAgents
  (arXiv 2412.20138), FinBERT (Araci, arXiv 1908.10063, CC BY-NC-SA):
  claims, limits, 5-min NSE applicability.
- `repos_digest.md` (36) — all 19 repos, one line each; entries whose
  full README was not fetched are marked "(from repo listing/search
  summary)"; Moirai non-commercial warning; vectorbt = Phase 2 only.
- `india_market.md` (170) — hours (pre-open 09:00–09:15, continuous
  09:15–15:30, post-close to 16:00), MIS ~5x + forced square-off
  15:15–15:20, full cost table, tick 0.05, circuits, T2T exclusion.
  NSE 2026 holidays: 16-entry set including extra 2026-01-15
  (Maharashtra municipal election), cross-checked across 5 secondary
  sources citing the NSE circular, weekdays verified with `date`.
  **Not fetched directly from nseindia.com — re-verify before relying
  on it all year.** Muhurat consensus Sun 2026-11-08; the bot does not
  trade Muhurat.
- `playbook.md` (119) — trend, momentum, RSI divergence, volume,
  ATR stops, support/resistance, opening-range breakout, VWAP,
  fixed-% sizing, expectancy, risk of ruin, the three killers
  (over-trading, moving stops, revenge trading).
- `trader_playbook.md` (123) — injected into EVERY LLM decision prompt:
  WHO YOU ARE / HARD RULES / DECISION FRAMEWORK (a)–(e) /
  all-five→BUY, any-two-fail→SKIP / exact rule
  `kronos_up_prob>0.58 AND 40<RSI<70 AND price>EMA21 AND finbert>=0 AND
  brain BUY AND risk gate` / JSON-only output / bull→bear→verdict /
  self-doubt 0.55–0.62 prefer SKIP / §7 weekly review / 2-losing-days
  halving rule.
- `review_TEMPLATE.md` (48).

## 9. Secrets (Phase 5 — done, names verified)

Verified by names only via the GitHub API (values are never read back):
`GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_NIM_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — all 5 present in repo
Settings → Secrets and variables → Actions.

Important, learned the hard way (see `~/workspace/mistake-book.md`):
keys given to Muse's secure vault are NOT GitHub Secrets and cannot be
copied there — GitHub Actions cannot read Muse's vault. The user added
these 5 directly in the repo on Oct 24 ~11:54 IST. Groq and NVIDIA are
new keys (the previous ones were deleted before a personal copy was
saved, because it was believed Muse held a retrievable copy — it does
not). Gemini's key is the same as the vault copy. If any key is ever
rotated again: save your own copy FIRST, then rotate, then update both
the vault (for Muse) and repo Secrets (for Actions) in the same sitting.

## 10. Self-review loop (Phase 7 — code done, first real run pending)

`weekly_review.py` + `review.yml` (Friday 16:00 IST) read the week's
journal and write `knowledge/review_<date>.md` answering: which rules
made/lost money; was the 0.58 Kronos threshold too low/high; was the
ATR stop multiple too tight; what would 1 position instead of 2 have
done; ONE concrete threshold change with evidence — then write that
change back into `trader_playbook.md`.
Thin-evidence guard: <20 Kronos decisions / <10 trades → "NO CHANGE".
Verified locally with 0 trades / 0 decisions: it correctly wrote
"NO CHANGE — evidence too thin this week" instead of inventing a rule.
(The local test file was removed afterwards so it is not committed as
a fake weekly review.)

## 11. What Monday will prove (the only part a Saturday cannot)

1. 08:50 IST Job A starts on schedule, heartbeat appears on `bot-state`
   (this also re-proves the §6 fix in production, not just in a
   dispatch test).
2. Shortlist from live NIFTY500 data, cheap filters, then Kronos on
   the final ≤5 candidates inside the 5-minute loop.
3. A real brain decision (Groq → Gemini → NIM) with real numbers.
4. Either a paper BUY with the exact Telegram templates, or a
   disciplined SKIP — both are correct outcomes; a forced trade is not.
5. Exits / 15:15 square-off / 15:35 market-closed message, then
   Friday's first real review from a real journal.

## 12. How to operate it

- Watch Telegram for `*BUY CONFIRMED*` / `*SELL CONFIRMED*` /
  `*MARKET CLOSED*` messages. A day with no BUY message means the
  pipeline skipped — by design, not a failure.
- Dashboard: `streamlit run dashboard.py` from the stack-test venv
  (or any env with Streamlit 1.66.1) — equity curve, open positions,
  all trades, reasoning.
- State: `bot-state` branch `state.json` (cash, positions, trades,
  heartbeat, losing-day streak, size multiplier).
- If a key rotates: update BOTH Muse's vault AND repo Secrets, and
  save your own copy first (see §9).
- Old tracks stay stopped: the Oct 18 "don't trade" order is superseded
  ONLY for this new paper-only bot; the old Angel One crons stay
  disabled, and nothing here places a real order.
