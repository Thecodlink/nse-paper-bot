# Indian Market Mechanics — NSE (for the paper bot)

> Paper-only bot. Yahoo Finance data, ~15-min delay (`DATA_DELAY_MINUTES=15`).
> Times are IST (Asia/Kolkata). Compiled 2026-10-24.

## 1. Market hours

| Session | Time (IST) | Notes |
|---|---|---|
| Pre-open | 09:00–09:15 | Order entry/modify/cancel ~09:00–09:08, order matching / price discovery ~09:08–09:12, buffer ~09:12–09:15. Sets the opening price; no continuous trading. Bot does **not** trade here. |
| Continuous (normal) | **09:15–15:30** | The only session the bot trades in. Rolling price-time priority matching. |
| Closing price calc. | 15:30–15:40 | Closing price = weighted average of last 30 min (15:00–15:30). |
| Post-close / closing session | 15:40–16:00 | Trades only at the official closing price. Bot does **not** trade here (its own EOD report is at 15:35, positions already flat). |

Reference given in brief: https://www.nseindia.com/static/market-data/market-timings
(timings above cross-checked against multiple broker/exchange-timing summaries found in search on 2026-10-24).

Bot day shape implied by this: shortlist/prep before open → trade loop 09:15–15:30 →
no new trades after **14:45** → force-exit all MIS by **15:20 at the latest** (bot target:
start square-off 15:15) → EOD summary 15:35.

Saturdays and Sundays are non-trading days, except special sessions (e.g. Muhurat, or a
budget-day session) announced by circular — the bot must treat a special-session notice
as a human decision, not auto-trade it.

## 2. NSE trading holidays 2026 — for `config.py`

**Verification status (2026-10-24):** The NSE official holiday page was not fetched
directly in this pass. The list below is the **consensus of multiple secondary sources**
that each state they reproduce the official NSE/BSE 2026 circular — Angel One, Groww,
Tickertape, Dhanarthi, and a Moneycontrol/TradingView news item — all agreeing on the
same 15 weekday closures. Weekday names were independently verified with `date`.
**Treat as cross-checked but re-verify against nseindia.com before hardcoding is relied
on for a full year**; exchanges can add special holidays by circular during the year
(it already happened in 2026 — see Jan 15 note).

### Core list — 15 weekday closures (equity / equity derivatives / SLB)

| Date (2026) | Day | Holiday |
|---|---|---|
| 2026-01-26 | Monday | Republic Day |
| 2026-03-03 | Tuesday | Holi |
| 2026-03-26 | Thursday | Shri Ram Navami |
| 2026-03-31 | Tuesday | Shri Mahavir Jayanti |
| 2026-04-03 | Friday | Good Friday |
| 2026-04-14 | Tuesday | Dr. Baba Saheb Ambedkar Jayanti |
| 2026-05-01 | Friday | Maharashtra Day |
| 2026-05-28 | Thursday | Bakri Id / Eid-ul-Adha |
| 2026-06-26 | Friday | Muharram |
| 2026-09-14 | Monday | Ganesh Chaturthi |
| 2026-10-02 | Friday | Mahatma Gandhi Jayanti |
| 2026-10-20 | Tuesday | Dussehra |
| 2026-11-10 | Tuesday | Diwali — Balipratipada |
| 2026-11-24 | Tuesday | Prakash Gurpurb Sri Guru Nanak Dev |
| 2026-12-25 | Friday | Christmas |

That is 15 rows — matching the "15 holidays" headline in the sources.
In code, store explicit ISO date strings — never compute from festival names.

### Additional / special items — handle explicitly

- **2026-01-15 (Thursday) — Municipal Corporation Election, Maharashtra:** listed as an
  extra 2026 closure by Angel One and Groww. This is why some sources count 16 weekday
  closures for 2026. **Include `2026-01-15` in `config.py` holidays** (it is in the past
  relative to go-live, but the list must be complete and auditable).
- **Weekend holidays (no extra weekday closure):** Mahashivratri 2026-02-15 (Sun),
  Id-Ul-Fitr / Ramadan Eid 2026-03-21 (Sat), Independence Day 2026-08-15 (Sat),
  Diwali Laxmi Pujan 2026-11-08 (Sun).
- **Muhurat Trading:** on Diwali Laxmi Pujan, **Sunday 2026-11-08** per most sources
  (a short special session; exact timings notified later). ⚠️ One source (Angel One page)
  carried a conflicting note saying Muhurat on Wed Oct 21, 2026 — treat that as an error
  in that page; the consensus date is Nov 8. Bot: **do not trade Muhurat** unless the
  user explicitly enables it.
- Possible special session: a budget-day (Feb 1, 2026 was a Sunday) special session was
  speculated in news coverage — bot must not assume it; only the hardcoded list + an
  explicit human override count.

Suggested `config.py` form:

```python
NSE_HOLIDAYS_2026 = {
    "2026-01-15",  # Municipal Corporation Election, Maharashtra (extra, per Angel One/Groww)
    "2026-01-26", "2026-03-03", "2026-03-26", "2026-03-31",
    "2026-04-03", "2026-04-14", "2026-05-01", "2026-05-28",
    "2026-06-26", "2026-09-14", "2026-10-02", "2026-10-20",
    "2026-11-10", "2026-11-24", "2026-12-25",
}
```

The set above has 16 entries: the 15 core holidays + the Jan 15 extra. Keep the set and
the table in sync when editing.

## 3. Intraday MIS — leverage and forced square-off

- **MIS (Margin Intraday Square-off)** is the product type for same-day leveraged equity.
  Typical leverage on liquid large caps: **~5x** (broker- and stock-dependent; SEBI peak-margin
  rules mean the effective leverage is capped and varies — never assume more than 5x, and
  this bot's risk gate must pass *without* needing the full 5x).
- MIS positions **cannot be carried overnight**. If the trader does not exit, the broker's
  risk system auto-squares-off, usually starting **~15:15–15:20**, at whatever market price
  is available, plus auto-square-off charges in real life.
- Bot rules that follow: position size = min(45% of cash, 5x MIS buying-power limit);
  no new trades after 14:45; bot-initiated square-off from 15:15; hard flat by 15:20 —
  never rely on a "broker" to close a paper position.
- Leverage cuts both ways: at 5x, a 1% adverse move is a 5% capital move on the deployed
  margin slice. With Rs 5,000 capital the bot sizes off **cash**, not off leveraged notional,
  for its 45% cap — leverage only affects how many shares the paper fill can take.

## 4. Full Indian intraday cost stack (paper fills must deduct ALL of it)

Reference in brief: https://www.quantinsti.com/articles/transaction-costs-automated-trading/

| Cost | Rate (intraday equity) | Charged on |
|---|---|---|
| Brokerage | **Rs 20 per executed order or 0.03%**, whichever is lower (discount-broker convention used by this bot: flat Rs 20/order per brief) | Each buy and each sell order |
| STT (Securities Transaction Tax) | **0.025%** | Sell side only, intraday equity |
| Exchange transaction charges (NSE) | **~0.00325%** of turnover (sources round to 0.00297–0.00345% depending on year/segment — bot uses 0.00325% per brief) | Both sides, on turnover |
| GST | **18%** | On (brokerage + exchange txn charges + SEBI fees) |
| SEBI charges | **Rs 10 per crore** of turnover (= 0.0001%) | Both sides, on turnover |
| Stamp duty | **0.003%** | Buy side only |
| Slippage (modelled) | **0.05–0.15%** (bot models 0.1% per brief: fill at next candle open ± slippage) | Each fill, adverse direction |
| DP charges | Not applicable intraday (no delivery) | — |

**Rule of thumb from the brief: all-in ≈ 0.08% round trip + ~Rs 40 fixed (2 orders).**

Why this dominates a Rs 5,000 account — worked example:
- One round trip deploying Rs 2,250 (45%): fixed brokerage alone is Rs 40 ≈ **1.8% of the
  deployed amount** before any percentage cost. The stock must move roughly **+1.9–2% in
  your favour just to break even** on a single 45% position at this capital size.
- Prior backtests in this workspace (Oct 2026, Rs 1,000 template, 16 variants) were all
  negative after costs — the cost stack, not the signal, was the binding constraint.
  Expect the same pressure at Rs 5,000. This is why the playbook rewards NO-TRADE.

Implementation rule for `paper_broker.py`: compute every line item separately, store the
breakdown per trade in the journal/SQLite, and report "Costs paid" in the EOD message.
Never use a single blended % — the fixed Rs 20/order is the whole story at this size.

## 5. Microstructure rules the bot must respect

- **Tick size: Rs 0.05** for most equities (prices move in 5-paise steps; SEBI/exchange
  have introduced smaller ticks for some low-priced stocks — the bot rounds all entries,
  stops, and targets to Rs 0.05 and does not assume finer granularity).
- **Circuit limits / price bands:** many stocks have daily bands (commonly 5% / 10% / 20%,
  some no band, some dynamic intraday operating ranges). A stock locked at upper/lower
  circuit cannot be exited normally — in paper, mark such a position **untradable that
  cycle**, never assume a fill at a locked circuit price.
- **T2T (trade-to-trade) segment:** stocks shifted to T2T have **no intraday trading** —
  every trade results in delivery, no netting off. **The bot must exclude T2T / BE-series
  names from its universe entirely.** (Yahoo suffix data does not reliably flag this —
  maintain an exclusion list in config.)
- **Liquidity matters more than price:** a Rs 120 stock with 50k shares/day is worse than
  a Rs 1,200 stock with 5M shares/day. Hence the shortlist gates: price Rs 100–1,500,
  average volume > 500k, ATR > 1% — and even then, prefer NIFTY 50 / liquid NIFTY 500 names.
  Wide spreads on illiquid names make the modelled 0.1% slippage optimistic.
- **Data delay:** Yahoo Finance NSE data is delayed (~15 min). A "5-min strategy" on
  15-min-delayed data is really trading the recent past — entries fill at the *next
  available candle open* in the bot's data, stops can be jumped through on gaps, and
  fast moves may already be over. The bot must timestamp every decision with the data
  timestamp, skip the cycle if data is >30 min old, and never pretend to tick-level accuracy.
- **Opening volatility:** the first minutes after 09:15 price overnight news violently.
  Opening-range logic (see `playbook.md`) waits for a range to form instead of chasing the open.
- **News / results days:** a stock with results, ex-date corporate actions, or index
  rebalancing flows behaves abnormally — sentiment veto + smaller confidence, or skip.

## 6. Background reading (from brief)

- Zerodha Varsity (https://zerodha.com/varsity) — technical analysis and risk-management
  modules: the source style for `playbook.md` (indicators, position sizing, drawdown discipline).
- NSE market timings: https://www.nseindia.com/static/market-data/market-timings
- Transaction costs: https://www.quantinsti.com/articles/transaction-costs-automated-trading/
