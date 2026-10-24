# nse-paper-bot

Fully automated NSE intraday **PAPER-TRADING** bot on GitHub Actions. Paper money only.
**No broker API. No real orders ever. Data: Yahoo Finance only (~15-min delay, `DATA_DELAY_MINUTES=15`).**
Public repo: public repos get unlimited standard Actions minutes; no paid services, no credit card.

## Research use & licences
This is for the owner's **research**, as confirmed Oct 24, 2026. On that basis FinBERT
(ProsusAI/finbert, CC BY-NC-SA), TimesFM weights, and Moirai/uni2ts may be used as
optional ensemble components (all default OFF in `config.py`) — **research only,
remove/replace all three if this ever goes commercial.** Kronos: MIT. TradingAgents
framework inspiration: Apache-2.0. Chronos: Apache-2.0.

## How it runs (GitHub Actions, `.github/workflows/trade.yml`)
- Job A cron `20 3 * * 1-5` UTC = 08:50 IST: `main.py --mode jobA`, 5-min internal loop, exits 14:50 IST, timeout 355 min.
- Job B cron `25 9 * * 1-5` UTC = 14:55 IST: `--mode jobB`, squares off, sends 15:35 MARKET CLOSED summary, exits 15:40, timeout 45 min.
- Watchdog cron `0 4 * * 1-5` UTC = 09:30 IST: checks today's heartbeat in state.json; if missing, Telegram alert + re-dispatch Job A.
- `workflow_dispatch` with a `mode` input for manual/test runs (jobA/jobB/watchdog/once/test-notify).
- Note: GitHub schedule crons can be delayed/dropped by GitHub under load — the watchdog exists for that reason.

## Decision rule
BUY only if: Kronos up-prob > 0.58 AND 40 < RSI < 70 AND price > EMA21 AND FinBERT >= 0
AND brain (Groq screen → Gemini decision → NVIDIA NIM critique; split = SKIP) says BUY
AND risk gate passes. Max 2 positions, 45% capital each, SL 1.5×ATR, TP 2.5×ATR,
trail after 1×ATR, no new trades after 14:45, square off by 15:20.
Playbook injected into LLM prompts: `knowledge/trader_playbook.md`.

## Secrets (GitHub Secrets, never in code/chat)
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_NIM_KEY`
Notifications are channel-agnostic (`notify.py`: `CHANNELS = ["telegram"]` by
default; a failing channel is logged and skipped — notify never blocks a trade).
Telegram uses the Bot API with Markdown formatting. CallMeBot/WhatsApp
(`CALLMEBOT_KEY`, `PHONE`) remains available as an OPTIONAL channel function,
disabled by default. Without keys the bot logs messages instead of sending, and
the brain returns SKIP — it still runs, it just does not trade on LLM decisions.

## Risk rules (extra)
- After **2 consecutive losing days, position size is halved** for the next day
  (`risk.update_day_close` tracks `daily_pnl`, `consecutive_losing_days` and
  `size_multiplier` 1.0/0.5 in state; a winning day resets the streak).
- Shortlist is capped at the **top 20 by score**; sentiment scores the **last 50
  headlines**; the brain retries bad LLM JSON **3 times** with a repair prompt
  before returning SKIP.

## Stack-test results (verified Oct 24, 2026, this sandbox)
Full report: `~/workspace/nse-stack-test/STACK_REPORT.md` (local). Tested on a
2-CPU / ~8 GB box, local Python **3.12** — Python **3.11 is Actions-only**
(the workflow requests 3.11 via setup-python; local runs use 3.12).

Tested versions (all import-verified): pandas **3.1.0** (pin `pandas>=3,<4` —
yfinance warns of pandas-4 breakage), numpy 2.5.4, yfinance 1.7.0,
curl_cffi 0.16.3, nsepython 2.101, pandas-ta-classic 0.8.32 (imports ONLY as
`pandas_ta_classic`, never `pandas_ta`), torch 2.14.1+cpu,
transformers **5.20.2**, huggingface_hub 2.3.0, einops 0.8.2 (required by
Kronos), streamlit 1.66.1, plotly 7.1.0, apscheduler 3.11.3.

- **Kronos-small timing:** 10 single-sample paths on RELIANCE took **57.7s**
  (~5.8s/path; total script 65.4s), up_probability **1.0** (10/10 final closes
  above the Rs 1,291 entry) — a single unvalidated sample, **not evidence of
  edge**. API fact: `predict(sample_count=N)` returns ONE averaged path, so
  `kronos_forecast.py` loops `predict(sample_count=1)` 10 times and counts.
- **Design rule (binding): Kronos runs ONLY on the final 2–5 candidates**
  after all cheap filters (price/volume/ATR/RSI/EMA/sentiment). At ~58s per
  symbol, forecasting the whole shortlist would overrun the 5-min cycle.
- **FinBERT:** scored the test headline ("Reliance Industries posts record
  quarterly profit…") at sentiment **+0.914** (positive 0.9433). Full snapshot
  is ~1.7 GB because it ships TF/Flax/PyTorch duplicates; the bot downloads
  safetensors + tokenizer/config only (`ignore_patterns` for `*.h5`,
  `*.msgpack`, `pytorch_model.bin`) in the workflow and in `sentiment.py`.
  FinBERT's licence is **CC BY-NC-SA — research only** (see licences above).
- **Peak RAM measured:** ~**941 MB** (FinBERT snapshot downloader, the single
  highest peak), **776 MB** FinBERT load+score, **709 MB** Kronos single call
  (547 MB for the 10-path run). Kronos and FinBERT were not loaded in the same
  process in the test; budget roughly their sum (~1.3 GB, estimate) in one bot
  process.
- **Indicator trap:** VWAP needs a DatetimeIndex — `indicators.py` never
  resets the index before VWAP.
- **jugaad-data** is a pip package in `requirements.txt` (import normally);
  a local git clone is only a fallback and needs PYTHONPATH to import.

## State
`state.json` persists on the `bot-state` branch (restored at job start, committed back
each cycle with `git pull --rebase` retry ×3). SQLite `journal.db` logs trades/decisions locally in the workspace.

## Dashboard
```bash
pip install streamlit plotly pandas
streamlit run dashboard.py
```
Shows equity curve, open positions, trades, decision reasoning from state.json + journal.db.

## Costs / risk warning
Full Indian intraday cost stack is deducted per fill (brokerage Rs 20/order, STT 0.025%
sell, exchange txn, GST 18%, SEBI, stamp, 0.1% slippage). At Rs 5,000 capital, fixed
costs are ~1.8–2% of a single 45% position — a stock must move ~2% in your favour just
to break even on one trade. Prior Rs 1,000 backtests in this project were all negative
after costs. Expect many NO-TRADE days; that is the strategy working, not a bug.
This is not investment advice and is not a profitable-system claim.
