"""Sentiment: RSS (Moneycontrol/ET/Pulse) + FinBERT ProsusAI/finbert.
Scores the last HEADLINES_N (=50) headlines.
FinBERT licence CC BY-NC-SA: research only, remove/replace if commercial.
Fallback: returns 0.0 with log if FinBERT unavailable - never crashes."""
import logging, urllib.request, xml.etree.ElementTree as ET
import config
log = logging.getLogger("sentiment")
_pipe = None
_tried = False


def fetch_headlines(limit=None):
    """Fetch up to `limit` headlines (default config.HEADLINES_N = 50)."""
    if limit is None:
        limit = getattr(config, "HEADLINES_N", 50)
    heads = []
    try:
        import feedparser
        for name, url in config.RSS_FEEDS.items():
            try:
                f = feedparser.parse(url)
                for e in f.entries[:limit]:
                    heads.append({"source": name, "title": e.get("title", "")})
            except Exception as e:
                log.warning("RSS %s: %s", name, e)
    except ImportError:
        for name, url in config.RSS_FEEDS.items():
            try:
                raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=15).read()
                root = ET.fromstring(raw)
                for item in root.iter("item"):
                    t = item.findtext("title")
                    if t:
                        heads.append({"source": name, "title": t})
            except Exception as e:
                log.warning("RSS stdlib %s: %s", name, e)
    return heads[:limit]


def _finbert():
    global _pipe, _tried
    if _pipe or _tried:
        return _pipe
    _tried = True
    try:
        from transformers import pipeline
        model_ref = "ProsusAI/finbert"
        # FinBERT's repo ships PyTorch + TF + Flax + safetensors (~1.7 GB total).
        # Download safetensors + tokenizer/config only, skipping the duplicate
        # TF/Flax/PyTorch-bin weights (~1.3 GB and ~8 min saved, stack-test lesson).
        try:
            from huggingface_hub import snapshot_download
            model_ref = snapshot_download(
                repo_id="ProsusAI/finbert",
                ignore_patterns=["*.h5", "*.msgpack", "pytorch_model.bin"],
            )
        except Exception as e:
            log.warning("FinBERT snapshot_download failed (%s); falling back to hub load", e)
        _pipe = pipeline("sentiment-analysis", model=model_ref, tokenizer="ProsusAI/finbert")
    except Exception as e:
        log.warning("FinBERT unavailable (%s); sentiment fallback = 0.0 neutral", e)
    return _pipe


def score_headlines(headlines, symbol=None):
    # Score the last HEADLINES_N headlines (Phase spec).
    limit = getattr(config, "HEADLINES_N", 50)
    texts = [h["title"] for h in (headlines or [])][-limit:]
    if symbol:
        texts = [t for t in texts if symbol.lower() in t.lower()] or texts
    texts = texts[:limit]
    if not texts:
        return 0.0, []
    pipe = _finbert()
    if pipe is None:
        return 0.0, [{"title": t, "score": 0.0} for t in texts]
    per = []
    try:
        for r, t in zip(pipe(texts, truncation=True), texts):
            s = float(r["score"]) if r["label"] == "positive" else (-float(r["score"]) if r["label"] == "negative" else 0.0)
            per.append({"title": t, "score": s})
    except Exception as e:
        log.warning("FinBERT scoring failed: %s", e)
        return 0.0, []
    agg = sum(p["score"] for p in per) / len(per) if per else 0.0
    return max(-1.0, min(1.0, agg)), per


def aggregate(symbol=None):
    h = fetch_headlines()
    return score_headlines(h, symbol)
