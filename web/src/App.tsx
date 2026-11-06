import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, careTopics, type Condition, type Owner, type Privacy, type Pet, type Question, type Species, type TriageResult, type PreventiveCareItem } from './api'
import AccountLink from './AccountLink'
import CheckResult from './CheckResult'
import CheckHistory from './CheckHistory'
import { CareGuides, StartCheckButtons } from './CareGuides'
import { checkSymptoms } from './symptoms'
import { downloadFile, downloadJson } from './download'
import { buildCareReminderIcs, reminderFileName, tomorrow } from './careReminders'
import { errorMessage, useRequest } from './useRequest'
import { formatDate, languages, readable, serverText, useI18n } from './i18n'
import { lifeStageLabel } from './checkReport'
import fullLogo from './assets/brand/Logo_new.png'
import nameLogo from './assets/brand/Logo_Just_Name.png'
import petsLogo from './assets/brand/Logo_Just_Pets.png'
import './App.css'

type View = 'triage' | 'library' | 'care' | 'history' | 'account'

function ErrorNotice({ message }: { message: string }) {
  return message ? <p className="error" role="alert">{message}</p> : null
}

function LanguageSwitch() {
  const { language, t, setLanguage } = useI18n()
  return <div className="language-switch" role="group" aria-label={t.language}>{languages.map((item) => <button key={item.code} type="button" lang={item.code} aria-label={item.label} title={item.label} aria-pressed={language === item.code} onClick={() => setLanguage(item.code)}>{item.code.toUpperCase()}</button>)}</div>
}

function App() {
  const { t } = useI18n()
  const guestOnlyPreview = import.meta.env.VITE_GUEST_ONLY_PREVIEW === 'true'
  const [accountLink, setAccountLink] = useState(() => {
    if (guestOnlyPreview) return null
    const values = new URLSearchParams(window.location.hash.slice(1))
    const action = values.get('action'), token = values.get('token')
    return (action === 'verify' || action === 'reset') && token ? { action, token } as { action: 'verify' | 'reset'; token: string } : null
  })
  const [owner, setOwner] = useState<Owner | null>(null)
  const [auth, setAuth] = useState<'checking' | 'signed-in' | 'guest' | 'error'>(guestOnlyPreview ? 'guest' : 'checking')
  const [view, setView] = useState<View>('triage')
  const [pets, setPets] = useState<Pet[]>([])
  const [selectedPetId, setSelectedPetId] = useState<string | null>(null)
  const [showPetForm, setShowPetForm] = useState(false)
  const [showAuth, setShowAuth] = useState(false)
  const [showQuickCheck, setShowQuickCheck] = useState(false)
  const [publicView, setPublicView] = useState<'library' | 'care' | null>(null)
  const [checkRequest, setCheckRequest] = useState<{ symptom: string; species: Species; id: number } | null>(null)
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
    if (guestOnlyPreview) return
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
  }, [load, guestOnlyPreview])

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

  function startCheck(symptom: string, species: Species) {
    setCheckRequest({ symptom, species, id: Date.now() })
    if (auth === 'guest') { setPublicView(null); setShowQuickCheck(true) } else setView('triage')
    window.scrollTo(0, 0)
  }

  function retryLoad() { setLoadError(''); setPetsLoaded(false); setAuth('checking'); setLoad((count) => count + 1) }

  if (accountLink) return <Shell><AccountLink {...accountLink} onDone={() => { setAccountLink(null); setShowAuth(true); retryLoad() }} /><Emergency /></Shell>

  if (auth === 'checking' || (auth === 'signed-in' && !petsLoaded)) return <Shell><p role="status">{t.app.loadingAccount}</p><Emergency /></Shell>
  if (auth === 'error' || loadError) return <Shell><h1>{t.app.loadErrorTitle}</h1><ErrorNotice message={loadError || t.app.loadErrorDetail} /><button className="primary" onClick={retryLoad}>{t.common.tryAgain}</button><Emergency /></Shell>
  if (auth === 'guest') {
    if (showAuth) return <AuthPanel onBack={() => setShowAuth(false)} onAuthenticated={() => { setShowAuth(false); setShowQuickCheck(false); retryLoad() }} />
    if (showQuickCheck) return <Shell onBack={() => { setShowQuickCheck(false); setCheckRequest(null) }}><Triage key={checkRequest?.id} pet={null} initialSymptom={checkRequest?.symptom} initialSpecies={checkRequest?.species} onLogin={guestOnlyPreview ? undefined : () => setShowAuth(true)} /><Emergency /></Shell>
    if (publicView) return <PublicEducation initialView={publicView} onBack={() => setPublicView(null)} onStartCheck={startCheck} />
    return <PublicLanding onBrowse={setPublicView} onQuickCheck={() => { setCheckRequest(null); setShowQuickCheck(true) }} onLogin={guestOnlyPreview ? undefined : () => setShowAuth(true)} />
  }

  if (owner?.email_verification_required && !owner.email_verified_at) return <Shell><VerificationNotice email={owner.email} onLogout={resetAccount} /><Account onDeleted={resetAccount} /><Emergency /></Shell>

  if ((!pet || showPetForm) && view !== 'account') return <Shell onBack={pet ? () => setShowPetForm(false) : undefined}>
    <section className="welcome"><p className="eyebrow">{pet ? t.petForm.eyebrowAnother : t.petForm.eyebrowFirst}</p>
      <h1>{t.petForm.title}</h1><p className="lead">{t.petForm.lead}</p>
      <form className="profile-form" onSubmit={createPet} aria-busy={busy}>
        <label>{t.petForm.name}<input name="name" required maxLength={100} placeholder={t.petForm.namePlaceholder} /></label>
        <label>{t.petForm.species}<select name="species"><option value="dog">{t.species.dog}</option><option value="cat">{t.species.cat}</option></select></label>
        <label>{t.petForm.dateOfBirth}<input name="date_of_birth" type="date" max={today} /></label>
        <label>{t.petForm.sex}<select name="sex"><option value="">{t.common.unknown}</option><option value="female">{t.petForm.female}</option><option value="male">{t.petForm.male}</option></select></label>
        <label>{t.petForm.neutered}<select name="neutered"><option value="">{t.common.unknown}</option><option value="yes">{t.common.yes}</option><option value="no">{t.common.no}</option></select></label>
        <label>{t.petForm.breedSize}<select name="breed_size"><option value="">{t.petForm.unknownOrCat}</option><option value="small">{t.petForm.small}</option><option value="medium">{t.petForm.medium}</option><option value="large">{t.petForm.large}</option><option value="giant">{t.petForm.giant}</option></select></label>
        <button className="primary" disabled={busy}>{busy ? t.petForm.saving : t.petForm.create}</button>
      </form><ErrorNotice message={error} />
      {!pet && <button className="secondary" onClick={() => setView('account')}>{t.petForm.accountPrivacy}</button>}
    </section><Emergency />
  </Shell>

  return <main className="shell">
    <header><img className="name-logo" src={nameLogo} alt="PETAdvice" /><LanguageSwitch /><div className="header-actions">
      {pet && <label className="pet-switcher"><img className="pets-logo" src={petsLogo} alt="" /><span className="pet-switcher-copy"><strong>{pet.name}</strong><small>{pet.life_stage ? lifeStageLabel(t, pet.life_stage) : t.app.ageUnknown}</small></span><select aria-label={t.app.changePet} value={pet.id} onChange={(event) => setSelectedPetId(event.target.value)}>{pets.map((item) => <option value={item.id} key={item.id}>{item.name} ({t.speciesLower[item.species]})</option>)}</select><span className="switcher-chevron" aria-hidden="true">⌄</span></label>}
      <button className="start-fresh" onClick={() => { setShowPetForm(true); setView('triage') }}>{t.app.newPet}</button>
      <button className="start-fresh" disabled={busy} onClick={() => void run(async () => { await api.logout(); resetAccount() })}>{t.common.logOut}</button>
    </div></header>
    <nav className="tabs" aria-label={t.app.mainNavigation}>{(['triage', 'library', 'care', 'history', 'account'] as View[]).map((item) => <button aria-current={view === item ? 'page' : undefined} className={view === item ? 'active' : ''} onClick={() => { setView(item); setCheckRequest(null) }} key={item}>{t.app.tabs[item]}</button>)}</nav>
    <ErrorNotice message={error} />
    {view === 'triage' && pet && <Triage key={`${pet.id}-${checkRequest?.id ?? ''}`} pet={pet} initialSymptom={checkRequest?.species === pet.species ? checkRequest.symptom : undefined} />}
    {view === 'library' && pet && <Library key={pet.species} species={pet.species} onStartCheck={startCheck} />}
    {view === 'care' && pet && <Care key={pet.id} pet={pet} onStartCheck={startCheck} />}
    {view === 'history' && pet && <CheckHistory key={pet.id} pet={pet} />}
    {view === 'account' && <Account onDeleted={resetAccount} />}
    <Emergency />
  </main>
}

function Shell({ children, onBack }: { children: React.ReactNode; onBack?: () => void }) {
  const { t } = useI18n()
  return <main className="shell"><header><img className="name-logo" src={nameLogo} alt="PETAdvice" /><LanguageSwitch />{onBack && <button className="cancel-fresh" onClick={onBack}>{t.common.back}</button>}</header>{children}</main>
}

function PublicLanding({ onQuickCheck, onLogin, onBrowse }: { onQuickCheck: () => void; onLogin?: () => void; onBrowse: (view: 'library' | 'care') => void }) {
  const { t } = useI18n()
  const l = t.landing
  return <main className="shell landing"><header><img className="main-logo" src={fullLogo} alt={l.logoAlt} /><LanguageSwitch />{onLogin && <button className="start-fresh login-button" onClick={onLogin}>{l.login}</button>}</header>
    <section className="intro"><p className="eyebrow">{l.eyebrow}</p><h1>{l.title}</h1><p className="intro-lead">{l.lead}</p>
      <div className="intro-actions"><button className="primary" onClick={onQuickCheck}>{l.start} <span aria-hidden="true">→</span></button>{onLogin && <button className="secondary" onClick={onLogin}>{l.save}</button>}</div>
      <div className="public-links"><button className="secondary" onClick={() => onBrowse('library')}>{l.browseLearn}</button><button className="secondary" onClick={() => onBrowse('care')}>{l.browseCare}</button></div>
      <div className="intro-points"><article><span>01</span><div><h2>{l.point1Title}</h2><p>{l.point1Body}</p></div></article><article><span>02</span><div><h2>{l.point2Title}</h2><p>{l.point2Body}</p></div></article><article><span>03</span><div><h2>{l.point3Title}</h2><p>{onLogin ? l.point3Account : l.point3Guest}</p></div></article></div>
      <p className="intro-boundary">{l.boundary}</p>
    </section>
    {!onLogin && <aside className="beta-notice"><strong>{l.guestPreviewTitle}</strong><p>{l.guestPreviewBody}</p></aside>}
    {import.meta.env.VITE_ACCOUNTS_WITHOUT_EMAIL_PREVIEW === 'true' && <aside className="beta-notice"><strong>{import.meta.env.VITE_PUBLIC_TEST_BETA === 'true' ? l.testerBeta : l.accountPreview}</strong><p>{l.accountPreviewBody}</p></aside>}
    <Emergency />
  </main>
}

function PublicEducation({ initialView, onBack, onStartCheck }: { initialView: 'library' | 'care'; onBack: () => void; onStartCheck: StartCheck }) {
  const [view, setView] = useState(initialView)
  const [species, setSpecies] = useState<Species>('dog')
  const { t } = useI18n()
  return <Shell onBack={onBack}><nav className="tabs" aria-label={t.publicEducation.navigation}>{(['library', 'care'] as const).map((item) => <button key={item} aria-current={view === item ? 'page' : undefined} className={view === item ? 'active' : ''} onClick={() => setView(item)}>{item === 'library' ? t.publicEducation.learn : t.publicEducation.care}</button>)}</nav>
    <label className="guest-species">{t.publicEducation.browseFor}<select value={species} onChange={(event) => setSpecies(event.target.value as Species)}><option value="dog">{t.speciesPlural.dog}</option><option value="cat">{t.speciesPlural.cat}</option></select></label>
    {view === 'library' ? <Library key={species} species={species} onStartCheck={onStartCheck} /> : <Care key={species} species={species} onStartCheck={onStartCheck} />}<Emergency />
  </Shell>
}

function PrivacyNotice() {
  const guestOnlyPreview = import.meta.env.VITE_GUEST_ONLY_PREVIEW === 'true'
  const [notice, setNotice] = useState<Privacy | null>(null)
  const { t } = useI18n()
  const p = t.privacy
  useEffect(() => { let active = true; api.privacy().then((data) => { if (active) setNotice(data) }).catch(() => {}); return () => { active = false } }, [])
  if (guestOnlyPreview) return <details className="privacy-notice"><summary>{p.summary}</summary><p>{p.guestStores}</p><p>{notice ? p.guestRetention(notice.guest_retention_hours) : p.guestRetentionUnknown} {p.guestControls}</p><p>{p.guestDraft}</p></details>
  return <details className="privacy-notice"><summary>{p.summary}</summary><p>{p.accountStores}</p><p>{notice ? p.accountRetention(notice.guest_retention_hours) : p.accountRetentionUnknown} {p.closingLoses}</p><p>{p.accountKept}</p>{notice?.policy_url && /^https:\/\//.test(notice.policy_url) ? <p><a href={notice.policy_url} target="_blank" rel="noopener noreferrer">{p.readPolicy}</a> · {notice.operator}{notice.contact && <> · <a href={`mailto:${notice.contact}`}>{notice.contact}</a></>}</p> : <p>{p.betaHosting}</p>}<p>{p.noSensitive}</p></details>
}

function VerificationNotice({ email, onLogout }: { email: string; onLogout: () => void }) {
  const { busy, error, run } = useRequest()
  const [status, setStatus] = useState('')
  const { t } = useI18n()
  const v = t.verification
  return <section className="panel"><h1>{v.title}</h1><p>{v.body(email)}</p><button className="primary" disabled={busy} onClick={() => void run(async () => { setStatus(serverText((await api.resendVerification(email)).message)) })}>{v.resend}</button><button className="secondary" onClick={() => window.location.reload()}>{v.verified}</button><button className="secondary" disabled={busy} onClick={() => void run(async () => { await api.logout(); onLogout() })}>{t.common.logOut}</button><p role="status">{status}</p><ErrorNotice message={error} /></section>
}

function AuthPanel({ onBack, onAuthenticated }: { onBack: () => void; onAuthenticated: () => void }) {
  const withoutEmail = import.meta.env.VITE_ACCOUNTS_WITHOUT_EMAIL_PREVIEW === 'true'
  const [mode, setMode] = useState<'login' | 'signup' | 'forgot'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [privacyAccepted, setPrivacyAccepted] = useState(false)
  const [status, setStatus] = useState('')
  const { busy, error, run, setError } = useRequest()
  const { t } = useI18n()
  const a = t.auth
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void run(async () => {
      if (mode === 'forgot') { setStatus(serverText((await api.forgotPassword(email)).message)); return }
      if (mode === 'login') await api.login(email, password)
      else await api.signup(email, password, privacyAccepted)
      onAuthenticated()
    })
  }
  return <Shell onBack={onBack}><section className="welcome auth-panel"><p className="eyebrow">{a.eyebrow}</p><h1>{mode === 'login' ? a.welcomeBack : mode === 'forgot' ? a.recover : a.create}</h1><p className="lead">{mode === 'forgot' ? a.leadForgot : a.lead}</p>
    {withoutEmail && <p role="note">{a.noEmailNote}</p>}
    <form className="profile-form auth-form" onSubmit={submit} aria-busy={busy}>
      <label>{a.email}<input name="email" type="email" autoComplete="username" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} /></label>
      {mode !== 'forgot' && <label>{a.password}<input name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'signup' ? 15 : 1} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} />{mode === 'signup' && <small>{a.passwordHint}</small>}</label>}
      {mode === 'signup' && <><PrivacyNotice /><label className="check"><input type="checkbox" required checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} /> {a.acceptNotice}</label></>}
      <button className="primary" disabled={busy}>{busy ? t.common.pleaseWait : mode === 'login' ? a.submitLogin : mode === 'forgot' ? a.submitForgot : a.submitCreate}</button>
    </form><p role="status">{status}</p><ErrorNotice message={error} /><button className="secondary" disabled={busy} onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); setPassword(''); setStatus('') }}>{mode === 'login' ? a.createAccount : a.backToLogin}</button>{mode === 'login' && !withoutEmail && <button className="secondary" onClick={() => { setMode('forgot'); setError(''); setPassword(''); setStatus('') }}>{a.forgot}</button>}
  </section><Emergency /></Shell>
}

type StartCheck = (symptom: string, species: Species) => void

function Triage({ pet, onLogin, initialSymptom, initialSpecies }: { pet: Pet | null; onLogin?: () => void; initialSymptom?: string; initialSpecies?: Species }) {
  const [symptom, setSymptom] = useState(initialSymptom ?? '')
  const [species, setSpecies] = useState<Species>(initialSpecies ?? 'dog')
  const [question, setQuestion] = useState<Question | null>(null)
  const [session, setSession] = useState('')
  const [guestToken, setGuestToken] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [complete, setComplete] = useState(false)
  const [result, setResult] = useState<TriageResult | null>(null)
  const { busy, error, run, setError } = useRequest()
  const { t } = useI18n()
  const tr = t.triage
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
    {onLogin && <button className="primary" onClick={onLogin}>{tr.createAccountCta}</button>}
    <button className="secondary" onClick={restart}>{tr.startAnother}</button>
    {guestControls}
  </CheckResult>
  if (complete) return <section className="panel"><h1 ref={heading} tabIndex={-1}>{tr.complete}</h1><p role="status">{busy ? tr.loadingGuidance : tr.guidanceNotLoaded}</p><ErrorNotice message={error} /><button className="primary" disabled={busy} onClick={() => void run(async () => { setResult(await api.result(session, guestToken)) })}>{tr.retryGuidance}</button>{guestControls}</section>
  if (question) return <section className="question" aria-busy={busy}><div className="progress">{tr.checkFor(pet?.name ?? tr.yourSpecies(t.speciesLower[species]))} <span>{tr.adaptive}</span></div><h1 ref={heading} tabIndex={-1}>{question.prompt}</h1><div className="options">{question.options.map((option, index) => <button disabled={busy} className="option" onClick={() => answer(option)} key={option}>{question.option_labels?.[index] ?? option}<span aria-hidden="true">→</span></button>)}</div><p role="status">{busy ? tr.savingAnswer : ''}</p><ErrorNotice message={error} /><button className="secondary" disabled={busy} onClick={restart}>{tr.restart}</button>{guestControls}</section>
  return <section className="panel" aria-busy={busy}><p className="eyebrow">{tr.eyebrow}</p><h1>{tr.title}</h1><p className="muted">{pet ? tr.checkingFor(pet.name) : ''}{tr.choose}</p>
    {!pet && <label className="guest-species">{tr.whoFor}<select disabled={busy} value={species} onChange={(event) => { setSpecies(event.target.value as Species); setSymptom(''); setError('') }}><option value="dog">{t.species.dog}</option><option value="cat">{t.species.cat}</option></select></label>}
    <div className="symptoms">{checkSymptoms.filter((item) => !item.only || item.only === activeSpecies).map((item) => <button disabled={busy} aria-pressed={symptom === item.value} className={symptom === item.value ? 'selected' : ''} onClick={() => setSymptom(item.value)} key={item.value}>{t.symptoms[item.value]}<span aria-hidden="true">＋</span></button>)}</div>
    <button className="primary wide" disabled={!symptom || busy} onClick={begin}>{busy ? tr.starting : tr.continue}</button><ErrorNotice message={error} />
    <p className="fine-print">{tr.finePrint}</p>
    {!pet && <PrivacyNotice />}
  </section>
}

function GuestControls({ session, token, expiresAt, disabled, onDeleted }: { session: string; token: string; expiresAt: string | null; disabled: boolean; onDeleted: () => void }) {
  const { busy, error, run } = useRequest()
  const [status, setStatus] = useState('')
  const { t } = useI18n()
  const g = t.guest
  return <div className="guest-controls"><p className="fine-print">{expiresAt ? g.expires(formatDate(expiresAt)) : ''}{g.closingLoses}</p><button className="secondary" disabled={disabled || busy} onClick={() => void run(async () => { downloadJson(await api.exportCheck(session, token), 'petadvice-guest-check.json'); setStatus(g.downloaded) })}>{g.download}</button><button className="secondary" disabled={disabled || busy} onClick={() => void run(async () => { await api.deleteGuestCheck(session, token); onDeleted() })}>{g.delete}</button><p role="status">{status}</p><ErrorNotice message={error} /></div>
}

function Sources({ sources }: { sources: string[] }) {
  const { t } = useI18n()
  const links = sources.filter((source) => /^https?:\/\//.test(source))
  return links.length ? <details className="sources"><summary>{t.common.sources}</summary><ul>{links.map((source) => <li key={source}><a href={source} target="_blank" rel="noopener noreferrer">{t.common.opensNewTab(new URL(source).hostname)}</a></li>)}</ul></details> : null
}

function Library({ species, onStartCheck }: { species: Species; onStartCheck?: StartCheck }) {
  const [items, setItems] = useState<Condition[] | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const { language, t } = useI18n()
  const lib = t.library
  useEffect(() => {
    let cancelled = false
    api.listConditions(species).then((data) => { if (!cancelled) { setItems(data); setError('') } })
      .catch((failure) => { if (!cancelled) setError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [species, retry, language])
  const category = (value: string) => t.category[value] ?? readable(value)
  const filtered = items?.filter((item) => `${item.name} ${category(item.category)} ${(item.symptom_tags ?? []).map((tag) => `${t.symptoms[tag] ?? ''} ${readable(tag)}`).join(' ')}`.toLocaleLowerCase(language).includes(query.toLocaleLowerCase(language))) ?? []
  return <section className="panel"><p className="eyebrow">{lib.eyebrow}</p><h1>{lib.title}</h1><p className="muted">{lib.muted}</p>
    <label className="search-label">{lib.search}<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={lib.searchPlaceholder} /></label>
    {!items && !error && <p role="status">{lib.loading}</p>}<ErrorNotice message={error} />
    {error && <button className="secondary" onClick={() => { setError(''); setRetry((value) => value + 1) }}>{t.common.tryAgain}</button>}
    {items && <p role="status">{lib.entries(filtered.length)}</p>}
    {items && filtered.length === 0 && <p>{lib.noMatch}</p>}
    <div className="entries">{filtered.map((item) => <details className="condition-entry" key={item.id}><summary aria-label={lib.readAbout(item.name, t.urgency[item.urgency_default])}><span className="tag">{category(item.category)}</span><strong>{item.name}</strong><span className={`urgency-label ${item.urgency_default}`}>{t.urgency[item.urgency_default]}</span></summary>
      {item.home_care_guidance && <p>{item.home_care_guidance}</p>}{item.red_flags.length > 0 && <><h3>{lib.promptSigns}</h3><ul>{item.red_flags.map((flag) => <li key={flag.description}>{flag.description} — {t.urgency[flag.escalates_to]}</li>)}</ul></>}
      {item.prevention_tips && <p>{item.prevention_tips}</p>}<CareGuides items={item.related_care_items} heading={lib.careGuides} level="h3" /><StartCheckButtons symptoms={item.symptom_tags ?? []} species={species} onStartCheck={onStartCheck} /><p className="fine-print">{item.vet_reviewed_by && item.last_reviewed_date ? lib.reviewed(item.vet_reviewed_by, item.last_reviewed_date) : lib.awaiting}</p><Sources sources={item.sources} />
    </details>)}</div>
  </section>
}

const OTHER_CARE_TOPIC = 'other'

/** Group care guides by topic in a fixed, meaningful order; unknown topics go last. */
function groupCareItems(items: PreventiveCareItem[]) {
  const order: string[] = [...careTopics]
  const groups = new Map<string, PreventiveCareItem[]>()
  for (const item of items) {
    const topic = item.topic && order.includes(item.topic) ? item.topic : OTHER_CARE_TOPIC
    groups.set(topic, [...(groups.get(topic) ?? []), item])
  }
  return [...order, OTHER_CARE_TOPIC].filter((topic) => groups.has(topic)).map((topic) => ({ topic, items: groups.get(topic) ?? [] }))
}

function Care({ pet, species = pet?.species ?? 'dog', onStartCheck }: { pet?: Pet; species?: Species; onStartCheck?: StartCheck }) {
  const [items, setItems] = useState<PreventiveCareItem[] | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [openIds, setOpenIds] = useState<Set<string>>(() => new Set())
  const [reminderStatus, setReminderStatus] = useState('')
  const { language, t } = useI18n()
  const c = t.care
  const allOpen = !!items?.length && items.every((item) => openIds.has(item.id))
  function setItemOpen(id: string, open: boolean) {
    setOpenIds((current) => {
      if (current.has(id) === open) return current
      const next = new Set(current)
      if (open) next.add(id)
      else next.delete(id)
      return next
    })
  }
  function addReminder(item: PreventiveCareItem) {
    const steps = item.steps ?? []
    const body = steps.length ? [item.summary ?? '', ...steps.map((step, index) => `${index + 1}. ${step}`)] : [item.description]
    const description = [...body, item.recurrence ? c.timing(item.recurrence) : '', c.reminderFooter].filter(Boolean).join('\n')
    const ics = buildCareReminderIcs({ id: item.id, title: c.reminderTitle(item.title, pet?.name), description, intervalDays: item.reminder_interval_days, start: tomorrow() })
    downloadFile(ics, reminderFileName(item.id), 'text/calendar;charset=utf-8')
    setReminderStatus(c.reminderAdded(item.title))
  }
  useEffect(() => {
    let cancelled = false
    api.listPreventive(species, pet?.life_stage ?? null).then((data) => { if (!cancelled) { setItems(data); setError('') } })
      .catch((failure) => { if (!cancelled) setError(errorMessage(failure)) })
    return () => { cancelled = true }
  }, [species, pet?.life_stage, retry, language])
  return <section className="panel"><p className="eyebrow">{c.eyebrow}</p><h1>{c.title}</h1><p className="muted">{pet?.life_stage ? c.basedOn(pet.name, lifeStageLabel(t, pet.life_stage)) : pet ? c.unknownAge(species, pet.name) : c.all(species)} {c.noReminders}</p>
    {!items && !error && <p role="status">{c.loading}</p>}<ErrorNotice message={error} />{error && <button className="secondary" onClick={() => { setError(''); setRetry((value) => value + 1) }}>{t.common.tryAgain}</button>}
    {items?.length === 0 && <p>{c.empty}</p>}
    {!!items?.length && <div className="care-toolbar"><button type="button" className="secondary" aria-expanded={allOpen} onClick={() => setOpenIds(allOpen ? new Set() : new Set(items.map((item) => item.id)))}>{allOpen ? c.collapseAll : c.expandAll}</button></div>}
    <p className="care-reminder-status" role="status">{reminderStatus}</p>
    <div className="care-list">{groupCareItems(items ?? []).map(({ topic, items: group }) => <section key={topic} className="care-topic" aria-labelledby={`care-topic-${topic}`}><h2 id={`care-topic-${topic}`}>{c.topics[topic] ?? c.otherTopic}</h2>
      {group.map((item) => {
        const steps = item.steps ?? []
        const lead = item.summary || (steps.length ? null : item.description)
        return <details key={item.id} className="care-item" open={openIds.has(item.id)} onToggle={(event) => setItemOpen(item.id, event.currentTarget.open)}>
          <summary><h3>{item.title}</h3>{lead && <p>{lead}</p>}</summary>
          <div className="care-item-body">
            {steps.length > 0 && <ol className="care-steps" aria-label={c.steps}>{steps.map((step) => <li key={step}>{step}</li>)}</ol>}
            {!!item.summary && steps.length === 0 && <p>{item.description}</p>}
            {item.recurrence && <p className="recurrence">{c.timing(item.recurrence)}</p>}
            {item.recurrence && <button type="button" className="secondary care-reminder" onClick={() => addReminder(item)}>{c.addReminder}</button>}
            <StartCheckButtons symptoms={item.related_symptoms ?? []} species={species} onStartCheck={onStartCheck} /><Sources sources={item.sources} />
          </div>
        </details>
      })}
    </section>)}</div>
  </section>
}

function Account({ onDeleted }: { onDeleted: () => void }) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [password, setPassword] = useState('')
  const { busy, error, run } = useRequest()
  const [status, setStatus] = useState('')
  const { t } = useI18n()
  const a = t.account
  function exportData() {
    void run(async () => {
      await api.reauthenticate(password)
      downloadJson(await api.exportMyData(), 'petadvice-data.json')
      setPassword('')
      setStatus(a.downloaded)
    })
  }
  return <section className="panel"><p className="eyebrow">{a.eyebrow}</p><h1>{a.title}</h1><PrivacyNotice /><label className="security-password">{a.confirmPassword}<input type="password" autoComplete="current-password" maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /></label><button className="secondary" disabled={busy || !password} onClick={exportData}>{a.download}</button><button className="secondary" disabled={busy || !password} onClick={() => void run(async () => { await api.reauthenticate(password); await api.logoutAll(); onDeleted() })}>{a.logoutAll}</button><p role="status">{status}</p><ErrorNotice message={error} />
    <div className="delete-account"><h3>{a.deleteTitle}</h3><p>{a.deleteBody}</p>
      {!confirmDelete ? <button className="secondary" disabled={busy} onClick={() => setConfirmDelete(true)}>{a.deleteStart}</button> : <><p role="alert">{a.deleteWarning}</p><button className="danger" disabled={busy || !password} onClick={() => void run(async () => { await api.reauthenticate(password); await api.deleteMyAccount(); onDeleted() })}>{a.deleteConfirm}</button><button className="secondary" disabled={busy} onClick={() => setConfirmDelete(false)}>{t.common.cancel}</button></>}
    </div>
  </section>
}

function Emergency() {
  const { t } = useI18n()
  return <aside className="emergency" aria-label={t.emergency.label}><span className="pulse" aria-hidden="true">!</span><div><strong>{t.emergency.title}</strong><span>{t.emergency.body}</span></div></aside>
}

export default App
