import { useEffect, useRef } from 'react'
import { urgencyLabels, type TriageResult } from './api'
import { downloadFile } from './download'
import { explanationGap, historicalNotice, readable, reportBoundary, reportDate, reportHtml } from './checkReport'

export default function CheckResult({ result, petName, saved = false, children }: { result: TriageResult; petName?: string; saved?: boolean; children?: React.ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [])
  return <section className={`result ${result.resulting_urgency}`}>
    <article className="check-report" aria-label="Check summary">
      <p className="eyebrow">{saved ? 'Saved check' : 'Guidance'} for {result.pet?.name ?? petName ?? 'your pet'}</p>
      <h1 ref={heading} tabIndex={-1}>{urgencyLabels[result.resulting_urgency]}</h1>
      {saved && <p className="report-notice">This is the guidance saved for this check, not a new assessment of your pet today.</p>}
      {result.historical && <p className="report-notice">{historicalNotice}</p>}
      <div className="report-action"><h2>Your next step</h2><p className="result-copy">{result.resulting_guidance}</p></div>
      <div className="report-context"><p><strong>Symptom:</strong> {readable(result.symptom ?? 'Not recorded')}<br /><strong>Started:</strong> {reportDate(result.started_at)}{result.recorded_at && <><br /><strong>Report preserved:</strong> {reportDate(result.recorded_at)}</>}</p>
        {result.pet && <p><strong>Pet context recorded:</strong> {result.pet.species}, {result.pet.life_stage ? readable(result.pet.life_stage) : 'age unknown'}; sex {result.pet.sex ?? 'unknown'}; neutered {result.pet.neutered == null ? 'unknown' : result.pet.neutered ? 'yes' : 'no'}{result.pet.breed_size && `; ${result.pet.breed_size} breed size`}{result.pet.date_of_birth && `; born ${result.pet.date_of_birth}`}</p>}
      </div>
      <div className="report-section"><h2>How this was decided</h2>{result.reasons?.length ? <ul>{result.reasons.map((reason, index) => <li key={index}>{reason.detail}</li>)}</ul> : <p>{explanationGap}</p>}</div>
      <div className="report-section"><h2>Your recorded answers</h2>{result.answers?.length ? <dl className="recorded-answers">{result.answers.map(answer => <div key={answer.question_id}><dt>{answer.prompt}</dt><dd>{answer.answer}</dd></div>)}</dl> : <p>No questionnaire answers were recorded.</p>}</div>
      {result.possible_causes.length > 0 && <div className="report-section"><h2>Possible causes to discuss with your vet</h2><ul>{result.possible_causes.map(cause => <li key={cause}>{cause}</li>)}</ul></div>}
      {result.recommended_examinations.length > 0 && <div className="report-section"><h2>Your vet may want to check</h2><ul>{result.recommended_examinations.map(examination => <li key={examination}>{examination}</li>)}</ul></div>}
      {!!result.sources?.length && <div className="report-section"><h2>Sources recorded with this check</h2><ul>{result.sources.map(source => <li key={source}>{/^https?:\/\//.test(source) ? <a href={source} target="_blank" rel="noopener noreferrer">{source}</a> : source}</li>)}</ul></div>}
      <p className="fine-print">{reportBoundary}</p><p className="fine-print">Content version: {result.content_version ?? 'Not recorded for this older check'}</p>
    </article>
    <div className="report-controls"><button className="primary" onClick={() => window.print()}>Print / save PDF</button><button className="secondary" onClick={() => downloadFile(reportHtml(result), 'petadvice-check-summary.html', 'text/html')}>Download summary</button><p className="fine-print">The downloaded summary stays on your device. Share it only with someone you choose.</p>{children}</div>
  </section>
}
