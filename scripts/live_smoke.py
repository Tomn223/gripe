"""End-to-end live check (real xAI calls; small budget). Needs XAI_API_KEY in env or backend/.env.
Usage: backend/.venv/bin/python scripts/live_smoke.py "air fryers"   (writes the result to the cache)"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.cache import Cache  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.llm import GrokClient  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.sources import XApiV2Source, XaiXSearchSource  # noqa: E402

topic = sys.argv[1] if len(sys.argv) > 1 else "air fryers"
s = get_settings()
if not s.live_enabled:
    sys.exit("Live mode disabled: set XAI_API_KEY (and X_BEARER_TOKEN for DATA_SOURCE=x_api_v2).")
grok = GrokClient(s.xai_api_key, s.base_url)
src = XApiV2Source(s.x_bearer_token) if s.resolved_source == "x_api_v2" else \
    XaiXSearchSource(grok, s.search_model, s.search_calls, s.lookback_days)
t0 = time.time()
last = {}


def progress(stages):
    for st in stages:
        key = (st["key"], st["status"], st["count"])
        if last.get(st["key"]) != key:
            last[st["key"]] = key
            print(f"[{time.time() - t0:6.1f}s] {st['label']:<28} {st['status']:<8} {st['count'] or ''} {st['detail']}")


doc = Pipeline(s, grok, src).run(topic, progress)
Cache(s.cache_dir).put(topic, doc)
print(json.dumps({"topic": topic, "elapsed_s": round(time.time() - t0, 1), "stats": doc["stats"],
                  "top_categories": [(c["name"], c["count"]) for c in doc["categories"][:5]],
                  "headline": doc["summary"]["headline"]}, indent=1))
