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
    # FIX (Oct 24, 2026, second attempt): save() does NO git at all in
    # branch mode. Two earlier designs both lost the heartbeat:
    #  (1) commit-then-push checked only the push returncode, and
    #  (2) pull --rebase origin bot-state rebased main onto the divergent
    #      orphan bot-state history and reset state.json to the OLD
    #      version, so the workflow backup step then saw "nothing to
    #      commit". bot-state is a snapshot branch, not a history branch:
    #      the workflow commit-back step is the SOLE committer — it adds
    #      state.json (+ journal.db if present), commits if staged, and
    #      force-pushes HEAD:bot-state. One writer, no rebase, no history
    #      merge. load() above still pulls the file from bot-state.
def heartbeat(state):
    n=config.now_ist(); state["heartbeat"]=n.isoformat(); state["heartbeat_date"]=n.date().isoformat(); return state
