import { type CareGuide, type Species } from './api'
import { useI18n } from './i18n'
import { checkableSymptoms } from './symptoms'

export function CareGuides({ items, heading, level = 'h2' }: { items?: CareGuide[]; heading: string; level?: 'h2' | 'h3' }) {
  const { t } = useI18n()
  if (!items?.length) return null
  const Heading = level
  return <div className="care-guides"><Heading>{heading}</Heading>{items.map((item) => <details key={item.id} className="care-guide"><summary>{item.title}</summary><p>{item.description}</p>{item.recurrence && <p className="recurrence">{t.care.timing(item.recurrence)}</p>}</details>)}</div>
}

export function StartCheckButtons({ symptoms, species, onStartCheck }: { symptoms: string[]; species: Species; onStartCheck?: (symptom: string, species: Species) => void }) {
  const { t } = useI18n()
  const available = checkableSymptoms(symptoms, species)
  if (!onStartCheck || available.length === 0) return null
  return <div className="start-checks">{available.map((symptom) => <button key={symptom} type="button" className="secondary" onClick={() => onStartCheck(symptom, species)}>{t.common.startCheck(t.symptoms[symptom])} <span aria-hidden="true">→</span></button>)}</div>
}
