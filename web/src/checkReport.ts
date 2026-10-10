import { urgencyLabels, type TriageResult } from './api'

export const explanationGap = 'The original rule explanations were not recorded for this check.'
export const historicalNotice = 'This is a saved check, not a new assessment. Older checks may not include the original pet context, sources or question wording.'
export const reportBoundary = 'General educational guidance, not a diagnosis. Beta content awaits veterinary review. This summary records this check; it does not assess later changes in symptoms. If your pet worsens or you are unsure, contact your veterinary practice.'
export function readable(value: string) { return value.replaceAll('_', ' ') }
export function reportDate(value?: string | null) { return value ? new Date(value).toLocaleString() : 'Not recorded' }

function escape(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')
}
function list(items: string[]) { return `<ul>${items.map(item => `<li>${escape(item)}</li>`).join('')}</ul>` }
export function reportHtml(result: TriageResult) {
  const pet = result.pet
  const context = pet ? `${pet.name} · ${pet.species} · Life stage: ${pet.life_stage ? readable(pet.life_stage) : 'unknown'} · Birth date: ${pet.date_of_birth ?? 'unknown'} · Sex: ${pet.sex ?? 'unknown'} · Neutered: ${pet.neutered == null ? 'unknown' : pet.neutered ? 'yes' : 'no'} · Breed size: ${pet.breed_size ?? 'unknown'}` : 'Original pet context was not recorded.'
  // Escape all stored text. This file contains no credentials, active scripts,
  // tracking, external assets or public share link.
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>PETAdvice check summary</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#26312d}h1,h2{line-height:1.2}h2{margin-top:30px}dt{font-weight:bold}dd{margin:0 0 16px}p,li,dd{overflow-wrap:anywhere}@media print{body{margin:0;max-width:none}h2{break-after:avoid}}</style></head><body><h1>PETAdvice check summary</h1><p>${escape(context)}</p><p>Started: ${escape(reportDate(result.started_at))}<br>Report preserved: ${escape(reportDate(result.recorded_at))}<br>Symptom: ${escape(readable(result.symptom ?? 'Not recorded'))}</p>${result.historical ? `<p>${historicalNotice}</p>` : ''}<h2>${escape(urgencyLabels[result.resulting_urgency])}</h2><p>${escape(result.resulting_guidance)}</p><h2>How this was decided</h2>${result.reasons?.length ? list(result.reasons.map(reason => reason.detail)) : `<p>${explanationGap}</p>`}<h2>Your recorded answers</h2>${result.answers?.length ? `<dl>${result.answers.map(answer => `<dt>${escape(answer.prompt)}</dt><dd>${escape(answer.answer)}</dd>`).join('')}</dl>` : '<p>No questionnaire answers were recorded.</p>'}${result.possible_causes.length ? '<h2>Possible causes to discuss with your vet</h2>' + list(result.possible_causes) : ''}${result.recommended_examinations.length ? '<h2>Your vet may want to check</h2>' + list(result.recommended_examinations) : ''}${result.sources?.length ? '<h2>Sources recorded with this check</h2>' + list(result.sources) : ''}<p>${reportBoundary}</p><p>Content version: ${escape(result.content_version ?? 'Not recorded for this older check')}</p></body></html>`
}
