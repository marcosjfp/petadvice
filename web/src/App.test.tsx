import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { api } from './api'
import App from './App'

vi.mock('./api', async (importOriginal) => {
  const original = await importOriginal<typeof import('./api')>()
  return { ...original, api: {
    history: vi.fn(), getMe: vi.fn(), listPets: vi.fn(), startTriage: vi.fn(), answer: vi.fn(), result: vi.fn(),
    listPreventive: vi.fn(), listConditions: vi.fn(), createPet: vi.fn(), logout: vi.fn(),
    login: vi.fn(), signup: vi.fn(), exportMyData: vi.fn(), deleteMyAccount: vi.fn(),
    privacy: vi.fn(), forgotPassword: vi.fn(), resendVerification: vi.fn(), verifyEmail: vi.fn(), resetPassword: vi.fn(), reauthenticate: vi.fn(), logoutAll: vi.fn(), exportCheck: vi.fn(), deleteGuestCheck: vi.fn(),
  } }
})
const pets = [
  { id: 'dog', name: 'Rex', species: 'dog' as const, life_stage: 'young_adult' },
  { id: 'cat', name: 'Miso', species: 'cat' as const, life_stage: null },
]
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.history).mockResolvedValue({ checks: [], next_cursor: null })
  vi.mocked(api.getMe).mockResolvedValue({ id: 'owner', email: 'test@example.com' })
  vi.mocked(api.listPets).mockResolvedValue(pets)
  vi.mocked(api.privacy).mockResolvedValue({ status: 'draft', operator: null, contact: null, policy_url: null, policy_version: 'test', guest_retention_hours: 24, account_retention: 'Until deletion', backup_retention: 'Pending' })
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

test('forgot password shows a neutral response without trying to sign in', async () => {
  const { ApiError } = await import('./api')
  vi.mocked(api.getMe).mockRejectedValue(new ApiError('Not authenticated', 401))
  vi.mocked(api.forgotPassword).mockResolvedValue({ message: 'If this address belongs to an eligible account, an email will arrive shortly.' })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Log in' }))
  await user.click(screen.getByRole('button', { name: 'Forgot your password?' }))
  await user.type(screen.getByRole('textbox', { name: 'Email' }), 'someone@example.com')
  await user.click(screen.getByRole('button', { name: 'Send reset link' }))
  expect(await screen.findByText(/eligible account/)).toBeInTheDocument()
  expect(api.forgotPassword).toHaveBeenCalledWith('someone@example.com')
  expect(api.login).not.toHaveBeenCalled()
})

test('a guest capability follows answers and results and allows deletion', async () => {
  const { ApiError } = await import('./api')
  vi.mocked(api.getMe).mockRejectedValue(new ApiError('Not authenticated', 401))
  vi.mocked(api.startTriage).mockResolvedValue({ session_id: 'guest-check', guest_token: 'private-capability', expires_at: '2026-10-10T12:00:00Z', flow_complete: false, next_question: { id: 'question', prompt: 'Any weakness?', options: ['No'] } })
  vi.mocked(api.answer).mockResolvedValue({ next_question: null, flow_complete: true })
  vi.mocked(api.result).mockResolvedValue({ resulting_urgency: 'vet_soon', resulting_guidance: 'Contact your vet.', matched_condition_ids: [], possible_causes: [], recommended_examinations: [] })
  vi.mocked(api.deleteGuestCheck).mockResolvedValue({ status: 'deleted' })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: /Start a quick check/ }))
  await user.click(screen.getByRole('button', { name: 'Vomiting' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(await screen.findByRole('button', { name: 'No' }))
  expect(await screen.findByRole('heading', { name: 'Book a vet appointment' })).toBeInTheDocument()
  expect(api.answer).toHaveBeenCalledWith('guest-check', 'question', 'No', 'private-capability')
  expect(api.result).toHaveBeenCalledWith('guest-check', 'private-capability')
  await user.click(screen.getByRole('button', { name: 'Delete this guest check' }))
  expect(await screen.findByRole('heading', { name: 'What have you noticed?' })).toBeInTheDocument()
  expect(api.deleteGuestCheck).toHaveBeenCalledWith('guest-check', 'private-capability')
})

test('account deletion confirms the password before deleting', async () => {
  vi.mocked(api.reauthenticate).mockRejectedValueOnce(new Error('Incorrect password')).mockResolvedValue({ status: 'confirmed' })
  vi.mocked(api.deleteMyAccount).mockResolvedValue({ status: 'deleted' })
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Account' }))
  await user.click(screen.getByRole('button', { name: 'Delete my account…' }))
  expect(screen.getByRole('button', { name: 'Permanently delete my account' })).toBeDisabled()
  await user.type(screen.getByLabelText('Confirm your password for account controls'), 'incorrect')
  await user.click(screen.getByRole('button', { name: 'Permanently delete my account' }))
  expect(await screen.findByText('Incorrect password')).toBeInTheDocument()
  expect(api.deleteMyAccount).not.toHaveBeenCalled()
  await user.clear(screen.getByLabelText('Confirm your password for account controls'))
  await user.type(screen.getByLabelText('Confirm your password for account controls'), 'correct-passphrase')
  await user.click(screen.getByRole('button', { name: 'Permanently delete my account' }))
  await waitFor(() => expect(api.deleteMyAccount).toHaveBeenCalledTimes(1))
})

test('password reset removes the link from the URL and requires matching passwords', async () => {
  const { ApiError } = await import('./api')
  vi.mocked(api.getMe).mockRejectedValue(new ApiError('Not authenticated', 401))
  vi.mocked(api.resetPassword).mockResolvedValue({ message: 'Password changed. Sign in with your new password.' })
  window.history.replaceState(null, '', '/#action=reset&token=private-reset-token')
  const user = userEvent.setup()
  render(<App />)
  expect(window.location.hash).toBe('')
  await user.type(screen.getByLabelText('New password'), 'a-new-long-passphrase')
  await user.type(screen.getByLabelText('Confirm new password'), 'a-different-passphrase')
  await user.click(screen.getByRole('button', { name: 'Reset password' }))
  expect(screen.getByRole('alert')).toHaveTextContent('The passwords do not match.')
  expect(api.resetPassword).not.toHaveBeenCalled()
  await user.clear(screen.getByLabelText('Confirm new password'))
  await user.type(screen.getByLabelText('Confirm new password'), 'a-new-long-passphrase')
  await user.click(screen.getByRole('button', { name: 'Reset password' }))
  expect(await screen.findByText(/Password changed/)).toBeInTheDocument()
  expect(api.resetPassword).toHaveBeenCalledWith('private-reset-token', 'a-new-long-passphrase')
})

test('guests browse species-specific learning and care without creating a profile', async () => {
  const { ApiError } = await import('./api')
  vi.mocked(api.getMe).mockRejectedValue(new ApiError('Not authenticated', 401))
  vi.mocked(api.listConditions).mockResolvedValue([{ id: 'c1', name: 'Bladder concern', category: 'urinary', symptom_tags: ['straining_to_urinate'], urgency_default: 'emergency_now', home_care_guidance: 'Contact your vet.', prevention_tips: null, red_flags: [], sources: [], vet_reviewed_by: null, last_reviewed_date: null }])
  vi.mocked(api.listPreventive).mockResolvedValue([{ id: 'care', title: 'Nutrition review', description: 'Discuss nutrition.', recurrence: null, sources: [] }])
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Browse Learn' }))
  await user.selectOptions(screen.getByRole('combobox', { name: 'Browse information for' }), 'cat')
  await waitFor(() => expect(api.listConditions).toHaveBeenLastCalledWith('cat'))
  await user.type(screen.getByRole('searchbox'), 'straining')
  expect(await screen.findByText('Bladder concern')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Care' }))
  expect(await screen.findByText('Discuss nutrition.')).toBeInTheDocument()
  expect(api.listPreventive).toHaveBeenLastCalledWith('cat', null)
  expect(api.createPet).not.toHaveBeenCalled()
  expect(api.login).not.toHaveBeenCalled()
})

test('history opens the recorded result and clears it when the active pet changes', async () => {
  vi.mocked(api.history).mockImplementation(async (petId) => ({ checks: petId === 'dog' ? [{ session_id: 'saved-check', started_at: '2026-10-10T12:00:00Z', symptom: 'vomiting', complete: true, urgency: 'vet_soon' }] : [], next_cursor: null }))
  vi.mocked(api.result).mockResolvedValue({ resulting_urgency: 'vet_soon', resulting_guidance: 'Original guidance.', possible_causes: [], recommended_examinations: [], matched_condition_ids: [], pet: { name: 'Rex at the time', species: 'dog', date_of_birth: null, life_stage: null, sex: null, neutered: null, breed_size: null }, reasons: [{ kind: 'answer', detail: 'Recorded rule explanation.', urgency: 'vet_soon' }], answers: [{ question_id: 'q1', prompt: 'Original question?', answer: 'Original answer' }] })
  const print = vi.spyOn(window, 'print').mockImplementation(() => {})
  const user = userEvent.setup()
  render(<App />)
  await user.click(await screen.findByRole('button', { name: 'Check history' }))
  await user.click(await screen.findByRole('button', { name: 'View saved check' }))
  expect(await screen.findByText('Original guidance.')).toBeInTheDocument()
  expect(screen.getByText('Recorded rule explanation.')).toBeInTheDocument()
  expect(screen.getByText('Original answer')).toBeInTheDocument()
  expect(screen.getByText(/not a new assessment of your pet today/)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Print / save PDF' }))
  expect(print).toHaveBeenCalledTimes(1)
  await user.selectOptions(screen.getByRole('combobox', { name: 'Change active pet' }), 'cat')
  expect(await screen.findByText('No checks saved for Miso yet. Complete a symptom check to see it here.')).toBeInTheDocument()
  expect(screen.queryByText('Original guidance.')).not.toBeInTheDocument()
  print.mockRestore()
})
