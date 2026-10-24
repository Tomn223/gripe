const BASE = import.meta.env.VITE_API_BASE || '/api'

async function req(path, opts) {
  const r = await fetch(BASE + path, opts)
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail || `Request failed (${r.status})`)
  return body
}

export const api = {
  analyze: (topic) => req(`/analyze?topic=${encodeURIComponent(topic)}`),
  job: (id) => req(`/jobs/${id}`),
  posts: (topic, category) =>
    req(`/posts?topic=${encodeURIComponent(topic)}&category=${encodeURIComponent(category)}&limit=60`),
  dig: (topic, suggestion) =>
    req('/dig', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ topic, suggestion }) }),
  health: () => req('/health'),
}
