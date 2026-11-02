# NSE Paper-Trading Bot — A-to-Z Stack & Setup Report (updated Nov 2, 2026)

This supersedes FULL_REPORT.md (Oct 24, 2026). Everything below was
verified by a command, a log, an API response, or a file on disk.
Paper money only. No broker API. No real orders, ever.

## 1. What it is

Fully automated NSE intraday PAPER-trading agent: virtual capital
Rs 5,000, simulated 5x MIS leverage (Rs 25,000 buying power), intraday
only, data from Yahoo Finance only. Runs on GitHub Actions; since
Nov 2, 2026 it is TRIGGERED on time by Muse crons (see §7 — GitHub's
own scheduler proved unreliable).

## 2. Where everything lives

| Thing | Where |
|---|---|
| Code repo (public) | https://github.com/Thecodlink/nse-paper-bot |
| Branch `main` | Bot code, workflows, knowledge base |
| Branch `bot-state` | `state.json` + `journal.db` — the bot's memory between runs |
| Local working copy | `~/workspace/nse-paper-bot/` (on Muse's sandbox) |
| Stack test + local models | `~/workspace/nse-stack-test/` (venv + `models/` — Kronos-small, Kronos-mini, Kronos-Tokenizer-base, FinBERT) |
| Stack test report | `~/workspace/nse-stack-test/STACK_REPORT.md` |
| Push/dispatch helper | `~/workspace/nse-paper-bot-push.py` (GitHub Git/API via vault credential, verified as login `Thecodlink`) |
| Mistake book | `~/workspace/mistake-book.md` (4 entries, incl. vault ≠ GitHub Secrets) |
| Tracked item for reports | goal_e2af0f9bbbed, slug `nse-paper-bot-daily-market-close-report` |
| This bot's chat | Side chat "NSE paper trading bot setup" (all reports land here) |

## 3. Runtime stack (versions test-verified Oct 24, 2026)

Local sandbox: 2 CPU / 8 GB, Python 3.12.3. GitHub Actions:
ubuntu-latest, Python 3.11 (workflow-pinned), pip cache + HF cache.

| Component | Version | Notes |
|---|---|---|
| torch (CPU) | 2.14.1+cpu | CPU wheel; import + run verified |
| pandas / numpy | 3.1.0 / 2.5.4 | pandas pinned >=3,<4 in requirements |
| yfinance | 1.7.0 | Live RELIANCE.NS fetch verified |
| curl_cffi | 0.16.3 | Chrome TLS fingerprint session for yfinance |
| pandas-ta-classic | 0.8.32 | Import name `pandas_ta_classic` only |
| transformers | 5.20.2 | FinBERT load + score verified |
| einops | 0.8.2 | Required by Kronos (was missing from original spec) |
| streamlit / plotly | 1.66.1 / 7.1.0 | Dashboard; runs from stack-test venv locally |
| apscheduler | 3.11.3 | Import verified |
| nsepython | 2.101 | Fallback data source |
| jugaad-data | pip package | Second fallback; git clone is NOT pip-importable |
| feedparser | — | RSS headlines for sentiment |

## 4. Models (all free tiers, no card anywhere)

Forecasting / sentiment (Hugging Face, downloaded in Actions each run,
safetensors only for FinBERT):
- `NeoQuasar/Kronos-small` (98,980,656 B) — main forecaster.
  Lookback 400, pred_len 12, T=1.0, top_p=0.9. up_probability computed
  by looping predict(sample_count=1) x10 (predict(sample_count=N)
  returns ONE averaged path — measured fact). 57.7s / 10 paths on
  2 CPU, peak 547 MB → Kronos runs ONLY on final <=5 candidates
  (`KRONOS_MAX_CANDIDATES=5`) after cheap filters. Rule: > 0.58.
- `NeoQuasar/Kronos-Tokenizer-base` (~16 MB), `NeoQuasar/Kronos-mini`
  (16,440,776 B, fallback).
- `ProsusAI/finbert` (safetensors 437,965,908 B) — sentiment on last
  50 headlines. Load+score 18.4s, peak 776 MB. Rule: score >= 0.
  Licence CC BY-NC-SA — research/paper only.

LLM brain, 3 tiers (each model live-verified before locking — listed
or default names were NOT callable for all three providers):
1. Groq screen: `qwen/qwen3.8-27b` (account has 11 models;
   llama-3.3-70b -> 404).
2. Gemini decision: `gemini-3.5-flash-lite` (2.5-flash/-lite -> 404
   for new users; flash-latest -> 503).
3. NVIDIA NIM critique: `meta/llama-3.2-90b-vision-instruct`
   (llama-3.3-70b -> 410 gone). NIM argues the opposite side;
   split verdict -> SKIP. Bad JSON retried x3, then SKIP.

Connector helpers for Muse's own checks (not used by Actions):
`~/workspace/custom-connectors/custom.gemini/bin/gemini_call.py`,
`custom.groq/bin/groq_call.py`, `custom.nvidia-nim/bin/nim_call.py`,
`custom.github` (repo/API surrogate).

Licence scope (user-confirmed, research only): FinBERT CC BY-NC-SA,
TimesFM weights, Moirai/uni2ts usable; remove/replace if ever
commercial. Kronos MIT; TradingAgents/Chronos Apache-2.0. Ensemble
flags for Chronos/TimesFM/Moirai are OFF by default.

## 5. Bot code (`~/workspace/nse-paper-bot/`, ~1,300 lines of Python)

| File | Job |
|---|---|
| `main.py` (163) | Orchestrator; modes jobA/jobB/watchdog/once/test-notify; 5-min loop |
| `config.py` (105) | Universe, thresholds, NSE 2026 holidays, DATA_DELAY_MINUTES=15 |
| `data.py` (108) | yfinance + curl_cffi, one batched download, daily cache, backoff 1/2/4/8s, fallback yfinance -> jugaad-data -> nsepython, staleness skip >30 min |
| `shortlist.py` (33) | Universe filter -> top 20 |
| `indicators.py` (62) | EMA9/21/50, RSI14, MACD, ATR14, VWAP, relative volume |
| `kronos_forecast.py` (98) | Per-path loop -> up_probability |
| `sentiment.py` (91) | RSS headlines + FinBERT aggregate |
| `brain.py` (140) | Groq -> Gemini -> NIM, JSON-only, retry x3 |
| `risk.py` (91) | Sizing, SL/TP, trailing stop, losing-day halving |
| `paper_broker.py` (39) | Paper fill at next candle open + full cost stack |
| `state.py` (40) | state.json read/write only — NO git (workflow is sole committer) |
| `journal.py` (22) | SQLite journal of decisions/trades |
| `notify.py` (111) | Telegram templates; CHANNELS=["telegram"]; never blocks a trade |
| `dashboard.py` (21) | Streamlit: equity curve, positions, trades, reasoning |
| `weekly_review.py` (21) | Friday review generator |
| `sim_trading_day.py` (77) | Closed-market simulation harness (passed Oct 24) |

Universe: NIFTY50 + liquid NIFTY500 subset (~110 symbols in config).
Rules (hard): price Rs 100–1500, avg vol >500k, ATR >1%, top 20 ->
cheap filters (RSI 40–70, price > EMA21, FinBERT >= 0) -> Kronos > 0.58
on final <=5 -> brain BUY -> risk gate. Max 2 positions, max 45%
capital each, SL 1.5xATR, TP 2.5xATR, trailing stop after +1xATR
trailing 1xATR, no new trades after 14:45, force close 15:15,
2 consecutive losing days -> halved size next day.
Cost stack per fill: brokerage Rs 20/order, STT 0.025% sell,
exchange txn ~0.00325%, GST 18% on brokerage+txn, SEBI Rs 10/crore,
stamp 0.003% buy, slippage 0.1%.

## 6. External websites / services used

| Service | Used for |
|---|---|
| github.com (repo + Actions) | Hosting, compute, scheduling (backup), state branch |
| Yahoo Finance (via yfinance) | ALL market data (~15 min delayed, by design) |
| huggingface.co | Kronos + FinBERT model downloads |
| api.groq.com | Brain tier 1 (screen) |
| Gemini API (Google AI Studio key) | Brain tier 2 (decision) |
| NVIDIA NIM API | Brain tier 3 (critique) |
| Telegram Bot API | BUY/SELL/MARKET CLOSED messages to the user |
| Moneycontrol RSS, Economic Times RSS, Zerodha Pulse RSS | Headlines for FinBERT sentiment |
| NSE holiday list (2026) | Compiled from 5 secondary sources citing the NSE circular; NOT fetched directly from nseindia.com — still to re-verify |

## 7. Scheduling — where every clock lives (updated Nov 2, 2026)

GitHub Actions workflows (in repo, `.github/workflows/`):
- `trade.yml` (id 394854815): crons '20 3 * * 1-5' Job A,
  '25 9 * * 1-5' Job B, '0 4 * * 1-5' watchdog + workflow_dispatch.
  Job A timeout 355 min, loop 300s, exit 14:50 IST. Job B timeout
  45 min, exit 15:40 IST, sends MARKET CLOSED at 15:35.
- `review.yml` (id 394854814): Friday 16:00 IST weekly review.
  First run Oct 30, 2026 succeeded 22:17 IST (late, thin evidence).

Muse crons (this chat; created because GitHub's scheduler is
best-effort and landed 6–8h late all of week 1 — see §9):
- `nse-paper-bot-dispatch-joba` — Mon–Fri 08:50 IST, POSTs
  workflow_dispatch mode=jobA, verifies the run started, reports here.
- `nse-paper-bot-dispatch-jobb` — Mon–Fri 14:55 IST, same for jobB.
- `nse-paper-bot-market-close-report` — Mon–Fri 16:00 IST, READ-ONLY
  report in this chat (open/close/P&L/trades/heartbeat, flags).
- `nse-bot-morning-check-nov03` — one-off, Tue Nov 3 10:30 IST,
  checks whether the first on-time Job A dispatch actually traded.
GitHub's own crons remain as backup triggers only.

## 8. Keys and secrets (names only — values never in chat or logs)

GitHub repo Secrets (added by the user in repo Settings, Oct 24):
GEMINI_API_KEY, GROQ_API_KEY, NVIDIA_NIM_KEY, TELEGRAM_BOT_TOKEN,
TELEGRAM_CHAT_ID. Actions reads ONLY these.
Muse's Secure Vault holds separate copies for Muse's own API
checks. Vault != GitHub Secrets and neither can be copied to the
other (Mistake Book entry 1). Current vault caveat: vault Groq key
is the revoked pre-rotation one (401 on test), vault NIM chat ping
403, vault Gemini key works (200). This does NOT affect Actions,
which uses the new keys from repo Secrets. A Telegram token and a
GitHub token that were pasted/shown in chat on Oct 24 were treated
as exposed and never stored or used.

## 9. Status as of Nov 2, 2026 (verified, not run-status alone)

- Week 1 (Oct 26–30): cash Rs 5,000 -> Rs 5,000, 0 trades all five
  days. Cause established from Actions timestamps: every GitHub
  scheduled trigger landed ~6h late (Oct 27: Job A 5h48m, watchdog
  5h41m, Job B 6h03m late), so Job A started after its 14:50 exit
  and did nothing (main.py loop_until breaks immediately and writes
  no heartbeat). Late Job B still does EOD bookkeeping, which is
  why each day closed flat in the evening (~21:00–21:45 IST).
- Nov 2: delay grew to ~8h (Job A landed 16:54 IST, watchdog
  17:39 IST, watchdog correctly failed on stale heartbeat). At
  16:00 there were zero runs for the day.
- Clock fix applied Nov 2 ~18:05 IST (user picked Option 1 over
  running the bot locally on the sandbox): the two Muse dispatch
  crons in §7. Live test the same evening: manual dispatch of Job B
  returned 204 and run 41445724667 started within seconds,
  completed success, heartbeat updated to 2026-11-02 18:05 IST and
  daily_pnl gained 2026-11-02: 0.0 — Nov 2 closed out properly.
- The 08:50 dispatch cron fired once at 18:04 IST as a catch-up for
  today's already-past slot (created after 08:50) and correctly
  skipped dispatching (Job A had already run, after exit). Its real
  first test is Tue Nov 3, 08:50 IST.
- Verified working: repo public, both workflows active, Actions
  enabled (all actions allowed), 5/5 secrets by name, state
  commit-back (workflow is sole committer; heartbeat proves it),
  Telegram (job log "Telegram send ok"), simulated trading day
  (BUY 2 @ 1031.03 -> SELL target 1067.43, costs Rs 47.96,
  net +Rs 24.84), dashboard HTTP 200 via stack-test venv.
- NOT yet proven: a real on-time morning session with a live
  shortlist, real Kronos forecasts in Actions, and a real
  BUY-or-SKIP brain decision. First chance: Tue Nov 3, 08:50 IST.

## 10. Knowledge base (in repo `knowledge/`, 646 lines)

papers_digest.md (Kronos/TradingAgents/FinBERT papers),
repos_digest.md (19 repos), india_market.md (hours, MIS, costs,
2026 holidays), playbook.md (strategy playbook), trader_playbook.md
(injected into every brain prompt: exact rule kronos_up_prob>0.58
AND 40<RSI<70 AND price>EMA21 AND finbert>=0 AND brain BUY AND
risk gate; JSON-only output; self-doubt 0.55–0.62 prefer SKIP),
review_TEMPLATE.md. Friday weekly_review.py writes
knowledge/review_<date>.md and proposes ONE threshold change back
into trader_playbook.md, with a thin-evidence guard (<20 Kronos
decisions / <10 trades -> NO CHANGE).

## 11. How to operate / check it yourself

- Repo: https://github.com/Thecodlink/nse-paper-bot — Actions tab
  shows every run; bot-state branch state.json shows cash,
  positions, trades, heartbeat, daily P&L.
- Telegram: *BUY CONFIRMED* / *SELL CONFIRMED* / *MARKET CLOSED*.
  No BUY message on a day = the pipeline skipped (by design) OR
  the trigger was late — the 16:00 report in this chat says which.
- Dashboard: run `streamlit run dashboard.py` from the stack-test
  venv (system Python has no streamlit).
- If a key rotates: save your own copy FIRST, then update BOTH
  the vault and repo Secrets in the same sitting.
- Old Angel One paper-trading crons (Oct 18 stop order) stay
  disabled; this bot supersedes that stop for this project only.
