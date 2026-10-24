import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import Landing from './components/Landing'
import Loading from './components/Loading'
import Dashboard from './components/Dashboard'

const EXAMPLES = ['refrigerators', 'standing desks', 'e-bikes']

function stagesFromResult(r) {
  const s = r.stats
  return [
    { key: 'pull', label: 'Pulling posts from X', count: s.raw, detail: `${s.raw} posts pulled, ${s.deduped} unique` },
    { key: 'filter', label: 'Filtering noise', count: s.kept, detail: `dropped ${s.noise_dropped} ads, promos & jokes` },
    { key: 'label', label: `Labeling ${s.kept} posts${r.source?.startsWith('live') ? ' with Grok' : ''}`, count: s.kept, detail: 'sentiment · pain point · brand · gist' },
    { key: 'group', label: 'Grouping into themes', count: r.categories.length, detail: `${r.categories.length} pain-point themes` },
    { key: 'summary', label: 'Writing summary', count: null, detail: 'headline + dig-deeper ideas' },
  ]
}

export default function App() {
  const [view, setView] = useState('landing') // landing | loading | dashboard
  const [topic, setTopic] = useState('')
  const [stages, setStages] = useState([])
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const runId = useRef(0)

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q')
    if (q) start(q)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function start(t) {
    const id = ++runId.current
    const clean = t.trim()
    if (!clean) return
    setTopic(clean)
    setError('')
    setResult(null)
    setStages([])
    setView('loading')
    window.history.replaceState(null, '', `?q=${encodeURIComponent(clean)}`)
    try {
      const res = await api.analyze(clean)
      if (id !== runId.current) return
      if (res.status === 'done') {
        // Cached topic: short animated replay of the real pipeline stages (~2.5s).
        const full = stagesFromResult(res.result)
        for (let i = 0; i <= full.length; i++) {
          if (id !== runId.current) return
          setStages(full.map((s, j) => ({ ...s, status: j < i ? 'done' : j === i ? 'running' : 'pending' })))
          await new Promise((r) => setTimeout(r, 480))
        }
        setResult(res.result)
        setTopic(res.result.topic)
        setView('dashboard')
        return
      }
      // Live job: poll real stage progress.
      setStages(res.stages || [])
      for (;;) {
        await new Promise((r) => setTimeout(r, 900))
        if (id !== runId.current) return
        const j = await api.job(res.job_id)
        setStages(j.stages || [])
        if (j.status === 'done') {
          setResult(j.result)
          setTopic(j.result.topic)
          setView('dashboard')
          return
        }
        if (j.status === 'error') throw new Error(j.error || 'Analysis failed')
      }
    } catch (e) {
      if (id !== runId.current) return
      setError(e.message)
      setView('landing')
    }
  }

  function home() {
    runId.current++
    setView('landing')
    setResult(null)
    window.history.replaceState(null, '', window.location.pathname)
  }

  if (view === 'loading') return <Loading topic={topic} stages={stages} onCancel={home} />
  if (view === 'dashboard' && result)
    return <Dashboard result={result} onHome={home} onSearch={start} examples={EXAMPLES} />
  return <Landing onSubmit={start} examples={EXAMPLES} error={error} />
}
