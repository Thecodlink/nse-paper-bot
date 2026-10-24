# Papers Digest — NSE Paper-Trading Bot

> Paper-only research. No broker, no real orders. Sources read 2026-10-24.
> Each entry: what it claims / limits / applicability to 5-minute NSE intraday.

---

## 1. Kronos: A Foundation Model for the Language of Financial Markets

- **Citation:** Shi et al., arXiv:2508.02739 (submitted 2 Aug 2025), accepted AAAI 2026 per repo.
- **Sources read:**
  - https://arxiv.org/abs/2508.02739
  - https://github.com/shiyu-coder/Kronos (README fetched in full)

### What it claims
- First open-source foundation model built specifically for financial candlesticks (K-lines),
  not a generic time-series model retrofitted to finance.
- Two-stage design: (1) a specialised tokenizer quantises continuous multi-dimensional
  OHLCV into hierarchical discrete tokens, preserving price dynamics and trade activity;
  (2) a decoder-only autoregressive Transformer is pre-trained on those tokens.
- Pre-training corpus: **over 12 billion K-line records from 45 global exchanges**.
- Zero-shot results claimed in the abstract: price-forecasting **RankIC +93% over the
  leading time-series foundation model and +87% over the best non-pre-trained baseline**;
  volatility forecasting **9% lower MAE**; synthetic K-line generation **22% better fidelity**.
- Model family (from README, fetched): Kronos-mini 4.1M params / context 2048,
  Kronos-small 24.7M / context 512, Kronos-base 102.3M / context 512, Kronos-large 499.2M (not open).
  Our bot uses **NeoQuasar/Kronos-small + NeoQuasar/Kronos-Tokenizer-base**, lookback 400
  (inside the 512 limit), pred_len 12, sample_count 10, T=1.0, top_p=0.9.
  `up_probability = fraction of sampled paths closing above entry`.

### Limits
- Benchmark RankIC is a cross-sectional rank-correlation metric, mostly evaluated on
  the datasets/regimes in the paper — it is **not** a P&L, win-rate, or after-cost result.
  A better RankIC does not prove a tradable edge after Indian intraday costs.
- High-noise warning is in the paper's own framing: generic TSFMs underperform on K-lines
  precisely because financial data is noisy and non-stationary. Kronos mitigates, not removes, that.
- No NSE-specific, 5-minute, after-cost, live-forward evaluation is presented in the abstract/README.
  NSE names, circuit behaviour, and the 15-min Yahoo delay are outside its evaluation.
- Sampling is stochastic: the same input can give different path sets. Our up-probability is
  an estimate from only 10 paths — at p=0.58 the sampling noise alone is large
  (binomial SE ≈ sqrt(0.58×0.42/10) ≈ 0.16). Treat 0.58 as a weak gate, not a precise probability.
- Repo itself warns its fine-tune/backtest pipeline is "a demonstration … not a
  production-ready quantitative trading system."

### Applicability to 5-min NSE intraday
- **Use as one gate only, never as the trade.** Our rule requires Kronos >0.58 **AND**
  RSI/EMA/FinBERT/brain/risk all passing — exactly because a single forecast score is not an edge.
- 5-min is a plausible horizon: pred_len 12 = next 60 minutes of 5-min candles.
- Practical constraints: load once at job start (CPU inference on GitHub Actions is slow —
  time one forecast before trusting a 5-min loop over many symbols); shortlist first, forecast only survivors.
- Validate forward, in paper: log Kronos prob vs actual next-hour direction weekly (see weekly review).

---

## 2. TradingAgents: Multi-Agent LLM Financial Trading Framework

- **Citation:** Xiao, Sun, Luo, Wang, arXiv:2412.20138 (Dec 2024, revised Jun 2025, v7).
- **Sources read:**
  - https://arxiv.org/abs/2412.20138
  - https://huggingface.co/papers/2412.20138 (paper page — same abstract/metadata; listed in user brief)
  - https://github.com/TauricResearch/TradingAgents (README fetched in full; Apache-2.0)

### What it claims
- Simulating a real trading firm with LLM agents beats single-agent / data-gathering-only
  frameworks: specialised **analysts** (fundamentals, sentiment, news, technical),
  **Bull and Bear researchers** who debate, a **Trader**, a **risk-management team**, and a
  **Portfolio Manager** who approves/rejects and sends the order to a simulated exchange.
- Paper experiments claim superiority over baselines on **cumulative return, Sharpe ratio,
  and maximum drawdown** (figures in secondary summaries: ~23–27% cumulative return on
  AAPL/GOOGL/AMZN test names — US large-cap tech only).

### Limits
- Evaluation universe is narrow and favourable: a handful of liquid US large caps,
  daily-decision horizon — not 500 NSE names on 5-min candles.
- Secondary/readme-level critiques consistently note what the paper does **not** model well:
  slippage, taxes/fees, market impact, and live-data latency (assumed ~zero in backtest).
  Those are precisely the things that kill a Rs 5,000 intraday account.
- LLM decisions are non-deterministic and model/temperature/data dependent; the current
  repo README itself says: "designed for research purposes … not intended as financial,
  investment, or trading advice" and that performance varies with backbone model,
  temperature, period, and data quality.
- Cost/latency: a full multi-agent debate per symbol per 5 minutes is unaffordable on free
  tiers (Groq 30 RPM, Gemini free quota) and too slow for intraday if run naively.

### Applicability to 5-min NSE intraday
- **Borrow the structure, not the scale.** Our brain.py compresses it into 3 tiers:
  Groq = fast screen (Tier 1), Gemini Flash = decision + written reasoning (Tier 2),
  NVIDIA NIM = critique / argue the other side (Tier 3). Split decision → skip.
- Keep the roles inside one structured prompt (fundamentals / sentiment / technical /
  bull / bear / trader / risk manager) instead of 7 separate LLM calls per symbol.
- The risk-manager / portfolio-manager veto maps directly to our `veto_flag` and risk.py gate.
- Never let the LLM override hard rules (position count, size, stop, 14:45 cutoff).

---

## 3. FinBERT: Financial Sentiment Analysis with Pre-trained Language Models

- **Citation (original):** Araci, arXiv:1908.10063 (27 Aug 2019), Univ. of Amsterdam / Prosus.
  Note: there are several later "FinBERT" variants (Yang et al. 2020, Liu et al. 2021);
  the model we actually load is **ProsusAI/finbert**, which descends from Araci's work.
- **Sources read:**
  - https://arxiv.org/abs/1908.10063v1
  - https://huggingface.co/ProsusAI/finbert (model card, incl. licence)
  - Follow-on usage paper read via search: "Financial Sentiment Analysis Using FinBERT
    with Application in Predicting Stock Movement", arXiv:2306.02136 — FinBERT + LSTM
    beat ARIMA / LSTM-without-sentiment in that study, with modest FinBERT-vs-BERT margins.

### What it claims
- Financial language is specialised and labelled data is scarce, so a BERT model further
  pre-trained on a financial corpus, then fine-tuned for sentiment, beats general BERT
  and prior SOTA on financial sentiment datasets — even with a smaller training set and
  only partial fine-tuning.
- Reported accuracies in the follow-on tables (FinBERT-FinVocab, uncased): Financial
  PhraseBank **0.872**, FiQA **0.844**, AnalystTone **0.887**, vs generic BERT uncased
  0.835 / 0.730 / 0.850.
- Output is a 3-way classification: **positive / negative / neutral**. ProsusAI/finbert was
  further pre-trained on a subset of the Reuters TRC2 corpus.

### Limits
- It classifies **sentiment of a text snippet**, it does not predict price, timing, or
  whether a headline is already priced in. Headline sentiment ≠ tradable signal.
- Training text is largely Western financial news / analyst tone / PhraseBank sentences.
  Indian headlines (Moneycontrol, Economic Times, Zerodha Pulse), Hinglish phrasing,
  and NSE-specific events (bulk deals, pledges, circuit hits) are a domain shift.
- Headline-only scoring loses article context; RSS feeds are delayed, duplicated across
  sources, and often published after the move.
- **Licence warning:** ProsusAI/finbert weights are **CC BY-NC-SA 4.0 — non-commercial**
  per the HF model card fetched. Fine for this paper-only research bot; do not assume
  commercial use is permitted.
- Later reproducibility work (found in search, Sentic 2026 benchmark) found frozen
  ProsusAI/FinBERT agreed with displayed long/short labels on a social-trading corpus
  only ~40% of the time — a reminder to validate on *our* headline stream, not PhraseBank.

### Applicability to 5-min NSE intraday
- Use as a **veto / confirmation, never a trigger**: our rule only requires
  `finbert_sentiment >= 0` (i.e. not negative) alongside Kronos + trend + momentum + brain.
- Score aggregates, not single headlines: average over recent, de-duplicated headlines
  for the symbol / index; log the score with every decision so the weekly review can
  test whether FinBERT added anything on NSE headlines.
- Keep latency in budget: batch headlines once per cycle, cache scores, don't re-score
  unchanged headlines every 5 minutes.

---

## Cross-paper conclusion for this bot

None of the three papers proves an after-cost edge on 5-minute NSE intraday with
Rs 5,000. They justify an *architecture* (forecast gate + sentiment veto + structured
LLM debate + hard risk gate), not an expectation of profit. The bot must therefore
default to NO-TRADE, log every gate value for every candidate, and let the weekly
review kill or tighten thresholds on evidence — see `trader_playbook.md`.
