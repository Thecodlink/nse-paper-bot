"""SQLite journal (stdlib sqlite3). Trades, decisions, reasoning, outcomes."""
import sqlite3, json, os, config
def _conn():
    c=sqlite3.connect(config.JOURNAL_DB); c.execute("CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, side TEXT, qty INTEGER, price REAL, gross REAL, costs REAL, cost_breakdown TEXT, net REAL, reason TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, ts TEXT, symbol TEXT, action TEXT, confidence REAL, kronos REAL, rsi REAL, sentiment REAL, payload TEXT)")
    return c
def log_trade(ts,symbol,side,qty,price,gross,costs,breakdown,net,reason):
    try:
        c=_conn(); c.execute("INSERT INTO trades(ts,symbol,side,qty,price,gross,costs,cost_breakdown,net,reason) VALUES(?,?,?,?,?,?,?,?,?,?)",(ts,symbol,side,qty,price,gross,costs,json.dumps(breakdown),net,reason)); c.commit(); c.close()
    except Exception: pass
def log_decision(ts,symbol,decision,kronos=None,rsi=None,sentiment=None):
    try:
        c=_conn(); c.execute("INSERT INTO decisions(ts,symbol,action,confidence,kronos,rsi,sentiment,payload) VALUES(?,?,?,?,?,?,?,?)",(ts,symbol,decision.get("action"),decision.get("confidence"),kronos,rsi,sentiment,json.dumps(decision,default=str))); c.commit(); c.close()
    except Exception: pass
def read_trades(limit=500):
    try:
        c=_conn(); rows=c.execute("SELECT ts,symbol,side,qty,price,gross,costs,net,reason FROM trades ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); c.close(); return rows
    except Exception: return []
def read_decisions(limit=500):
    try:
        c=_conn(); rows=c.execute("SELECT ts,symbol,action,confidence,kronos,rsi,sentiment,payload FROM decisions ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); c.close(); return rows
    except Exception: return []
