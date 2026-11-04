import { useState, type FormEvent } from 'react'
import { api } from './api'
import { serverText, useI18n } from './i18n'
import { useRequest } from './useRequest'

export default function AccountLink({ action, token, onDone }: { action: 'verify' | 'reset'; token: string; onDone: () => void }) {
  const { t } = useI18n()
  const a = t.accountLink
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [status, setStatus] = useState('')
  const { busy, error, run, setError } = useRequest()
  function submit(event: FormEvent) {
    event.preventDefault()
    if (action === 'reset' && password !== confirmation) { setError(a.mismatch); return }
    void run(async () => {
      const response = action === 'verify' ? await api.verifyEmail(token) : await api.resetPassword(token, password)
      setStatus(serverText(response.message)); setPassword(''); setConfirmation('')
    })
  }
  return <section className="panel auth-panel"><h1>{action === 'verify' ? a.verifyTitle : a.resetTitle}</h1>
    {status ? <><p role="status">{status}</p><button className="primary" onClick={onDone}>{a.continue}</button></> : <>
      <form className="profile-form auth-form" onSubmit={submit} aria-busy={busy}>
        {action === 'reset' && <><div className="form-field"><label htmlFor="reset-password">{a.newPassword}</label><input id="reset-password" aria-describedby="reset-password-help" type="password" autoComplete="new-password" required minLength={15} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /><small id="reset-password-help">{a.hint}</small></div><label>{a.confirm}<input type="password" autoComplete="new-password" required minLength={15} maxLength={128} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} /></label></>}
        <button className="primary" disabled={busy}>{busy ? t.common.pleaseWait : action === 'verify' ? a.verify : a.reset}</button>
      </form>{error && <p className="error" role="alert">{error}</p>}
      <button className="secondary" disabled={busy} onClick={onDone}>{a.back}</button>
    </>}
  </section>
}
