import { useEffect, useState } from 'react'
import { api, urgencyLabels, type CheckHistory as HistoryData, type Pet, type TriageResult } from './api'
import { errorMessage, useRequest } from './useRequest'
import { readable, reportDate } from './checkReport'
import CheckResult from './CheckResult'

export default function CheckHistory({ pet }: { pet: Pet }) {
  const [history, setHistory] = useState<HistoryData | null>(null)
  const [result, setResult] = useState<TriageResult | null>(null)
  const [retry, setRetry] = useState(0)
  const { busy, error, setError, run } = useRequest()
  useEffect(() => {
    let active = true
    api.history(pet.id).then(data => { if (active) setHistory(data) }).catch(failure => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [pet.id, retry, setError])
  if (result) return <CheckResult result={result} petName={pet.name} saved><button className="secondary" onClick={() => { setResult(null); setError('') }}>Back to check history</button></CheckResult>
  return <section className="panel"><p className="eyebrow">Saved checks for {pet.name}</p><h1>Check history</h1><p className="muted">Revisit the guidance and answers recorded for earlier checks. If symptoms have changed, start a new check.</p>
    {!history && !error && <p role="status">Loading check history…</p>}{error && <p role="alert" className="error">{error}</p>}
    {!history && error && <button className="secondary" onClick={() => { setError(''); setRetry(value => value + 1) }}>Try again</button>}
    {history && history.checks.length === 0 && <p>No checks saved for {pet.name} yet. Complete a symptom check to see it here.</p>}
    <ol className="check-history">{history?.checks.map(check => <li key={check.session_id}><div><h2>{readable(check.symptom)}</h2><p>{reportDate(check.started_at)}</p><span className={`urgency-label ${check.urgency ?? ''}`}>{check.complete ? check.urgency ? urgencyLabels[check.urgency] : 'Questions completed; guidance not yet saved' : 'Questions not completed'}</span></div>{check.complete ? <button className="secondary" disabled={busy} onClick={() => void run(async () => { setResult(await api.result(check.session_id)) })}>View saved check</button> : <p className="fine-print">Start a new check if you still need guidance.</p>}</li>)}</ol>
    {history?.next_cursor && <button className="secondary" disabled={busy} onClick={() => void run(async () => { const next = await api.history(pet.id, history.next_cursor!); setHistory({ checks: [...history.checks, ...next.checks], next_cursor: next.next_cursor }) })}>Load older checks</button>}
    <p role="status">{busy ? 'Loading saved guidance…' : ''}</p>
  </section>
}
