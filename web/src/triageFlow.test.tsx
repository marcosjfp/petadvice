import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { api, ApiError, type TriageResult } from './api'
import App from './App'
import CheckResult from './CheckResult'
import { setLanguage } from './i18n'

vi.mock('./api', async (importOriginal) => {
  const original = await importOriginal<typeof import('./api')>()
  return { ...original, api: {
    getMe: vi.fn(), listPets: vi.fn(), history: vi.fn(), startTriage: vi.fn(), answer: vi.fn(), back: vi.fn(), result: vi.fn(),
    privacy: vi.fn(), exportCheck: vi.fn(), deleteGuestCheck: vi.fn(), listConditions: vi.fn(), listPreventive: vi.fn(),
  } }
})

const homeResult: TriageResult = {
  resulting_urgency: 'monitor_home', resulting_guidance: 'Offer small amounts of water.', matched_condition_ids: ['dog-gi-001'],
  possible_causes: [], recommended_examinations: [], language: 'en', content_version: 'a'.repeat(64),
  started_at: '2026-10-10T12:34:56Z', recorded_at: '2026-10-10T12:40:56Z',
  sources: ['https://www.vet.example.org/vomiting?ref=1'],
  watch_for: [{ description: 'Blood in the vomit', urgency: 'emergency_now' }, { description: 'Repeated vomiting', urgency: 'vet_24h' }],
  recheck_advice: 'If your pet is not clearly improving within 24–48 hours, or you are worried at any point, contact your vet.',
  context_notes: [{ kind: 'missing_life_stage', detail: "Your pet's age was not given.", urgency: 'vet_soon' }],
  pet: { name: 'Guest pet', species: 'dog', date_of_birth: null, life_stage: null, age_group: 'adult', sex: 'male', neutered: null, breed_size: null },
}

beforeEach(() => {
  setLanguage('en')
  vi.unstubAllEnvs()
  vi.resetAllMocks()
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  vi.mocked(api.getMe).mockRejectedValue(new ApiError('Not authenticated', 401))
  vi.mocked(api.privacy).mockResolvedValue({ status: 'draft', operator: null, contact: null, policy_url: null, policy_version: 'test', guest_retention_hours: 24, account_retention: 'Until deletion', backup_retention: 'Pending' })
})

async function startGuestCheck(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('button', { name: /Start a quick check/ }))
  await user.click(screen.getByRole('button', { name: 'Vomiting' }))
}

test('guest context is optional and sent with the check', async () => {
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 's', guest_token: 'tok', flow_complete: false, next_question: { id: 'q1', prompt: 'How often?', options: ['Once'] }, progress: { step: 1, max_steps: 4 } })
  const user = userEvent.setup()
  await startGuestCheck(user)
  const context = screen.getByRole('group', { name: 'About your pet (optional)' })
  expect(within(context).getByRole('combobox', { name: 'Age' })).toHaveValue('')
  await user.selectOptions(within(context).getByRole('combobox', { name: 'Age' }), 'Puppy')
  await user.selectOptions(within(context).getByRole('combobox', { name: 'Sex' }), 'Female')
  await user.selectOptions(within(context).getByRole('combobox', { name: 'Spayed or neutered' }), 'No')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  expect(api.startTriage).toHaveBeenCalledWith(null, 'vomiting', 'dog', { age_group: 'young', sex: 'female', neutered: false })
  expect(await screen.findByText('Question 1 of 4')).toBeInTheDocument()
})

test('questions show progress, can go back, and keep guest file controls for the result', async () => {
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 's', guest_token: 'tok', expires_at: '2026-10-10T12:34:56Z', flow_complete: false, next_question: { id: 'q1', prompt: 'How often has your pet vomited?', options: ['Once', 'Twice'] }, progress: { step: 1, max_steps: 3 } })
  const second = { flow_complete: false, next_question: { id: 'q2', prompt: 'Has your pet had any access to toxins, chocolate, medicines or a foreign object such as a toy or bone?', options: ['No'] }, progress: { step: 2, max_steps: 3 } }
  vi.mocked(api.answer).mockResolvedValueOnce(second).mockResolvedValueOnce(second)
    .mockResolvedValueOnce({ flow_complete: true, next_question: null, progress: null })
  vi.mocked(api.back).mockResolvedValue({ flow_complete: false, next_question: { id: 'q1', prompt: 'How often has your pet vomited?', options: ['Once', 'Twice'] }, progress: { step: 1, max_steps: 3 } })
  vi.mocked(api.result).mockResolvedValue(homeResult)
  const user = userEvent.setup()
  await startGuestCheck(user)
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  expect(await screen.findByText('Question 1 of 3')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Previous question' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Download raw data/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Delete this guest check' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Once' }))
  const long = await screen.findByRole('heading', { name: /access to toxins/ })
  expect(long).toHaveFocus()
  expect(long).toHaveClass('long-prompt')
  expect(screen.getByText('Question 2 of 3')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Previous question/ }))
  expect(api.back).toHaveBeenCalledWith('s', 'q2', 'tok')
  expect(await screen.findByRole('heading', { name: 'How often has your pet vomited?' })).toHaveFocus()
  expect(window.scrollTo).toHaveBeenCalledWith(0, 0)
  await user.click(screen.getByRole('button', { name: 'Twice' }))
  await user.click(await screen.findByRole('button', { name: 'No' }))
  expect(await screen.findByRole('heading', { name: 'Monitor at home' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Download raw data (JSON)' })).toHaveClass('link-button')
  expect(screen.getByRole('button', { name: 'Delete this guest check' })).toBeInTheDocument()
})

test('leaving an unfinished guest check asks for confirmation in the page', async () => {
  const confirm = vi.spyOn(window, 'confirm')
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 's', guest_token: 'tok', flow_complete: false, next_question: { id: 'q1', prompt: 'How often?', options: ['Once'] }, progress: { step: 1, max_steps: 2 } })
  const user = userEvent.setup()
  await startGuestCheck(user)
  // Nothing started yet: Back leaves straight away.
  await user.click(screen.getByRole('button', { name: 'Back' }))
  expect(await screen.findByRole('button', { name: /Start a quick check/ })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Start a quick check/ }))
  await user.click(screen.getByRole('button', { name: 'Vomiting' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await screen.findByRole('heading', { name: 'How often?' })
  await user.click(screen.getByRole('button', { name: 'Back' }))
  const dialog = screen.getByRole('alertdialog', { name: 'Leave this check?' })
  expect(within(dialog).getByRole('button', { name: 'Stay on this check' })).toHaveFocus()
  await user.click(within(dialog).getByRole('button', { name: 'Stay on this check' }))
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'How often?' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Back' }))
  await user.click(screen.getByRole('button', { name: 'Leave this check' }))
  expect(await screen.findByRole('button', { name: /Start a quick check/ })).toBeInTheDocument()
  expect(confirm).not.toHaveBeenCalled()
})

test('leaving a guest result warns that it is not saved', async () => {
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 's', guest_token: 'tok', flow_complete: true, next_question: null })
  vi.mocked(api.result).mockResolvedValue(homeResult)
  const user = userEvent.setup()
  await startGuestCheck(user)
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await screen.findByRole('heading', { name: 'Monitor at home' })
  await user.click(screen.getByRole('button', { name: 'Back' }))
  expect(screen.getByRole('alertdialog')).toHaveTextContent('Download the summary first')
})

test('result shows signs to watch for, re-check advice, context notes and tidy technical details', async () => {
  render(<CheckResult result={homeResult} />)
  const watch = screen.getByRole('heading', { name: 'Watch for these signs — contact a vet if…' }).parentElement!
  expect(watch).toHaveTextContent('not clearly improving within 24–48 hours')
  expect(within(watch).getByText('Blood in the vomit — Emergency veterinary care now')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Details that could change this guidance' })).toBeInTheDocument()
  expect(screen.getByText(/adult; sex male/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'www.vet.example.org (opens a new tab)' })).toHaveAttribute('href', 'https://www.vet.example.org/vomiting?ref=1')
  expect(screen.getByText(`Content version: ${'a'.repeat(64)}`)).not.toBeVisible()
  await userEvent.setup().click(screen.getByText('Technical information'))
  expect(screen.getByText(`Content version: ${'a'.repeat(64)}`)).toBeVisible()
  expect(screen.getByText('Started:').parentElement!.textContent).not.toMatch(/\d{1,2}:\d{2}:\d{2}/)
})

test('signed-in checks do not ask for guest context', async () => {
  vi.mocked(api.getMe).mockResolvedValue({ id: 'owner', email: 'test@example.com' })
  vi.mocked(api.listPets).mockResolvedValue([{ id: 'dog', name: 'Rex', species: 'dog', life_stage: null }])
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 's', flow_complete: false, next_question: { id: 'q1', prompt: 'How often?', options: ['Once'] } })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Vomiting' }))
  expect(screen.queryByRole('group', { name: 'About your pet (optional)' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await waitFor(() => expect(api.startTriage).toHaveBeenCalledWith('dog', 'vomiting', 'dog'))
  expect(await screen.findByText('Adaptive questions')).toBeInTheDocument()  // No progress from an older API.
})
