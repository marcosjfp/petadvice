import { useSyncExternalStore } from 'react'

export type Language = 'en' | 'pt' | 'es'
export const languages: { code: Language; label: string }[] = [
  { code: 'en', label: 'English' }, { code: 'pt', label: 'Português' }, { code: 'es', label: 'Español' },
]
const dateLocales: Record<Language, string | undefined> = { en: undefined, pt: 'pt-PT', es: 'es-ES' }
const STORAGE_KEY = 'petadvice_language'

const en = {
  language: 'Language',
  common: {
    back: 'Back', tryAgain: 'Try again', logOut: 'Log out', cancel: 'Cancel', pleaseWait: 'Please wait…', yes: 'Yes', no: 'No', unknown: 'Unknown',
    sources: 'Sources', opensNewTab: (host: string) => `${host} (opens a new tab)`, notRecorded: 'Not recorded',
    startCheck: (symptom: string) => `Start a check: ${symptom}`,
  },
  species: { dog: 'Dog', cat: 'Cat' } as Record<string, string>,
  speciesLower: { dog: 'dog', cat: 'cat', both: 'dog or cat' } as Record<string, string>,
  speciesPlural: { dog: 'Dogs', cat: 'Cats' } as Record<string, string>,
  urgency: { monitor_home: 'Monitor at home', vet_soon: 'Book a vet appointment', vet_24h: 'Contact a vet within 24 hours', emergency_now: 'Emergency veterinary care now' },
  lifeStage: { puppy: 'puppy', kitten: 'kitten', young_adult: 'young adult', mature_adult: 'mature adult', senior: 'senior' } as Record<string, string>,
  sex: { male: 'male', female: 'female' } as Record<string, string>,
  breedSize: { small: 'small', medium: 'medium', large: 'large', giant: 'giant' } as Record<string, string>,
  category: {
    gastrointestinal: 'gastrointestinal', dermatological: 'skin', musculoskeletal: 'muscles and joints', dental_oral: 'teeth and mouth', ear_eye: 'ears and eyes',
    respiratory: 'breathing', urinary_reproductive: 'urinary and reproductive', parasites: 'parasites', behavioral: 'behaviour', weight_nutrition: 'weight and nutrition', emergency_trauma: 'emergency and injury',
  } as Record<string, string>,
  symptoms: {
    straining_to_urinate: 'Straining to urinate', vomiting: 'Vomiting', diarrhea: 'Diarrhea', limping: 'Limping after exercise', reverse_sneezing: 'Reverse sneezing',
    scratching: 'Scratching or fleas', scooting: 'Scooting or worms in stool', nervous_or_stressed: 'Nervous or stressed', increased_thirst: 'Drinking more than usual', vaginal_discharge: 'Unexpected discharge',
  } as Record<string, string>,
  app: {
    loadingAccount: 'Loading your account…', loadErrorTitle: 'We could not load your account.', loadErrorDetail: 'Check your connection and try again.',
    ageUnknown: 'Age unknown', changePet: 'Change active pet', newPet: 'New pet', mainNavigation: 'Main navigation',
    tabs: { triage: 'Check symptoms', library: 'Learn', care: 'Care plan', history: 'Check history', account: 'Account' },
  },
  petForm: {
    eyebrowAnother: 'Add another companion', eyebrowFirst: 'Set up your first pet', title: 'Tell us about your pet.',
    lead: 'A few details help keep guidance relevant. Leave anything you do not know as unknown.',
    name: 'Pet name', namePlaceholder: 'e.g. Miso', species: 'Species', dateOfBirth: 'Date of birth (optional)', sex: 'Sex', female: 'Female', male: 'Male',
    neutered: 'Spayed or neutered?', breedSize: 'Dog breed size (optional)', unknownOrCat: 'Unknown / cat', small: 'Small', medium: 'Medium', large: 'Large', giant: 'Giant',
    saving: 'Saving…', create: 'Create pet profile', accountPrivacy: 'Account and privacy',
  },
  landing: {
    logoAlt: 'PETAdvice dog and cat logo', login: 'Log in', eyebrow: 'Friendly guidance for everyday pet worries', title: 'A clearer next step for your pet.',
    lead: 'When something feels different, PETAdvice helps you work out what to look for, how urgently to act, and what to discuss with your vet.',
    start: 'Start a quick check', save: 'Save my pet profiles', browseLearn: 'Browse Learn', browseCare: 'Browse Care',
    point1Title: 'Make sense of symptoms', point1Body: 'Find straightforward information about common concerns.',
    point2Title: 'Know how urgent it is', point2Body: 'Answer focused questions to help decide when to contact a vet.',
    point3Title: 'Keep care on track', point3Account: 'Save pet profiles and browse care information for their life stage.', point3Guest: 'Browse preventive care information for dogs and cats.',
    boundary: "General educational guidance, not a diagnosis. This beta's content is awaiting veterinary review. No account is needed for a quick check.",
    guestPreviewTitle: 'Private guest preview', guestPreviewBody: 'Try symptom checks, Learn and Care. Accounts and email are unavailable in this preview. Use synthetic test information only.',
    testerBeta: 'Tester beta', accountPreview: 'Private account preview',
    accountPreviewBody: 'Accounts are available for testing. Email verification and password recovery are unavailable. Use a test email, fictional pet details and a password you do not use elsewhere.',
  },
  publicEducation: { navigation: 'Public learning navigation', learn: 'Learn', care: 'Care', browseFor: 'Browse information for' },
  privacy: {
    summary: 'How your data is used',
    guestStores: 'This private preview stores guest symptom checks. Accounts and email are disabled; use synthetic test information only.',
    guestRetention: (hours: number) => `Guest access expires after ${hours} hours. Scheduled cleanup removes expired checks.`,
    guestRetentionUnknown: 'Guest access is temporary; the retention notice could not be loaded.',
    guestControls: 'You can download or delete your check while it is open. Closing or refreshing the page loses access.',
    guestDraft: 'The privacy policy is still a draft. This preview is for private testing.',
    accountStores: 'The app stores your email, a password hash, pet profiles, symptom checks and security records. You can download account data or delete your account and its profiles and checks from the app database.',
    accountRetention: (hours: number) => `Guest checks expire after ${hours} hours and are removed by scheduled cleanup. You can also download or delete a guest check while it is open.`,
    accountRetentionUnknown: 'Guest checks have a limited retention period; the current notice could not be loaded.',
    closingLoses: 'Closing the page loses access to that guest check.',
    accountKept: 'Account data is kept until you delete the account. Backups follow the deployment operator’s separate retention schedule.',
    readPolicy: 'Read the privacy policy',
    betaHosting: 'This test beta uses Vercel hosting, Supabase database storage and Upstash for request limits and scheduled cleanup. The full privacy policy and operator contact are not yet published. Use a test email and fictional pet details only.',
    noSensitive: 'Do not enter personal or sensitive details in pet names.',
  },
  verification: {
    title: 'Check your email.', body: (email: string) => `Verify ${email} before saving pet profiles. Open the link in your verification email, then return here.`,
    resend: 'Resend verification email', verified: 'I have verified my email',
  },
  auth: {
    eyebrow: 'Private guidance for your pets', welcomeBack: 'Welcome back.', recover: 'Recover your account.', create: 'Create your account.',
    leadForgot: 'Enter your email to request a password reset link.', lead: 'Your pet profiles and checks stay tied to your account.',
    noEmailNote: 'Email verification and password recovery are unavailable in this test version. Keep your test password; the app cannot email a reset link.',
    email: 'Email', password: 'Password', passwordHint: 'Use 15–128 characters. A passphrase works well.', acceptNotice: 'I have read the beta data-use notice.',
    submitLogin: 'Log in', submitForgot: 'Send reset link', submitCreate: 'Create account', createAccount: 'Create an account', backToLogin: 'Back to log in', forgot: 'Forgot your password?',
  },
  triage: {
    createAccountCta: 'Create an account for future pet profiles', startAnother: 'Start another check', complete: 'Your questions are complete.',
    loadingGuidance: 'Loading guidance…', guidanceNotLoaded: 'Guidance could not be loaded yet.', retryGuidance: 'Try loading guidance again',
    checkFor: (name: string) => `Check for ${name}`, yourSpecies: (species: string) => `your ${species}`, adaptive: 'Adaptive questions', savingAnswer: 'Saving your answer…', restart: 'Restart this check',
    eyebrow: 'A calmer next step', title: 'What have you noticed?', checkingFor: (name: string) => `Checking symptoms for ${name}. `,
    choose: 'Choose the closest match. This check gives urgency guidance, not a diagnosis.', whoFor: 'Who is this check for?', starting: 'Starting your check…', continue: 'Continue',
    finePrint: 'Cannot find the symptom? Contact your veterinary practice. Breathing trouble or collapse needs emergency care immediately.',
    questionStep: (step: number, total?: number | null) => total ? `Question ${step} of ${total}` : `Question ${step}`,
    previous: 'Previous question', goingBack: 'Going back…',
  },
  guest: {
    expires: (date: string) => `This guest check expires ${date}. `, closingLoses: 'Closing this page loses access. Download the summary to keep it.',
    download: 'Download raw data (JSON)', downloaded: 'The raw data file has been downloaded.', delete: 'Delete this guest check',
    contextTitle: 'About your pet (optional)', contextHint: 'Some guidance depends on age, sex or spay/neuter status. Choose “Not sure” if you do not know.',
    age: 'Age', young: (species: string): string => species === 'cat' ? 'Kitten' : 'Puppy', adult: 'Adult', senior: 'Senior', notSure: 'Not sure',
    sex: 'Sex', female: 'Female', male: 'Male', neutered: 'Spayed or neutered',
    leaveTitle: 'Leave this check?', leaveBody: 'Guest checks are not saved. If you leave now, the answers and guidance for this check will be lost.',
    leaveResultBody: 'This guest check is not saved. Download the summary first if you want to keep it.', leave: 'Leave this check', stay: 'Stay on this check',
  },
  library: {
    eyebrow: 'Reference library', title: 'Plain-language starting points', muted: 'Information for conversations with your vet. Beta content awaits veterinary review.',
    search: 'Search the library', searchPlaceholder: 'Search by symptom, name or category', loading: 'Loading the library…',
    entries: (count: number) => `${count} ${count === 1 ? 'entry' : 'entries'}`,
    noMatch: 'No entries match your search. Try another word or contact your vet for concerns outside this library.',
    readAbout: (name: string, urgency: string) => `Read about ${name}. ${urgency}`, promptSigns: 'Signs that need prompt attention',
    reviewed: (by: string, date: string) => `Reviewed by ${by} on ${date}.`, awaiting: 'Awaiting veterinary review.', careGuides: 'Related care guides',
  },
  care: {
    eyebrow: 'Preventive care', title: 'Small check-ins, less worry.',
    basedOn: (name: string, stage: string) => `Based on ${name}'s ${stage} life stage.`,
    unknownAge: (species: string, name: string) => `Showing all available ${species} care information because ${name}'s age is unknown. Ask your vet which items apply.`,
    all: (species: string) => `Showing all available ${species} care information. Ask your vet which items apply to your pet's age and circumstances.`,
    noReminders: 'This is information, with no scheduled reminders yet.', loading: 'Loading care information…',
    empty: 'No care items are published for this life stage yet. Ask your vet about routine check-ups, vaccinations, parasite prevention and dental care.',
    timing: (value: string) => `Timing: ${value}`,
  },
  account: {
    eyebrow: 'Account and privacy', title: 'Your data, your choice.', confirmPassword: 'Confirm your password for account controls', download: 'Download my data',
    logoutAll: 'Log out all devices', downloaded: 'Your data export has been downloaded.', deleteTitle: 'Delete account',
    deleteBody: 'This permanently removes your account, pet profiles and associated checks from the app database.', deleteStart: 'Delete my account…',
    deleteWarning: 'This cannot be undone. Download your data first if you want a copy.', deleteConfirm: 'Permanently delete my account',
  },
  emergency: { label: 'Emergency warning', title: 'Go straight to a vet', body: 'Breathing trouble, collapse, seizures, uncontrolled bleeding, or straining with no urine.' },
  result: {
    summary: 'Check summary', eyebrow: (saved: boolean, name: string) => `${saved ? 'Saved check' : 'Guidance'} for ${name}`, yourPet: 'your pet',
    savedNotice: 'This is the guidance saved for this check, not a new assessment of your pet today.', nextStep: 'Your next step',
    symptom: 'Symptom:', started: 'Started:', preserved: 'Report preserved:', petContext: 'Pet context recorded:',
    ageUnknown: 'age unknown', sexLabel: 'sex', neuteredLabel: 'neutered', breedSizeSuffix: 'breed size', born: 'born',
    howDecided: 'How this was decided', answers: 'Your recorded answers', noAnswers: 'No questionnaire answers were recorded.',
    careGuides: 'Care guides for this situation', causes: 'Possible causes to discuss with your vet', exams: 'Your vet may want to check', sources: 'Sources recorded with this check',
    contentVersion: (version: string) => `Content version: ${version}`, contentVersionMissing: 'Not recorded for this older check',
    watchFor: 'Watch for these signs — contact a vet if…', contextNotes: 'Details that could change this guidance', adult: 'adult', technicalInfo: 'Technical information',
    print: 'Print / save PDF', downloadSummary: 'Download summary', summaryStays: 'The downloaded summary stays on your device. Share it only with someone you choose.',
    explanationGap: 'The original rule explanations were not recorded for this check.',
    historicalNotice: 'This is a saved check, not a new assessment. Older checks may not include the original pet context, sources or question wording.',
    boundary: 'General educational guidance, not a diagnosis. Beta content awaits veterinary review. This summary records this check; it does not assess later changes in symptoms. If your pet worsens or you are unsure, contact your veterinary practice.',
    reportTitle: 'PETAdvice check summary', lifeStage: 'Life stage', birthDate: 'Birth date', breedSize: 'Breed size', noContext: 'Original pet context was not recorded.',
  },
  history: {
    eyebrow: (name: string) => `Saved checks for ${name}`, title: 'Check history', muted: 'Revisit the guidance and answers recorded for earlier checks. If symptoms have changed, start a new check.',
    loading: 'Loading check history…', none: (name: string) => `No checks saved for ${name} yet. Complete a symptom check to see it here.`,
    guidanceNotSaved: 'Questions completed; guidance not yet saved', notCompleted: 'Questions not completed', view: 'View saved check',
    startNew: 'Start a new check if you still need guidance.', loadOlder: 'Load older checks', loadingSaved: 'Loading saved guidance…', back: 'Back to check history',
  },
  accountLink: {
    verifyTitle: 'Verify your email.', resetTitle: 'Choose a new password.', continue: 'Continue to sign in', newPassword: 'New password', hint: 'Use 15–128 characters.',
    confirm: 'Confirm new password', verify: 'Verify email', reset: 'Reset password', back: 'Back to sign in / request a new link', mismatch: 'The passwords do not match.',
  },
  errors: {
    generic: 'Something went wrong. Please try again.', requestFailed: 'The request could not be completed. Please try again.',
    timeout: 'The request timed out. Check your connection and try again.', network: 'Could not connect. Check your connection and try again.',
  },
  update: { ready: 'A new version of PETAdvice is ready.', refresh: 'Refresh', dismiss: 'Dismiss' },
  server: {} as Record<string, string>,
}

export type Messages = typeof en

const pt: Messages = {
  language: 'Idioma',
  common: {
    back: 'Voltar', tryAgain: 'Tentar novamente', logOut: 'Terminar sessão', cancel: 'Cancelar', pleaseWait: 'Aguarde…', yes: 'Sim', no: 'Não', unknown: 'Desconhecido',
    sources: 'Fontes', opensNewTab: (host) => `${host} (abre num novo separador)`, notRecorded: 'Não registado',
    startCheck: (symptom) => `Fazer uma verificação: ${symptom}`,
  },
  species: { dog: 'Cão', cat: 'Gato' },
  speciesLower: { dog: 'cão', cat: 'gato', both: 'cão ou gato' },
  speciesPlural: { dog: 'Cães', cat: 'Gatos' },
  urgency: { monitor_home: 'Vigiar em casa', vet_soon: 'Marcar consulta no veterinário', vet_24h: 'Contactar um veterinário nas próximas 24 horas', emergency_now: 'Urgência veterinária já' },
  lifeStage: { puppy: 'cachorro', kitten: 'gatinho', young_adult: 'adulto jovem', mature_adult: 'adulto maduro', senior: 'sénior' },
  sex: { male: 'macho', female: 'fêmea' },
  breedSize: { small: 'pequeno', medium: 'médio', large: 'grande', giant: 'gigante' },
  category: {
    gastrointestinal: 'gastrointestinal', dermatological: 'pele', musculoskeletal: 'músculos e articulações', dental_oral: 'dentes e boca', ear_eye: 'ouvidos e olhos',
    respiratory: 'respiração', urinary_reproductive: 'urinário e reprodutor', parasites: 'parasitas', behavioral: 'comportamento', weight_nutrition: 'peso e nutrição', emergency_trauma: 'urgência e lesões',
  },
  symptoms: {
    straining_to_urinate: 'Esforço para urinar', vomiting: 'Vómitos', diarrhea: 'Diarreia', limping: 'Coxeio depois do exercício', reverse_sneezing: 'Espirro invertido',
    scratching: 'Comichão ou pulgas', scooting: 'Arrasta o rabo ou vermes nas fezes', nervous_or_stressed: 'Nervoso ou stressado', increased_thirst: 'Bebe mais do que o habitual', vaginal_discharge: 'Corrimento inesperado',
  },
  app: {
    loadingAccount: 'A carregar a sua conta…', loadErrorTitle: 'Não foi possível carregar a sua conta.', loadErrorDetail: 'Verifique a ligação e tente novamente.',
    ageUnknown: 'Idade desconhecida', changePet: 'Mudar de animal', newPet: 'Novo animal', mainNavigation: 'Navegação principal',
    tabs: { triage: 'Verificar sintomas', library: 'Aprender', care: 'Plano de cuidados', history: 'Histórico', account: 'Conta' },
  },
  petForm: {
    eyebrowAnother: 'Adicionar outro companheiro', eyebrowFirst: 'Configure o seu primeiro animal', title: 'Fale-nos do seu animal.',
    lead: 'Alguns dados ajudam a manter as orientações relevantes. Deixe como desconhecido o que não souber.',
    name: 'Nome do animal', namePlaceholder: 'ex.: Miso', species: 'Espécie', dateOfBirth: 'Data de nascimento (opcional)', sex: 'Sexo', female: 'Fêmea', male: 'Macho',
    neutered: 'Esterilizado ou castrado?', breedSize: 'Porte da raça do cão (opcional)', unknownOrCat: 'Desconhecido / gato', small: 'Pequeno', medium: 'Médio', large: 'Grande', giant: 'Gigante',
    saving: 'A guardar…', create: 'Criar perfil do animal', accountPrivacy: 'Conta e privacidade',
  },
  landing: {
    logoAlt: 'Logótipo PETAdvice com cão e gato', login: 'Iniciar sessão', eyebrow: 'Orientação simpática para as preocupações do dia a dia', title: 'Um próximo passo mais claro para o seu animal.',
    lead: 'Quando algo parece diferente, o PETAdvice ajuda-o a perceber o que observar, com que urgência agir e o que falar com o seu veterinário.',
    start: 'Fazer uma verificação rápida', save: 'Guardar os perfis dos meus animais', browseLearn: 'Explorar Aprender', browseCare: 'Explorar Cuidados',
    point1Title: 'Perceber os sintomas', point1Body: 'Encontre informação simples sobre preocupações comuns.',
    point2Title: 'Saber a urgência', point2Body: 'Responda a perguntas concretas para decidir quando contactar um veterinário.',
    point3Title: 'Manter os cuidados em dia', point3Account: 'Guarde perfis dos animais e consulte cuidados para a fase de vida de cada um.', point3Guest: 'Consulte informação de cuidados preventivos para cães e gatos.',
    boundary: 'Orientação educativa geral, não um diagnóstico. O conteúdo desta versão beta aguarda revisão veterinária. Não precisa de conta para uma verificação rápida.',
    guestPreviewTitle: 'Pré-visualização privada para convidados', guestPreviewBody: 'Experimente verificações de sintomas, Aprender e Cuidados. As contas e o email não estão disponíveis nesta pré-visualização. Use apenas dados de teste fictícios.',
    testerBeta: 'Beta de testes', accountPreview: 'Pré-visualização privada de contas',
    accountPreviewBody: 'As contas estão disponíveis para testes. A verificação de email e a recuperação de palavra-passe não estão disponíveis. Use um email de teste, dados fictícios do animal e uma palavra-passe que não use noutro sítio.',
  },
  publicEducation: { navigation: 'Navegação de aprendizagem pública', learn: 'Aprender', care: 'Cuidados', browseFor: 'Ver informação para' },
  privacy: {
    summary: 'Como os seus dados são usados',
    guestStores: 'Esta pré-visualização privada guarda verificações de sintomas de convidados. As contas e o email estão desativados; use apenas dados de teste fictícios.',
    guestRetention: (hours) => `O acesso de convidado expira ao fim de ${hours} horas. Uma limpeza agendada remove as verificações expiradas.`,
    guestRetentionUnknown: 'O acesso de convidado é temporário; não foi possível carregar o aviso de retenção.',
    guestControls: 'Pode descarregar ou apagar a sua verificação enquanto estiver aberta. Fechar ou atualizar a página faz perder o acesso.',
    guestDraft: 'A política de privacidade ainda é um rascunho. Esta pré-visualização destina-se a testes privados.',
    accountStores: 'A aplicação guarda o seu email, um hash da palavra-passe, perfis dos animais, verificações de sintomas e registos de segurança. Pode descarregar os dados da conta ou apagar a conta, com os perfis e verificações, da base de dados da aplicação.',
    accountRetention: (hours) => `As verificações de convidado expiram ao fim de ${hours} horas e são removidas por uma limpeza agendada. Também pode descarregar ou apagar uma verificação de convidado enquanto estiver aberta.`,
    accountRetentionUnknown: 'As verificações de convidado têm um período de retenção limitado; não foi possível carregar o aviso atual.',
    closingLoses: 'Fechar a página faz perder o acesso a essa verificação de convidado.',
    accountKept: 'Os dados da conta são mantidos até apagar a conta. As cópias de segurança seguem o calendário de retenção próprio do operador.',
    readPolicy: 'Ler a política de privacidade',
    betaHosting: 'Esta beta de testes usa alojamento Vercel, base de dados Supabase e Upstash para limites de pedidos e limpeza agendada. A política de privacidade completa e o contacto do operador ainda não estão publicados. Use apenas um email de teste e dados fictícios do animal.',
    noSensitive: 'Não introduza dados pessoais ou sensíveis nos nomes dos animais.',
  },
  verification: {
    title: 'Verifique o seu email.', body: (email) => `Verifique ${email} antes de guardar perfis de animais. Abra a ligação no email de verificação e depois volte aqui.`,
    resend: 'Reenviar email de verificação', verified: 'Já verifiquei o meu email',
  },
  auth: {
    eyebrow: 'Orientação privada para os seus animais', welcomeBack: 'Bem-vindo de volta.', recover: 'Recuperar a sua conta.', create: 'Crie a sua conta.',
    leadForgot: 'Introduza o seu email para pedir uma ligação de reposição da palavra-passe.', lead: 'Os perfis dos seus animais e as verificações ficam associados à sua conta.',
    noEmailNote: 'A verificação de email e a recuperação de palavra-passe não estão disponíveis nesta versão de testes. Guarde a sua palavra-passe de teste; a aplicação não consegue enviar uma ligação de reposição.',
    email: 'Email', password: 'Palavra-passe', passwordHint: 'Use 15 a 128 caracteres. Uma frase-passe funciona bem.', acceptNotice: 'Li o aviso de utilização de dados da beta.',
    submitLogin: 'Iniciar sessão', submitForgot: 'Enviar ligação de reposição', submitCreate: 'Criar conta', createAccount: 'Criar uma conta', backToLogin: 'Voltar ao início de sessão', forgot: 'Esqueceu-se da palavra-passe?',
  },
  triage: {
    createAccountCta: 'Criar uma conta para futuros perfis de animais', startAnother: 'Fazer outra verificação', complete: 'As perguntas estão concluídas.',
    loadingGuidance: 'A carregar orientações…', guidanceNotLoaded: 'Ainda não foi possível carregar as orientações.', retryGuidance: 'Tentar carregar as orientações novamente',
    checkFor: (name) => `Verificação para ${name}`, yourSpecies: (species) => `o seu ${species}`, adaptive: 'Perguntas adaptativas', savingAnswer: 'A guardar a sua resposta…', restart: 'Recomeçar esta verificação',
    eyebrow: 'Um próximo passo com mais calma', title: 'O que notou?', checkingFor: (name) => `A verificar sintomas de ${name}. `,
    choose: 'Escolha a opção mais próxima. Esta verificação indica a urgência, não faz um diagnóstico.', whoFor: 'Para quem é esta verificação?', starting: 'A iniciar a verificação…', continue: 'Continuar',
    finePrint: 'Não encontra o sintoma? Contacte o seu veterinário. Dificuldade em respirar ou colapso precisam de urgência imediata.',
    questionStep: (step, total) => total ? `Pergunta ${step} de ${total}` : `Pergunta ${step}`,
    previous: 'Pergunta anterior', goingBack: 'A voltar atrás…',
  },
  guest: {
    expires: (date) => `Esta verificação de convidado expira a ${date}. `, closingLoses: 'Fechar esta página faz perder o acesso. Descarregue o resumo para o guardar.',
    download: 'Descarregar dados em bruto (JSON)', downloaded: 'O ficheiro de dados em bruto foi descarregado.', delete: 'Apagar esta verificação',
    contextTitle: 'Sobre o seu animal (opcional)', contextHint: 'Algumas orientações dependem da idade, do sexo ou da esterilização. Escolha «Não sei» se não souber.',
    age: 'Idade', young: (species) => species === 'cat' ? 'Gatinho' : 'Cachorro', adult: 'Adulto', senior: 'Sénior', notSure: 'Não sei',
    sex: 'Sexo', female: 'Fêmea', male: 'Macho', neutered: 'Esterilizado ou castrado',
    leaveTitle: 'Sair desta verificação?', leaveBody: 'As verificações de convidado não são guardadas. Se sair agora, as respostas e orientações desta verificação perdem-se.',
    leaveResultBody: 'Esta verificação de convidado não está guardada. Descarregue primeiro o resumo se a quiser manter.', leave: 'Sair desta verificação', stay: 'Continuar nesta verificação',
  },
  library: {
    eyebrow: 'Biblioteca de referência', title: 'Pontos de partida em linguagem simples', muted: 'Informação para conversar com o seu veterinário. O conteúdo beta aguarda revisão veterinária.',
    search: 'Pesquisar na biblioteca', searchPlaceholder: 'Pesquisar por sintoma, nome ou categoria', loading: 'A carregar a biblioteca…',
    entries: (count) => `${count} ${count === 1 ? 'entrada' : 'entradas'}`,
    noMatch: 'Nenhuma entrada corresponde à pesquisa. Experimente outra palavra ou contacte o seu veterinário para questões fora desta biblioteca.',
    readAbout: (name, urgency) => `Ler sobre ${name}. ${urgency}`, promptSigns: 'Sinais que precisam de atenção rápida',
    reviewed: (by, date) => `Revisto por ${by} em ${date}.`, awaiting: 'Aguarda revisão veterinária.', careGuides: 'Guias de cuidados relacionados',
  },
  care: {
    eyebrow: 'Cuidados preventivos', title: 'Pequenas verificações, menos preocupação.',
    basedOn: (name, stage) => `Com base na fase de vida de ${name}: ${stage}.`,
    unknownAge: (species, name) => `A mostrar toda a informação de cuidados disponível para ${species === 'cat' ? 'gatos' : 'cães'} porque a idade de ${name} é desconhecida. Pergunte ao veterinário o que se aplica.`,
    all: (species) => `A mostrar toda a informação de cuidados disponível para ${species === 'cat' ? 'gatos' : 'cães'}. Pergunte ao veterinário o que se aplica à idade e às circunstâncias do seu animal.`,
    noReminders: 'Isto é informação; ainda não há lembretes agendados.', loading: 'A carregar informação de cuidados…',
    empty: 'Ainda não há cuidados publicados para esta fase de vida. Pergunte ao veterinário sobre consultas de rotina, vacinas, prevenção de parasitas e cuidados dentários.',
    timing: (value) => `Frequência: ${value}`,
  },
  account: {
    eyebrow: 'Conta e privacidade', title: 'Os seus dados, a sua escolha.', confirmPassword: 'Confirme a palavra-passe para as opções da conta', download: 'Descarregar os meus dados',
    logoutAll: 'Terminar sessão em todos os dispositivos', downloaded: 'A exportação dos seus dados foi descarregada.', deleteTitle: 'Apagar conta',
    deleteBody: 'Isto remove permanentemente a sua conta, os perfis dos animais e as verificações associadas da base de dados da aplicação.', deleteStart: 'Apagar a minha conta…',
    deleteWarning: 'Não é possível anular. Descarregue primeiro os seus dados se quiser uma cópia.', deleteConfirm: 'Apagar a minha conta permanentemente',
  },
  emergency: { label: 'Aviso de urgência', title: 'Vá diretamente ao veterinário', body: 'Dificuldade em respirar, colapso, convulsões, hemorragia descontrolada ou esforço para urinar sem sair urina.' },
  result: {
    summary: 'Resumo da verificação', eyebrow: (saved, name) => `${saved ? 'Verificação guardada' : 'Orientação'} para ${name}`, yourPet: 'o seu animal',
    savedNotice: 'Esta é a orientação guardada para esta verificação, não uma nova avaliação do seu animal hoje.', nextStep: 'O próximo passo',
    symptom: 'Sintoma:', started: 'Início:', preserved: 'Relatório guardado:', petContext: 'Contexto do animal registado:',
    ageUnknown: 'idade desconhecida', sexLabel: 'sexo', neuteredLabel: 'castrado', breedSizeSuffix: 'porte da raça', born: 'nascido a',
    howDecided: 'Como foi decidido', answers: 'As suas respostas registadas', noAnswers: 'Não foram registadas respostas ao questionário.',
    careGuides: 'Guias de cuidados para esta situação', causes: 'Causas possíveis para falar com o veterinário', exams: 'O veterinário pode querer verificar', sources: 'Fontes registadas com esta verificação',
    contentVersion: (version) => `Versão do conteúdo: ${version}`, contentVersionMissing: 'Não registada nesta verificação mais antiga',
    watchFor: 'Esteja atento a estes sinais — contacte um veterinário se…', contextNotes: 'Dados que podem mudar esta orientação', adult: 'adulto', technicalInfo: 'Informação técnica',
    print: 'Imprimir / guardar PDF', downloadSummary: 'Descarregar resumo', summaryStays: 'O resumo descarregado fica no seu dispositivo. Partilhe-o apenas com quem escolher.',
    explanationGap: 'As explicações originais das regras não foram registadas nesta verificação.',
    historicalNotice: 'Esta é uma verificação guardada, não uma nova avaliação. As verificações mais antigas podem não incluir o contexto original do animal, as fontes ou o texto das perguntas.',
    boundary: 'Orientação educativa geral, não um diagnóstico. O conteúdo beta aguarda revisão veterinária. Este resumo regista esta verificação; não avalia alterações posteriores nos sintomas. Se o seu animal piorar ou tiver dúvidas, contacte o seu veterinário.',
    reportTitle: 'Resumo da verificação PETAdvice', lifeStage: 'Fase de vida', birthDate: 'Data de nascimento', breedSize: 'Porte da raça', noContext: 'O contexto original do animal não foi registado.',
  },
  history: {
    eyebrow: (name) => `Verificações guardadas de ${name}`, title: 'Histórico de verificações', muted: 'Reveja as orientações e respostas registadas em verificações anteriores. Se os sintomas mudaram, faça uma nova verificação.',
    loading: 'A carregar o histórico…', none: (name) => `Ainda não há verificações guardadas para ${name}. Faça uma verificação de sintomas para a ver aqui.`,
    guidanceNotSaved: 'Perguntas concluídas; orientação ainda não guardada', notCompleted: 'Perguntas não concluídas', view: 'Ver verificação guardada',
    startNew: 'Faça uma nova verificação se ainda precisar de orientação.', loadOlder: 'Carregar verificações mais antigas', loadingSaved: 'A carregar a orientação guardada…', back: 'Voltar ao histórico',
  },
  accountLink: {
    verifyTitle: 'Verifique o seu email.', resetTitle: 'Escolha uma nova palavra-passe.', continue: 'Continuar para iniciar sessão', newPassword: 'Nova palavra-passe', hint: 'Use 15 a 128 caracteres.',
    confirm: 'Confirmar a nova palavra-passe', verify: 'Verificar email', reset: 'Repor palavra-passe', back: 'Voltar ao início de sessão / pedir nova ligação', mismatch: 'As palavras-passe não coincidem.',
  },
  errors: {
    generic: 'Algo correu mal. Tente novamente.', requestFailed: 'Não foi possível concluir o pedido. Tente novamente.',
    timeout: 'O pedido demorou demasiado. Verifique a ligação e tente novamente.', network: 'Não foi possível ligar. Verifique a ligação e tente novamente.',
  },
  update: { ready: 'Está disponível uma nova versão do PETAdvice.', refresh: 'Atualizar', dismiss: 'Fechar' },
  server: {
    'Incorrect email or password': 'Email ou palavra-passe incorretos',
    'An account with this email already exists': 'Já existe uma conta com este email',
    'Incorrect password': 'Palavra-passe incorreta',
    'Too many requests. Please try again later.': 'Demasiados pedidos. Tente novamente mais tarde.',
    'Request protection is temporarily unavailable. Try again shortly.': 'A proteção de pedidos está temporariamente indisponível. Tente novamente daqui a pouco.',
    'Invalid or expired session': 'Sessão inválida ou expirada',
    'Not authenticated': 'Sessão não iniciada',
    'Confirm your password before this sensitive action': 'Confirme a sua palavra-passe antes desta ação',
    'Verify your email before saving pet profiles or starting account checks': 'Verifique o seu email antes de guardar perfis ou iniciar verificações',
    'Verify your email before starting account checks': 'Verifique o seu email antes de iniciar verificações',
    'This link is invalid or expired. Request a new link.': 'Esta ligação é inválida ou expirou. Peça uma nova ligação.',
    'Email verification and password recovery are unavailable in this test version': 'A verificação de email e a recuperação de palavra-passe não estão disponíveis nesta versão de testes',
    'Accounts are unavailable in this guest-only preview': 'As contas não estão disponíveis nesta pré-visualização para convidados',
    'Triage session not found or expired': 'Verificação não encontrada ou expirada',
    'Triage session not found': 'Verificação não encontrada',
    'Complete the remaining questions before viewing guidance': 'Responda às perguntas que faltam antes de ver as orientações',
    'Answer is not valid for this question': 'A resposta não é válida para esta pergunta',
    'This check cannot go back from here': 'Esta verificação não pode voltar atrás a partir daqui',
    'This symptom is not supported. Contact your veterinary practice for guidance.': 'Este sintoma não é suportado. Contacte o seu veterinário para orientação.',
    'An unexpected error occurred. Try again shortly.': 'Ocorreu um erro inesperado. Tente novamente daqui a pouco.',
    'Date of birth cannot be in the future': 'A data de nascimento não pode ser no futuro',
    'You must accept the privacy policy to create an account': 'Tem de aceitar a política de privacidade para criar uma conta',
    'If this address belongs to an eligible account, an email will arrive shortly.': 'Se este endereço pertencer a uma conta elegível, receberá um email em breve.',
    'Email verified. You can now sign in and save your pet profiles.': 'Email verificado. Já pode iniciar sessão e guardar os perfis dos seus animais.',
    'Password changed. Sign in with your new password.': 'Palavra-passe alterada. Inicie sessão com a nova palavra-passe.',
  },
}

const es: Messages = {
  language: 'Idioma',
  common: {
    back: 'Volver', tryAgain: 'Reintentar', logOut: 'Cerrar sesión', cancel: 'Cancelar', pleaseWait: 'Espera…', yes: 'Sí', no: 'No', unknown: 'Desconocido',
    sources: 'Fuentes', opensNewTab: (host) => `${host} (se abre en una pestaña nueva)`, notRecorded: 'No registrado',
    startCheck: (symptom) => `Hacer una revisión: ${symptom}`,
  },
  species: { dog: 'Perro', cat: 'Gato' },
  speciesLower: { dog: 'perro', cat: 'gato', both: 'perro o gato' },
  speciesPlural: { dog: 'Perros', cat: 'Gatos' },
  urgency: { monitor_home: 'Vigilar en casa', vet_soon: 'Pedir cita con el veterinario', vet_24h: 'Contactar con un veterinario en 24 horas', emergency_now: 'Urgencia veterinaria ya' },
  lifeStage: { puppy: 'cachorro', kitten: 'gatito', young_adult: 'adulto joven', mature_adult: 'adulto maduro', senior: 'sénior' },
  sex: { male: 'macho', female: 'hembra' },
  breedSize: { small: 'pequeño', medium: 'mediano', large: 'grande', giant: 'gigante' },
  category: {
    gastrointestinal: 'gastrointestinal', dermatological: 'piel', musculoskeletal: 'músculos y articulaciones', dental_oral: 'dientes y boca', ear_eye: 'oídos y ojos',
    respiratory: 'respiración', urinary_reproductive: 'urinario y reproductor', parasites: 'parásitos', behavioral: 'comportamiento', weight_nutrition: 'peso y nutrición', emergency_trauma: 'urgencias y lesiones',
  },
  symptoms: {
    straining_to_urinate: 'Esfuerzo para orinar', vomiting: 'Vómitos', diarrhea: 'Diarrea', limping: 'Cojera después del ejercicio', reverse_sneezing: 'Estornudo inverso',
    scratching: 'Picor o pulgas', scooting: 'Arrastra el trasero o lombrices en las heces', nervous_or_stressed: 'Nervioso o estresado', increased_thirst: 'Bebe más de lo normal', vaginal_discharge: 'Flujo inesperado',
  },
  app: {
    loadingAccount: 'Cargando tu cuenta…', loadErrorTitle: 'No hemos podido cargar tu cuenta.', loadErrorDetail: 'Comprueba tu conexión e inténtalo de nuevo.',
    ageUnknown: 'Edad desconocida', changePet: 'Cambiar de mascota', newPet: 'Nueva mascota', mainNavigation: 'Navegación principal',
    tabs: { triage: 'Revisar síntomas', library: 'Aprender', care: 'Plan de cuidados', history: 'Historial', account: 'Cuenta' },
  },
  petForm: {
    eyebrowAnother: 'Añadir otro compañero', eyebrowFirst: 'Configura tu primera mascota', title: 'Háblanos de tu mascota.',
    lead: 'Algunos datos ayudan a que las orientaciones sean relevantes. Deja como desconocido lo que no sepas.',
    name: 'Nombre de la mascota', namePlaceholder: 'p. ej., Miso', species: 'Especie', dateOfBirth: 'Fecha de nacimiento (opcional)', sex: 'Sexo', female: 'Hembra', male: 'Macho',
    neutered: '¿Esterilizado o castrado?', breedSize: 'Tamaño de la raza del perro (opcional)', unknownOrCat: 'Desconocido / gato', small: 'Pequeño', medium: 'Mediano', large: 'Grande', giant: 'Gigante',
    saving: 'Guardando…', create: 'Crear perfil de la mascota', accountPrivacy: 'Cuenta y privacidad',
  },
  landing: {
    logoAlt: 'Logotipo de PETAdvice con perro y gato', login: 'Iniciar sesión', eyebrow: 'Orientación amable para las preocupaciones del día a día', title: 'Un siguiente paso más claro para tu mascota.',
    lead: 'Cuando algo parece distinto, PETAdvice te ayuda a saber qué observar, con qué urgencia actuar y qué comentar con tu veterinario.',
    start: 'Hacer una revisión rápida', save: 'Guardar los perfiles de mis mascotas', browseLearn: 'Explorar Aprender', browseCare: 'Explorar Cuidados',
    point1Title: 'Entender los síntomas', point1Body: 'Encuentra información sencilla sobre problemas habituales.',
    point2Title: 'Saber la urgencia', point2Body: 'Responde a preguntas concretas para decidir cuándo contactar con un veterinario.',
    point3Title: 'Mantener los cuidados al día', point3Account: 'Guarda perfiles de tus mascotas y consulta cuidados para su etapa de vida.', point3Guest: 'Consulta información de cuidados preventivos para perros y gatos.',
    boundary: 'Orientación educativa general, no un diagnóstico. El contenido de esta beta está pendiente de revisión veterinaria. No necesitas cuenta para una revisión rápida.',
    guestPreviewTitle: 'Vista previa privada para invitados', guestPreviewBody: 'Prueba las revisiones de síntomas, Aprender y Cuidados. Las cuentas y el correo no están disponibles en esta vista previa. Usa solo datos de prueba ficticios.',
    testerBeta: 'Beta de pruebas', accountPreview: 'Vista previa privada de cuentas',
    accountPreviewBody: 'Las cuentas están disponibles para pruebas. La verificación de correo y la recuperación de contraseña no están disponibles. Usa un correo de prueba, datos ficticios de la mascota y una contraseña que no uses en otro sitio.',
  },
  publicEducation: { navigation: 'Navegación de aprendizaje pública', learn: 'Aprender', care: 'Cuidados', browseFor: 'Ver información para' },
  privacy: {
    summary: 'Cómo se usan tus datos',
    guestStores: 'Esta vista previa privada guarda revisiones de síntomas de invitados. Las cuentas y el correo están desactivados; usa solo datos de prueba ficticios.',
    guestRetention: (hours) => `El acceso de invitado caduca a las ${hours} horas. Una limpieza programada elimina las revisiones caducadas.`,
    guestRetentionUnknown: 'El acceso de invitado es temporal; no se ha podido cargar el aviso de conservación.',
    guestControls: 'Puedes descargar o eliminar tu revisión mientras esté abierta. Si cierras o recargas la página, pierdes el acceso.',
    guestDraft: 'La política de privacidad todavía es un borrador. Esta vista previa es para pruebas privadas.',
    accountStores: 'La aplicación guarda tu correo, un hash de la contraseña, perfiles de mascotas, revisiones de síntomas y registros de seguridad. Puedes descargar los datos de tu cuenta o eliminarla, con sus perfiles y revisiones, de la base de datos de la aplicación.',
    accountRetention: (hours) => `Las revisiones de invitado caducan a las ${hours} horas y se eliminan con una limpieza programada. También puedes descargar o eliminar una revisión de invitado mientras esté abierta.`,
    accountRetentionUnknown: 'Las revisiones de invitado tienen un periodo de conservación limitado; no se ha podido cargar el aviso actual.',
    closingLoses: 'Si cierras la página, pierdes el acceso a esa revisión de invitado.',
    accountKept: 'Los datos de la cuenta se conservan hasta que la elimines. Las copias de seguridad siguen el calendario de conservación propio del operador.',
    readPolicy: 'Leer la política de privacidad',
    betaHosting: 'Esta beta de pruebas usa alojamiento de Vercel, base de datos de Supabase y Upstash para límites de peticiones y limpieza programada. La política de privacidad completa y el contacto del operador aún no están publicados. Usa solo un correo de prueba y datos ficticios de la mascota.',
    noSensitive: 'No introduzcas datos personales o sensibles en los nombres de las mascotas.',
  },
  verification: {
    title: 'Revisa tu correo.', body: (email) => `Verifica ${email} antes de guardar perfiles de mascotas. Abre el enlace del correo de verificación y vuelve aquí.`,
    resend: 'Reenviar correo de verificación', verified: 'Ya he verificado mi correo',
  },
  auth: {
    eyebrow: 'Orientación privada para tus mascotas', welcomeBack: 'Hola de nuevo.', recover: 'Recupera tu cuenta.', create: 'Crea tu cuenta.',
    leadForgot: 'Introduce tu correo para solicitar un enlace para restablecer la contraseña.', lead: 'Los perfiles de tus mascotas y tus revisiones quedan vinculados a tu cuenta.',
    noEmailNote: 'La verificación de correo y la recuperación de contraseña no están disponibles en esta versión de pruebas. Guarda tu contraseña de prueba; la aplicación no puede enviarte un enlace para restablecerla.',
    email: 'Correo electrónico', password: 'Contraseña', passwordHint: 'Usa de 15 a 128 caracteres. Una frase de contraseña funciona bien.', acceptNotice: 'He leído el aviso de uso de datos de la beta.',
    submitLogin: 'Iniciar sesión', submitForgot: 'Enviar enlace', submitCreate: 'Crear cuenta', createAccount: 'Crear una cuenta', backToLogin: 'Volver a iniciar sesión', forgot: '¿Has olvidado tu contraseña?',
  },
  triage: {
    createAccountCta: 'Crear una cuenta para futuros perfiles de mascotas', startAnother: 'Hacer otra revisión', complete: 'Has terminado las preguntas.',
    loadingGuidance: 'Cargando orientación…', guidanceNotLoaded: 'Todavía no se ha podido cargar la orientación.', retryGuidance: 'Volver a cargar la orientación',
    checkFor: (name) => `Revisión para ${name}`, yourSpecies: (species) => `tu ${species}`, adaptive: 'Preguntas adaptativas', savingAnswer: 'Guardando tu respuesta…', restart: 'Reiniciar esta revisión',
    eyebrow: 'Un siguiente paso con más calma', title: '¿Qué has notado?', checkingFor: (name) => `Revisando síntomas de ${name}. `,
    choose: 'Elige la opción más parecida. Esta revisión orienta sobre la urgencia, no es un diagnóstico.', whoFor: '¿Para quién es esta revisión?', starting: 'Iniciando la revisión…', continue: 'Continuar',
    finePrint: '¿No encuentras el síntoma? Contacta con tu clínica veterinaria. La dificultad para respirar o un colapso necesitan urgencias de inmediato.',
    questionStep: (step, total) => total ? `Pregunta ${step} de ${total}` : `Pregunta ${step}`,
    previous: 'Pregunta anterior', goingBack: 'Volviendo atrás…',
  },
  guest: {
    expires: (date) => `Esta revisión de invitado caduca el ${date}. `, closingLoses: 'Si cierras esta página, pierdes el acceso. Descarga el resumen para conservarla.',
    download: 'Descargar datos en bruto (JSON)', downloaded: 'Se ha descargado el archivo de datos en bruto.', delete: 'Eliminar esta revisión',
    contextTitle: 'Sobre tu mascota (opcional)', contextHint: 'Parte de la orientación depende de la edad, el sexo o la esterilización. Elige «No lo sé» si no lo sabes.',
    age: 'Edad', young: (species) => species === 'cat' ? 'Gatito' : 'Cachorro', adult: 'Adulto', senior: 'Sénior', notSure: 'No lo sé',
    sex: 'Sexo', female: 'Hembra', male: 'Macho', neutered: 'Esterilizado o castrado',
    leaveTitle: '¿Salir de esta revisión?', leaveBody: 'Las revisiones de invitado no se guardan. Si sales ahora, se perderán las respuestas y la orientación de esta revisión.',
    leaveResultBody: 'Esta revisión de invitado no está guardada. Descarga primero el resumen si quieres conservarla.', leave: 'Salir de esta revisión', stay: 'Seguir en esta revisión',
  },
  library: {
    eyebrow: 'Biblioteca de consulta', title: 'Puntos de partida en lenguaje sencillo', muted: 'Información para hablar con tu veterinario. El contenido beta está pendiente de revisión veterinaria.',
    search: 'Buscar en la biblioteca', searchPlaceholder: 'Buscar por síntoma, nombre o categoría', loading: 'Cargando la biblioteca…',
    entries: (count) => `${count} ${count === 1 ? 'entrada' : 'entradas'}`,
    noMatch: 'Ninguna entrada coincide con tu búsqueda. Prueba con otra palabra o consulta a tu veterinario si tu duda no está en esta biblioteca.',
    readAbout: (name, urgency) => `Leer sobre ${name}. ${urgency}`, promptSigns: 'Signos que requieren atención rápida',
    reviewed: (by, date) => `Revisado por ${by} el ${date}.`, awaiting: 'Pendiente de revisión veterinaria.', careGuides: 'Guías de cuidados relacionadas',
  },
  care: {
    eyebrow: 'Cuidados preventivos', title: 'Pequeñas revisiones, menos preocupaciones.',
    basedOn: (name, stage) => `Según la etapa de vida de ${name}: ${stage}.`,
    unknownAge: (species, name) => `Mostrando toda la información de cuidados disponible para ${species === 'cat' ? 'gatos' : 'perros'} porque no se conoce la edad de ${name}. Pregunta a tu veterinario qué aplica.`,
    all: (species) => `Mostrando toda la información de cuidados disponible para ${species === 'cat' ? 'gatos' : 'perros'}. Pregunta a tu veterinario qué aplica a la edad y las circunstancias de tu mascota.`,
    noReminders: 'Es información; todavía no hay recordatorios programados.', loading: 'Cargando información de cuidados…',
    empty: 'Todavía no hay cuidados publicados para esta etapa de vida. Pregunta a tu veterinario por revisiones rutinarias, vacunas, prevención de parásitos y cuidado dental.',
    timing: (value) => `Frecuencia: ${value}`,
  },
  account: {
    eyebrow: 'Cuenta y privacidad', title: 'Tus datos, tu decisión.', confirmPassword: 'Confirma tu contraseña para las opciones de la cuenta', download: 'Descargar mis datos',
    logoutAll: 'Cerrar sesión en todos los dispositivos', downloaded: 'Se ha descargado la exportación de tus datos.', deleteTitle: 'Eliminar cuenta',
    deleteBody: 'Esto elimina de forma permanente tu cuenta, los perfiles de tus mascotas y las revisiones asociadas de la base de datos de la aplicación.', deleteStart: 'Eliminar mi cuenta…',
    deleteWarning: 'No se puede deshacer. Descarga primero tus datos si quieres una copia.', deleteConfirm: 'Eliminar mi cuenta definitivamente',
  },
  emergency: { label: 'Aviso de urgencia', title: 'Ve directamente al veterinario', body: 'Dificultad para respirar, colapso, convulsiones, sangrado incontrolado o esfuerzo para orinar sin que salga orina.' },
  result: {
    summary: 'Resumen de la revisión', eyebrow: (saved, name) => `${saved ? 'Revisión guardada' : 'Orientación'} para ${name}`, yourPet: 'tu mascota',
    savedNotice: 'Esta es la orientación guardada para esta revisión, no una nueva valoración de tu mascota hoy.', nextStep: 'Tu siguiente paso',
    symptom: 'Síntoma:', started: 'Inicio:', preserved: 'Informe guardado:', petContext: 'Contexto de la mascota registrado:',
    ageUnknown: 'edad desconocida', sexLabel: 'sexo', neuteredLabel: 'castrado', breedSizeSuffix: 'tamaño de raza', born: 'nacido el',
    howDecided: 'Cómo se ha decidido', answers: 'Tus respuestas registradas', noAnswers: 'No se registraron respuestas al cuestionario.',
    careGuides: 'Guías de cuidados para esta situación', causes: 'Posibles causas para comentar con tu veterinario', exams: 'Tu veterinario puede querer revisar', sources: 'Fuentes registradas con esta revisión',
    contentVersion: (version) => `Versión del contenido: ${version}`, contentVersionMissing: 'No registrada en esta revisión antigua',
    watchFor: 'Vigila estos signos — contacta con un veterinario si…', contextNotes: 'Datos que pueden cambiar esta orientación', adult: 'adulto', technicalInfo: 'Información técnica',
    print: 'Imprimir / guardar PDF', downloadSummary: 'Descargar resumen', summaryStays: 'El resumen descargado se queda en tu dispositivo. Compártelo solo con quien tú elijas.',
    explanationGap: 'Las explicaciones originales de las reglas no se registraron en esta revisión.',
    historicalNotice: 'Esta es una revisión guardada, no una nueva valoración. Las revisiones antiguas pueden no incluir el contexto original de la mascota, las fuentes o el texto de las preguntas.',
    boundary: 'Orientación educativa general, no un diagnóstico. El contenido beta está pendiente de revisión veterinaria. Este resumen registra esta revisión; no valora cambios posteriores en los síntomas. Si tu mascota empeora o tienes dudas, contacta con tu clínica veterinaria.',
    reportTitle: 'Resumen de la revisión de PETAdvice', lifeStage: 'Etapa de vida', birthDate: 'Fecha de nacimiento', breedSize: 'Tamaño de raza', noContext: 'No se registró el contexto original de la mascota.',
  },
  history: {
    eyebrow: (name) => `Revisiones guardadas de ${name}`, title: 'Historial de revisiones', muted: 'Vuelve a ver la orientación y las respuestas registradas en revisiones anteriores. Si los síntomas han cambiado, haz una nueva revisión.',
    loading: 'Cargando el historial…', none: (name) => `Todavía no hay revisiones guardadas de ${name}. Haz una revisión de síntomas para verla aquí.`,
    guidanceNotSaved: 'Preguntas completadas; orientación aún no guardada', notCompleted: 'Preguntas sin completar', view: 'Ver revisión guardada',
    startNew: 'Haz una nueva revisión si todavía necesitas orientación.', loadOlder: 'Cargar revisiones anteriores', loadingSaved: 'Cargando la orientación guardada…', back: 'Volver al historial',
  },
  accountLink: {
    verifyTitle: 'Verifica tu correo.', resetTitle: 'Elige una contraseña nueva.', continue: 'Continuar para iniciar sesión', newPassword: 'Contraseña nueva', hint: 'Usa de 15 a 128 caracteres.',
    confirm: 'Confirma la contraseña nueva', verify: 'Verificar correo', reset: 'Restablecer contraseña', back: 'Volver a iniciar sesión / pedir un enlace nuevo', mismatch: 'Las contraseñas no coinciden.',
  },
  errors: {
    generic: 'Algo ha ido mal. Inténtalo de nuevo.', requestFailed: 'No se ha podido completar la petición. Inténtalo de nuevo.',
    timeout: 'La petición ha tardado demasiado. Comprueba tu conexión e inténtalo de nuevo.', network: 'No se ha podido conectar. Comprueba tu conexión e inténtalo de nuevo.',
  },
  update: { ready: 'Hay una nueva versión de PETAdvice disponible.', refresh: 'Actualizar', dismiss: 'Cerrar' },
  server: {
    'Incorrect email or password': 'Correo o contraseña incorrectos',
    'An account with this email already exists': 'Ya existe una cuenta con este correo',
    'Incorrect password': 'Contraseña incorrecta',
    'Too many requests. Please try again later.': 'Demasiadas peticiones. Inténtalo más tarde.',
    'Request protection is temporarily unavailable. Try again shortly.': 'La protección de peticiones no está disponible temporalmente. Inténtalo en un momento.',
    'Invalid or expired session': 'Sesión no válida o caducada',
    'Not authenticated': 'No has iniciado sesión',
    'Confirm your password before this sensitive action': 'Confirma tu contraseña antes de esta acción',
    'Verify your email before saving pet profiles or starting account checks': 'Verifica tu correo antes de guardar perfiles o iniciar revisiones',
    'Verify your email before starting account checks': 'Verifica tu correo antes de iniciar revisiones',
    'This link is invalid or expired. Request a new link.': 'Este enlace no es válido o ha caducado. Solicita uno nuevo.',
    'Email verification and password recovery are unavailable in this test version': 'La verificación de correo y la recuperación de contraseña no están disponibles en esta versión de pruebas',
    'Accounts are unavailable in this guest-only preview': 'Las cuentas no están disponibles en esta vista previa para invitados',
    'Triage session not found or expired': 'Revisión no encontrada o caducada',
    'Triage session not found': 'Revisión no encontrada',
    'Complete the remaining questions before viewing guidance': 'Responde a las preguntas que faltan antes de ver la orientación',
    'Answer is not valid for this question': 'La respuesta no es válida para esta pregunta',
    'This check cannot go back from here': 'Esta revisión no puede volver atrás desde aquí',
    'This symptom is not supported. Contact your veterinary practice for guidance.': 'Este síntoma no está disponible. Contacta con tu clínica veterinaria para que te oriente.',
    'An unexpected error occurred. Try again shortly.': 'Se ha producido un error inesperado. Inténtalo en un momento.',
    'Date of birth cannot be in the future': 'La fecha de nacimiento no puede ser futura',
    'You must accept the privacy policy to create an account': 'Debes aceptar la política de privacidad para crear una cuenta',
    'If this address belongs to an eligible account, an email will arrive shortly.': 'Si esta dirección pertenece a una cuenta válida, recibirás un correo en breve.',
    'Email verified. You can now sign in and save your pet profiles.': 'Correo verificado. Ya puedes iniciar sesión y guardar los perfiles de tus mascotas.',
    'Password changed. Sign in with your new password.': 'Contraseña cambiada. Inicia sesión con tu nueva contraseña.',
  },
}

const messages: Record<Language, Messages> = { en, pt, es }

function isLanguage(value: unknown): value is Language {
  return value === 'en' || value === 'pt' || value === 'es'
}

export function detectLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(stored)) return stored
  } catch { /* Storage can be disabled; fall back to the browser language. */ }
  for (const tag of navigator.languages ?? [navigator.language]) {
    const base = tag?.toLowerCase().split('-')[0]
    if (isLanguage(base)) return base
  }
  return 'en'
}

let current: Language = detectLanguage()
const listeners = new Set<() => void>()
if (typeof document !== 'undefined') document.documentElement.lang = current

export function getLanguage(): Language { return current }

export function setLanguage(language: Language) {
  current = language
  try { localStorage.setItem(STORAGE_KEY, language) } catch { /* Preference lasts for this page only. */ }
  document.documentElement.lang = language
  listeners.forEach((listener) => listener())
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function translations(language: Language = current): Messages { return messages[language] }

export function serverText(text: string): string { return messages[current].server[text] ?? text }

// Date and time to the minute; seconds add noise to reports and expiry notices.
export function formatDate(value: string): string { return new Date(value).toLocaleString(dateLocales[current], { dateStyle: 'medium', timeStyle: 'short' }) }

export function readable(value: string) { return value.replaceAll('_', ' ') }

export function useI18n() {
  const language = useSyncExternalStore(subscribe, getLanguage)
  return { language, t: messages[language], setLanguage }
}
