"""Builds the cached analysis document from labeled posts (shared by live pipeline and seed scripts)."""
import datetime as dt
import math
import re
from collections import Counter, defaultdict

SCHEMA_VERSION = 1
SENTIMENTS = ("negative", "neutral", "positive")
WISH_RE = re.compile(r"\b(i wish|wish (it|they|there|my|i)|should (have|be|make)|why (do|does|can't|won't|is|are)|"
                     r"if only|would love|need(s)? (a|an|to)|want(ed)? (a|an)|someone (should|needs to)|"
                     r"please (make|add|fix)|looking for|recommendations?|any tips|does anyone know)\b", re.I)


def finalize_representativeness(posts):
    """Blend the labeler's representativeness (0-1) with engagement so strong, liked examples rank first."""
    max_likes = max([p.get("likes") or 0 for p in posts] + [1])
    for p in posts:
        llm = float(p.get("rep_llm", 0.5))
        eng = math.log1p(p.get("likes") or 0) / math.log1p(max_likes)
        neg = 1.0 if p.get("sentiment") == "negative" else 0.0
        p["representativeness"] = round(0.65 * llm + 0.25 * eng + 0.10 * neg, 3)
        p.pop("rep_llm", None)
    return posts


def detect_wish(p):
    """Labelers set 'wish' (possibly ''); only unlabeled posts fall back to a regex."""
    if "wish" in p:
        return p["wish"] or ""
    return p["gist"] if WISH_RE.search(p.get("text", "")) else ""


def build_document(topic, posts, category_meta, summary, dig_suggestions, stats, *, source, model=None,
                   queries=None, volume=None, notes=None, generated_at=None):
    """posts: labeled posts with keys id,url,username,created_at,text,likes,reposts,sentiment,category,brand,gist,
    representativeness[,wish]. category_meta: {name: description}."""
    for p in posts:
        p["wish"] = detect_wish(p)
        p["brand"] = p.get("brand") or "none"
    counts = Counter(p["category"] for p in posts)
    total = max(1, len(posts))
    cats = []
    by_cat = defaultdict(list)
    for p in posts:
        by_cat[p["category"]].append(p)
    order = sorted(counts, key=lambda c: (c == "other", -counts[c], c))
    for name in order:
        ps = by_cat[name]
        s = Counter(p["sentiment"] for p in ps)
        b = Counter(p["brand"] for p in ps if p["brand"] != "none")
        top = sorted(ps, key=lambda p: -p["representativeness"])[:3]
        cats.append({
            "name": name, "count": counts[name], "share": round(counts[name] / total, 3),
            "description": category_meta.get(name, ""),
            "sentiment": {k: s.get(k, 0) for k in SENTIMENTS},
            "top_brands": [{"name": n, "count": c} for n, c in b.most_common(5)],
            "example_gists": [p["gist"] for p in top],
        })
    sent = Counter(p["sentiment"] for p in posts)
    brands = Counter(p["brand"] for p in posts if p["brand"] != "none")
    posts_sorted = sorted(posts, key=lambda p: -p["representativeness"])
    return {
        "schema_version": SCHEMA_VERSION,
        "topic": topic,
        "generated_at": generated_at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "model": model,
        "queries": queries or [],
        "stats": {**stats, "kept": len(posts)},
        "summary": summary,
        "categories": cats,
        "sentiment": {k: sent.get(k, 0) for k in SENTIMENTS},
        "brands": [{"name": n, "count": c} for n, c in brands.most_common(12)],
        "volume": volume,
        "dig_suggestions": dig_suggestions,
        "notes": notes or [],
        "posts": posts_sorted,
    }


def public_view(doc):
    """Dashboard payload: everything except the full post list (served by /posts)."""
    d = {k: v for k, v in doc.items() if k != "posts"}
    d["date_range"] = date_range(doc["posts"])
    return d


def date_range(posts):
    ds = sorted(p["created_at"][:10] for p in posts if p.get("created_at"))
    return {"from": ds[0], "to": ds[-1]} if ds else None
