"""Streamlit dashboard: equity curve, positions, trades, reasoning. Reads state.json + journal.db."""
import json, pathlib
try:
    import streamlit as st, plotly.express as px, pandas as pd
    HAS_UI=True
except Exception:
    HAS_UI=False  # py_compile / import guard when streamlit not installed
def _load_state():
    try: return json.loads(pathlib.Path("state.json").read_text())
    except Exception: return {"cash":5000,"positions":[],"trades":[],"equity_curve":[]}
if HAS_UI:
    st.set_page_config(page_title="NSE Paper Bot", layout="wide"); st.title("NSE Paper Bot - Paper Trading Only")
    s=_load_state(); st.metric("Cash (Rs)", f"{s.get('cash',0):.2f}"); st.write(f"Heartbeat: {s.get('heartbeat')}")
    eq=s.get("equity_curve",[])
    if eq: st.plotly_chart(px.line(pd.DataFrame(eq), x="ts", y="cash", title="Equity (cash) curve"))
    st.subheader("Open positions"); st.dataframe(s.get("positions",[]))
    st.subheader("Trades"); st.dataframe(s.get("trades",[]))
    st.subheader("Decision reasoning")
    try:
        import journal; st.dataframe(journal.read_decisions(100))
    except Exception: st.dataframe(s.get("decisions",[]))
