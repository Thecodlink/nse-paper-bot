"""state.json persistence. Pure local file read/write - NO git here.

The workflow restores state.json from the bot-state branch before the
run (checkout step) and is the SOLE committer after it. An earlier
pull_state_branch() helper was deleted in Phase 0.5: it checked out a
local ref `bot-state` that only exists as `origin/bot-state`, so it
always silently failed; and the Oct 24 incident proved in-process git
in state.py loses heartbeats (push-returncode checked instead of the
commit; pull --rebase onto the divergent orphan history reset
state.json to the old version). One writer, no rebase, no history
merge: the workflow commit-back step adds state.json (+ journal.db
if present), commits if staged, and force-pushes HEAD:bot-state.
"""
import json
import logging
import os

import config

log = logging.getLogger("state")
DEFAULT = {"cash": config.CAPITAL, "starting_cash": config.CAPITAL, "positions": [], "trades": [],
           "equity_curve": [], "heartbeat": None, "heartbeat_date": None, "decisions": [],
           "daily_pnl": {}, "consecutive_losing_days": 0, "size_multiplier": 1.0}


def load():
    try:
        with open(config.STATE_FILE) as f:
            s = json.load(f)
        for k, v in DEFAULT.items():
            s.setdefault(k, v)
        return s
    except Exception:
        return dict(DEFAULT)


def save(state):
    tmp = config.STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, config.STATE_FILE)


def heartbeat(state):
    n = config.now_ist()
    state["heartbeat"] = n.isoformat()
    state["heartbeat_date"] = n.date().isoformat()
    return state
