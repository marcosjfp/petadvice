import { useEffect, useState } from 'react'
import { api, type CheckHistory as HistoryData, type Pet, type TriageResult } from './api'
import { errorMessage, useRequest } from './useRequest'
import { reportDate, symptomLabel } from './checkReport'
import { useI18n } from './i18n'
import CheckResult from './CheckResult'

export default function CheckHistory({ pet }: { pet: Pet }) {
  const { t } = useI18n()
  const h = t.history
  const [history, setHistory] = useState<HistoryData | null>(null)
  const [result, setResult] = useState<TriageResult | null>(null)
  const [retry, setRetry] = useState(0)
  const { busy, error, setError, run } = useRequest()
  useEffect(() => {
    let active = true
    api.history(pet.id).then(data => { if (active) setHistory(data) }).catch(failure => { if (active) setError(errorMessage(failure)) })
    return () => { active = false }
  }, [pet.id, retry, setError])
  if (result) return <CheckResult result={result} petName={pet.name} saved><button className="secondary" onClick={() => { setResult(null); setError('') }}>{h.back}</button></CheckResult>
  return <section className="panel"><p className="eyebrow">{h.eyebrow(pet.name)}</p><h1>{h.title}</h1><p className="muted">{h.muted}</p>
    {!history && !error && <p role="status">{h.loading}</p>}{error && <p role="alert" className="error">{error}</p>}
    {!history && error && <button className="secondary" onClick={() => { setError(''); setRetry(value => value + 1) }}>{t.common.tryAgain}</button>}
    {history && history.checks.length === 0 && <p>{h.none(pet.name)}</p>}
    <ol className="check-history">{history?.checks.map(check => <li key={check.session_id}><div><h2>{symptomLabel(t, check.symptom)}</h2><p>{reportDate(check.started_at)}</p><span className={`urgency-label ${check.urgency ?? ''}`}>{check.complete ? check.urgency ? t.urgency[check.urgency] : h.guidanceNotSaved : h.notCompleted}</span></div>{check.complete ? <button className="secondary" disabled={busy} onClick={() => void run(async () => { setResult(await api.result(check.session_id)) })}>{h.view}</button> : <p className="fine-print">{h.startNew}</p>}</li>)}</ol>
    {history?.next_cursor && <button className="secondary" disabled={busy} onClick={() => void run(async () => { const next = await api.history(pet.id, history.next_cursor!); setHistory({ checks: [...history.checks, ...next.checks], next_cursor: next.next_cursor }) })}>{h.loadOlder}</button>}
    <p role="status">{busy ? h.loadingSaved : ''}</p>
  </section>
}
