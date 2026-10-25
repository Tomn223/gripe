import { useMemo, useState } from 'react'
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis, Area, AreaChart } from 'recharts'
import { api } from '../api'
import Logo from './Logo'
import PostsPanel from './PostsPanel'
import Opportunities from './Opportunities'

const SENT = [
  { key: 'negative', label: 'Negative', color: '#ff5a36' },
  { key: 'neutral', label: 'Neutral', color: '#8b93a7' },
  { key: 'positive', label: 'Positive', color: '#3ecf8e' },
]

function fmtDate(d) {
  return new Date(d + 'T00:00:00Z').toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function provenanceLine(result) {
  const p = result.provenance
  const live = p ? /live/i.test(p.method || '') : result.source?.startsWith('live')
  if (live) {
    const m = (p?.model || result.model?.label || '').split('-').slice(0, 2).join('-')
    return `Real X posts · labeled live by Grok${m ? ` (${m})` : ''}`
  }
  return 'Real X posts · labeled and grouped by Grok'
}

export default function Dashboard({ result, onHome, onSearch }) {
  const [panel, setPanel] = useState(null) // {title, subtitle, posts|category}
  const [dig, setDig] = useState(null) // {suggestion, loading, answer, error}
  const [q, setQ] = useState('')
  const cats = result.categories
  const chartData = useMemo(() => cats.map((c) => ({ ...c, label: c.name === 'other' ? 'Other' : c.name })), [cats])
  const total = result.stats.kept
  const sentTotal = SENT.reduce((a, s) => a + (result.sentiment[s.key] || 0), 0) || 1

  async function openCategory(name) {
    const c = cats.find((x) => x.name === name)
    setPanel({ title: c.name === 'other' ? 'Other' : c.name, subtitle: `${c.count} posts · most representative first`, loading: true, posts: [] })
    try {
      const r = await api.posts(result.topic, name)
      setPanel((p) => ({ ...p, loading: false, posts: r.posts }))
    } catch (e) {
      setPanel((p) => ({ ...p, loading: false, error: e.message }))
    }
  }

  async function runDig(s) {
    setDig({ suggestion: s, loading: true })
    try {
      const r = await api.dig(result.topic, s)
      setDig({ suggestion: s, loading: false, ...r })
    } catch (e) {
      setDig({ suggestion: s, loading: false, error: e.message })
    }
  }

  const vol = result.volume?.series || []

  return (
    <div className="dash">
      <header className="topbar">
        <button className="logo-btn" onClick={onHome} aria-label="New search">
          <Logo size={26} />
        </button>
        <form
          className="mini-search"
          onSubmit={(e) => {
            e.preventDefault()
            if (q.trim()) onSearch(q)
          }}
        >
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Try another market…" />
        </form>
      </header>

      <section className="hero-summary card">
        <div className="eyebrow">
          {result.topic} · {total} genuine posts from {result.stats.deduped} pulled
          {result.date_range && ` · ${fmtDate(result.date_range.from)} – ${fmtDate(result.date_range.to)}`}
        </div>
        <h1 className="headline">{result.summary.headline}</h1>
        <p className="summary-text">{result.summary.text}</p>
        <div className="pipeline-strip">
          <span><b>{result.stats.deduped}</b> unique posts pulled</span>
          <span className="arrow">→</span>
          <span><b>{result.stats.noise_dropped}</b> noise dropped</span>
          <span className="arrow">→</span>
          <span><b>{total}</b> labeled</span>
          <span className="arrow">→</span>
          <span><b>{cats.length}</b> themes</span>
        </div>
      </section>

      <div className="grid">
        <section className="card chart-card">
          <div className="card-head">
            <h3>Pain points, ranked</h3>
            <span className="hint">Click a bar to read the posts</span>
          </div>
          <ResponsiveContainer width="100%" height={Math.max(260, chartData.length * 44)}>
            <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 48, left: 8, bottom: 4 }} barCategoryGap={8}>
              <defs>
                <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#ff5a36" />
                  <stop offset="100%" stopColor="#ff8a3d" />
                </linearGradient>
              </defs>
              <XAxis type="number" hide />
              <YAxis
                type="category"
                dataKey="label"
                width={250}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#d7dbe6', fontSize: 13.5 }}
              />
              <Tooltip
                cursor={{ fill: 'rgba(255,255,255,0.04)' }}
                contentStyle={{ background: '#151924', border: '1px solid #2a3040', borderRadius: 10, color: '#e8ebf2' }}
                formatter={(v, _n, p) => [`${v} posts (${Math.round(p.payload.share * 100)}%)`, '']}
                labelStyle={{ color: '#fff', fontWeight: 600 }}
              />
              <Bar dataKey="count" radius={[0, 8, 8, 0]} onClick={(d) => openCategory(d.name)} style={{ cursor: 'pointer' }}>
                {chartData.map((c, i) => (
                  <Cell key={c.name} fill={c.name === 'other' ? '#3a4152' : 'url(#barGrad)'} fillOpacity={1 - i * 0.05} />
                ))}
                <LabelList dataKey="count" position="right" fill="#e8ebf2" fontSize={13} fontWeight={700} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </section>

        <aside className="side">
          <section className="card">
            <h3>Sentiment</h3>
            <div className="sent-bar">
              {SENT.map((s) => (
                <div
                  key={s.key}
                  style={{ width: `${((result.sentiment[s.key] || 0) / sentTotal) * 100}%`, background: s.color }}
                  title={`${s.label}: ${result.sentiment[s.key]}`}
                />
              ))}
            </div>
            <ul className="sent-legend">
              {SENT.map((s) => (
                <li key={s.key}>
                  <i style={{ background: s.color }} />
                  {s.label}
                  <b>{Math.round(((result.sentiment[s.key] || 0) / sentTotal) * 100)}%</b>
                  <span>{result.sentiment[s.key] || 0}</span>
                </li>
              ))}
            </ul>
          </section>

          {vol.length > 1 && (
            <section className="card">
              <h3>Mentions, last 7 days</h3>
              <ResponsiveContainer width="100%" height={70}>
                <AreaChart data={vol} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ff8a3d" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#ff8a3d" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    contentStyle={{ background: '#151924', border: '1px solid #2a3040', borderRadius: 8, color: '#e8ebf2' }}
                    labelFormatter={(_, p) => (p?.[0] ? fmtDate(p[0].payload.date) : '')}
                    formatter={(v) => [v.toLocaleString(), 'posts']}
                  />
                  <Area type="monotone" dataKey="count" stroke="#ff8a3d" strokeWidth={2} fill="url(#volGrad)" />
                </AreaChart>
              </ResponsiveContainer>
              <div className="vol-foot">
                {vol.slice(1, -1).reduce((a, b) => a + b.count, 0).toLocaleString()} posts in the last 6 full days
              </div>
            </section>
          )}

          {result.brands?.length > 0 && (
            <section className="card">
              <h3>Brands mentioned</h3>
              <div className="brand-list">
                {result.brands.slice(0, 6).map((b) => (
                  <span key={b.name} className="brand-pill">
                    {b.name} <b>{b.count}</b>
                  </span>
                ))}
              </div>
              <div className="fine">Reflects search terms, not market share.</div>
            </section>
          )}
        </aside>
      </div>

      <Opportunities result={result} onOpenPosts={openCategory} />

      <section className="card dig-card">
        <div className="card-head">
          <h3>Dig deeper</h3>
        </div>
        <div className="chips left">
          {result.dig_suggestions.map((s) => (
            <button
              key={s.label}
              className={`chip ${dig?.suggestion?.label === s.label ? 'active' : ''}`}
              onClick={() => runDig(s)}
            >
              {s.label}
            </button>
          ))}
        </div>
        {dig && (
          <div className="dig-answer">
            {dig.loading ? (
              <div className="shimmer">Thinking…</div>
            ) : dig.error ? (
              <div className="error">{dig.error}</div>
            ) : (
              <>
                <p>{dig.answer}</p>
                {dig.brands?.length > 0 && (
                  <div className="brand-list">
                    {dig.brands.map((b) => (
                      <span key={b.name} className="brand-pill">
                        {b.name} <b>{b.count}</b>
                      </span>
                    ))}
                  </div>
                )}
                {dig.posts?.length > 0 && (
                  <button
                    className="link"
                    onClick={() =>
                      setPanel({ title: dig.suggestion.label, subtitle: `${dig.posts.length} matching posts`, posts: dig.posts })
                    }
                  >
                    See the {dig.posts.length} posts behind this →
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </section>

      <section className="track-card">
        <div>
          <div className="track-title">Track this market with Mika, our GrokBot</div>
          <div className="track-sub">
            Opens a GitHub issue for this market. Every week Mika re-searches X, ranks the gripes, flags anything new or spiking, and posts the update on the issue. Click Subscribe on the issue to get the updates by email.
          </div>
        </div>
        <a
          className="track-btn"
          target="_blank"
          rel="noopener noreferrer"
          href={`https://github.com/Tomn223/gripe/issues/new?title=${encodeURIComponent('Track: ' + (result.topic || ''))}&body=${encodeURIComponent('Please track the "' + (result.topic || '') + '" market and post weekly gripe updates here.\n\n(Mika, our GrokBot, picks up open issues titled "Track: <market>" every Monday.)')}`}
        >
          Track weekly ↗
        </a>
      </section>

      <details className="how-grok">
        <summary>How Grok powers this</summary>
        <ol>
          <li><b>x_search</b>: Grok searches X for real posts about the market</li>
          <li><b>Relevance filter</b>: Grok drops ads, jokes, news, and off-topic posts</li>
          <li><b>Per-post labeling</b>: sentiment, pain point, brand, and a one-line gist for every post</li>
          <li><b>Theme grouping</b>: Grok clusters pain points into ranked themes</li>
          <li><b>Summary and dig-deeper chips</b>: the headline and follow-up questions</li>
          <li><b>Opportunity judging</b>: fixability and why each theme is an opening</li>
        </ol>
      </details>

      <footer className="foot">
        {provenanceLine(result)} · every post links to x.com
      </footer>

      {panel && <PostsPanel panel={panel} onClose={() => setPanel(null)} />}
    </div>
  )
}
