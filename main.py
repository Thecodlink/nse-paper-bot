"""Orchestrator. Paper only, Yahoo data only, no real orders.
Modes: jobA | jobB | watchdog | once | test-notify
Internal loop 300s. Decision rule: BUY only if kronos>0.58 AND 40<RSI<70 AND price>EMA21 AND finbert>=0 AND brain BUY AND risk passes."""
import argparse, time, logging, sys, os, subprocess
import config, state as state_mod, notify, risk, paper_broker, journal
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log=logging.getLogger("main")

def _ist_time_str(): return config.now_ist().strftime("%H:%M:%S IST")

def _notify(fn, *args):
    """Call a notify.* function; notify must NEVER block/crash a trade.
    notify.send already swallows channel errors -- this is belt-and-braces so
    an unexpected notify bug can never propagate into the trading loop."""
    try: return fn(*args)
    except Exception as e: log.warning("notify call failed (ignored): %s", e); return False

def manage_exits(st, intraday):
    """Exits first: SL / TP / trail / square-off. Fill assumed at current close as next-open proxy in paper sim."""
    now=config.now_ist()
    for pos in list(st.get("positions",[])):
        df=(intraday or {}).get(pos["symbol"])
        if df is None or len(df)==0: continue
        price=float(df["Close"].iloc[-1]); atr=float(df["ATR14"].iloc[-1]) if "ATR14" in df else 0
        reason=None
        if config.SQUARE_OFF_FROM <= now.time(): reason="close"
        elif price<=pos["stop"]: reason="stop"
        elif price>=pos["target"]: reason="target"
        if atr: pos["stop"]=risk.trail_stop(pos, price, atr)
        is_trail_exit = reason is None and price<=pos["stop"] and pos["stop"]> (pos["entry"]-config.SL_ATR*atr if atr else pos["stop"])
        if reason or is_trail_exit:
            reason=reason or "trail"
            entry_cost=pos["entry"]*pos["qty"]+pos.get("costs_buy",0)
            trade,cb=paper_broker.sell(st,pos,price,reason,config.now_ist())
            pct=(trade["net_pnl"]/entry_cost*100) if entry_cost else 0
            _notify(notify.sell_confirmed,pos["symbol"],pos["qty"],_ist_time_str(),trade["exit"],trade["gross"],trade["costs"],trade["net_pnl"],pct,reason)

def run_cycle(st):
    state_mod.heartbeat(st)
    if not config.is_trading_day():
        log.info("Not a trading day (weekend/holiday) - skip cycle"); state_mod.save(st); return st
    try:
        import data as data_mod
        from indicators import add_indicators, latest
        from shortlist import build_shortlist
    except Exception as e:
        log.warning("data stack unavailable: %s - skip cycle", e); state_mod.save(st); return st
    daily=data_mod.fetch_daily_cached(config.SYMBOLS)
    if not daily:
        log.warning("No daily data (source=%s) - skip cycle", data_mod.last_source()); state_mod.save(st); return st
    candidates=build_shortlist(daily)
    symbols=[c["symbol"] for c in candidates[:getattr(config,"SHORTLIST_TOP_N",20)]] or config.NIFTY50[:10]
    intra_raw=data_mod.fetch_intraday(symbols + [p["symbol"] for p in st.get("positions",[])])
    intraday={}
    for sym,df in (intra_raw or {}).items():
        try: intraday[sym]=add_indicators(df)
        except Exception: intraday[sym]=df
    # staleness check on first available frame
    for sym,df in intraday.items():
        stale,age=data_mod.is_stale(df)
        if stale:
            log.warning("Data stale for %s age=%s min (>30) - skip cycle", sym, age); state_mod.save(st); return st
        break
    manage_exits(st, intraday)
    # decisions
    if config.no_new_trades() or len(st.get("positions",[]))>=config.MAX_POSITIONS:
        state_mod.save(st); return st
    import sentiment, kronos_forecast, brain
    # Cheap filters FIRST (stack-test design rule): Kronos costs ~58s/symbol on
    # 2 CPU, so it runs ONLY on the final KRONOS_MAX_CANDIDATES (default 5)
    # candidates that pass price/EMA/RSI/sentiment -- never on the whole list.
    cheap_pass=[]
    for cand in candidates[:getattr(config,"SHORTLIST_TOP_N",20)]:
        sym=cand["symbol"]; df=intraday.get(sym)
        if df is None: continue
        vals=latest(df)
        if not vals.get("Close"): continue
        if not (config.RSI_MIN < (vals.get("RSI14") or 0) < config.RSI_MAX): log.info("%s skip: RSI %s", sym, vals.get("RSI14")); continue
        if not (vals["Close"] > (vals.get("EMA21") or float("inf"))): log.info("%s skip: price<=EMA21", sym); continue
        sent,_=sentiment.aggregate(sym)
        if sent < config.FINBERT_MIN: log.info("%s skip: sentiment %s", sym, sent); continue
        cheap_pass.append((cand, vals, sent))
    for cand, vals, sent in cheap_pass[:getattr(config,"KRONOS_MAX_CANDIDATES",5)]:
        if len(st["positions"])>=config.MAX_POSITIONS: break
        sym=cand["symbol"]; df=intraday.get(sym)
        kp=kronos_forecast.up_probability(df, vals["Close"], symbol=sym)
        feats={**vals,"kronos_up_prob":kp,"finbert_sentiment":sent}
        if kp is None or kp<=config.KRONOS_THRESHOLD: log.info("%s skip: kronos %s", sym, kp); continue
        decision=brain.decide(sym, feats); journal.log_decision(str(config.now_ist()), sym, decision, kp, vals.get("RSI14"), sent)
        st.setdefault("decisions",[]).append({"symbol":sym, **decision})
        if decision["action"]!="BUY" or decision.get("veto_flag"): continue
        ok,why,qty,sl,tp=risk.check(st, sym, vals["Close"], vals.get("ATR14") or 0)
        if not ok: log.info("%s risk gate: %s", sym, why); continue
        pos,cb=paper_broker.buy(st, sym, qty, vals["Close"], sl, tp,
            f"kronos {kp:.2f}, RSI {vals.get('RSI14'):.1f}, price>EMA21, sentiment {sent:.2f}, brain: {decision['reasoning'][:200]}", config.now_ist())
        _notify(notify.buy_confirmed,sym, qty, _ist_time_str(), pos["entry"], qty*pos["entry"], sl, tp, pos["reason"], st["cash"])
    st.setdefault("equity_curve",[]).append({"ts":config.now_ist().isoformat(),"cash":st["cash"],"positions":len(st["positions"])})
    state_mod.save(st); return st

def square_off_and_eod(st):
    try:
        import data as data_mod
        intra=data_mod.fetch_intraday([p["symbol"] for p in st.get("positions",[])])
        from indicators import add_indicators
        intra={k:add_indicators(v) for k,v in (intra or {}).items()}
    except Exception: intra={}
    manage_exits(st, intra)  # at/after 15:15 this forces 'close'
    # force any remaining closed at last known entry (paper, logged)
    for pos in list(st.get("positions",[])):
        log.warning("Force square-off %s at entry proxy (no live frame)", pos["symbol"])
        paper_broker.sell(st, pos, pos["entry"], "close", config.now_ist())
    trades_today=[t for t in st.get("trades",[]) if str(config.today_ist()) in str(t.get("time",""))] or st.get("trades",[])
    wins=sum(1 for t in trades_today if t["net_pnl"]>0); losses=sum(1 for t in trades_today if t["net_pnl"]<=0)
    costs=sum(t.get("costs",0) for t in trades_today); pnl=st["cash"]-st.get("starting_cash",config.CAPITAL)
    pct=pnl/st.get("starting_cash",config.CAPITAL)*100
    # Losing-day streak -> position-size halving rule (risk.py): day P&L = today's trades' net.
    try:
        day_pnl=sum(t.get("net_pnl",0) for t in trades_today)
        streak,mult=risk.update_day_close(st, str(config.today_ist()), day_pnl)
        log.info("day close: pnl %.2f, consecutive losing days=%d, size_multiplier=%.1f", day_pnl, streak, mult)
    except Exception as e: log.warning("update_day_close failed (ignored): %s", e)
    _notify(notify.market_closed,str(config.today_ist()), st.get("starting_cash",5000), st["cash"], pnl, pct, len(trades_today), wins, losses, costs,
                           "Paper session complete. Data: Yahoo Finance (~15m delay). No real orders.")
    state_mod.heartbeat(st); state_mod.save(st); return st

def watchdog():
    st=state_mod.load(); today=str(config.today_ist())
    if st.get("heartbeat_date")!=today and config.is_trading_day():
        _notify(notify.send,f"WATCHDOG ALERT\nNo heartbeat for {today} in nse-paper-bot state.json. Re-dispatching Job A if possible.")
        token=os.environ.get("GITHUB_TOKEN")
        if token:
            try: subprocess.run(["gh","workflow","run","trade.yml","-f","mode=jobA"], capture_output=True, timeout=30); log.info("watchdog dispatched jobA via gh")
            except Exception as e: log.warning("watchdog dispatch failed: %s", e)
        else: log.warning("watchdog: no GITHUB_TOKEN, alert only")
        return 1
    log.info("watchdog: heartbeat OK for %s", today); return 0

def loop_until(exit_time, mode):
    st=state_mod.load()
    while True:
        now=config.now_ist()
        if now.time()>=exit_time: break
        try: st=run_cycle(st)
        except Exception as e: log.exception("cycle crashed, continuing: %s", e)
        if mode=="once": break
        time.sleep(config.LOOP_SECONDS)
    if mode=="jobB": square_off_and_eod(st)
    return st

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mode", default="once", choices=["jobA","jobB","watchdog","once","test-notify"])
    a=ap.parse_args()
    if a.mode=="test-notify":
        _notify(notify.send,"TEST - nse-paper-bot Telegram notify is configured. Paper trading only, no real orders."); return 0
    if a.mode=="watchdog": return watchdog()
    if a.mode=="jobA": loop_until(config.JOB_A_EXIT,"jobA")
    elif a.mode=="jobB": loop_until(config.JOB_B_EXIT,"jobB")
    elif a.mode=="once":
        st=state_mod.load()
        try: run_cycle(st)
        except Exception as e: log.exception("once cycle error (non-fatal): %s", e)
    return 0
if __name__=="__main__": sys.exit(main())
