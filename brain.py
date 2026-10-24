"""3-tier brain: Groq screen -> Gemini decision -> NVIDIA NIM critique.
Keys from env only, never printed. No keys -> SKIP, no crash.
Bad-JSON handling: the Gemini response is parsed strictly; on failure the
request is retried (up to 3 attempts total) with a repair prompt, then SKIP.
Output JSON exactly: {"symbol","action","confidence","entry","stop","target","reasoning","veto_flag"}"""
import os, json, logging, pathlib
log = logging.getLogger("brain")
MAX_JSON_ATTEMPTS = 3


def _playbook():
    try:
        return pathlib.Path("knowledge/trader_playbook.md").read_text()[:8000]
    except Exception:
        return ""


def _skip(symbol, why, entry=0, stop=0, target=0):
    return {"symbol": symbol, "action": "SKIP", "confidence": 0.0, "entry": entry,
            "stop": stop, "target": target, "reasoning": why, "veto_flag": False}


def _try_parse(text, symbol):
    """Strict parse. Returns the decision dict, or None if the JSON is bad."""
    if not text:
        return None
    try:
        t = text.strip().strip("`")
        t = t[t.index("{"):t.rindex("}") + 1]
        d = json.loads(t)
        if not isinstance(d, dict) or "action" not in d:
            return None
        return {"symbol": d.get("symbol", symbol), "action": d.get("action", "SKIP"),
                "confidence": float(d.get("confidence", 0)),
                "entry": float(d.get("entry", 0)), "stop": float(d.get("stop", 0)),
                "target": float(d.get("target", 0)),
                "reasoning": str(d.get("reasoning", "")), "veto_flag": bool(d.get("veto_flag", False))}
    except Exception:
        return None


def _parse(text, symbol):
    """Back-compatible wrapper: bad JSON -> SKIP dict."""
    return _try_parse(text, symbol) or _skip(symbol, "Unparseable LLM output")


def _groq_screen(prompt):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    try:
        from groq import Groq
        c = Groq(api_key=key)
        # Verified 2026-10-24: this Groq account's models list has no
        # llama-3.3-70b-versatile (404 model_not_found); qwen/qwen3.8-27b
        # returned 200 OK on the screen prompt. Use that as the screen model.
        r = c.chat.completions.create(model="qwen/qwen3.8-27b", messages=[{"role": "user", "content": prompt}], max_tokens=300)
        return r.choices[0].message.content
    except Exception as e:
        log.warning("Groq tier failed: %s", type(e).__name__)
        return None


def _gemini(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        # Verified 2026-10-24: gemini-2.5-flash / 2.5-flash-lite return 404 for new
        # users; gemini-3.5-flash-lite returned 200 OK. Use that as the Flash default.
        r = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
        return r.text
    except Exception as e:
        log.warning("Gemini tier failed: %s", type(e).__name__)
        return None


def _gemini_decision(prompt, symbol):
    """Call Gemini and parse its JSON, retrying on bad JSON (x3 total).

    Each retry appends a repair instruction demanding ONLY a valid JSON
    object. Returns a decision dict, or None if all attempts fail.
    """
    repair = ("\n\nIMPORTANT: your previous reply was not valid JSON. "
              "Reply with ONE valid JSON object ONLY -- no prose, no markdown "
              "fences, no explanation -- with keys "
              '{"symbol","action","confidence","entry","stop","target","reasoning","veto_flag"}.')
    attempt_prompt = prompt
    for attempt in range(1, MAX_JSON_ATTEMPTS + 1):
        text = _gemini(attempt_prompt)
        if text is None:
            return None  # tier unavailable / no key -- not a JSON problem, don't spin
        decision = _try_parse(text, symbol)
        if decision is not None:
            if attempt > 1:
                log.info("brain: valid JSON on retry %d for %s", attempt, symbol)
            return decision
        log.warning("brain: bad JSON from Gemini for %s (attempt %d/%d)", symbol, attempt, MAX_JSON_ATTEMPTS)
        attempt_prompt = prompt + repair
    return None


def _nim_critique(prompt, decision_text):
    key = os.environ.get("NVIDIA_NIM_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
        c = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=key)
        # Verified 2026-10-24: meta/llama-3.3-70b-instruct returns 410 (gone)
        # on NIM; meta/llama-3.2-90b-vision-instruct returned 200 OK. Use that.
        r = c.chat.completions.create(model="meta/llama-3.2-90b-vision-instruct",
            messages=[{"role": "user", "content": f"Argue the OTHER side of this trade decision. If the counter-case is stronger reply starting VETO, else AGREE.\nDecision: {decision_text}\nContext: {prompt[:2000]}"}], max_tokens=300)
        return r.choices[0].message.content
    except Exception as e:
        log.warning("NIM tier failed: %s", type(e).__name__)
        return None


def decide(symbol, features: dict):
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GROQ_API_KEY")):
        return _skip(symbol, "LLM keys not configured")
    prompt = (f"PLAYBOOK:\n{_playbook()}\n\nSymbol: {symbol}\nFeatures: {json.dumps(features, default=str)}\n"
              "State bull case, then bear case, then verdict. Return JSON only: "
              '{"symbol","action","confidence","entry","stop","target","reasoning","veto_flag"}')
    screen = _groq_screen(f"Fast screen - is this worth a full decision? Reply SKIP or PROCEED with one line.\n{prompt[:2000]}")
    if screen and screen.strip().upper().startswith("SKIP"):
        return _skip(symbol, f"Groq screen: {screen[:200]}")
    decision = _gemini_decision(prompt, symbol)
    if decision is None:
        return _skip(symbol, "Gemini unavailable or returned bad JSON after 3 attempts")
    critique = _nim_critique(prompt, json.dumps(decision))
    if critique and critique.strip().upper().startswith("VETO"):
        # Tiers split -> SKIP per spec
        decision["action"] = "SKIP"
        decision["veto_flag"] = True
        decision["reasoning"] = (decision["reasoning"] + " | NIM critique veto: " + critique[:300])
    return decision
