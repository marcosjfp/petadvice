import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { api } from './api'
import App from './App'

vi.mock('./api', async (importOriginal) => {
  const original = await importOriginal<typeof import('./api')>()
  return { ...original, api: {
    getMe: vi.fn(), listPets: vi.fn(), startTriage: vi.fn(), answer: vi.fn(), result: vi.fn(),
    listPreventive: vi.fn(), listConditions: vi.fn(), createPet: vi.fn(), logout: vi.fn(),
    login: vi.fn(), signup: vi.fn(), exportMyData: vi.fn(), deleteMyAccount: vi.fn(),
  } }
})
const pets = [
  { id: 'dog', name: 'Rex', species: 'dog' as const, life_stage: 'young_adult' },
  { id: 'cat', name: 'Miso', species: 'cat' as const, life_stage: null },
]
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.getMe).mockResolvedValue({ id: 'owner', email: 'test@example.com' })
  vi.mocked(api.listPets).mockResolvedValue(pets)
})

test('switching pets discards the previous pet question and hides dog-only symptoms', async () => {
  const user = userEvent.setup()
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 'session', flow_complete: false, next_question: { id: 'q1', prompt: 'How often has Rex vomited?', options: ['Once'] } })
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Vomiting' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  expect(await screen.findByRole('heading', { name: 'How often has Rex vomited?' })).toHaveFocus()
  await user.selectOptions(screen.getByRole('combobox', { name: 'Change active pet' }), 'cat')
  expect(screen.queryByText('How often has Rex vomited?')).not.toBeInTheDocument()
  expect(screen.getByText(/Checking symptoms for Miso/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Reverse sneezing' })).not.toBeInTheDocument()
})

test('care plan displays the API title, description and recurrence, including age unknown', async () => {
  const user = userEvent.setup()
  vi.mocked(api.listPreventive).mockResolvedValue([{ id: 'care1', title: 'Review nutrition', description: 'Discuss calories with your vet.', recurrence: 'every 6 months', sources: [] }])
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Care plan' }))
  expect(await screen.findByRole('heading', { name: 'Review nutrition' })).toBeInTheDocument()
  expect(screen.getByText('Discuss calories with your vet.')).toBeInTheDocument()
  expect(screen.getByText('Timing: every 6 months')).toBeInTheDocument()
  await user.selectOptions(screen.getByRole('combobox', { name: 'Change active pet' }), 'cat')
  await waitFor(() => expect(api.listPreventive).toHaveBeenLastCalledWith('cat', null))
  expect(screen.getByText(/age is unknown/)).toBeInTheDocument()
})

test('a failed result can be retried without resubmitting the answer', async () => {
  const user = userEvent.setup()
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 'session', flow_complete: false, next_question: { id: 'q1', prompt: 'Any weakness?', options: ['No'] } })
  vi.mocked(api.answer).mockResolvedValue({ next_question: null, flow_complete: true })
  vi.mocked(api.result).mockRejectedValueOnce(new Error('Could not connect.')).mockResolvedValue({ resulting_urgency: 'vet_soon', resulting_guidance: 'Contact your vet.', matched_condition_ids: [], possible_causes: [], recommended_examinations: [] })
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Scratching or fleas' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(await screen.findByRole('button', { name: 'No' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not connect.')
  await user.click(screen.getByRole('button', { name: 'Try loading guidance again' }))
  expect(await screen.findByRole('heading', { name: 'Book a vet appointment' })).toBeInTheDocument()
  expect(api.answer).toHaveBeenCalledTimes(1)
})

test('library supports search, details and readable urgency', async () => {
  const user = userEvent.setup()
  vi.mocked(api.listConditions).mockResolvedValue([{ id: 'c1', name: 'Vomiting', category: 'gastrointestinal', urgency_default: 'monitor_home', home_care_guidance: 'Watch for changes.', prevention_tips: null, red_flags: [{ description: 'Blood', escalates_to: 'vet_24h' }], sources: ['https://example.com'], vet_reviewed_by: null, last_reviewed_date: null }])
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Learn' }))
  await user.click(await screen.findByText('Vomiting'))
  expect(screen.getByText('Watch for changes.')).toBeVisible()
  expect(screen.getByText('Awaiting veterinary review.')).toBeVisible()
  expect(screen.getByText('Blood — Contact a vet within 24 hours')).toBeVisible()
  await user.type(screen.getByRole('searchbox', { name: 'Search the library' }), 'no-match')
  expect(screen.getByText(/No entries match/)).toBeInTheDocument()
})
