"""'Dig deeper' answers computed from already-labeled data (works fully offline for cached topics)."""
import re
from collections import Counter

STOP = set("the a an of in on for to and or with what which who do does is are most come up people this that these "
           "those about wish existed exist category complaints complaint filter show me only posts brands brand".split())


def _post_brief(p):
    keys = ("id", "url", "username", "created_at", "text", "likes", "sentiment", "category", "brand", "gist",
            "representativeness", "wish")
    return {k: p.get(k) for k in keys}


def _match_category(doc, name):
    if not name:
        return None
    names = [c["name"] for c in doc["categories"]]
    for n in names:
        if n.lower() == name.lower():
            return n
    for n in names:
        if name.lower() in n.lower() or n.lower() in name.lower():
            return n
    return None


def answer(doc, suggestion: dict):
    """suggestion: {label, kind, category?}. kind in filter_category|brands|wishes|top_liked|sentiment|query."""
    kind = (suggestion.get("kind") or "query").lower()
    label = suggestion.get("label") or ""
    posts = doc["posts"]
    cat = _match_category(doc, suggestion.get("category"))
    scope = [p for p in posts if p["category"] == cat] if cat else posts
    scope_name = f"“{cat}”" if cat else "all kept posts"

    if kind == "filter_category" and cat:
        c = next(c for c in doc["categories"] if c["name"] == cat)
        neg = c["sentiment"]["negative"]
        brands = ", ".join(f"{b['name']} ({b['count']})" for b in c["top_brands"][:3]) or "no single brand"
        text = (f"{c['count']} of {len(posts)} posts ({round(c['share'] * 100)}%) fall under “{cat}”; "
                f"{neg} of them negative. Most-named brands: {brands}. "
                f"Typical complaint: {c['example_gists'][0] if c['example_gists'] else ''}")
        return {"answer": text, "category": cat, "posts": [_post_brief(p) for p in scope[:25]], "mode": "offline"}

    if kind == "brands":
        b = Counter(p["brand"] for p in scope if p["brand"] != "none")
        unbranded = sum(1 for p in scope if p["brand"] == "none")
        if b:
            top = ", ".join(f"{n} ({c})" for n, c in b.most_common(5))
            text = (f"Within {scope_name}, the most-mentioned brands are {top}. {unbranded} of {len(scope)} posts name "
                    f"no brand, so treat brand counts as directional: they depend on how people tag and on the searches.")
        else:
            text = f"Posts in {scope_name} rarely name a brand ({unbranded} of {len(scope)} are unbranded)."
        bp = sorted([p for p in scope if p["brand"] != "none"], key=lambda p: -p["representativeness"])
        return {"answer": text, "category": cat, "brands": [{"name": n, "count": c} for n, c in b.most_common(8)],
                "posts": [_post_brief(p) for p in bp[:25]], "mode": "offline"}

    if kind == "wishes":
        w = [p for p in scope if p.get("wish")]
        cats = Counter(p["category"] for p in w)
        if w:
            themes = ", ".join(f"{n.lower()} ({c})" for n, c in cats.most_common(3))
            examples = "; ".join(f"“{p['wish']}”" for p in w[:3])
            text = (f"{len(w)} posts voice an explicit wish, question, or unmet need, clustered around {themes}. "
                    f"Examples: {examples}")
        else:
            text = "Few posts state an explicit wish; the unmet need is implied by the complaints themselves."
        return {"answer": text, "category": cat, "posts": [_post_brief(p) for p in w[:25]], "mode": "offline"}

    if kind in ("top_liked", "sentiment"):
        tl = sorted(scope, key=lambda p: -(p.get("likes") or 0))[:10]
        s = Counter(p["sentiment"] for p in scope)
        text = (f"Sentiment in {scope_name}: {s.get('negative', 0)} negative, {s.get('neutral', 0)} neutral, "
                f"{s.get('positive', 0)} positive. The most-liked post ({tl[0]['likes']} likes) says: {tl[0]['gist']}"
                if tl else "No posts.")
        return {"answer": text, "category": cat, "posts": [_post_brief(p) for p in tl], "mode": "offline"}

    # free-text: keyword filter over text, gist, category
    words = [w for w in re.findall(r"[a-z0-9\-]{3,}", label.lower()) if w not in STOP]
    hits = []
    for p in scope:
        hay = f"{p['text']} {p['gist']} {p['category']} {p['brand']}".lower()
        score = sum(1 for w in words if w in hay)
        if score:
            hits.append((score, p))
    hits.sort(key=lambda t: (-t[0], -t[1]["representativeness"]))
    ps = [p for _, p in hits]
    if ps:
        cats = Counter(p["category"] for p in ps)
        text = (f"{len(ps)} labeled posts match “{label}”, mostly in {', '.join(n.lower() for n, _ in cats.most_common(2))}. "
                f"Top example: {ps[0]['gist']}")
    else:
        text = f"No labeled posts match “{label}” in the cached data."
    return {"answer": text, "category": cat, "posts": [_post_brief(p) for p in ps[:25]], "mode": "offline"}
