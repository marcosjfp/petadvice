import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, urgencyLabels, type Condition, type Owner, type Privacy, type Pet, type Question, type Species, type TriageResult, type PreventiveCareItem } from './api'
import AccountLink from './AccountLink'
import CheckResult from './CheckResult'
import CheckHistory from './CheckHistory'
import { downloadJson } from './download'
import { errorMessage, useRequest } from './useRequest'
import fullLogo from './assets/brand/Logo_new.png'
import nameLogo from './assets/brand/Logo_Just_Name.png'
import petsLogo from './assets/brand/Logo_Just_Pets.png'
import './App.css'

type View = 'triage' | 'library' | 'care' | 'history' | 'account'

function ErrorNotice({ message }: { message: string }) {
  return message ? <p className="error" role="alert">{message}</p> : null
}

function App() {
  const [accountLink, setAccountLink] = useState(() => {
    const values = new URLSearchParams(window.location.hash.slice(1))
    const action = values.get('action'), token = values.get('token')
    return (action === 'verify' || action === 'reset') && token ? { action, token } as { action: 'verify' | 'reset'; token: string } : null
  })
  const [owner, setOwner] = useState<Owner | null>(null)
  const [auth, setAuth] = useState<'checking' | 'signed-in' | 'guest' | 'error'>('checking')
  const [view, setView] = useState<View>('triage')
  const [pets, setPets] = useState<Pet[]>([])
  const [selectedPetId, setSelectedPetId] = useState<string | null>(null)
  const [showPetForm, setShowPetForm] = useState(false)
  const [showAuth, setShowAuth] = useState(false)
  const [showQuickCheck, setShowQuickCheck] = useState(false)
  const [publicView, setPublicView] = useState<'library' | 'care' | null>(null)
  const [load, setLoad] = useState(0)
  const [petsLoaded, setPetsLoaded] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [today] = useState(() => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  })
  const pet = pets.find((item) => item.id === selectedPetId) ?? pets[0] ?? null
  const { busy, error, run } = useRequest()

  useEffect(() => {
    if (accountLink) window.history.replaceState(null, '', window.location.pathname + window.location.search)
  }, [accountLink])

  useEffect(() => {
    // Remove credentials stored by the previous version. Cookies are HttpOnly.
    try { localStorage.removeItem('petadvice_token') } catch { /* Storage can be disabled; cookie auth still works. */ }
    let cancelled = false
    api.getMe().then((data) => { if (!cancelled) { setOwner(data); setAuth('signed-in') } })
      .catch((failure) => { if (!cancelled) setAuth(failure instanceof ApiError && failure.status === 401 ? 'guest' : 'error') })
    const expired = () => {
      setOwner(null)
      setAuth('guest'); setPets([]); setSelectedPetId(null); setPetsLoaded(false)
      setShowAuth(true); setShowQuickCheck(false)
    }
    window.addEventListener('petadvice:session-expired', expired)
    return () => { cancelled = true; window.removeEventListener('petadvice:session-expired', expired) }
  }, [load])

  useEffect(() => {
    if (auth !== 'signed-in') return
    let cancelled = false
    api.listPets().then((loadedPets) => {
      if (cancelled) return
      setPets(loadedPets); setSelectedPetId((current) => current ?? loadedPets[0]?.id ?? null)
      setPetsLoaded(true); setLoadError('')
    }).catch((failure) => { if (!cancelled) { setLoadError(errorMessage(failure)); setPetsLoaded(true) } })
    return () => { cancelled = true }
  }, [auth, load])

  function resetAccount() {
    setOwner(null)
    setAuth('guest'); setPets([]); setSelectedPetId(null); setPetsLoaded(false)
    setShowPetForm(false); setShowAuth(false); setShowQuickCheck(false); setView('triage')
  }

  function createPet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    void run(async () => {
      const neutered = form.get('neutered')
      const created = await api.createPet({
        name: String(form.get('name')).trim(), species: form.get('species') as Species,
        date_of_birth: String(form.get('date_of_birth') || '') || null,
        sex: String(form.get('sex') || '') || null,
        neutered: neutered === '' ? null : neutered === 'yes',
        breed_size: String(form.get('breed_size') || '') || null, environment_factors: [],
      })
      setPets((current) => [...current, created]); setSelectedPetId(created.id)
      setShowPetForm(false); setView('triage')
    })
  }

  function retryLoad() { setLoadError(''); setPetsLoaded(false); setAuth('checking'); setLoad((count) => count + 1) }

  if (accountLink) return <Shell><AccountLink {...accountLink} onDone={() => { setAccountLink(null); setShowAuth(true); retryLoad() }} /><Emergency /></Shell>

  if (auth === 'checking' || (auth === 'signed-in' && !petsLoaded)) return <Shell><p role="status">Loading your account…</p><Emergency /></Shell>
  if (auth === 'error' || loadError) return <Shell><h1>We could not load your account.</h1><ErrorNotice message={loadError || 'Check your connection and try again.'} /><button className="primary" onClick={retryLoad}>Try again</button><Emergency /></Shell>
  if (auth === 'guest') {
    if (showAuth) return <AuthPanel onBack={() => setShowAuth(false)} onAuthenticated={() => { setShowAuth(false); setShowQuickCheck(false); retryLoad() }} />
    if (showQuickCheck) return <Shell onBack={() => setShowQuickCheck(false)}><Triage pet={null} onLogin={() => setShowAuth(true)} /><Emergency /></Shell>
    if (publicView) return <PublicEducation initialView={publicView} onBack={() => setPublicView(null)} />
    return <PublicLanding onBrowse={setPublicView} onQuickCheck={() => setShowQuickCheck(true)} onLogin={() => setShowAuth(true)} />
  }

  if (owner?.email_verification_required && !owner.email_verified_at) return <Shell><VerificationNotice email={owner.email} onLogout={resetAccount} /><Account onDeleted={resetAccount} /><Emergency /></Shell>

  if ((!pet || showPetForm) && view !== 'account') return <Shell onBack={pet ? () => setShowPetForm(false) : undefined}>
    <section className="welcome"><p className="eyebrow">{pet ? 'Add another companion' : 'Set up your first pet'}</p>
      <h1>Tell us about your pet.</h1><p className="lead">A few details help keep guidance relevant. Leave anything you do not know as unknown.</p>
      <form className="profile-form" onSubmit={createPet} aria-busy={busy}>
        <label>Pet name<input name="name" required maxLength={100} placeholder="e.g. Miso" /></label>
        <label>Species<select name="species"><option value="dog">Dog</option><option value="cat">Cat</option></select></label>
        <label>Date of birth (optional)<input name="date_of_birth" type="date" max={today} /></label>
        <label>Sex<select name="sex"><option value="">Unknown</option><option value="female">Female</option><option value="male">Male</option></select></label>
        <label>Spayed or neutered?<select name="neutered"><option value="">Unknown</option><option value="yes">Yes</option><option value="no">No</option></select></label>
        <label>Dog breed size (optional)<select name="breed_size"><option value="">Unknown / cat</option><option value="small">Small</option><option value="medium">Medium</option><option value="large">Large</option><option value="giant">Giant</option></select></label>
        <button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Create pet profile'}</button>
      </form><ErrorNotice message={error} />
      {!pet && <button className="secondary" onClick={() => setView('account')}>Account and privacy</button>}
    </section><Emergency />
  </Shell>

  return <main className="shell">
    <header><img className="name-logo" src={nameLogo} alt="PETAdvice" /><div className="header-actions">
      {pet && <label className="pet-switcher"><img className="pets-logo" src={petsLogo} alt="" /><span className="pet-switcher-copy"><strong>{pet.name}</strong><small>{pet.life_stage?.replaceAll('_', ' ') ?? 'Age unknown'}</small></span><select aria-label="Change active pet" value={pet.id} onChange={(event) => setSelectedPetId(event.target.value)}>{pets.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.species})</option>)}</select><span className="switcher-chevron" aria-hidden="true">⌄</span></label>}
      <button className="start-fresh" onClick={() => { setShowPetForm(true); setView('triage') }}>New pet</button>
      <button className="start-fresh" disabled={busy} onClick={() => void run(async () => { await api.logout(); resetAccount() })}>Log out</button>
    </div></header>
    <nav className="tabs" aria-label="Main navigation">{(['triage', 'library', 'care', 'history', 'account'] as View[]).map((item) => <button aria-current={view === item ? 'page' : undefined} className={view === item ? 'active' : ''} onClick={() => setView(item)} key={item}>{({ triage: 'Check symptoms', library: 'Learn', care: 'Care plan', history: 'Check history', account: 'Account' })[item]}</button>)}</nav>
    <ErrorNotice message={error} />
    {view === 'triage' && pet && <Triage key={pet.id} pet={pet} />}
    {view === 'library' && pet && <Library key={pet.species} species={pet.species} />}
    {view === 'care' && pet && <Care key={pet.id} pet={pet} />}
    {view === 'history' && pet && <CheckHistory key={pet.id} pet={pet} />}
    {view === 'account' && <Account onDeleted={resetAccount} />}
    <Emergency />
  </main>
}

function Shell({ children, onBack }: { children: React.ReactNode; onBack?: () => void }) {
  return <main className="shell"><header><img className="name-logo" src={nameLogo} alt="PETAdvice" />{onBack && <button className="cancel-fresh" onClick={onBack}>Back</button>}</header>{children}</main>
}

function PublicLanding({ onQuickCheck, onLogin, onBrowse }: { onQuickCheck: () => void; onLogin: () => void; onBrowse: (view: 'library' | 'care') => void }) {
  return <main className="shell"><header><img className="main-logo" src={fullLogo} alt="PETAdvice dog and cat logo" /><button className="start-fresh" onClick={onLogin}>Log in</button></header>
    <section className="intro"><p className="eyebrow">Friendly guidance for everyday pet worries</p><h1>A clearer next step for your pet.</h1><p className="intro-lead">When something feels different, PETAdvice helps you work out what to look for, how urgently to act, and what to discuss with your vet.</p>
      <div className="intro-actions"><button className="primary" onClick={onQuickCheck}>Start a quick check <span aria-hidden="true">→</span></button><button className="secondary" onClick={onLogin}>Save my pet profiles</button></div>
      <div className="public-links"><button className="secondary" onClick={() => onBrowse('library')}>Browse Learn</button><button className="secondary" onClick={() => onBrowse('care')}>Browse Care</button></div>
      <div className="intro-points"><article><span>01</span><div><h2>Make sense of symptoms</h2><p>Find straightforward information about common concerns.</p></div></article><article><span>02</span><div><h2>Know how urgent it is</h2><p>Answer focused questions to help decide when to contact a vet.</p></div></article><article><span>03</span><div><h2>Keep care on track</h2><p>Save pet profiles and browse care information for their life stage.</p></div></article></div>
      <p className="intro-boundary">General educational guidance, not a diagnosis. This beta's content is awaiting veterinary review. No account is needed for a quick check.</p>
    </section><Emergency />
  </main>
}

function PublicEducation({ initialView, onBack }: { initialView: 'library' | 'care'; onBack: () => void }) {
  const [view, setView] = useState(initialView)
  const [species, setSpecies] = useState<Species>('dog')
  return <Shell onBack={onBack}><nav className="tabs" aria-label="Public learning navigation">{(['library', 'care'] as const).map((item) => <button key={item} aria-current={view === item ? 'page' : undefined} className={view === item ? 'active' : ''} onClick={() => setView(item)}>{item === 'library' ? 'Learn' : 'Care'}</button>)}</nav>
    <label className="guest-species">Browse information for<select value={species} onChange={(event) => setSpecies(event.target.value as Species)}><option value="dog">Dogs</option><option value="cat">Cats</option></select></label>
    {view === 'library' ? <Library key={species} species={species} /> : <Care key={species} species={species} />}<Emergency />
  </Shell>
}

function PrivacyNotice() {
  const [notice, setNotice] = useState<Privacy | null>(null)
  useEffect(() => { let active = true; api.privacy().then((data) => { if (active) setNotice(data) }).catch(() => {}); return () => { active = false } }, [])
  return <details className="privacy-notice"><summary>How your data is used</summary><p>The app stores your email, a password hash, pet profiles, symptom checks and security records. You can download account data or delete your account and its profiles and checks from the app database.</p><p>{notice ? `Guest checks expire after ${notice.guest_retention_hours} hours and are removed by scheduled cleanup. You can also download or delete a guest check while it is open.` : 'Guest checks have a limited retention period; the current notice could not be loaded.'} Closing the page loses access to that guest check.</p><p>Account data is kept until you delete the account. Backups follow the deployment operator’s separate retention schedule.</p>{notice?.policy_url && /^https:\/\//.test(notice.policy_url) ? <p><a href={notice.policy_url} target="_blank" rel="noopener noreferrer">Read the privacy policy</a> · {notice.operator}{notice.contact && <> · <a href={`mailto:${notice.contact}`}>{notice.contact}</a></>}</p> : <p>This beta notice is a draft. Operator, hosting, backup retention and privacy contact details are still pending before public release.</p>}<p>Do not enter personal or sensitive details in pet names.</p></details>
}

function VerificationNotice({ email, onLogout }: { email: string; onLogout: () => void }) {
  const { busy, error, run } = useRequest()
  const [status, setStatus] = useState('')
  return <section className="panel"><h1>Check your email.</h1><p>Verify {email} before saving pet profiles. Open the link in your verification email, then return here.</p><button className="primary" disabled={busy} onClick={() => void run(async () => { setStatus((await api.resendVerification(email)).message) })}>Resend verification email</button><button className="secondary" onClick={() => window.location.reload()}>I have verified my email</button><button className="secondary" disabled={busy} onClick={() => void run(async () => { await api.logout(); onLogout() })}>Log out</button><p role="status">{status}</p><ErrorNotice message={error} /></section>
}

function AuthPanel({ onBack, onAuthenticated }: { onBack: () => void; onAuthenticated: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup' | 'forgot'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [privacyAccepted, setPrivacyAccepted] = useState(false)
  const [status, setStatus] = useState('')
  const { busy, error, run, setError } = useRequest()
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void run(async () => {
      if (mode === 'forgot') { setStatus((await api.forgotPassword(email)).message); return }
      if (mode === 'login') await api.login(email, password)
      else await api.signup(email, password, privacyAccepted)
      onAuthenticated()
    })
  }
  return <Shell onBack={onBack}><section className="welcome auth-panel"><p className="eyebrow">Private guidance for your pets</p><h1>{mode === 'login' ? 'Welcome back.' : mode === 'forgot' ? 'Recover your account.' : 'Create your account.'}</h1><p className="lead">{mode === 'forgot' ? 'Enter your email to request a password reset link.' : 'Your pet profiles and checks stay tied to your account.'}</p>
    <form className="profile-form auth-form" onSubmit={submit} aria-busy={busy}>
      <label>Email<input name="email" type="email" autoComplete="username" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      {mode !== 'forgot' && <label>Password<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'signup' ? 15 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />{mode === 'signup' && <small>Use 15–128 characters. A passphrase works well.</small>}</label>}
      {mode === 'signup' && <><PrivacyNotice /><label className="check"><input type="checkbox" required checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} /> I have read the beta data-use notice.</label></>}
      <button className="primary" disabled={busy}>{busy ? 'Please wait…' : mode === 'login' ? 'Log in' : mode === 'forgot' ? 'Send reset link' : 'Create account'}</button>
    </form><p role="status">{status}</p><ErrorNotice message={error} /><button className="secondary" disabled={busy} onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); setPassword(''); setStatus('') }}>{mode === 'login' ? 'Create an account' : 'Back to log in'}</button>{mode === 'login' && <button className="secondary" onClick={() => { setMode('forgot'); setError(''); setPassword(''); setStatus('') }}>Forgot your password?</button>}
  </section><Emergency /></Shell>
}

const symptoms = [
  { value: 'straining_to_urinate', label: 'Straining to urinate' }, { value: 'vomiting', label: 'Vomiting' },
  { value: 'diarrhea', label: 'Diarrhea' }, { value: 'limping', label: 'Limping after exercise', dogOnly: true },
  { value: 'reverse_sneezing', label: 'Reverse sneezing', dogOnly: true }, { value: 'scratching', label: 'Scratching or fleas' },
  { value: 'increased_thirst', label: 'Drinking more than usual' }, { value: 'vaginal_discharge', label: 'Unexpected discharge' },
]

function Triage({ pet, onLogin }: { pet: Pet | null; onLogin?: () => void }) {
  const [symptom, setSymptom] = useState('')
  const [species, setSpecies] = useState<Species>('dog')
  const [question, setQuestion] = useState<Question | null>(null)
  const [session, setSession] = useState('')
  const [guestToken, setGuestToken] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [complete, setComplete] = useState(false)
  const [result, setResult] = useState<TriageResult | null>(null)
  const { busy, error, run, setError } = useRequest()
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { if (question || complete) heading.current?.focus() }, [question, complete, result])
  const activeSpecies = pet?.species ?? species
  async function finish(sessionId: string, token = guestToken) {
    setQuestion(null); setComplete(true)
    setResult(await api.result(sessionId, token))
  }
  function begin() {
    void run(async () => {
      const started = await api.startTriage(pet?.id ?? null, symptom, activeSpecies)
      setSession(started.session_id)
      setGuestToken(started.guest_token ?? null); setExpiresAt(started.expires_at ?? null)
      if (started.flow_complete) await finish(started.session_id, started.guest_token ?? null)
      else setQuestion(started.next_question)
    })
  }
  function answer(value: string) {
    if (!question) return
    void run(async () => {
      const next = await api.answer(session, question.id, value, guestToken)
      if (next.flow_complete) await finish(session)
      else setQuestion(next.next_question)
    })
  }
  function restart() { setResult(null); setSession(''); setGuestToken(null); setExpiresAt(null); setQuestion(null); setComplete(false); setError('') }
  const guestControls = guestToken ? <GuestControls session={session} token={guestToken} expiresAt={expiresAt} disabled={busy} onDeleted={restart} /> : null
  if (result) return <CheckResult result={result} petName={pet?.name}>
    {onLogin && <button className="primary" onClick={onLogin}>Create an account for future pet profiles</button>}
    <button className="secondary" onClick={restart}>Start another check</button>
    {guestControls}
  </CheckResult>
  if (complete) return <section className="panel"><h1 ref={heading} tabIndex={-1}>Your questions are complete.</h1><p role="status">{busy ? 'Loading guidance…' : 'Guidance could not be loaded yet.'}</p><ErrorNotice message={error} /><button className="primary" disabled={busy} onClick={() => void run(async () => { setResult(await api.result(session, guestToken)) })}>Try loading guidance again</button>{guestControls}</section>
  if (question) return <section className="question" aria-busy={busy}><div className="progress">Check for {pet?.name ?? `your ${species}`} <span>Adaptive questions</span></div><h1 ref={heading} tabIndex={-1}>{question.prompt}</h1><div className="options">{question.options.map((option) => <button disabled={busy} className="option" onClick={() => answer(option)} key={option}>{option}<span aria-hidden="true">→</span></button>)}</div><p role="status">{busy ? 'Saving your answer…' : ''}</p><ErrorNotice message={error} /><button className="secondary" disabled={busy} onClick={restart}>Restart this check</button>{guestControls}</section>
  return <section className="panel" aria-busy={busy}><p className="eyebrow">A calmer next step</p><h1>What have you noticed?</h1><p className="muted">{pet ? `Checking symptoms for ${pet.name}. ` : ''}Choose the closest match. This check gives urgency guidance, not a diagnosis.</p>
    {!pet && <label className="guest-species">Who is this check for?<select disabled={busy} value={species} onChange={(event) => { setSpecies(event.target.value as Species); setSymptom(''); setError('') }}><option value="dog">Dog</option><option value="cat">Cat</option></select></label>}
    <div className="symptoms">{symptoms.filter((item) => !item.dogOnly || activeSpecies === 'dog').map((item) => <button disabled={busy} aria-pressed={symptom === item.value} className={symptom === item.value ? 'selected' : ''} onClick={() => setSymptom(item.value)} key={item.value}>{item.label}<span aria-hidden="true">＋</span></button>)}</div>
    <button className="primary wide" disabled={!symptom || busy} onClick={begin}>{busy ? 'Starting your check…' : 'Continue'}</button><ErrorNotice message={error} />
    <p className="fine-print">Cannot find the symptom? Contact your veterinary practice. Breathing trouble or collapse needs emergency care immediately.</p>
    {!pet && <PrivacyNotice />}
  </section>
}

function GuestControls({ session, token, expiresAt, disabled, onDeleted }: { session: string; token: string; expiresAt: string | null; disabled: boolean; onDeleted: () => void }) {
  const { busy, error, run } = useRequest()
  const [status, setStatus] = useState('')
  return <div className="guest-controls"><p className="fine-print">{expiresAt ? `This guest check expires ${new Date(expiresAt).toLocaleString()}. ` : ''}Closing this page loses access. Download a copy to keep it.</p><button className="secondary" disabled={disabled || busy} onClick={() => void run(async () => { downloadJson(await api.exportCheck(session, token), 'petadvice-guest-check.json'); setStatus('Your guest check has been downloaded.') })}>Download this guest check</button><button className="secondary" disabled={disabled || busy} onClick={() => void run(async () => { await api.deleteGuestCheck(session, token); onDeleted() })}>Delete this guest check</button><p role="status">{status}</p><ErrorNotice message={error} /></div>
}

function Sources({ sources }: { sources: string[] }) {
  const links = sources.filter((source) => /^https?:\/\//.test(source))
  return links.length ? <details className="sources"><summary>Sources</summary><ul>{links.map((source) => <li key={source}><a href={source} target="_blank" rel="noopener noreferrer">{new URL(source).hostname} (opens a new tab)</a></li>)}</ul></details> : null
}

function Library({ species }: { species: Species }) {
  const [items, setItems] = useState<Condition[] | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let cancelled = false
    api.listConditions(species).then((data) => { if (!cancelled) setItems(data) })
      .catch((failure) => { if (!cancelled) setError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [species, retry])
  const filtered = items?.filter((item) => `${item.name} ${item.category.replaceAll('_', ' ')} ${(item.symptom_tags ?? []).join(' ').replaceAll('_', ' ')}`.toLowerCase().includes(query.toLowerCase())) ?? []
  return <section className="panel"><p className="eyebrow">Reference library</p><h1>Plain-language starting points</h1><p className="muted">Information for conversations with your vet. Beta content awaits veterinary review.</p>
    <label className="search-label">Search the library<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by symptom, name or category" /></label>
    {!items && !error && <p role="status">Loading the library…</p>}<ErrorNotice message={error} />
    {error && <button className="secondary" onClick={() => { setError(''); setRetry((value) => value + 1) }}>Try again</button>}
    {items && <p role="status">{filtered.length} {filtered.length === 1 ? 'entry' : 'entries'}</p>}
    {items && filtered.length === 0 && <p>No entries match your search. Try another word or contact your vet for concerns outside this library.</p>}
    <div className="entries">{filtered.map((item) => <details className="condition-entry" key={item.id}><summary aria-label={`Read about ${item.name}. ${urgencyLabels[item.urgency_default]}`}><span className="tag">{item.category.replaceAll('_', ' ')}</span><strong>{item.name}</strong><span className={`urgency-label ${item.urgency_default}`}>{urgencyLabels[item.urgency_default]}</span></summary>
      {item.home_care_guidance && <p>{item.home_care_guidance}</p>}{item.red_flags.length > 0 && <><h3>Signs that need prompt attention</h3><ul>{item.red_flags.map((flag) => <li key={flag.description}>{flag.description} — {urgencyLabels[flag.escalates_to]}</li>)}</ul></>}
      {item.prevention_tips && <p>{item.prevention_tips}</p>}<p className="fine-print">{item.vet_reviewed_by && item.last_reviewed_date ? `Reviewed by ${item.vet_reviewed_by} on ${item.last_reviewed_date}.` : 'Awaiting veterinary review.'}</p><Sources sources={item.sources} />
    </details>)}</div>
  </section>
}

function Care({ pet, species = pet?.species ?? 'dog' }: { pet?: Pet; species?: Species }) {
  const [items, setItems] = useState<PreventiveCareItem[] | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    let cancelled = false
    api.listPreventive(species, pet?.life_stage ?? null).then((data) => { if (!cancelled) setItems(data) })
      .catch((failure) => { if (!cancelled) setError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [species, pet?.life_stage, retry])
  return <section className="panel"><p className="eyebrow">Preventive care</p><h1>Small check-ins, less worry.</h1><p className="muted">{pet?.life_stage ? `Based on ${pet.name}'s ${pet.life_stage.replaceAll('_', ' ')} life stage.` : pet ? `Showing all available ${species} care information because ${pet.name}'s age is unknown. Ask your vet which items apply.` : `Showing all available ${species} care information. Ask your vet which items apply to your pet's age and circumstances.`} This is information, with no scheduled reminders yet.</p>
    {!items && !error && <p role="status">Loading care information…</p>}<ErrorNotice message={error} />{error && <button className="secondary" onClick={() => { setError(''); setRetry((value) => value + 1) }}>Try again</button>}
    {items?.length === 0 && <p>No care items are published for this life stage yet. Ask your vet about routine check-ups, vaccinations, parasite prevention and dental care.</p>}
    <div className="care-list">{items?.map((item) => <article key={item.id}><div><h3>{item.title}</h3><p>{item.description}</p>{item.recurrence && <p className="recurrence">Timing: {item.recurrence}</p>}<Sources sources={item.sources} /></div></article>)}</div>
  </section>
}

function Account({ onDeleted }: { onDeleted: () => void }) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [password, setPassword] = useState('')
  const { busy, error, run } = useRequest()
  const [status, setStatus] = useState('')
  function exportData() {
    void run(async () => {
      await api.reauthenticate(password)
      downloadJson(await api.exportMyData(), 'petadvice-data.json')
      setPassword('')
      setStatus('Your data export has been downloaded.')
    })
  }
  return <section className="panel"><p className="eyebrow">Account and privacy</p><h1>Your data, your choice.</h1><PrivacyNotice /><label className="security-password">Confirm your password for account controls<input type="password" autoComplete="current-password" maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /></label><button className="secondary" disabled={busy || !password} onClick={exportData}>Download my data</button><button className="secondary" disabled={busy || !password} onClick={() => void run(async () => { await api.reauthenticate(password); await api.logoutAll(); onDeleted() })}>Log out all devices</button><p role="status">{status}</p><ErrorNotice message={error} />
    <div className="delete-account"><h3>Delete account</h3><p>This permanently removes your account, pet profiles and associated checks from the app database.</p>
      {!confirmDelete ? <button className="secondary" disabled={busy} onClick={() => setConfirmDelete(true)}>Delete my account…</button> : <><p role="alert">This cannot be undone. Download your data first if you want a copy.</p><button className="danger" disabled={busy || !password} onClick={() => void run(async () => { await api.reauthenticate(password); await api.deleteMyAccount(); onDeleted() })}>Permanently delete my account</button><button className="secondary" disabled={busy} onClick={() => setConfirmDelete(false)}>Cancel</button></>}
    </div>
  </section>
}

function Emergency() {
  return <aside className="emergency" aria-label="Emergency warning"><span className="pulse" aria-hidden="true">!</span><div><strong>Go straight to a vet</strong><span>Breathing trouble, collapse, seizures, uncontrolled bleeding, or straining with no urine.</span></div></aside>
}

export default App
