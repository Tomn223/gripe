"""Narrow live re-query for a free-text dig-deeper question (only used when API keys exist)."""
import json

from .analysis import finalize_representativeness
from .llm import GrokClient
from .noise import heuristic_filter
from .pipeline import LABEL_SYS
from .sources import XApiV2Source, XaiXSearchSource, topic_terms


def live_dig(s, doc, sug):
    grok = GrokClient(s.xai_api_key, s.base_url)
    topic, q = doc["topic"], sug["label"]
    if s.resolved_source == "x_api_v2":
        src = XApiV2Source(s.x_bearer_token, per_query=50)
    else:
        src = XaiXSearchSource(grok, s.search_model, 1, s.lookback_days)
    raw, _ = src.fetch(f"{topic} ({q})", [f'"{topic}" {q} -is:retweet lang:en'], max_posts=30)
    kept, _ = heuristic_filter(raw, topic_terms(topic))
    if not kept:
        return None
    cats = [c["name"] for c in doc["categories"]]
    items = [{"i": i, "text": p["text"][:500]} for i, p in enumerate(kept[:30])]
    out = grok.chat_json(s.label_model, LABEL_SYS + f" Also return category: one of {json.dumps(cats)}.",
        f"Product category: {topic}\nQuestion: {q}\nPosts:\n{json.dumps(items, ensure_ascii=False)}\n"
        'Return {"answer":"2 sentences answering the question from these posts","labels":[{"i":0,"sentiment":"",'
        '"category":"","brand":"","gist":"","representativeness":0.5,"wish":""}]}')
    labels = {int(l["i"]): l for l in out.get("labels", []) if "i" in l}
    posts = []
    for i, p in enumerate(kept[:30]):
        l = labels.get(i)
        if not l:
            continue
        posts.append({**p, "sentiment": l.get("sentiment", "neutral"), "category": l.get("category", "other"),
                      "brand": l.get("brand", "none"), "gist": l.get("gist", ""),
                      "rep_llm": float(l.get("representativeness", 0.5)), "wish": l.get("wish", "")})
    finalize_representativeness(posts)
    posts.sort(key=lambda p: -p["representativeness"])
    return {"answer": out.get("answer", ""), "category": None, "posts": posts, "mode": "live"}
