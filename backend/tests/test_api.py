"""API tests against the committed seed caches (offline, zero API calls)."""
import os
os.environ["XAI_API_KEY"] = ""
os.environ["X_BEARER_TOKEN"] = ""
from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)


def test_cached_topics_load():
    for t in ["refrigerators", "standing desks", "e-bikes", "Fridge", "ebike"]:
        r = c.get("/analyze", params={"topic": t})
        assert r.status_code == 200, t
        d = r.json()
        assert d["cached"] and d["result"]["categories"] and "posts" not in d["result"]
        assert d["result"]["stats"]["kept"] >= 50


def test_posts_sorted_by_representativeness():
    r = c.get("/posts", params={"topic": "refrigerators", "category": "Ice maker & water dispenser"}).json()
    assert r["total"] == 21
    reps = [p["representativeness"] for p in r["posts"]]
    assert reps == sorted(reps, reverse=True)
    assert all(p["url"].startswith("https://x.com/") for p in r["posts"])


def test_dig_offline():
    d = c.get("/analyze", params={"topic": "e-bikes"}).json()["result"]
    for s in d["dig_suggestions"]:
        r = c.post("/dig", json={"topic": "e-bikes", "suggestion": s})
        assert r.status_code == 200 and r.json()["answer"] and r.json()["mode"] == "offline"
    r = c.post("/dig", json={"topic": "e-bikes", "suggestion": "stairs heavy"}).json()
    assert r["posts"]


def test_uncached_topic_without_keys_is_503():
    assert c.get("/analyze", params={"topic": "air fryers"}).status_code == 503
