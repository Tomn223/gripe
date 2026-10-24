"""Live pipeline: pull -> filter noise -> label -> group into themes -> summarize."""
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .analysis import build_document, finalize_representativeness
from .noise import heuristic_filter
from .sources import build_queries, topic_terms

STAGES = [
    ("pull", "Pulling posts from X"),
    ("filter", "Filtering noise"),
    ("label", "Labeling posts with Grok"),
    ("group", "Grouping into themes"),
    ("summary", "Writing summary"),
]

RELEVANCE_SYS = (
    "You screen X posts for a market-research tool about a product category. Mark a post as noise if it is an ad, "
    "deal/affiliate post, brand or repair-shop marketing, news headline, content-farm/engagement bait, a joke or meme "
    "that says nothing about using the product, or off-topic (the product word is used in another sense). Keep genuine "
    "first-hand experiences, complaints, frustrations, questions, wishes or opinions from users. Reply with JSON only.")

LABEL_SYS = (
    "You label X posts about a product category for would-be market entrants. For each post return: sentiment "
    "(negative|neutral|positive, toward the product/experience), pain_point (a short 2-5 word noun phrase naming the "
    "specific problem, e.g. 'ice maker failure'; use 'none' if no problem), brand (brand/product named, else 'none'), "
    "gist (one plain-English line, max 16 words, faithful to the post), representativeness (0-1: how clearly this post "
    "illustrates a common, concrete pain point), wish (the unmet need or desired product the author expresses, max 12 "
    "words, or ''). Reply with JSON only.")

GROUP_SYS = (
    "You group short pain-point phrases from product complaints into 6-10 clear, mutually exclusive categories for a "
    "bar chart, plus 'other'. Category names: 2-5 words, Title-like sentence case, specific (e.g. 'Ice maker & water "
    "dispenser'), never brand names. Every input phrase must be assigned to exactly one category. Reply with JSON only.")

SUMMARY_SYS = (
    "You write for a founder deciding whether to enter a market. Be concrete, cite counts, no hype. Reply JSON only.")


class StageReporter:
    def __init__(self, cb=None):
        self.cb = cb or (lambda *_: None)
        self.stages = [{"key": k, "label": l, "status": "pending", "count": None, "detail": ""} for k, l in STAGES]

    def update(self, key, status=None, count=None, detail=None, queries=None):
        for s in self.stages:
            if s["key"] == key:
                if status:
                    s["status"] = status
                if count is not None:
                    s["count"] = count
                if detail is not None:
                    s["detail"] = detail
                if queries is not None:
                    s["queries"] = list(queries)
        self.cb(self.stages)


def _batches(xs, n):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


class Pipeline:
    def __init__(self, settings, grok, source):
        self.s, self.grok, self.source = settings, grok, source

    # ---- stage helpers -------------------------------------------------
    def relevance(self, topic, posts, reporter):
        dropped = {}
        def run(batch):
            items = [{"i": i, "text": p["text"][:500], "author": p.get("username")} for i, p in batch]
            out = self.grok.chat_json(self.s.label_model, RELEVANCE_SYS,
                f"Product category: {topic}\nPosts:\n{json.dumps(items, ensure_ascii=False)}\n"
                'Return {"noise":[{"i":<int>,"reason":"ad|deal|marketing|news|joke|off-topic|not user experience"}]} '
                "listing ONLY the noise posts.")
            return out.get("noise", []) if isinstance(out, dict) else []
        indexed = list(enumerate(posts))
        with ThreadPoolExecutor(max_workers=4) as ex:
            for res in ex.map(run, _batches(indexed, 40)):
                for r in res:
                    try:
                        dropped[int(r["i"])] = r.get("reason", "llm: not relevant")
                    except (KeyError, ValueError, TypeError):
                        continue
        kept = [p for i, p in indexed if i not in dropped]
        reasons = Counter(f"llm: {v}" for v in dropped.values())
        return kept, reasons

    def label(self, topic, posts, reporter):
        n = len(posts)
        done = [0]
        labels = {}
        def run(batch):
            items = [{"i": i, "text": p["text"][:600]} for i, p in batch]
            out = self.grok.chat_json(self.s.label_model, LABEL_SYS,
                f"Product category: {topic}\nPosts:\n{json.dumps(items, ensure_ascii=False)}\n"
                'Return {"labels":[{"i":0,"sentiment":"negative","pain_point":"...","brand":"none","gist":"...",'
                '"representativeness":0.7,"wish":""}]} with one entry per post.')
            return out.get("labels", []) if isinstance(out, dict) else []
        indexed = list(enumerate(posts))
        with ThreadPoolExecutor(max_workers=4) as ex:
            for batch, res in zip(_batches(indexed, self.s.label_batch),
                                  ex.map(run, _batches(indexed, self.s.label_batch))):
                for r in res:
                    try:
                        labels[int(r["i"])] = r
                    except (KeyError, ValueError, TypeError):
                        continue
                done[0] += len(batch)
                reporter.update("label", count=done[0], detail=f"{done[0]}/{n} posts labeled")
        out = []
        for i, p in indexed:
            r = labels.get(i)
            if not r:
                continue
            sent = r.get("sentiment") if r.get("sentiment") in ("negative", "neutral", "positive") else "neutral"
            try:
                rep = max(0.0, min(1.0, float(r.get("representativeness", 0.5))))
            except (TypeError, ValueError):
                rep = 0.5
            out.append({**p, "sentiment": sent, "pain_point": (r.get("pain_point") or "none").strip().lower(),
                        "brand": (r.get("brand") or "none").strip() or "none",
                        "gist": (r.get("gist") or p["text"][:100]).strip(), "rep_llm": rep,
                        "wish": (r.get("wish") or "").strip()})
        return out

    def group(self, topic, posts):
        phrases = Counter(p["pain_point"] for p in posts)
        listing = [{"phrase": ph, "count": c} for ph, c in phrases.most_common()]
        out = self.grok.chat_json(self.s.label_model, GROUP_SYS,
            f"Product category: {topic}\nPain-point phrases with post counts:\n{json.dumps(listing, ensure_ascii=False)}\n"
            'Return {"categories":[{"name":"...","description":"one line","members":["phrase", ...]}]} '
            "with 6-10 categories plus an 'other' category if needed.")
        cats = out.get("categories", []) if isinstance(out, dict) else []
        mapping, meta = {}, {}
        for c in cats:
            name = (c.get("name") or "").strip()
            if not name:
                continue
            if name.lower() == "other":
                name = "other"
            meta[name] = c.get("description", "")
            for m in c.get("members", []) or []:
                mapping[str(m).strip().lower()] = name
        for p in posts:
            p["category"] = mapping.get(p["pain_point"], "other")
        return posts, meta

    def summarize(self, topic, doc_stub):
        cats = [{"name": c["name"], "count": c["count"], "examples": c["example_gists"][:2]}
                for c in doc_stub["categories"]]
        out = self.grok.chat_json(self.s.label_model, SUMMARY_SYS,
            f"Market: {topic}\nKept posts: {doc_stub['stats']['kept']}\nSentiment: {json.dumps(doc_stub['sentiment'])}\n"
            f"Top brands: {json.dumps(doc_stub['brands'][:6])}\nCategories (ranked): {json.dumps(cats, ensure_ascii=False)}\n"
            'Return {"headline":"Top frustrations with <market>: a, b, c.","summary":"2-3 sentences with counts and '
            'what it means for a new entrant","dig_suggestions":[{"label":"Filter to <category> complaints",'
            '"kind":"filter_category","category":"<exact category name>"},{"label":"Which brands come up most in '
            '<category>?","kind":"brands","category":"<exact category name>"},{"label":"What do people wish existed?",'
            '"kind":"wishes"},{"label":"<one more specific question>","kind":"query"}]}. Use exact category names.')
        return out if isinstance(out, dict) else {}

    # ---- main ---------------------------------------------------------
    def run(self, topic, progress=None):
        t0 = time.time()
        rep = StageReporter(progress)
        queries = build_queries(topic)

        rep.update("pull", "running", 0, "searching X")
        raw, src_stats = self.source.fetch(topic, queries, self.s.max_posts,
                                           progress=lambda n, d, q=None: rep.update("pull", count=n, detail=d, queries=q))
        seen, deduped = set(), []
        for p in raw:
            if p["id"] not in seen:
                seen.add(p["id"])
                deduped.append(p)
        rep.update("pull", "done", len(deduped), f"{len(raw)} fetched, {len(deduped)} unique")
        if not deduped:
            raise RuntimeError("No posts were returned for this topic. Try a broader market name.")

        rep.update("filter", "running", len(deduped), "heuristics: ads, promo links, repeat posters")
        kept, dropped = heuristic_filter(deduped, topic_terms(topic))
        reasons = Counter(d["noise_reason"] for d in dropped)
        rep.update("filter", detail=f"{len(dropped)} dropped by heuristics, Grok relevance check on {len(kept)}")
        kept, llm_reasons = self.relevance(topic, kept, rep)
        reasons.update(llm_reasons)
        kept = kept[: self.s.max_posts]
        rep.update("filter", "done", len(kept), f"kept {len(kept)} of {len(deduped)}")
        if not kept:
            raise RuntimeError("Every post was filtered as noise. Try a different market name.")

        rep.update("label", "running", 0, f"0/{len(kept)} posts labeled")
        labeled = self.label(topic, kept, rep)
        rep.update("label", "done", len(labeled), f"{len(labeled)} posts labeled")

        rep.update("group", "running", None, "clustering pain points")
        labeled, meta = self.group(topic, labeled)
        finalize_representativeness(labeled)
        for p in labeled:
            p.pop("author_id", None)
        stats = {"raw": len(raw), "deduped": len(deduped), "noise_dropped": len(deduped) - len(kept),
                 "noise_reasons": dict(reasons), **src_stats}
        stub = build_document(topic, labeled, meta, {}, [], stats, source=self.source.name)
        rep.update("group", "done", len(stub["categories"]), f"{len(stub['categories'])} themes")

        rep.update("summary", "running", None, "Grok is writing the headline")
        summ = self.summarize(topic, stub)
        volume = None
        try:
            volume = self.source.volume(topic)
        except Exception:
            volume = None
        names = {c["name"] for c in stub["categories"]}
        digs = [d for d in summ.get("dig_suggestions", []) if isinstance(d, dict) and d.get("label")]
        for d in digs:
            if d.get("category") and d["category"] not in names:
                d.pop("category")
        if not digs and stub["categories"]:
            top = stub["categories"][0]["name"]
            digs = [{"label": f"Filter to {top.lower()} complaints", "kind": "filter_category", "category": top},
                    {"label": f"Which brands come up most in {top.lower()}?", "kind": "brands", "category": top},
                    {"label": "What do people wish existed?", "kind": "wishes"}]
        stats["elapsed_s"] = round(time.time() - t0, 1)
        stats["llm_usage"] = dict(self.grok.usage)
        doc = build_document(topic, labeled, meta,
                             {"headline": summ.get("headline", ""), "text": summ.get("summary", "")},
                             digs[:4], stats, source=f"live:{self.source.name}",
                             model={"search": self.s.search_model, "label": self.s.label_model},
                             queries=queries, volume=volume)
        judged = {}
        try:  # one extra Grok call: fixability + why-an-opening + evidence ids for every theme
            from .opportunities import judge_with_grok
            judged = judge_with_grok(self.grok, self.s.label_model, topic, labeled)
        except Exception:
            judged = {}
        from .opportunities import build_opportunities
        doc["opportunities"] = build_opportunities(doc["posts"], judged, source="grok" if judged else "heuristic")
        doc["stats"]["llm_usage"] = dict(self.grok.usage)
        rep.update("summary", "done", None, "done")
        return doc
