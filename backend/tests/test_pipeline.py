"""Live path tests with a mocked xAI API (no network, no key)."""
import json
import httpx
import pytest

from app.config import Settings
from app.llm import GrokClient, extract_json
from app.noise import heuristic_filter
from app.pipeline import Pipeline
from app.sources import XApiV2Source, XaiXSearchSource, build_queries, parse_status_url, topic_terms

POSTS = [
    ("111", "alice", "My air fryer basket coating is peeling after 3 months, flakes in food. Hate it.", 40),
    ("112", "bob", "Air fryer is too small to cook for a family of four, I wish it had a bigger basket", 12),
    ("113", "dealbot", "Air fryer 50% OFF today only! #ad https://amzn.to/xyz", 0),
    ("114", "carol", "The air fryer beeps so loudly and there's no way to mute it. Worst design ever.", 7),
    ("115", "dave", "lol my cat thinks the air fryer is a tv", 300),
    ("116", "erin", "Second air fryer in a year where the heating element just stopped working. Returned it.", 3),
]
HALLUCINATED = {"url": "https://x.com/ghost/status/999", "username": "ghost", "text": "air fryer fake", "likes": 5}


def xai_handler(request: httpx.Request):
    body = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer test-key"
    if request.url.path.endswith("/responses"):
        assert body["tools"][0]["type"] == "x_search"
        posts = [{"url": f"https://x.com/{u}/status/{i}", "username": u, "created_at": "2026-10-20T10:00:00Z",
                  "text": t, "likes": l} for i, u, t, l in POSTS] + [HALLUCINATED]
        return httpx.Response(200, json={
            "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps({"posts": posts})}]}],
            "citations": [f"https://x.com/i/status/{i}" for i, *_ in POSTS],
            "usage": {"input_tokens": 100, "output_tokens": 50}})
    sys = body["messages"][0]["content"]
    user = body["messages"][1]["content"]
    if "screen X posts" in sys:
        items = json.loads(user.split("Posts:\n", 1)[1].split("\nReturn", 1)[0])
        noise = [{"i": it["i"], "reason": "joke"} for it in items if "cat thinks" in it["text"]]
        content = {"noise": noise}
    elif "You label X posts" in sys:
        items = json.loads(user.split("Posts:\n", 1)[1].split("\nReturn", 1)[0])
        def pp(t):
            return ("coating peeling" if "coating" in t else "too small" if "small" in t else
                    "loud beeping" if "beeps" in t else "heating element failure")
        content = {"labels": [{"i": it["i"], "sentiment": "negative", "pain_point": pp(it["text"]), "brand": "none",
                               "gist": it["text"][:40], "representativeness": 0.8,
                               "wish": "bigger basket" if "wish" in it["text"] else ""} for it in items]}
    elif "group short pain-point" in sys:
        content = {"categories": [
            {"name": "Durability & coating", "description": "", "members": ["coating peeling", "heating element failure"]},
            {"name": "Capacity", "description": "", "members": ["too small"]},
            {"name": "Noise & beeps", "description": "", "members": ["loud beeping"]}]}
    else:
        content = {"headline": "Top frustrations with air fryers: durability, size, beeping.",
                   "summary": "Two sentences.", "dig_suggestions": [
                       {"label": "Filter to durability complaints", "kind": "filter_category", "category": "Durability & coating"},
                       {"label": "What do people wish existed?", "kind": "wishes"},
                       {"label": "bad", "kind": "brands", "category": "Nonexistent"}]}
    return httpx.Response(200, json={"choices": [{"message": {"content": "```json\n" + json.dumps(content) + "\n```"}}],
                                     "usage": {"prompt_tokens": 10, "completion_tokens": 5}})


def settings(tmp_path):
    s = Settings()
    s.xai_api_key, s.data_source, s.cache_dir, s.search_calls = "test-key", "xai_x_search", tmp_path, 2
    return s


def test_live_pipeline_with_mocked_xai(tmp_path):
    s = settings(tmp_path)
    grok = GrokClient("test-key", transport=httpx.MockTransport(xai_handler))
    src = XaiXSearchSource(grok, s.search_model, calls=2)
    stages_seen = []
    doc = Pipeline(s, grok, src).run("air fryers", progress=lambda st: stages_seen.append([dict(x) for x in st]))
    ids = {p["id"] for p in doc["posts"]}
    assert "999" not in ids                      # uncited (hallucinated) post dropped
    assert "113" not in ids                      # ad dropped by heuristics
    assert "115" not in ids                      # joke dropped by LLM relevance check
    assert ids == {"111", "112", "114", "116"}
    names = [c["name"] for c in doc["categories"]]
    assert names[0] == "Durability & coating" and doc["categories"][0]["count"] == 2
    assert doc["summary"]["headline"].startswith("Top frustrations")
    assert all("category" not in d or d["category"] in names for d in doc["dig_suggestions"])
    assert doc["stats"]["unverified_dropped"] == 2  # ghost post, once per search call
    final = stages_seen[-1]
    assert [x["key"] for x in final] == ["pull", "filter", "label", "group", "summary"]
    assert all(x["status"] == "done" for x in final)
    assert any(p["wish"] == "bigger basket" for p in doc["posts"])
    assert doc["posts"][0]["url"].startswith("https://x.com/")


def test_x_api_v2_source_parses():
    def h(req):
        if req.url.path.endswith("/counts/recent"):
            return httpx.Response(200, json={"data": [{"start": "2026-10-20T00:00:00Z", "tweet_count": 5}]})
        assert "-is:retweet" in req.url.params["query"]
        return httpx.Response(200, json={
            "data": [{"id": "1", "text": "my standing desk broke", "author_id": "9", "created_at": "2026-10-20T00:00:00Z",
                      "public_metrics": {"like_count": 3, "retweet_count": 1}}],
            "includes": {"users": [{"id": "9", "username": "zed"}]}})
    src = XApiV2Source("tok", transport=httpx.MockTransport(h))
    posts, _ = src.fetch("standing desks", build_queries("standing desks")[:1])
    assert posts[0]["url"] == "https://x.com/zed/status/1" and posts[0]["likes"] == 3
    assert src.volume("standing desks")["series"][0]["count"] == 5


def test_helpers():
    assert parse_status_url("https://x.com/i/status/123") == ("123", None)
    assert parse_status_url("https://twitter.com/bob/status/55?s=20") == ("55", "bob")
    assert extract_json('Sure! {"a": 1} done') == {"a": 1}
    assert "desk" in topic_terms("standing desks")
    qs = build_queries("e-bikes")
    assert all("-is:retweet lang:en" in q for q in qs) and '"e-bike"' in qs[0]


def test_heuristic_filter():
    posts = [{"id": str(i), "username": "spam", "text": f"standing desk number {i} is great to own really"} for i in range(5)]
    posts += [{"id": "a", "username": "u1", "text": "Call us at +1 555 123 4567 for fridge repair today!"},
              {"id": "b", "username": "u2", "text": "My fridge ice maker died again after six months, so annoying"}]
    kept, dropped = heuristic_filter(posts, ["fridge", "standing desk"])
    assert [p["id"] for p in kept] == ["b"]
    reasons = {d["id"]: d["noise_reason"] for d in dropped}
    assert reasons["0"] == "repeat-posting account" and "phone" in reasons["a"]


def test_grok_error_never_leaks_key():
    grok = GrokClient("secret-key-123", transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": "bad"})))
    with pytest.raises(Exception) as e:
        grok.chat_json("m", "s", "u")
    assert "secret-key-123" not in str(e.value)
