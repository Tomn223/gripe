"""Thin Grok client over xAI's OpenAI-compatible REST API (https://api.x.ai/v1).

Uses httpx directly so tests can inject an httpx.MockTransport.
"""
import json
import re
import httpx


class LLMError(RuntimeError):
    pass


def extract_json(text: str):
    """Parse the first JSON object/array in a model reply (tolerates ```json fences / prose)."""
    if text is None:
        raise LLMError("empty model reply")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    for opener in ("{", "["):
        i = t.find(opener)
        if i >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(t[i:])
                return obj
            except json.JSONDecodeError:
                continue
    raise LLMError(f"could not parse JSON from model reply: {t[:200]!r}")


class GrokClient:
    def __init__(self, api_key: str, base_url: str = "https://api.x.ai/v1", transport=None, timeout=480.0):
        if not api_key:
            raise LLMError("XAI_API_KEY is not set")
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_in_usd_ticks": 0}

    def _add_usage(self, u):
        u = u or {}
        self.usage["prompt_tokens"] += u.get("prompt_tokens", u.get("input_tokens", 0)) or 0
        self.usage["completion_tokens"] += u.get("completion_tokens", u.get("output_tokens", 0)) or 0
        self.usage["cost_in_usd_ticks"] += u.get("cost_in_usd_ticks", 0) or 0

    def _post(self, path, payload):
        r = self.http.post(path, json=payload)
        self.usage["calls"] += 1
        if r.status_code >= 400:
            # never include request headers (key) in errors
            raise LLMError(f"xAI {path} HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        self._add_usage(data.get("usage"))
        return data

    def chat_json(self, model, system, user, temperature=0.2, max_tokens=None):
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        data = self._post("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"unexpected chat response shape: {str(data)[:200]}") from e
        return extract_json(content)

    def responses(self, model, prompt, tools, include=None):
        payload = {"model": model, "input": [{"role": "user", "content": prompt}], "tools": tools}
        if include:
            payload["include"] = include
        return self._post("/responses", payload)


    def responses_stream(self, model, prompt, tools, include=None, on_event=None):
        """Streamed Responses API call (SSE). Calls on_event(event_dict) for every event and returns the final
        response object from `response.completed`. Raises LLMError if the stream ends without one."""
        payload = {"model": model, "input": [{"role": "user", "content": prompt}], "tools": tools, "stream": True}
        if include:
            payload["include"] = include
        self.usage["calls"] += 1
        final = None
        with self.http.stream("POST", "/responses", json=payload) as r:
            if r.status_code >= 400:
                r.read()
                raise LLMError(f"xAI /responses (stream) HTTP {r.status_code}: {r.text[:300]}")
            for ev in iter_sse(r.iter_lines()):
                if ev.get("type") in ("response.completed", "response.done"):
                    final = ev.get("response")
                elif ev.get("type") in ("response.failed", "error"):
                    raise LLMError(f"xAI stream error: {str(ev)[:300]}")
                if on_event:
                    try:
                        on_event(ev)
                    except Exception:
                        pass  # progress reporting must never break the call
        if not isinstance(final, dict):
            raise LLMError("stream ended without response.completed")
        self._add_usage(final.get("usage"))
        return final


def iter_sse(lines):
    """Parse Server-Sent Events lines into JSON dicts (ignores comments, `event:` lines, [DONE], bad JSON)."""
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8", "replace")
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            ev = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            yield ev


def response_text_and_citations(resp: dict):
    """Collect output text and every cited URL from a Responses API payload."""
    texts, urls = [], set(resp.get("citations") or [])
    for item in resp.get("output") or []:
        if item.get("type") != "message":
            continue
        for c in item.get("content") or []:
            if c.get("type") == "output_text":
                texts.append(c.get("text") or "")
                for a in c.get("annotations") or []:
                    if a.get("url"):
                        urls.add(a["url"])
    if not texts and isinstance(resp.get("output_text"), str):
        texts.append(resp["output_text"])
    return "\n".join(texts), urls
