import { useState, type FormEvent } from 'react'
import { api } from './api'
import { useRequest } from './useRequest'

export default function AccountLink({ action, token, onDone }: { action: 'verify' | 'reset'; token: string; onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [status, setStatus] = useState('')
  const { busy, error, run, setError } = useRequest()
  function submit(event: FormEvent) {
    event.preventDefault()
    if (action === 'reset' && password !== confirmation) { setError('The passwords do not match.'); return }
    void run(async () => {
      const response = action === 'verify' ? await api.verifyEmail(token) : await api.resetPassword(token, password)
      setStatus(response.message); setPassword(''); setConfirmation('')
    })
  }
  return <section className="panel auth-panel"><h1>{action === 'verify' ? 'Verify your email.' : 'Choose a new password.'}</h1>
    {status ? <><p role="status">{status}</p><button className="primary" onClick={onDone}>Continue to sign in</button></> : <>
      <form className="profile-form auth-form" onSubmit={submit} aria-busy={busy}>
        {action === 'reset' && <><div className="form-field"><label htmlFor="reset-password">New password</label><input id="reset-password" aria-describedby="reset-password-help" type="password" autoComplete="new-password" required minLength={15} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /><small id="reset-password-help">Use 15–128 characters.</small></div><label>Confirm new password<input type="password" autoComplete="new-password" required minLength={15} maxLength={128} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label></>}
        <button className="primary" disabled={busy}>{busy ? 'Please wait…' : action === 'verify' ? 'Verify email' : 'Reset password'}</button>
      </form>{error && <p className="error" role="alert">{error}</p>}
      <button className="secondary" disabled={busy} onClick={onDone}>Back to sign in / request a new link</button>
    </>}
  </section>
}
