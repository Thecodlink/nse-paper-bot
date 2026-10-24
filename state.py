"""state.json persistence. Local file by default; bot-state branch mode via env STATE_BRANCH_MODE=1.
Git: pull --rebase retry x3 before write-back (workflow also commits)."""
import json, os, subprocess, logging, config
log=logging.getLogger("state")
DEFAULT={"cash":config.CAPITAL,"starting_cash":config.CAPITAL,"positions":[],"trades":[],"equity_curve":[],"heartbeat":None,"heartbeat_date":None,"decisions":[],"daily_pnl":{},"consecutive_losing_days":0,"size_multiplier":1.0}
def _branch_mode(): return os.environ.get("STATE_BRANCH_MODE")=="1"
def _git(*args, check=False):
    return subprocess.run(["git"]+list(args), capture_output=True, text=True, timeout=30)
def pull_state_branch():
    if not _branch_mode(): return
    for i in range(3):
        try:
            _git("fetch","origin",config.STATE_BRANCH)
            r=_git("checkout",config.STATE_BRANCH,"--","state.json")
            if r.returncode==0: return
        except Exception as e: log.warning("state pull attempt %d: %s", i, e)
def load():
    pull_state_branch()
    try:
        with open(config.STATE_FILE) as f: s=json.load(f)
        for k,v in DEFAULT.items(): s.setdefault(k,v)
        return s
    except Exception: return dict(DEFAULT)
def save(state):
    tmp=config.STATE_FILE+".tmp"
    with open(tmp,"w") as f: json.dump(state,f,indent=2,default=str)
    os.replace(tmp, config.STATE_FILE)
    if _branch_mode():
        for i in range(3):
            try:
                _git("add","state.json"); _git("commit","-m","bot state update")
                r=_git("pull","--rebase","origin",config.STATE_BRANCH)
                r2=_git("push","origin",f"HEAD:{config.STATE_BRANCH}")
                if r2.returncode==0: return
            except Exception as e: log.warning("state push attempt %d: %s", i, e)
def heartbeat(state):
    n=config.now_ist(); state["heartbeat"]=n.isoformat(); state["heartbeat_date"]=n.date().isoformat(); return state
