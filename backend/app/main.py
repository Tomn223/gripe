"""Gripe: FastAPI backend (X market pain-point analyzer)."""
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import dig as dig_mod
from .analysis import public_view
from .cache import Cache, normalize_topic, slugify
from .config import get_settings
from .jobs import JobStore

settings = get_settings()
cache = Cache(settings.cache_dir)
jobs = JobStore()
app = FastAPI(title="Gripe API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def make_pipeline():
    from .llm import GrokClient
    from .pipeline import Pipeline
    from .sources import XApiV2Source, XaiXSearchSource
    s = get_settings()
    if not s.live_enabled:
        raise HTTPException(503, "Live analysis needs XAI_API_KEY (and X_BEARER_TOKEN for DATA_SOURCE=x_api_v2). "
                                 "Cached example topics still work.")
    grok = GrokClient(s.xai_api_key, s.base_url)
    if s.resolved_source == "x_api_v2":
        src = XApiV2Source(s.x_bearer_token)
    else:
        src = XaiXSearchSource(grok, s.search_model, s.search_calls, s.lookback_days)
    return Pipeline(s, grok, src)


@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "live_enabled": s.live_enabled, "data_source": s.resolved_source,
            "models": {"search": s.search_model, "label": s.label_model}, "cached_topics": cache.list()}


@app.get("/topics")
def topics():
    return cache.list()


@app.get("/analyze")
def analyze(topic: str = Query(..., min_length=2, max_length=80), refresh: bool = False):
    """Returns the cached analysis instantly, or starts a live job and returns its id (202-style payload)."""
    t = normalize_topic(topic)
    doc = None if refresh else cache.get(t)
    if doc:
        return {"status": "done", "cached": True, "topic": doc["topic"], "result": public_view(doc)}
    pipe = make_pipeline()

    def work(progress):
        d = pipe.run(t, progress)
        cache.put(t, d)

    job = jobs.start(slugify(t), work)
    return {"status": "running", "cached": False, "topic": t, "job_id": job["id"], "stages": job["stages"]}


@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "unknown job")
    out = {k: job[k] for k in ("id", "status", "stages", "error")}
    if job["status"] == "done":
        doc = _by_slug(job["slug"])
        out["result"] = public_view(doc) if doc else None
    return out


def _by_slug(slug):
    p = cache.dir / f"{slug}.json"
    if p.exists():
        import json
        return json.loads(p.read_text())
    return None


def _doc(topic):
    doc = cache.get(normalize_topic(topic))
    if not doc:
        raise HTTPException(404, f"No analysis for '{topic}' yet. Call /analyze first.")
    return doc


@app.get("/posts")
def posts(topic: str, category: str | None = None, limit: int = Query(50, ge=1, le=500), offset: int = 0):
    doc = _doc(topic)
    ps = doc["posts"]
    if category and category.lower() != "all":
        ps = [p for p in ps if p["category"].lower() == category.lower()]
    ps = sorted(ps, key=lambda p: -p["representativeness"])
    return {"topic": doc["topic"], "category": category, "total": len(ps), "posts": ps[offset:offset + limit]}


@app.post("/dig")
def dig(payload: dict = Body(...)):
    topic = payload.get("topic")
    sug = payload.get("suggestion")
    if isinstance(sug, str):
        sug = {"label": sug, "kind": "query"}
    if not topic or not sug:
        raise HTTPException(422, "body must be {topic, suggestion}")
    doc = _doc(topic)
    res = dig_mod.answer(doc, sug)
    s = get_settings()
    # Narrower live re-query for free-text questions when keys exist and the offline filter found little.
    if s.live_enabled and (sug.get("kind") or "query") == "query" and payload.get("live", True) and len(res["posts"]) < 5:
        try:
            from .livedig import live_dig
            res = live_dig(s, doc, sug) or res
        except Exception as e:
            res["live_error"] = str(e)[:200]
    return res
