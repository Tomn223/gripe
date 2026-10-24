import { useState } from 'react'

const FIX = {
  product: { label: 'Product / design', cls: 'fix-product' },
  mixed: { label: 'Mixed', cls: 'fix-mixed' },
  structural: { label: 'Structural', cls: 'fix-structural' },
  unknown: { label: 'Not judged', cls: 'fix-mixed' },
}

function Bar({ label, value, note }) {
  return (
    <div className="opp-sub">
      <div className="opp-sub-head">
        <span>{label}</span>
        <b>{Math.round(value * 10)}/10</b>
      </div>
      <div className="opp-track">
        <div style={{ width: `${Math.max(3, value * 100)}%` }} />
      </div>
      <div className="opp-note">{note}</div>
    </div>
  )
}

function grokPrompt(result, items) {
  const top = items.slice(0, 3)
  const lines = top.map(
    (o, i) =>
      `${i + 1}. ${o.theme} (score ${o.score}/10; ${o.count} of ${result.stats.kept} posts; fixability: ${o.fixability.label}). ${o.why_opening}`,
  )
  let p =
    `I'm exploring entering the ${result.topic} market. An analysis of ${result.stats.kept} genuine X complaints found these top opportunities ` +
    `(heuristic score = frequency + intensity + fixability):\n${lines.join('\n')}\n\n` +
    `Help me explore these: search X for more recent evidence, who is already solving each one, what a minimum viable product could look like, ` +
    `and which opportunity you'd pursue first and why.`
  return p.slice(0, 1500)
}

export default function Opportunities({ result, onOpenPosts }) {
  const [toast, setToast] = useState('')
  const [showRubric, setShowRubric] = useState(false)
  const opp = result.opportunities
  if (!opp?.items?.length) return null
  const prompt = grokPrompt(result, opp.items)
  const href = `https://grok.com/?q=${encodeURIComponent(prompt)}`

  function onGrok() {
    navigator.clipboard?.writeText(prompt).then(
      () => {
        setToast('Prompt copied too, paste it if Grok opens empty')
        setTimeout(() => setToast(''), 3500)
      },
      () => {},
    )
  }

  return (
    <section className="card opp-card">
      <div className="card-head">
        <h3>Opportunities · score is a heuristic</h3>
        <button className="link" onClick={() => setShowRubric((v) => !v)}>
          {showRubric ? 'Hide' : 'How this is scored'}
        </button>
      </div>
      {showRubric && (
        <div className="opp-rubric">
          <div><b>{opp.rubric.formula}</b></div>
          <div><b>Frequency:</b> {opp.rubric.frequency}</div>
          <div><b>Intensity:</b> {opp.rubric.intensity}</div>
          <div><b>Fixability:</b> {opp.rubric.fixability}</div>
          <div className="hint">
            Themes with at least {opp.rubric.min_posts} posts. Fixability and "why an opening" judged by: {opp.judged_by}. A ranking aid, not a market forecast.
          </div>
        </div>
      )}
      <ol className="opp-list">
        {opp.items.map((o, i) => {
          const fx = FIX[o.fixability.label] || FIX.unknown
          return (
            <li key={o.theme} className="opp">
              <div className="opp-top">
                <div className="opp-rank">{i + 1}</div>
                <div className="opp-title">
                  <button className="opp-theme" onClick={() => onOpenPosts(o.theme)}>{o.theme}</button>
                  <span className={`fix-pill ${fx.cls}`}>{fx.label}</span>
                </div>
                <div className="opp-score">
                  {o.score}
                  <span>/10</span>
                </div>
              </div>
              {o.why_opening && <p className="opp-why">{o.why_opening}</p>}
              <div className="opp-subs">
                <Bar label="Frequency" value={o.frequency.value} note={o.frequency.reason} />
                <Bar label="Intensity" value={o.intensity.value} note={o.intensity.reason} />
                <Bar label="Fixability" value={o.fixability.value} note={o.fixability.reason} />
              </div>
              <div className="opp-evidence">
                {o.evidence.map((e) => (
                  <a key={e.id} href={e.url} target="_blank" rel="noopener noreferrer" className="opp-ev">
                    <span>“{e.gist || e.text.slice(0, 120)}”</span>
                    <small>@{e.username} · ♥ {e.likes} ↗</small>
                  </a>
                ))}
              </div>
            </li>
          )
        })}
      </ol>
      <div className="grok-callout">
        <div>
          <b>Explore these opportunities with Grok</b>
          <div className="hint">Opens Grok in a new tab with the top 3 opportunities and their scores pre-filled.</div>
        </div>
        <a className="grok-btn" href={href} target="_blank" rel="noopener noreferrer" onClick={onGrok}>
          Open in Grok ↗
        </a>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </section>
  )
}
