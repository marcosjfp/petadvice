const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'petadvice_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    ...options,
  })
  if (!response.ok) throw new Error(await response.text())
  return response.json() as Promise<T>
}

export type Pet = { id: string; name: string; species: 'dog' | 'cat'; life_stage?: string | null }
export type Condition = { id: string; name: string; category: string; urgency_default: string; prevention_tips?: string | null }
export type Question = { id: string; prompt: string; options: string[] }
export type TriageResult = { resulting_urgency: string; resulting_guidance: string; matched_condition_ids: string[]; possible_causes: string[]; recommended_examinations: string[] }
export type TriageStart = { session_id: string; next_question: Question | null; flow_complete: boolean }
export type TriageAnswer = { next_question: Question | null; flow_complete: boolean }
export type AuthResponse = { access_token: string; token_type: string }

export const api = {
  signup: (email: string, password: string, privacyPolicyAccepted: boolean) => request<AuthResponse>('/auth/signup', { method: 'POST', body: JSON.stringify({ email, password, privacy_policy_accepted: privacyPolicyAccepted }) }),
  login: (email: string, password: string) => request<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  getMe: () => request<{ id: string; email: string }>('/auth/me'),
  exportMyData: () => request<unknown>('/auth/me/export'),
  deleteMyAccount: () => request<{ status: string }>('/auth/me', { method: 'DELETE' }),
  createPet: (payload: unknown) => request<Pet>('/pets', { method: 'POST', body: JSON.stringify(payload) }),
  listPets: () => request<Pet[]>('/pets'),
  listConditions: (species: string) => request<Condition[]>(`/conditions?species=${species}`),
  listPreventive: (species: string, lifeStage: string) => request<Condition[]>(`/preventive-care?species=${species}&life_stage=${lifeStage}`),
  questions: (symptom: string) => request<Question[]>(`/triage/questions?symptom_tag=${symptom}`),
  startTriage: (petId: string, symptom: string) => request<TriageStart>('/triage/start', { method: 'POST', body: JSON.stringify({ pet_id: petId, symptom_tag: symptom }) }),
  answer: (sessionId: string, questionId: string, answer: string) => request<TriageAnswer>('/triage/' + sessionId + '/answer', { method: 'POST', body: JSON.stringify({ question_id: questionId, answer }) }),
  result: (sessionId: string) => request<TriageResult>('/triage/' + sessionId + '/result'),
}
