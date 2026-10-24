"""Simulated trading-day cycle (market closed) — NOT part of the live bot.
Patches only the data/brain inputs, never risk/broker/state/notify logic:
- forces is_trading_day=True
- synthetic daily + 5-min candles for SIMTEST (price ~1000, vol 800k, ATR% >1%)
- sentiment +0.5, Kronos up_prob 0.72, brain BUY (all mocked inputs, clearly labelled)
Then runs run_cycle twice: cycle 1 should BUY, cycle 2 (price at target) should SELL.
Run: cd ~/workspace/nse-paper-bot && /path/to/venv/python sim_trading_day.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
import config, state as state_mod, notify
config.is_trading_day = lambda d=None: True
# --- synthetic candles ---
idx_daily = pd.date_range("2026-10-19", periods=60, freq="D")
close_d = np.linspace(980, 1010, 60) + np.sin(np.arange(60)) * 5
daily = pd.DataFrame({"Open": close_d - 2, "High": close_d + 8, "Low": close_d - 8,
                      "Close": close_d, "Volume": np.full(60, 800_000)}, index=idx_daily)
idx_intra = pd.date_range("2026-10-24 09:15", periods=60, freq="5min")
# gentle uptrend with pullbacks: RSI lands mid-range, ATR ~15 (1.5%)
close_i = 1000 + np.cumsum(np.where(np.arange(60) % 5 == 4, -1.5, 1.0))
intra = pd.DataFrame({"Open": close_i - 1, "High": close_i + 8, "Low": close_i - 7,
                      "Close": close_i, "Volume": np.full(60, 900_000)}, index=idx_intra)
# --- mock data module ---
import types
data_mod = types.ModuleType("data")
data_mod.fetch_daily_cached = lambda symbols: {"SIMTEST": daily}
data_mod.fetch_intraday = lambda symbols: {"SIMTEST": intra}
data_mod.last_source = lambda: "simulated"
data_mod.is_stale = lambda df: (False, 0)
sys.modules["data"] = data_mod
# --- mock sentiment / kronos / brain (inputs only) ---
sent = types.ModuleType("sentiment"); sent.aggregate = lambda sym: (0.5, [])
sys.modules["sentiment"] = sent
kron = types.ModuleType("kronos_forecast"); kron.up_probability = lambda df, entry, symbol=None: 0.72
sys.modules["kronos_forecast"] = kron
brain = types.ModuleType("brain")
brain.decide = lambda sym, feats: {"symbol": sym, "action": "BUY", "confidence": 0.75,
    "entry": feats["Close"], "stop": feats["Close"] - 20, "target": feats["Close"] + 35,
    "reasoning": "SIMULATED brain: trend up, kronos 0.72, RSI mid-range, sentiment +0.5", "veto_flag": False}
sys.modules["brain"] = brain
import main
# capture notify messages instead of sending
sent_msgs = []
orig_send = notify.send
notify.send = lambda text: (sent_msgs.append(text), True)[1]
main.notify.send = notify.send
# state in a temp dir copy: use bot's state file in cwd (sim_state) via STATE_FILE override
config.STATE_FILE = "sim_state.json"
if os.path.exists("sim_state.json"): os.remove("sim_state.json")
if os.path.exists("sim_journal.db"): os.remove("sim_journal.db")
st = state_mod.load()
print("CYCLE 1 — entry")
st = main.run_cycle(st)
print("positions:", json.dumps(st["positions"], indent=2))
print("cash:", st["cash"])
assert len(st["positions"]) == 1, "expected 1 BUY position"
pos = st["positions"][0]
print(f"BUY {pos['symbol']} qty={pos['qty']} entry={pos['entry']} stop={pos['stop']} target={pos['target']}")
# cycle 2: price jumps to target
intra2 = intra.copy()
last = intra2.iloc[-1].copy()
last["Close"] = pos["target"] + 1; last["High"] = pos["target"] + 2
intra2.iloc[-1] = last
data_mod.fetch_intraday = lambda symbols: {"SIMTEST": intra2}
print("\nCYCLE 2 — exit at target")
st = main.run_cycle(st)
print("positions after:", st["positions"])
print("trades:", json.dumps(st["trades"], indent=2))
print("cash after:", st["cash"])
assert len(st["positions"]) == 0 and len(st["trades"]) == 1, "expected target exit trade"
tr = st["trades"][0]
print(f"SELL exit={tr['exit']} net_pnl={tr['net_pnl']:.2f} costs={tr['costs']:.2f}")
print("\nNOTIFY MESSAGES CAPTURED:")
for m in sent_msgs: print("---\n" + m)
print("\nSIM RESULT: PASS — BUY then target SELL, risk/broker/state/notify path proven (data/brain inputs mocked, labelled above)")
