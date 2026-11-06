import { useEffect, useRef } from 'react'
import { type TriageResult } from './api'
import { downloadFile } from './download'
import { petContextLine, petDisplayName, reportDate, reportHtml, sourceHost, symptomLabel, watchSignLine } from './checkReport'
import { useI18n } from './i18n'
import { CareGuides } from './CareGuides'

export default function CheckResult({ result, petName, saved = false, children }: { result: TriageResult; petName?: string; saved?: boolean; children?: React.ReactNode }) {
  const { t } = useI18n()
  const r = t.result
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { window.scrollTo?.(0, 0); heading.current?.focus() }, [])
  const watchFor = result.watch_for ?? []
  return <section className={`result ${result.resulting_urgency}`}>
    <article className="check-report" aria-label={r.summary} lang={result.language ?? undefined}>
      <p className="eyebrow">{r.eyebrow(saved, petDisplayName(t, result.pet?.name ?? petName))}</p>
      <h1 ref={heading} tabIndex={-1}>{t.urgency[result.resulting_urgency]}</h1>
      {saved && <p className="report-notice">{r.savedNotice}</p>}
      {result.historical && <p className="report-notice">{r.historicalNotice}</p>}
      <div className="report-action"><h2>{r.nextStep}</h2><p className="result-copy">{result.resulting_guidance}</p><CareGuides items={result.related_care} heading={r.careGuides} level="h3" /></div>
      {(watchFor.length > 0 || result.recheck_advice) && <div className="report-section watch-for"><h2>{r.watchFor}</h2>{result.recheck_advice && <p>{result.recheck_advice}</p>}{watchFor.length > 0 && <ul>{watchFor.map(sign => <li key={sign.description}>{watchSignLine(t, sign)}</li>)}</ul>}</div>}
      {!!result.context_notes?.length && <div className="report-section context-notes"><h2>{r.contextNotes}</h2><ul>{result.context_notes.map((note, index) => <li key={index}>{note.detail}</li>)}</ul></div>}
      <div className="report-context"><p><strong>{r.symptom}</strong> {symptomLabel(t, result.symptom)}<br /><strong>{r.started}</strong> {reportDate(result.started_at)}{result.recorded_at && <><br /><strong>{r.preserved}</strong> {reportDate(result.recorded_at)}</>}</p>
        {result.pet && <p><strong>{r.petContext}</strong> {petContextLine(t, result.pet)}</p>}
      </div>
      <div className="report-section"><h2>{r.howDecided}</h2>{result.reasons?.length ? <ul>{result.reasons.map((reason, index) => <li key={index}>{reason.detail}</li>)}</ul> : <p>{r.explanationGap}</p>}</div>
      <div className="report-section"><h2>{r.answers}</h2>{result.answers?.length ? <dl className="recorded-answers">{result.answers.map(answer => <div key={answer.question_id}><dt>{answer.prompt}</dt><dd>{answer.answer}</dd></div>)}</dl> : <p>{r.noAnswers}</p>}</div>
      {result.possible_causes.length > 0 && <div className="report-section"><h2>{r.causes}</h2><ul>{result.possible_causes.map(cause => <li key={cause}>{cause}</li>)}</ul></div>}
      {result.recommended_examinations.length > 0 && <div className="report-section"><h2>{r.exams}</h2><ul>{result.recommended_examinations.map(examination => <li key={examination}>{examination}</li>)}</ul></div>}
      {!!result.sources?.length && <div className="report-section"><h2>{r.sources}</h2><ul>{result.sources.map(source => <li key={source}>{/^https?:\/\//.test(source) ? <a href={source} target="_blank" rel="noopener noreferrer">{t.common.opensNewTab(sourceHost(source))}</a> : source}</li>)}</ul></div>}
      <p className="fine-print">{r.boundary}</p>
      <details className="technical-info"><summary>{r.technicalInfo}</summary><p className="fine-print">{r.contentVersion(result.content_version ?? r.contentVersionMissing)}</p></details>
    </article>
    <div className="report-controls"><button className="primary" onClick={() => window.print()}>{r.print}</button><button className="secondary" onClick={() => downloadFile(reportHtml(result), 'petadvice-check-summary.html', 'text/html')}>{r.downloadSummary}</button><p className="fine-print">{r.summaryStays}</p>{children}</div>
  </section>
}
