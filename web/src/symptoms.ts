import { type Species } from './api'

export type SymptomGroup = 'urgent' | 'digestion' | 'breathing_eyes_ears' | 'skin_behaviour' | 'body'
export const symptomGroups: SymptomGroup[] = ['urgent', 'digestion', 'breathing_eyes_ears', 'skin_behaviour', 'body']

// Emergencies come first so someone in a hurry finds them without scrolling.
export const checkSymptoms: { value: string; group: SymptomGroup; only?: Species }[] = [
  { value: 'ate_something_toxic', group: 'urgent' }, { value: 'swollen_belly_retching', group: 'urgent', only: 'dog' },
  { value: 'heatstroke', group: 'urgent' }, { value: 'straining_to_urinate', group: 'urgent' },
  { value: 'vomiting', group: 'digestion' }, { value: 'diarrhea', group: 'digestion' }, { value: 'constipation', group: 'digestion' },
  { value: 'not_eating_or_lethargic', group: 'digestion' }, { value: 'scooting', group: 'digestion' },
  { value: 'coughing', group: 'breathing_eyes_ears' }, { value: 'reverse_sneezing', group: 'breathing_eyes_ears', only: 'dog' },
  { value: 'eye_problem', group: 'breathing_eyes_ears' }, { value: 'ear_scratching_or_head_shaking', group: 'breathing_eyes_ears' },
  { value: 'scratching', group: 'skin_behaviour' }, { value: 'nervous_or_stressed', group: 'skin_behaviour', only: 'cat' },
  { value: 'limping', group: 'body', only: 'dog' }, { value: 'increased_thirst', group: 'body' }, { value: 'vaginal_discharge', group: 'body' },
]

export function checkableSymptoms(tags: string[], species: Species) {
  return checkSymptoms.filter((item) => tags.includes(item.value) && (!item.only || item.only === species)).map((item) => item.value)
}
