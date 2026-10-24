# Playbook — Trading Skills (Section D)

> The skill layer under `trader_playbook.md`. The trader playbook (hard rules + decision
> framework) always wins over anything here. Paper trading only.

## 1. Trend

- Trade **with** the trend, on both timeframes you can see: daily trend (EMA stack on
  daily candles) and intraday trend (5-min).
- **Higher highs / higher lows** = uptrend. Lower highs / lower lows = downtrend.
  A sequence that is neither is a range — ranges are for skipping, not forcing breakouts.
- **EMA stack:** price > EMA9 > EMA21 > EMA50, all sloping up = healthy uptrend.
  Price > EMA21 is a hard gate in our decision rule; a tangled, flat EMA stack = no trend = skip.
- Slope matters: a rising EMA21 that price keeps reclaiming after dips is trend strength;
  one violent candle through all three EMAs is not a trend, it is an event.
- **Don't fight the higher timeframe.** A 5-min pop against a falling daily trend is a
  bounce, not a setup. If daily and 5-min disagree, the answer is skip.

## 2. Momentum

- **RSI(14):** healthy momentum lives roughly 40–70 for a long. RSI < 40 = weak/falling.
  RSI > 70 = overbought — late entries chase exhausted moves. Our gate is strict: `40 < RSI < 70`.
- **RSI divergence:** price makes a new high but RSI does not (bearish divergence) =
  momentum is tiring even if price looks fine — downgrade or skip. Price new low + RSI
  higher low (bullish divergence) is a warning against shorts / a possible turn, not by
  itself a buy signal.
- **MACD:** a MACD line crossing up through signal, with a rising histogram, confirms
  momentum is turning up. A cross after a long extended run is late — context first.
- **Volume confirmation:** a breakout/move on **relative volume well above average**
  (rel-volume > 1, ideally > 1.5) is real participation. A price move on thin volume is
  a drift — it reverses without warning. No volume, no trade.
- Momentum without trend is noise; trend without momentum is a grind that costs will eat.

## 3. Volatility and ATR stops

- **ATR(14)** is the market's current "normal wiggle" for that stock, in rupees.
- Stops are set from ATR, never from a fixed rupee amount or a round number:
  **stop = entry − 1.5 × ATR, target = entry + 2.5 × ATR** (our locked multiples).
- **A stop tighter than 1×ATR gets shaken out by ordinary noise.** If you cannot afford
  a 1.5×ATR stop within your position-size rule, the trade is too big — shrink size or skip.
- ATR also filters the universe: shortlist requires **ATR > 1% of price** — below that,
  the expected move cannot clear the cost stack (see §7).
- Rising ATR = expanding volatility: expect faster moves both ways, trail sooner.
  Collapsing ATR after a move = energy spent; don't open fresh trades into dead air.
- Trail after price moves **+1×ATR** in your favour (per risk.py) — lock in progress,
  never widen a stop. A stop only ever moves up (for a long), never down.

## 4. Support / resistance, opening range, VWAP

- **Support/resistance:** prior day high/low, swing highs/lows, round numbers, and the
  20-day high/low (distance from 20d high/low is a computed indicator in this bot).
  Buying 0.2% below a hard resistance ceiling is a bad trade even if every indicator agrees —
  there is no room for the 2.5×ATR target. Check headroom before entry.
- **Opening Range Breakout (ORB):** mark the high/low of the first 15–30 minutes.
  A decisive 5-min close beyond that range, on strong rel-volume, with the daily trend
  in the same direction, is a classic intraday setup. A poke beyond the range that
  immediately falls back inside is a trap (false breakout) — require the close, not the wick.
- **VWAP is the intraday mean** — the price institutions benchmark against.
  Price above VWAP = buyers in control today; below = sellers. Prefer longs above VWAP.
  A stock stretched far above VWAP tends to mean-revert toward it — don't chase extension;
  a stock reclaiming VWAP after holding below it is a genuine intraday character change.
- Combine, don't stack blindly: ORB breakout + above VWAP + uptrend stack is a setup.
  ORB breakout *into* major daily resistance is not.

## 5. Position sizing

- **Risk a fixed % of capital, not a fixed rupee amount.** Size comes from the stop
  distance: `qty ≈ (capital × risk%) / (entry − stop)`, then capped by the bot's hard rules.
- Bot hard caps (they override any sizing formula): **max 2 positions, max 45% of cash
  per position**, position size = min(45% of cash, 5x MIS buying-power limit).
- As capital grows or shrinks, size follows it automatically — a fixed-rupee habit
  over-risks after losses and under-risks after wins.
- If the ATR stop is wide, qty must be small. If the computed qty is < 1 share, skip —
  do not tighten the stop to make the trade "fit".
- Correlated positions are one position in disguise: two NIFTY heavyweights moving
  together do not diversify anything. Prefer genuinely different setups for slot 2.

## 6. Risk of ruin and expectancy

- **Expectancy = (win% × avg win) − (loss% × avg loss).** Track it from the journal,
  after costs. If expectancy is negative, the correct action is to stop and fix the
  system — not to trade more to "win it back".
- **Break-even maths:** with a **45% win rate you need R:R > 1.2 just to break even
  *before* costs** — (1 − 0.45)/0.45 ≈ 1.22. After the Indian intraday cost stack
  (~0.08% + ~Rs 40 round trip, which is huge relative to a Rs 5,000 account), the
  required R:R is higher still. Our 1.5×ATR stop / 2.5×ATR target gives R:R ≈ 1.67 —
  that headroom exists precisely to survive costs and a sub-50% win rate.
- Risk of ruin grows brutally with size-per-trade and losing streaks: at 45% win rate,
  a run of 5–6 straight losses is normal, not exceptional. Two 45%-of-capital positions
  losing together must never be able to end the account — stops, not hope, enforce that.
- Drawdown discipline: losses cluster. After a bad day, the next day starts at the same
  rules and the same size formula — never bigger to recover.

## 7. Costs — fewer, better trades

- Every extra trade costs money: **~Rs 40 fixed + ~0.08% round trip** (full stack in
  `india_market.md`). On Rs 5,000, one unnecessary round trip can cost ~1% of the account.
- Therefore: **fewer, better trades.** Two high-conviction setups beat eight maybes.
  A day with zero trades and zero costs is a good day if nothing qualified.
- Churning also degrades every other edge: more fills at worse prices, more slippage,
  more chances to hit a circuit or a data glitch.
- Judge strategies **net**, always. Any backtest, review, or "what if" that does not
  deduct the full cost stack is fiction.

## 8. The 3 killers

1. **Over-trading** — trading from boredom, screen-time, or "the bot should do something".
   The gates exist so most cycles produce NO-TRADE. That is the system working.
2. **Moving stops** — widening a stop after entry converts a planned, sized loss into an
   unplanned, unsized one. A stop moves only in the trade's favour (trailing). Never down.
3. **Revenge trading** — forcing a new trade to recover the last loss. It doubles size,
   halves standards, and usually doubles the loss. After a stop-out, the next trade must
   pass exactly the same gates as the first — no exceptions, no "make it back" trades.

## 9. Putting it together (one-line checks before any BUY)

Trend up on daily **and** 5-min? Momentum healthy (not overbought, volume confirming)?
Stop ≥ 1×ATR away and sized as % of capital? Room to the 2.5×ATR target before resistance?
Expected move clearly bigger than the full cost stack? If any answer is no — skip.
