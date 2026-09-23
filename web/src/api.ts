const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export type Pet = { id: string; name: string; species: 'dog' | 'cat'; life_stage?: string | null }
export type Condition = { id: string; name: string; category: string; urgency_default: string; prevention_tips?: string | null }
export type Question = { id: string; prompt: string; options: string[] }
export type TriageResult = { resulting_urgency: string; resulting_guidance: string; matched_condition_ids: string[] }

export const api = {
  createPet: (payload: unknown) => request<Pet>('/pets', { method: 'POST', body: JSON.stringify(payload) }),
  listPets: () => request<Pet[]>('/pets?owner_id=demo-owner'),
  listConditions: (species: string) => request<Condition[]>(`/conditions?species=${species}`),
  listPreventive: (species: string, lifeStage: string) => request<Condition[]>(`/preventive-care?species=${species}&life_stage=${lifeStage}`),
  questions: (symptom: string) => request<Question[]>(`/triage/questions?symptom_tag=${symptom}`),
  startTriage: (petId: string, symptom: string) => request<{ session_id: string }>('/triage/start', { method: 'POST', body: JSON.stringify({ pet_id: petId, symptom_tag: symptom }) }),
  answer: (sessionId: string, questionId: string, answer: string) => request('/triage/' + sessionId + '/answer', { method: 'POST', body: JSON.stringify({ question_id: questionId, answer }) }),
  result: (sessionId: string) => request<TriageResult>('/triage/' + sessionId + '/result'),
}
