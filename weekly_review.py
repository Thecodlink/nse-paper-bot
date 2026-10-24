"""Friday 16:00 weekly review (playbook s.7). Reads journal, writes knowledge/review_<date>.md, proposes ONE change."""
import datetime, pathlib, collections, journal, config
def main():
    trades=journal.read_trades(1000); decisions=journal.read_decisions(1000)
    pnl=sum(r[7] or 0 for r in trades if r[2]=="SELL") if trades else 0
    stops=[r for r in trades if r[8]=="stop"]; targets=[r for r in trades if r[8]=="target"]
    # Kronos threshold evidence from decisions
    kp=[(r[4],r[2]) for r in decisions if r[4] is not None]
    date=str(config.today_ist()); out=pathlib.Path(f"knowledge/review_{date}.md")
    txt=f"""# Weekly Review - {date}

Trades rows: {len(trades)} | Decision rows: {len(decisions)} | Net SELL pnl (journal net col): Rs {pnl:.2f}

1. Which rules made/lost money: stop exits {len(stops)}, target exits {len(targets)}. (Fill narrative from trades table in journal.db - automated counts above.)
2. Kronos 0.58 threshold: decisions with kronos recorded: {len(kp)}. Evidence is {'thin - no change justified' if len(kp)<20 else 'see decisions table'}.
3. ATR multiple: stop-out count {len(stops)} vs target count {len(targets)} - {'too few trades to judge' if len(stops)+len(targets)<10 else 'compare in journal'}.
4. 1 position vs 2: counterfactual requires replaying journal decisions in order - not auto-computed; record manually before proposing a change.
5. ONE concrete threshold change: {'NO CHANGE - evidence too thin this week.' if len(trades)<10 else 'Review journal and record exactly one change here with evidence, then edit knowledge/trader_playbook.md.'}
"""
    out.write_text(txt); print(f"Wrote {out}"); return str(out)
if __name__=="__main__": main()
