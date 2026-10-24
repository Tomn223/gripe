"""Streaming (SSE) parsing and live progress, with a fake stream (no network)."""
import json
import httpx

from app.llm import GrokClient, iter_sse
from app.sources import XaiXSearchSource


def sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"


def test_iter_sse_skips_noise():
    lines = [": keepalive", "event: x", 'data: {"type":"a"}', "", "data: not-json", b'data: {"type":"b"}', "data: [DONE]"]
    assert [e["type"] for e in iter_sse(lines)] == ["a", "b"]


def test_streamed_search_reports_queries_and_counts():
    text = json.dumps({"posts": [
        {"url": "https://x.com/alice/status/1111111111", "username": "alice", "text": "air fryer broke", "likes": 3},
        {"url": "https://x.com/bob/status/2222222222", "username": "bob", "text": "air fryer too small", "likes": 1}]})
    final = {"output": [{"type": "message", "content": [{"type": "output_text", "text": text, "annotations": [
        {"type": "url_citation", "url": "https://x.com/i/status/1111111111"},
        {"type": "url_citation", "url": "https://x.com/i/status/2222222222"}]}]}],
        "usage": {"input_tokens": 10, "output_tokens": 5, "cost_in_usd_ticks": 123}}
    chunks = [text[i:i + 7] for i in range(0, len(text), 7)]
    events = ([{"type": "response.created"},
               {"type": "response.custom_tool_call_input.done", "input": json.dumps({"query": "air fryer broke"})},
               {"type": "response.custom_tool_call_input.done", "input": json.dumps({"query": "air fryer small"})}]
              + [{"type": "response.output_text.delta", "delta": c} for c in chunks]
              + [{"type": "response.completed", "response": final}])

    def handler(req):
        assert json.loads(req.content)["stream"] is True
        return httpx.Response(200, content=sse(events).encode(), headers={"content-type": "text/event-stream"})

    grok = GrokClient("k", transport=httpx.MockTransport(handler))
    seen = []
    src = XaiXSearchSource(grok, "m", calls=1)
    posts, stats = src.fetch("air fryers", ["q1"], 40, progress=lambda n, d, q=None: seen.append((n, d, q)))
    assert {p["id"] for p in posts} == {"1111111111", "2222222222"}
    counts = [n for n, _, _ in seen]
    assert counts == sorted(counts) and 1 in counts and counts[-1] == 2
    assert any(q and q[-1] == "air fryer small" for _, _, q in seen)
    assert grok.usage["cost_in_usd_ticks"] == 123


def test_stream_failure_falls_back_to_plain_call():
    final = {"output": [{"type": "message", "content": [{"type": "output_text", "text": '{"posts":[]}'}]}]}

    def handler(req):
        if json.loads(req.content).get("stream"):
            return httpx.Response(200, content=b"data: {\"type\":\"weird\"}\n\n")  # no response.completed
        return httpx.Response(200, json=final)

    grok = GrokClient("k", transport=httpx.MockTransport(handler))
    posts, _ = XaiXSearchSource(grok, "m", calls=1).fetch("air fryers", ["q1"], 40, progress=lambda *a: None)
    assert posts == [] and grok.usage["calls"] == 2
