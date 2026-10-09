const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 15_000)
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options, headers, credentials: 'include', signal: controller.signal,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail = body?.detail
      const message = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg.replace(/^Value error, /, '')).join('. ')
        : 'The request could not be completed. Please try again.'
      if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me') {
        window.dispatchEvent(new Event('petadvice:session-expired'))
      }
      throw new ApiError(message, response.status)
    }
    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new Error(controller.signal.aborted
      ? 'The request timed out. Check your connection and try again.'
      : 'Could not connect. Check your connection and try again.')
  } finally {
    window.clearTimeout(timeout)
  }
}

export type Species = 'dog' | 'cat'
export type Urgency = 'monitor_home' | 'vet_soon' | 'vet_24h' | 'emergency_now'
export const urgencyLabels: Record<Urgency, string> = {
  monitor_home: 'Monitor at home', vet_soon: 'Book a vet appointment',
  vet_24h: 'Contact a vet within 24 hours', emergency_now: 'Emergency veterinary care now',
}
export type Pet = { id: string; name: string; species: Species; life_stage?: string | null }
export type PetCreate = { name: string; species: Species; date_of_birth: string | null; sex: string | null; neutered: boolean | null; breed_size: string | null; environment_factors: string[] }
export type Condition = {
  id: string; name: string; category: string; urgency_default: Urgency;
  home_care_guidance: string | null; prevention_tips: string | null;
  red_flags: { description: string; escalates_to: Urgency }[];
  sources: string[]; vet_reviewed_by: string | null; last_reviewed_date: string | null;
}
export type PreventiveCareItem = { id: string; title: string; description: string; recurrence: string | null; sources: string[] }
export type Question = { id: string; prompt: string; options: string[] }
export type TriageResult = { resulting_urgency: Urgency; resulting_guidance: string; matched_condition_ids: string[]; possible_causes: string[]; recommended_examinations: string[] }
export type TriageStart = { session_id: string; next_question: Question | null; flow_complete: boolean }
export type TriageAnswer = { next_question: Question | null; flow_complete: boolean }

export const api = {
  signup: (email: string, password: string, privacyPolicyAccepted: boolean) => request('/auth/signup', { method: 'POST', body: JSON.stringify({ email, password, privacy_policy_accepted: privacyPolicyAccepted }) }),
  login: (email: string, password: string) => request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  getMe: () => request<{ id: string; email: string }>('/auth/me'),
  exportMyData: () => request<unknown>('/auth/me/export'),
  deleteMyAccount: () => request('/auth/me', { method: 'DELETE' }),
  createPet: (payload: PetCreate) => request<Pet>('/pets', { method: 'POST', body: JSON.stringify(payload) }),
  listPets: () => request<Pet[]>('/pets'),
  listConditions: (species: Species) => request<Condition[]>(`/conditions?${new URLSearchParams({ species })}`),
  listPreventive: (species: Species, lifeStage?: string | null) => request<PreventiveCareItem[]>(`/preventive-care?${new URLSearchParams({ species, ...(lifeStage ? { life_stage: lifeStage } : {}) })}`),
  startTriage: (petId: string | null, symptom: string, species: Species = 'dog') => request<TriageStart>('/triage/start', { method: 'POST', body: JSON.stringify({ pet_id: petId, symptom_tag: symptom, species }) }),
  answer: (sessionId: string, questionId: string, answer: string) => request<TriageAnswer>(`/triage/${encodeURIComponent(sessionId)}/answer`, { method: 'POST', body: JSON.stringify({ question_id: questionId, answer }) }),
  result: (sessionId: string) => request<TriageResult>(`/triage/${encodeURIComponent(sessionId)}/result`),
}
