import { useEffect, useState } from 'react'
import { api, clearToken, getToken, setToken, type Condition, type Pet, type Question, type TriageResult } from './api'
import fullLogo from './assets/brand/Logo_new.png'
import nameLogo from './assets/brand/Logo_Just_Name.png'
import petsLogo from './assets/brand/Logo_Just_Pets.png'
import './App.css'

type View = 'triage' | 'library' | 'care'

function App() {
  const [authenticated, setAuthenticated] = useState(false)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [view, setView] = useState<View>('triage')
  const [error, setError] = useState('')
  const [pets, setPets] = useState<Pet[]>([])
  const [selectedPetId, setSelectedPetId] = useState<string | null>(null)
  const [showPetForm, setShowPetForm] = useState(false)
  const [showIntro, setShowIntro] = useState(true)
  const pet = pets.find((item) => item.id === selectedPetId) ?? pets[0] ?? null

  useEffect(() => {
    if (!getToken()) {
      setCheckingAuth(false)
      return
    }
    api.getMe().then(() => setAuthenticated(true)).catch(() => clearToken()).finally(() => setCheckingAuth(false))
  }, [])

  useEffect(() => {
    if (!authenticated) return
    api.listPets().then((loadedPets) => {
      setPets(loadedPets)
      setSelectedPetId(loadedPets[0]?.id ?? null)
    }).catch(() => setError('Your pets could not be loaded. Is the API running on port 8000?'))
  }, [authenticated])

  async function createPet(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    try {
      setError('')
      const created = await api.createPet({ name: form.get('name'), species: form.get('species'), date_of_birth: form.get('date_of_birth') || null, sex: form.get('sex') || null, neutered: form.get('neutered') === 'on', environment_factors: [] })
      setPets((currentPets) => [...currentPets, created])
      setSelectedPetId(created.id)
      setShowPetForm(false)
      setShowIntro(false)
    } catch { setError('The profile could not be saved. Is the API running on port 8000?') }
  }

  function logout() {
    clearToken()
    setAuthenticated(false)
    setPets([])
    setSelectedPetId(null)
    setShowIntro(false)
  }

  if (checkingAuth) return <main className="shell"><header><img className="main-logo" src={fullLogo} alt="PETAdvice dog and cat logo" /></header></main>
  if (!authenticated) return <AuthPanel onAuthenticated={() => { setAuthenticated(true); setShowIntro(false) }} />

  if (showIntro) return <main className="shell"><header><img className="main-logo" src={fullLogo} alt="PETAdvice dog and cat logo" /></header><section className="intro"><p className="eyebrow">Friendly guidance for everyday pet worries</p><h1>A clearer next step for your pet.</h1><p className="intro-lead">When something feels different, PETAdvice helps you work out what to look for, how urgently to act, and what to discuss with your vet.</p><div className="intro-points"><article><span>01</span><div><h2>Make sense of symptoms</h2><p>Find straightforward information about common concerns, without confusing medical language.</p></div></article><article><span>02</span><div><h2>Know how urgent it is</h2><p>Answer a few focused questions to decide whether to monitor at home or contact a vet.</p></div></article><article><span>03</span><div><h2>Keep care on track</h2><p>Get useful reminders shaped around your pet's age, lifestyle, and everyday needs.</p></div></article></div><p className="intro-boundary">It is a helpful starting point, not a diagnosis or a replacement for your veterinary practice.</p><div className="intro-actions">{pet ? <button className="primary intro-start" onClick={() => setShowIntro(false)}>Continue with {pet.name} <span>→</span></button> : <button className="primary intro-start" onClick={() => setShowPetForm(true)}>Create a pet profile <span>→</span></button>}{pet && <button className="secondary intro-secondary" onClick={() => { setShowIntro(false); setShowPetForm(true) }}>Add a new pet</button>}</div></section><Emergency /></main>

  if (!pet || showPetForm) return <main className="shell"><header><img className="name-logo" src={nameLogo} alt="PETAdvice" />{pet && <button className="cancel-fresh" onClick={() => { setShowPetForm(false); setError('') }}>Cancel</button>}</header><section className="welcome"><p className="eyebrow">{pet ? 'Add another companion' : 'Set up your first pet'}</p><h1>{pet ? 'Start a fresh profile.' : 'Tell us about your pet.'}</h1><p className="lead">{pet ? 'Create a separate profile so every check and care plan stays matched to the right pet.' : 'A few details help PETAdvice keep guidance relevant to your pet.'}</p><form className="profile-form" onSubmit={createPet}><label>Pet name<input name="name" required placeholder="e.g. Miso" /></label><label>Species<select name="species"><option value="dog">Dog</option><option value="cat">Cat</option></select></label><label>Date of birth<input name="date_of_birth" type="date" /></label><label>Sex<select name="sex"><option value="">Unknown</option><option value="female">Female</option><option value="male">Male</option></select></label><label className="check"><input name="neutered" type="checkbox" /> Spayed or neutered</label><button className="primary" type="submit">Create pet profile <span>→</span></button></form>{error && <p className="error">{error}</p>}</section><Emergency /></main>

  return <main className="shell"><Header pet={pet} pets={pets} onPetChange={setSelectedPetId} onStartFresh={() => { setShowPetForm(true); setShowIntro(false); setError('') }} onLogout={logout} /><nav className="tabs" aria-label="Main navigation">{(['triage', 'library', 'care'] as View[]).map((item) => <button className={view === item ? 'active' : ''} onClick={() => setView(item)} key={item}>{item === 'triage' ? 'What is happening?' : item === 'library' ? 'Learn' : 'Care plan'}</button>)}</nav>{view === 'triage' && <Triage pet={pet} />}{view === 'library' && <Library pet={pet} />}{view === 'care' && <Care pet={pet} />}<Emergency /></main>
}

function Header({ pet, pets, onPetChange, onStartFresh, onLogout }: { pet: Pet; pets: Pet[]; onPetChange: (petId: string) => void; onStartFresh: () => void; onLogout: () => void }) {
  return <header><img className="name-logo" src={nameLogo} alt="PETAdvice" /><div className="header-actions"><label className="pet-switcher"><img className="pets-logo" src={petsLogo} alt="" /><span className="pet-switcher-copy"><strong>{pet.name}</strong><small>{pet.life_stage?.replace('_', ' ') ?? 'profile'}</small></span><select aria-label="Change active pet" value={pet.id} onChange={(event) => onPetChange(event.target.value)}>{pets.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.species})</option>)}</select><span className="switcher-chevron">⌄</span></label><button className="start-fresh" onClick={onStartFresh}>＋ New pet</button><button className="start-fresh" onClick={onLogout}>Log out</button></div></header>
}

function AuthPanel({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [privacyAccepted, setPrivacyAccepted] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    try {
      const response = mode === 'login'
        ? await api.login(email, password)
        : await api.signup(email, password, privacyAccepted)
      setToken(response.access_token)
      onAuthenticated()
    } catch {
      setError(mode === 'login' ? 'Incorrect email or password.' : 'Use a password of at least 8 characters and accept the privacy policy.')
    }
  }

  return <main className="shell"><header><img className="main-logo" src={fullLogo} alt="PETAdvice dog and cat logo" /></header><section className="welcome auth-panel"><p className="eyebrow">Private guidance for your pets</p><h1>{mode === 'login' ? 'Welcome back.' : 'Create your account.'}</h1><p className="lead">Your pet profiles and triage history stay tied to your account.</p><form className="profile-form auth-form" onSubmit={submit}><label>Email<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label><label>Password<input type="password" required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label>{mode === 'signup' && <label className="check"><input type="checkbox" checked={privacyAccepted} onChange={(event) => setPrivacyAccepted(event.target.checked)} /> I accept the Privacy Policy</label>}<button className="primary" type="submit">{mode === 'login' ? 'Log in' : 'Create account'} <span>→</span></button></form>{error && <p className="error">{error}</p>}<button className="secondary" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError('') }}>{mode === 'login' ? 'Create an account' : 'Already have an account? Log in'}</button></section><Emergency /></main>
}

function Triage({ pet }: { pet: Pet }) {
  const [symptom, setSymptom] = useState('')
  const [question, setQuestion] = useState<Question | null>(null)
  const [session, setSession] = useState('')
  const [result, setResult] = useState<TriageResult | null>(null)
  const symptoms = [{ value: 'straining_to_urinate', label: 'Straining to urinate' }, { value: 'vomiting', label: 'Vomiting' }, { value: 'diarrhea', label: 'Diarrhea' }, { value: 'limping', label: 'Limping after exercise' }, { value: 'reverse_sneezing', label: 'Reverse sneezing' }, { value: 'scratching', label: 'Scratching or fleas' }, { value: 'increased_thirst', label: 'Drinking more than usual' }, { value: 'vaginal_discharge', label: 'Unexpected discharge' }]
  async function begin() { const started = await api.startTriage(pet.id, symptom); setSession(started.session_id); if (started.flow_complete) setResult(await api.result(started.session_id)); else setQuestion(started.next_question) }
  async function answer(value: string) { if (!question) return; const next = await api.answer(session, question.id, value); if (next.flow_complete) setResult(await api.result(session)); else setQuestion(next.next_question) }
  if (result) return <section className={`result ${result.resulting_urgency}`}><p className="eyebrow">Guidance for {pet.name}</p><h1>{result.resulting_urgency.replaceAll('_', ' ')}</h1><p className="result-copy">{result.resulting_guidance}</p>{result.possible_causes.length > 0 && <div className="result-detail"><h2>Commonly associated with</h2><ul>{result.possible_causes.map((cause) => <li key={cause}>{cause}</li>)}</ul></div>}{result.recommended_examinations.length > 0 && <div className="result-detail"><h2>Your vet may want to check</h2><ul>{result.recommended_examinations.map((examination) => <li key={examination}>{examination}</li>)}</ul></div>}<p className="fine-print">General guidance only, not a diagnosis. Contact your veterinary practice if you are concerned.</p><button className="secondary" onClick={() => { setResult(null); setSession(''); setQuestion(null) }}>Start another check</button></section>
  if (question) return <section className="question"><div className="progress">Next question <span>Adaptive check</span></div><h2>{question.prompt}</h2><div className="options">{question.options.map((option) => <button className="option" onClick={() => answer(option)} key={option}>{option}<span>→</span></button>)}</div></section>
  return <section className="panel"><p className="eyebrow">Triage, without the guesswork</p><h2>What have you noticed?</h2><p className="muted">Choose the closest match. This check gives urgency guidance, not a diagnosis.</p><div className="symptoms">{symptoms.map((item) => <button className={symptom === item.value ? 'selected' : ''} onClick={() => setSymptom(item.value)} key={item.value}>{item.label}<span>＋</span></button>)}</div><button className="primary wide" disabled={!symptom} onClick={begin}>Continue <span>→</span></button></section>
}

function Library({ pet }: { pet: Pet }) { const [items, setItems] = useState<Condition[]>([]); useEffect(() => { api.listConditions(pet.species).then(setItems).catch(() => undefined) }, [pet.species]); return <section className="panel"><p className="eyebrow">Reference library</p><h2>Plain-language starting points</h2><p className="muted">A browsable guide for conversations with your vet.</p><div className="entries">{items.map((item) => <article key={item.id}><div><span className="tag">{item.category.replaceAll('_', ' ')}</span><h3>{item.name}</h3></div><span className={`urgency-dot ${item.urgency_default}`} /></article>)}</div></section> }

function Care({ pet }: { pet: Pet }) { const [items, setItems] = useState<Condition[]>([]); useEffect(() => { if (pet.life_stage) api.listPreventive(pet.species, pet.life_stage).then(setItems).catch(() => undefined) }, [pet]); return <section className="panel"><p className="eyebrow">Preventive care</p><h2>Small check-ins, less worry.</h2><p className="muted">Based on {pet.name}'s profile and current life stage.</p><div className="care-list">{items.map((item) => <article key={item.id}><span className="checkmark">✓</span><div><h3>{item.name}</h3><p>{item.prevention_tips ?? 'Discuss this item at your next veterinary appointment.'}</p></div></article>)}</div></section> }

function Emergency() { return <aside className="emergency"><span className="pulse">!</span><div><strong>Go straight to a vet</strong><span>Breathing trouble, collapse, seizures, uncontrolled bleeding, or straining with no urine.</span></div></aside> }

export default App
