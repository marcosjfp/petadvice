import { type TriageResult } from './api'
import { formatDate, getLanguage, readable, translations, type Language, type Messages } from './i18n'

export { readable }
export function reportDate(value?: string | null) { return value ? formatDate(value) : translations().common.notRecorded }
export function symptomLabel(t: Messages, symptom?: string | null) { return symptom ? t.symptoms[symptom] ?? readable(symptom) : t.common.notRecorded }
// Guest checks are stored against a placeholder pet the owner never named.
const GUEST_PET_NAME = 'Guest pet'
export function petDisplayName(t: Messages, name?: string | null) { return name && name !== GUEST_PET_NAME ? name : t.result.yourPet }
export function lifeStageLabel(t: Messages, stage: string) { return t.lifeStage[stage] ?? readable(stage) }

export function petContextLine(t: Messages, pet: NonNullable<TriageResult['pet']>) {
  const yesNo = pet.neutered == null ? t.common.unknown.toLowerCase() : pet.neutered ? t.common.yes.toLowerCase() : t.common.no.toLowerCase()
  return `${t.speciesLower[pet.species] ?? pet.species}, ${pet.life_stage ? lifeStageLabel(t, pet.life_stage) : t.result.ageUnknown}; ${t.result.sexLabel} ${pet.sex ? t.sex[pet.sex] ?? pet.sex : t.common.unknown.toLowerCase()}; ${t.result.neuteredLabel} ${yesNo}`
    + (pet.breed_size ? `; ${t.result.breedSizeSuffix}: ${t.breedSize[pet.breed_size] ?? pet.breed_size}` : '')
    + (pet.date_of_birth ? `; ${t.result.born} ${pet.date_of_birth}` : '')
}

function escape(value: string) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;')
}
function list(items: string[]) { return `<ul>${items.map(item => `<li>${escape(item)}</li>`).join('')}</ul>` }
function reportLanguage(result: TriageResult): Language {
  return result.language === 'pt' || result.language === 'es' || result.language === 'en' ? result.language : getLanguage()
}

export function reportHtml(result: TriageResult) {
  // Labels follow the language the guidance was recorded in, so the file reads as one document.
  const language = reportLanguage(result)
  const t = translations(language)
  const r = t.result
  const pet = result.pet
  const unknown = t.common.unknown.toLowerCase()
  const context = pet ? `${petDisplayName(t, pet.name)} · ${t.speciesLower[pet.species] ?? pet.species} · ${r.lifeStage}: ${pet.life_stage ? lifeStageLabel(t, pet.life_stage) : unknown} · ${r.birthDate}: ${pet.date_of_birth ?? unknown} · ${t.petForm.sex}: ${pet.sex ? t.sex[pet.sex] ?? pet.sex : unknown} · ${r.neuteredLabel}: ${pet.neutered == null ? unknown : pet.neutered ? t.common.yes : t.common.no} · ${r.breedSize}: ${pet.breed_size ? t.breedSize[pet.breed_size] ?? pet.breed_size : unknown}` : r.noContext
  // Escape all stored text. This file contains no credentials, active scripts,
  // tracking, external assets or public share link.
  return `<!doctype html><html lang="${language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>${escape(r.reportTitle)}</title><style>body{font:16px/1.6 system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 20px;color:#26312d}h1,h2{line-height:1.2}h2{margin-top:30px}dt{font-weight:bold}dd{margin:0 0 16px}p,li,dd{overflow-wrap:anywhere}@media print{body{margin:0;max-width:none}h2{break-after:avoid}}</style></head><body><h1>${escape(r.reportTitle)}</h1><p>${escape(context)}</p><p>${escape(r.started)} ${escape(reportDate(result.started_at))}<br>${escape(r.preserved)} ${escape(reportDate(result.recorded_at))}<br>${escape(r.symptom)} ${escape(symptomLabel(t, result.symptom))}</p>${result.historical ? `<p>${escape(r.historicalNotice)}</p>` : ''}<h2>${escape(t.urgency[result.resulting_urgency])}</h2><p>${escape(result.resulting_guidance)}</p>${result.related_care?.length ? `<h2>${escape(r.careGuides)}</h2>` + result.related_care.map(item => `<h3>${escape(item.title)}</h3><p>${escape(item.description)}</p>${item.recurrence ? `<p>${escape(t.care.timing(item.recurrence))}</p>` : ''}`).join('') : ''}<h2>${escape(r.howDecided)}</h2>${result.reasons?.length ? list(result.reasons.map(reason => reason.detail)) : `<p>${escape(r.explanationGap)}</p>`}<h2>${escape(r.answers)}</h2>${result.answers?.length ? `<dl>${result.answers.map(answer => `<dt>${escape(answer.prompt)}</dt><dd>${escape(answer.answer)}</dd>`).join('')}</dl>` : `<p>${escape(r.noAnswers)}</p>`}${result.possible_causes.length ? `<h2>${escape(r.causes)}</h2>` + list(result.possible_causes) : ''}${result.recommended_examinations.length ? `<h2>${escape(r.exams)}</h2>` + list(result.recommended_examinations) : ''}${result.sources?.length ? `<h2>${escape(r.sources)}</h2>` + list(result.sources) : ''}<p>${escape(r.boundary)}</p><p>${escape(r.contentVersion(result.content_version ?? r.contentVersionMissing))}</p></body></html>`
}
