import pathlib

import config
import state


def test_pull_state_branch_deleted():
    # Phase 0.5: the helper checked out a local ref that only exists as
    # origin/bot-state and always silently failed.
    assert not hasattr(state, "pull_state_branch")


def test_load_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_FILE", str(tmp_path / "nope.json"))
    s = state.load()
    assert s["cash"] == config.CAPITAL
    assert s["positions"] == []


def test_save_load_roundtrip(tmp_path, monkeypatch):
    f = str(tmp_path / "state.json")
    monkeypatch.setattr(config, "STATE_FILE", f)
    s = state.load()
    s["cash"] = 4321.0
    state.save(s)
    assert state.load()["cash"] == 4321.0


def test_trade_yml_jobA_no_longer_accepts_once():
    yml = pathlib.Path(__file__).resolve().parent.parent.joinpath(
        ".github/workflows/trade.yml").read_text()
    joba_if = [ln for ln in yml.splitlines() if "inputs.mode == 'jobA'" in ln]
    assert joba_if, "jobA if: line not found"
    assert "inputs.mode == 'once'" not in joba_if[0]
    # ...but the GitHub crons and the HF cache step stay (constraints).
    assert "'20 3 * * 1-5'" in yml
    assert "Cache HF models" in yml
