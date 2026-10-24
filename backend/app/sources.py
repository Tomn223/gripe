"""Pluggable live data sources for X posts.

- XaiXSearchSource: xAI Responses API + Grok's built-in `x_search` tool (default).
  Every returned post must match a status id in the response citations, so Grok cannot
  invent posts: anything not backed by a tool citation is dropped.
- XApiV2Source: official X API v2 recent search (+ counts) with a bearer token.
"""
import datetime as dt
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

from .llm import GrokClient, extract_json, response_text_and_citations

STATUS_RE = re.compile(r"(?:x|twitter)\.com/(?:i/(?:web/)?status|([A-Za-z0-9_]{1,15})/status)/(\d+)")

COMPLAINT_TERMS = ["broken", "broke", "hate", "wish", "problem", "returned", "worst", "stopped working",
                   "regret", "annoying", "disappointed", "customer service", "warranty", "useless"]


def topic_variants(topic):
    t = topic.strip().lower()
    out = [t]
    if t.endswith("ies"):
        out.append(t[:-3] + "y")
    elif t.endswith("s") and not t.endswith("ss"):
        out.append(t[:-1])
    if "-" in t:
        out += [v.replace("-", "") for v in out]
    return list(dict.fromkeys(out))


def topic_terms(topic):
    """Lowercase substrings used to check a post actually mentions the topic."""
    terms = set()
    for v in topic_variants(topic):
        terms.add(v)
        if " " in v:
            terms.add(v.split()[-1])  # 'standing desk' -> 'desk'
    return sorted(terms)


def build_queries(topic, n_groups=4):
    """Brand-neutral complaint-oriented X query variants (X search syntax)."""
    vs = topic_variants(topic)
    subj = "(" + " OR ".join(f'"{v}"' for v in vs) + ")" if len(vs) > 1 else f'"{vs[0]}"'
    groups = [COMPLAINT_TERMS[i::n_groups] for i in range(n_groups)]
    qs = []
    for g in groups:
        terms = " OR ".join(f'"{x}"' if " " in x else x for x in g)
        qs.append(f"{subj} ({terms}) -is:retweet lang:en")
    return qs


def parse_status_url(url):
    m = STATUS_RE.search(url or "")
    if not m:
        return None, None
    return m.group(2), m.group(1)


class XaiXSearchSource:
    name = "xai_x_search"

    def __init__(self, client: GrokClient, model: str, calls: int = 3, lookback_days: int = 30, today=None):
        self.client, self.model, self.calls, self.lookback = client, model, max(1, calls), lookback_days
        self.today = today or dt.date.today()

    def _prompt(self, topic, queries, per_call):
        qs = "\n".join(f"- {q}" for q in queries)
        return (
            f"You are a data collector for a market-research tool. Use the x_search tool to find up to {per_call} "
            f"distinct, recent, English X posts in which ordinary people complain about, criticize, or describe "
            f"problems, frustrations or unmet wishes with {topic}. Run keyword searches such as:\n{qs}\n"
            "Prefer first-hand experiences from real users. Skip ads, deal bots, giveaways, news headlines and "
            "brand marketing accounts. Do not repeat the same author more than twice.\n"
            "Return ONLY a JSON object, no prose, of the form:\n"
            '{"posts":[{"url":"https://x.com/<handle>/status/<id>","username":"<handle>","created_at":"YYYY-MM-DDTHH:MM:SSZ",'
            '"text":"<the post text, verbatim>","likes":<int or null>,"reposts":<int or null>}]}\n'
            "Only include posts you actually retrieved with the tool in this session, copy the text exactly, and never "
            "invent posts, URLs, or numbers."
        )

    def _one(self, topic, queries, per_call):
        tool = {"type": "x_search",
                "from_date": (self.today - dt.timedelta(days=self.lookback)).isoformat(),
                "to_date": (self.today + dt.timedelta(days=1)).isoformat()}
        resp = self.client.responses(self.model, self._prompt(topic, queries, per_call), [tool],
                                     include=["no_inline_citations"])
        text, cited = response_text_and_citations(resp)
        cited_ids = {parse_status_url(u)[0] for u in cited} - {None}
        try:
            data = extract_json(text)
        except Exception:
            data = {"posts": []}
        rows = data.get("posts", []) if isinstance(data, dict) else data
        out, unverified = [], 0
        for r in rows or []:
            pid, handle = parse_status_url(r.get("url", ""))
            if not pid:
                continue
            if pid not in cited_ids:
                unverified += 1
                continue  # not backed by a tool citation -> could be hallucinated; drop
            user = r.get("username") or handle or "i"
            out.append({
                "id": pid, "username": user.lstrip("@"),
                "url": f"https://x.com/{user.lstrip('@')}/status/{pid}",
                "created_at": r.get("created_at"), "text": r.get("text") or "",
                "likes": r.get("likes") if isinstance(r.get("likes"), int) else 0,
                "reposts": r.get("reposts") if isinstance(r.get("reposts"), int) else 0,
                "query": " | ".join(queries), "verified_by_citation": True,
            })
        return out, unverified

    def fetch(self, topic, queries, max_posts=200, progress=None):
        n = self.calls
        groups = [queries[i::n] for i in range(n)]
        groups = [g for g in groups if g]
        per_call = max(15, min(50, max_posts // max(1, len(groups))))
        posts, unverified, errors = [], 0, []
        if progress:
            progress(0, f"Grok is searching X (0/{len(groups)} searches done, usually 1-4 min)")
        with ThreadPoolExecutor(max_workers=len(groups)) as ex:
            futs = [ex.submit(self._one, topic, g, per_call) for g in groups]
            done = 0
            for f in as_completed(futs):
                done += 1
                try:
                    got, unv = f.result()
                    posts += got
                    unverified += unv
                except Exception as e:  # one slow/failed search shouldn't sink the whole run
                    errors.append(str(e)[:200])
                if progress:
                    progress(len(posts), f"Grok is searching X ({done}/{len(groups)} searches done)")
        if errors and not posts:
            raise RuntimeError("all X searches failed: " + errors[0])
        return posts, {"unverified_dropped": unverified, "search_calls": len(groups), "search_errors": errors}

    def volume(self, topic):
        return None


class XApiV2Source:
    name = "x_api_v2"
    BASE = "https://api.x.com/2"

    def __init__(self, bearer: str, transport=None, per_query=100):
        self.http = httpx.Client(base_url=self.BASE, headers={"Authorization": f"Bearer {bearer}"},
                                 timeout=30, transport=transport)
        self.per_query = per_query

    def _search(self, q):
        r = self.http.get("/tweets/search/recent", params={
            "query": q, "max_results": min(100, self.per_query),
            "tweet.fields": "created_at,public_metrics,author_id,lang",
            "expansions": "author_id", "user.fields": "username"})
        if r.status_code >= 400:
            raise RuntimeError(f"X API HTTP {r.status_code}: {r.text[:200]}")
        d = r.json()
        users = {u["id"]: u["username"] for u in d.get("includes", {}).get("users", [])}
        out = []
        for t in d.get("data", []) or []:
            u = users.get(t.get("author_id"), "i")
            pm = t.get("public_metrics") or {}
            out.append({"id": t["id"], "username": u, "url": f"https://x.com/{u}/status/{t['id']}",
                        "created_at": t.get("created_at"), "text": t.get("text", ""),
                        "likes": pm.get("like_count", 0), "reposts": pm.get("retweet_count", 0),
                        "author_id": t.get("author_id"), "query": q})
        return out

    def fetch(self, topic, queries, max_posts=200, progress=None):
        posts = []
        for i, q in enumerate(queries):
            posts += self._search(q)
            if progress:
                progress(len(posts), f"query {i + 1}/{len(queries)}")
            if len(posts) >= max_posts * 2:
                break
        return posts, {"search_calls": len(queries)}

    def volume(self, topic):
        vs = topic_variants(topic)
        q = "(" + " OR ".join(f'"{v}"' for v in vs) + ") -is:retweet lang:en"
        r = self.http.get("/tweets/counts/recent", params={"query": q, "granularity": "day"})
        if r.status_code >= 400:
            return None
        series = [{"date": b["start"][:10], "count": b["tweet_count"]} for b in r.json().get("data", [])]
        return {"query": q, "granularity": "day", "series": series}
