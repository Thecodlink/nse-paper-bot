"""SQLite journal (stdlib sqlite3). Trades, decisions, reasoning, outcomes."""
import json
import sqlite3

import config


def _conn():
    c=sqlite3.connect(config.JOURNAL_DB)
    c.execute("CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, side TEXT, qty INTEGER, price REAL, gross REAL, costs REAL, cost_breakdown TEXT, net REAL, reason TEXT, label TEXT, mae_pct REAL, mfe_pct REAL)")
    existing={r[1] for r in c.execute("PRAGMA table_info(trades)").fetchall()}
    for col, typ in (("label", "TEXT"), ("mae_pct", "REAL"), ("mfe_pct", "REAL")):
        if col not in existing: c.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ}")
    c.execute("CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, action TEXT, confidence REAL, kronos REAL, rsi REAL, sentiment REAL, payload TEXT)")
    return c
def log_trade(ts,symbol,side,qty,price,gross,costs,breakdown,net,reason,label=None,mae_pct=None,mfe_pct=None):
    try:
        c=_conn(); c.execute("INSERT INTO trades(ts,symbol,side,qty,price,gross,costs,cost_breakdown,net,reason,label,mae_pct,mfe_pct) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(ts,symbol,side,qty,price,gross,costs,json.dumps(breakdown),net,reason,label,mae_pct,mfe_pct)); c.commit(); c.close()
    except Exception: pass  # noqa: S110 - journal must never raise into the trade loop (hard constraint 4)
def log_decision(ts,symbol,decision,kronos=None,rsi=None,sentiment=None):
    try:
        c=_conn(); c.execute("INSERT INTO decisions(ts,symbol,action,confidence,kronos,rsi,sentiment,payload) VALUES(?,?,?,?,?,?,?,?)",(ts,symbol,decision.get("action"),decision.get("confidence"),kronos,rsi,sentiment,json.dumps(decision,default=str))); c.commit(); c.close()
    except Exception: pass  # noqa: S110 - journal must never raise into the trade loop (hard constraint 4)
def read_trades(limit=500):
    try:
        c=_conn(); rows=c.execute("SELECT ts,symbol,side,qty,price,gross,costs,net,reason FROM trades ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); c.close(); return rows
    except Exception: return []
def read_decisions(limit=500):
    try:
        c=_conn(); rows=c.execute("SELECT ts,symbol,action,confidence,kronos,rsi,sentiment,payload FROM decisions ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); c.close(); return rows
    except Exception: return []
