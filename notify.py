"""Channel-agnostic notifications. NEVER raises / never blocks a trade.

Channels are tried in order; each failure is logged and the next channel is
tried. Primary channel: Telegram (env TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID).
The Telegram token is read from the environment ONLY, is never printed or
logged, and is never included in any logged string/URL.

CallMeBot/WhatsApp is kept as an OPTIONAL, disabled-by-default channel
function only -- it is NOT in CHANNELS unless a human explicitly enables it.
"""
import os, logging, json, urllib.parse, urllib.request
log = logging.getLogger("notify")

CHANNELS = ["telegram"]


def _send_telegram(text):
    """Send via Telegram Bot API. Returns True/False, never raises."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        # Log the message (never any credential) so paper trades stay auditable.
        log.info("[Telegram not configured] Message would be:\n%s", text)
        print(text)
        return False
    try:
        # URL contains the token: it is built locally and NEVER logged.
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        ).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        ok = bool(body.get("ok"))
        log.info("Telegram send %s (%d chars)", "ok" if ok else "rejected", len(text))
        return ok
    except Exception as e:
        # Log only the exception type: str(e) on a URL error could embed the URL/token.
        log.warning("Telegram send failed: %s", type(e).__name__)
        return False


def _send_callmebot_whatsapp(text):
    """OPTIONAL CallMeBot/WhatsApp channel. Disabled by default (not in CHANNELS)."""
    phone = os.environ.get("PHONE")
    key = os.environ.get("CALLMEBOT_KEY")
    if not phone or not key:
        log.info("[CallMeBot not configured] Message would be:\n%s", text)
        return False
    try:
        url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(
            {"phone": phone, "text": text, "apikey": key}
        )
        urllib.request.urlopen(url, timeout=20).read()
        log.info("CallMeBot sent (%d chars)", len(text))
        return True
    except Exception as e:
        log.warning("CallMeBot send failed: %s", type(e).__name__)
        return False


# Channel name -> sender function. Add a channel here + to CHANNELS to enable it.
dispatch = {
    "telegram": _send_telegram,
    "whatsapp": _send_callmebot_whatsapp,
}


def send(text):
    """Try each configured channel. Returns True if any succeeded.

    NEVER raises: a notification failure must never block or crash a trade.
    """
    sent_any = False
    for ch in CHANNELS:
        try:
            fn = dispatch.get(ch)
            if fn is None:
                log.warning("notify: unknown channel %r, skipping", ch)
                continue
            if fn(text):
                sent_any = True
        except Exception as e:
            log.warning("notify channel %s failed: %s -- continuing", ch, type(e).__name__)
            continue
    return sent_any


# EXACT templates (Phase spec, Telegram Markdown bold headers)
def buy_confirmed(symbol, qty, time_str, price, amount, sl, tp, reason, cash):
    return send(f"""*BUY CONFIRMED*
Stock: {symbol} | Qty: {qty} | Time: {time_str}
Buy price: Rs {price:.2f} | Amount: Rs {amount:.2f}
Stop: Rs {sl:.2f} | Target: Rs {tp:.2f}
Reason: {reason}
Cash left: Rs {cash:.2f}""")


def sell_confirmed(symbol, qty, time_str, price, gross, costs, net, pct, exit_reason):
    return send(f"""*SELL CONFIRMED*
Stock: {symbol} | Qty: {qty} | Time: {time_str}
Sell price: Rs {price:.2f} | Gross: Rs {gross:.2f} | Costs: Rs {costs:.2f} | NET: Rs {net:.2f} ({pct:.2f}%)
Exit reason: {exit_reason}""")


def market_closed(date_str, open_amt, close_amt, pnl, pct, n, w, l, costs, notes):
    return send(f"""*MARKET CLOSED - {date_str}*
Open: Rs 5000 | Close: Rs {close_amt:.2f} | P&L: Rs {pnl:.2f} ({pct:.2f}%)
Trades: {n} (win {w} / loss {l}) | Costs paid: Rs {costs:.2f}
Notes: {notes}""")
