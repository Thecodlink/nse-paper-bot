"""Paper broker: fills at NEXT candle open +/- 0.1% slippage, full Indian cost stack itemised.
Paper only - no broker API, no real orders ever."""
import config, journal

def cost_breakdown(side, qty, price):
    turnover=qty*price
    brokerage=config.BROKERAGE_PER_ORDER
    stt=turnover*config.STT_SELL_PCT if side=="SELL" else 0.0
    txn=turnover*config.EXCHANGE_TXN_PCT
    sebi=turnover*(config.SEBI_PER_CRORE/1e7)
    stamp=turnover*config.STAMP_BUY_PCT if side=="BUY" else 0.0
    gst=config.GST_PCT*(brokerage+txn+sebi)
    total=brokerage+stt+txn+sebi+stamp+gst
    return {"brokerage":round(brokerage,2),"stt":round(stt,2),"exchange_txn":round(txn,2),"sebi":round(sebi,2),"stamp_duty":round(stamp,2),"gst":round(gst,2),"total":round(total,2),"turnover":round(turnover,2)}

def fill_price(next_open, side):
    return round(next_open*(1+config.SLIPPAGE_PCT) if side=="BUY" else next_open*(1-config.SLIPPAGE_PCT),2)

def buy(state, symbol, qty, next_open, stop, target, reason, ts):
    price=fill_price(next_open,"BUY"); cb=cost_breakdown("BUY",qty,price); gross=qty*price
    total_cost=gross+cb["total"]
    state["cash"]=round(state["cash"]-total_cost,2)
    pos={"symbol":symbol,"qty":qty,"entry":price,"stop":stop,"target":target,"costs_buy":cb["total"],"time":str(ts),"reason":reason}
    state["positions"].append(pos)
    journal.log_trade(str(ts),symbol,"BUY",qty,price,gross,cb["total"],cb,-total_cost,reason)
    return pos, cb

def sell(state, pos, next_open, reason, ts):
    qty=pos["qty"]; price=fill_price(next_open,"SELL"); cb=cost_breakdown("SELL",qty,price); gross=qty*price
    net=gross-cb["total"]
    state["cash"]=round(state["cash"]+net,2)
    state["positions"]=[p for p in state["positions"] if p is not pos]
    buy_cost=pos.get("costs_buy",0)
    pnl=net-(pos["entry"]*qty+buy_cost)
    trade={"symbol":pos["symbol"],"qty":qty,"entry":pos["entry"],"exit":price,"gross":gross,"costs":round(cb["total"]+buy_cost,2),
           "costs_sell":cb["total"],"net_pnl":round(pnl,2),"reason":reason,"time":str(ts)}
    state.setdefault("trades",[]).append(trade)
    journal.log_trade(str(ts),pos["symbol"],"SELL",qty,price,gross,cb["total"],cb,round(pnl,2),reason)
    return trade, cb
