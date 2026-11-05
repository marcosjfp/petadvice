import { type Species } from './api'

export const checkSymptoms: { value: string; only?: Species }[] = [
  { value: 'straining_to_urinate' }, { value: 'vomiting' }, { value: 'diarrhea' }, { value: 'limping', only: 'dog' },
  { value: 'reverse_sneezing', only: 'dog' }, { value: 'scratching' }, { value: 'scooting' }, { value: 'nervous_or_stressed', only: 'cat' },
  { value: 'increased_thirst' }, { value: 'vaginal_discharge' },
]

export function checkableSymptoms(tags: string[], species: Species) {
  return checkSymptoms.filter((item) => tags.includes(item.value) && (!item.only || item.only === species)).map((item) => item.value)
}
