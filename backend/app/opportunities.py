"""Opportunity scoring (a transparent heuristic, not a forecast).

Per theme:
  Frequency   = share of genuine posts in the theme (normalized so the biggest theme = 1.0).
  Intensity   = deterministic signals from the post text + engagement:
                repeat failures, $ amounts, switching / "never again" language, and likes + reposts.
  Fixability  = Grok's judgment: product/design problem (a new entrant can fix it) vs structural
                (regulation, physics, user behavior, infrastructure).
Score (0-10) = 10 * (0.40 * frequency + 0.35 * intensity + 0.25 * fixability).
"""
import math
import re

WEIGHTS = {"frequency": 0.40, "intensity": 0.35, "fixability": 0.25}
FIX_VALUES = {"product": 1.0, "mixed": 0.6, "structural": 0.2, "unknown": 0.5}
MIN_POSTS = 3
MAX_ITEMS = 6

SIGNALS = {
    "repeat": re.compile(
        r"\b(again|twice|three times|\d+\s*(?:times|x)\b|(?:2nd|3rd|4th|second|third|fourth) (?:time|one|replacement)|"
        r"keeps? (?:breaking|failing|dying|happening|stopping|freezing|getting)|kept (?:breaking|failing|dying)|"
        r"every (?:time|year|few months)|over and over|multiple times|repeated(?:ly)?|another one|"
        r"(?:replaced|fixed|repaired) .{0,30}(?:twice|again|times))\b", re.I),
    "money": re.compile(r"(?:[$£€₹]\s?\d[\d,.]*\s?[kK]?|\b\d[\d,.]*\s?(?:dollars|bucks|rs\.?|rupees|usd|cad)\b|\bRs\.?\s?\d)", re.I),
    "switching": re.compile(
        r"\b(never (?:again|buy(?:ing)?|getting|purchas\w*)|won'?t (?:buy|be buying|get) (?:another|again|a)|"
        r"do not buy|don'?t buy|switch(?:ed|ing)? (?:to|back)|going back to|moved to|returned it|returning it|"
        r"sending it back|get(?:ting)? rid of|selling (?:it|my)|last \w+ i(?:'ll| will) ever|regret|refund)\b", re.I),
}
SIGNAL_LABELS = {"repeat": "repeat-failure language", "money": "dollar amounts",
                 "switching": "switching / 'never again' / return language"}


def post_signals(text):
    return {k: bool(rx.search(text or "")) for k, rx in SIGNALS.items()}


def _engagement(p):
    return (p.get("likes") or 0) + 2 * (p.get("reposts") or 0)


def _evidence_view(p):
    return {"id": p["id"], "url": p["url"], "username": p.get("username"), "gist": p.get("gist", ""),
            "text": (p.get("text") or "")[:280], "likes": p.get("likes") or 0, "reposts": p.get("reposts") or 0}


def theme_stats(posts):
    """Deterministic frequency + intensity per theme (excluding 'other' and tiny themes)."""
    total = max(1, len(posts))
    by = {}
    for p in posts:
        by.setdefault(p["category"], []).append(p)
    eng_all = [math.log1p(_engagement(p)) for p in posts] or [0]
    # engagement normalizer: 90th percentile of per-post log engagement across the market
    ref = sorted(eng_all)[int(0.9 * (len(eng_all) - 1))] or 1.0
    out = []
    for name, ps in by.items():
        if name == "other" or len(ps) < MIN_POSTS:
            continue
        sig = {k: 0 for k in SIGNALS}
        for p in ps:
            for k, v in post_signals(p.get("text")).items():
                sig[k] += v
        n = len(ps)
        any_sig = sum(1 for p in ps if any(post_signals(p.get("text")).values()))
        # text part: share of posts with >=1 signal, plus a bonus for each signal type that fires often
        text_part = min(1.0, any_sig / n + 0.15 * sum(1 for k in sig if sig[k] / n >= 0.2))
        eng_mean = sum(math.log1p(_engagement(p)) for p in ps) / n
        eng_part = min(1.0, eng_mean / ref)
        intensity = round(0.7 * text_part + 0.3 * eng_part, 3)
        out.append({"name": name, "count": n, "share": round(n / total, 3), "signals": sig,
                    "signal_posts": any_sig, "likes": sum(p.get("likes") or 0 for p in ps),
                    "reposts": sum(p.get("reposts") or 0 for p in ps), "engagement_score": round(eng_part, 3),
                    "intensity": intensity, "_posts": ps})
    mx = max([t["share"] for t in out] + [1e-9])
    for t in out:
        t["frequency"] = round(t["share"] / mx, 3)
    return out


def signal_summary(t):
    parts = []
    s = t["signals"]
    if s["money"]:
        parts.append(f"{s['money']} mention $ amounts")
    if s["repeat"]:
        parts.append(f"{s['repeat']} describe repeat failures")
    if s["switching"]:
        parts.append(f"{s['switching']} say never again / switching / returning")
    eng = f"{t['likes']:,} likes, {t['reposts']:,} reposts"
    return (", ".join(parts) + " · " if parts else "no strong-language signals · ") + eng


def build_opportunities(posts, judgments=None, source="heuristic"):
    """judgments: {theme_name: {fixability, fixability_reason, why_opening, evidence_ids}} (from Grok or hand-authored)."""
    judgments = {(k or "").lower(): v for k, v in (judgments or {}).items()}
    items = []
    for t in theme_stats(posts):
        j = judgments.get(t["name"].lower()) or {}
        fix = str(j.get("fixability") or "unknown").lower()
        if fix not in FIX_VALUES:
            fix = "unknown"
        ids = {p["id"]: p for p in t["_posts"]}
        ev = [ids[i] for i in (j.get("evidence_ids") or []) if i in ids][:2]
        if len(ev) < 2:  # fallback: most representative posts in the theme
            for p in sorted(t["_posts"], key=lambda p: -(p.get("representativeness") or 0)):
                if p not in ev:
                    ev.append(p)
                if len(ev) == 2:
                    break
        fx = FIX_VALUES[fix]
        score = 10 * (WEIGHTS["frequency"] * t["frequency"] + WEIGHTS["intensity"] * t["intensity"]
                      + WEIGHTS["fixability"] * fx)
        items.append({
            "theme": t["name"], "count": t["count"], "share": t["share"], "score": round(score, 1),
            "frequency": {"value": t["frequency"], "share": t["share"],
                          "reason": f"{t['count']} posts, {round(t['share'] * 100)}% of genuine posts"},
            "intensity": {"value": t["intensity"], "signals": t["signals"], "signal_posts": t["signal_posts"],
                          "likes": t["likes"], "reposts": t["reposts"], "reason": signal_summary(t)},
            "fixability": {"value": fx, "label": fix,
                           "reason": (j.get("fixability_reason") or "Not judged (no Grok call)").strip()[:200]},
            "why_opening": (j.get("why_opening") or "").strip()[:400],
            "evidence": [_evidence_view(p) for p in ev],
        })
    items.sort(key=lambda x: -x["score"])
    return {
        "heuristic": True,
        "judged_by": source,
        "rubric": {
            "formula": "score = 10 x (0.40 x frequency + 0.35 x intensity + 0.25 x fixability)",
            "frequency": "Share of genuine posts in the theme, scaled so the biggest theme = 1.0.",
            "intensity": "70% text signals (share of posts with repeat-failure, $ amount, or switching/'never again' "
                         "language, plus a bonus per signal type in 20%+ of posts) + 30% likes and reposts.",
            "fixability": "Grok's call: product/design problem = 1.0, mixed = 0.6, structural (regulation, physics, "
                          "behavior, infrastructure) = 0.2.",
            "min_posts": MIN_POSTS,
        },
        "items": items[:MAX_ITEMS],
    }


OPP_SYS = (
    "You assess pain-point themes from X posts for a founder deciding whether to enter a market. For each theme judge "
    "fixability: 'product' if a better-designed product or service from a new entrant could fix it (e.g. a more "
    "reliable ice maker), 'structural' if it comes from regulation, physics/running costs, infrastructure or user "
    "behavior that a product can't really change (e.g. cold fridges cost money to run), or 'mixed'. Ground everything "
    "in the posts given; no invented facts or statistics. Reply with JSON only.")


def judge_with_grok(grok, model, topic, posts):
    """One LLM call for all themes. Returns {theme: judgment} or {} on any failure."""
    import json
    themes = []
    for t in theme_stats(posts)[:10]:
        top = sorted(t["_posts"], key=lambda p: -(p.get("representativeness") or 0))[:6]
        themes.append({"theme": t["name"], "count": t["count"], "intensity_signals": signal_summary(t),
                       "posts": [{"id": p["id"], "text": (p.get("text") or "")[:240]} for p in top]})
    if not themes:
        return {}
    out = grok.chat_json(model, OPP_SYS,
        f"Market: {topic}\nThemes with sample posts:\n{json.dumps(themes, ensure_ascii=False)}\n"
        'Return {"themes":[{"theme":"<exact theme name>","fixability":"product|mixed|structural",'
        '"fixability_reason":"one line, max 20 words","why_opening":"1-2 sentences on why this is (or isn\'t) an '
        'opening for a new entrant, grounded in the posts","evidence_ids":["<post id>","<post id>"]}]}. '
        "Pick the 2 post ids that best evidence the opening, from that theme's posts only.")
    rows = out.get("themes", []) if isinstance(out, dict) else []
    valid = {t["theme"] for t in themes}
    res = {}
    for r in rows:
        if not isinstance(r, dict) or r.get("theme") not in valid:
            continue
        res[r["theme"]] = {"fixability": r.get("fixability"), "fixability_reason": str(r.get("fixability_reason") or ""),
                           "why_opening": str(r.get("why_opening") or ""),
                           "evidence_ids": [str(i) for i in (r.get("evidence_ids") or [])][:2]}
    return res
