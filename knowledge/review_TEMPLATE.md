# Weekly Self-Review — <YYYY-MM-DD> (week of <Mon date> to <Fri date>)

> Copy this file to `knowledge/review_<YYYY-MM-DD>.md` every Friday at 16:00 IST and fill it in
> from the week's journal. Paper trading only. All P&L figures are NET (after the full cost stack).

## Week in numbers

- Trading days: <n> | Cycles run: <n> | Cycles skipped (stale data): <n>
- Trades taken: <n> (BUY <n> / exits: target <n>, stop <n>, trail <n>, square-off <n>)
- Skips by gate: Kronos <n> | RSI/EMA <n> | FinBERT <n> | brain <n> | risk <n> | after 14:45 <n>
- Starting capital: Rs <x> | Ending capital: Rs <x> | Net P&L: Rs <x> (<pct>%)
- Gross P&L: Rs <x> | Total costs paid: Rs <x> | Win rate: <pct>% | Avg win: Rs <x> | Avg loss: Rs <x>
- Expectancy per trade = (win% x avgWin) − (loss% x avgLoss) = Rs <x>

## 1. Which rules made money, which lost money?

- Made money: <rule — e.g. "Kronos > 0.65 subset", trades, net Rs>
- Lost money: <rule / failure pattern — e.g. "entries within 0.3% of daily resistance", trades, net Rs>
- Worst trade and why: <symbol, date, what the gates said, what actually happened>

## 2. Was the 0.58 Kronos threshold too low or too high?

- Trades by Kronos band (0.58–0.65 / 0.65–0.75 / >0.75): <counts, win rates, net Rs per band>
- Skipped candidates in 0.50–0.58 that would have won/lost (from logged gate values): <evidence>
- Verdict: too low / too high / about right — because: <evidence>

## 3. Was the ATR multiple too tight?

- Stop-outs: <n> of <n> trades | Stop-outs that later reached target the same day: <n> (<pct>%)
- Average adverse excursion before recovery, on stopped trades: <x ATR>
- Verdict on 1.5x ATR stop / 2.5x ATR target: <keep / evidence for a change>

## 4. What if only 1 position instead of 2?

- Second-position trades this week: <n>, net Rs <x>
- Counterfactual (only the first/best position each time): net Rs <x>
- Verdict: did slot 2 help or hurt, and were the two positions correlated?

## 5. ONE concrete threshold change for next week

- Change: <exactly one — e.g. "Raise Kronos gate from 0.58 to 0.62" — or "No change">
- Evidence: <the numbers from §§1–4 that justify it; if "no change", why the evidence is too thin>
- Applied to `trader_playbook.md` on: <date / not applied, with reason>
- How we will know next week if it worked: <the metric to compare>

## Notes / market context

- <regime notes: trending vs range week, news events, data outages, anything unusual>
