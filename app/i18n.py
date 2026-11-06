from fastapi import Request

DEFAULT_LANGUAGE = 'en'
SUPPORTED_LANGUAGES = ('en', 'pt', 'es')

_MESSAGES: dict[str, dict[str, str]] = {
    'en': {
        'guidance.monitor_home': 'Monitor your pet closely and contact a vet if things change or do not improve.',
        'guidance.vet_soon': 'Arrange a veterinary appointment within the next few days.',
        'guidance.vet_24h': 'Please arrange a veterinary appointment within 24 hours.',
        'guidance.emergency_now': 'This needs emergency veterinary attention now. Contact an emergency clinic immediately.',
        'reason.symptom_guidance': 'The existing symptom guidance for {name} sets this minimum action level. This is not a diagnosis of that condition.',
        'reason.limited_content': 'No condition guidance matches the available pet context. The check uses the existing cautious fallback.',
        'reason.life_stage': 'The existing guidance for {name} includes a higher action level for the {life_stage} life stage.',
        'reason.answer': '{prompt} Your answer: {answer}. The existing question rule sets this action level.',
        'reason.red_flag': 'An answer matched this existing warning rule: {flag}',
        'question_id': 'Question ID: {id}',
        'life_stage.puppy': 'puppy', 'life_stage.kitten': 'kitten', 'life_stage.young_adult': 'young adult',
        'life_stage.mature_adult': 'mature adult', 'life_stage.senior': 'senior',
        'recheck.monitor_home': 'If your pet is not clearly improving within 24–48 hours, or you are worried at any point, contact your vet.',
        'reason.missing_context': "Some guidance for this symptom ({name}) applies only to pets that are: {scope}. Your pet's {details} was not given, so it was not used. If this describes your pet, that guidance recommends: {urgency}.",
        'reason.missing_life_stage': "Your pet's age was not given. For a {life_stages}, the guidance for {name} recommends: {urgency}.",
        'detail.sex': 'sex', 'detail.neutered': 'spay/neuter status', 'detail.join': ' and ', 'list.or': ' or ',
        'scope.female': 'female', 'scope.male': 'male', 'scope.intact': 'not spayed or neutered', 'scope.neutered': 'spayed or neutered',
        'urgency.monitor_home': 'Monitor at home', 'urgency.vet_soon': 'Book a vet appointment',
        'urgency.vet_24h': 'Contact a vet within 24 hours', 'urgency.emergency_now': 'Emergency veterinary care now',
    },
    'pt': {
        'guidance.monitor_home': 'Vigie o seu animal de perto e contacte um veterinário se algo mudar ou não melhorar.',
        'guidance.vet_soon': 'Marque uma consulta veterinária nos próximos dias.',
        'guidance.vet_24h': 'Marque uma consulta veterinária nas próximas 24 horas.',
        'guidance.emergency_now': 'Esta situação precisa de atenção veterinária urgente agora. Contacte imediatamente uma clínica de urgências.',
        'reason.symptom_guidance': 'As orientações existentes para «{name}» definem este nível mínimo de ação. Isto não é um diagnóstico dessa condição.',
        'reason.limited_content': 'Nenhuma orientação corresponde ao contexto disponível do animal. A verificação usa a opção prudente predefinida.',
        'reason.life_stage': 'As orientações existentes para «{name}» incluem um nível de ação mais elevado para a fase de vida {life_stage}.',
        'reason.answer': '{prompt} A sua resposta: {answer}. A regra existente para esta pergunta define este nível de ação.',
        'reason.red_flag': 'Uma resposta corresponde a este sinal de alerta existente: {flag}',
        'question_id': 'ID da pergunta: {id}',
        'life_stage.puppy': 'cachorro', 'life_stage.kitten': 'gatinho', 'life_stage.young_adult': 'adulto jovem',
        'life_stage.mature_adult': 'adulto maduro', 'life_stage.senior': 'sénior',
        'recheck.monitor_home': 'Se o seu animal não melhorar claramente em 24 a 48 horas, ou se estiver preocupado em qualquer momento, contacte o seu veterinário.',
        'reason.missing_context': 'Algumas orientações para este sintoma («{name}») aplicam-se apenas a animais que sejam: {scope}. Não foi indicado o {details} do seu animal, por isso essas orientações não foram usadas. Se isto descreve o seu animal, recomendam: {urgency}.',
        'reason.missing_life_stage': 'Não foi indicada a idade do seu animal. Para um {life_stages}, as orientações para «{name}» recomendam: {urgency}.',
        'detail.sex': 'sexo', 'detail.neutered': 'estado de esterilização', 'detail.join': ' e ', 'list.or': ' ou ',
        'scope.female': 'fêmea', 'scope.male': 'macho', 'scope.intact': 'não esterilizado(a)', 'scope.neutered': 'esterilizado(a)',
        'urgency.monitor_home': 'Vigiar em casa', 'urgency.vet_soon': 'Marcar consulta no veterinário',
        'urgency.vet_24h': 'Contactar um veterinário nas próximas 24 horas', 'urgency.emergency_now': 'Urgência veterinária já',
    },
    'es': {
        'guidance.monitor_home': 'Vigila de cerca a tu mascota y contacta con un veterinario si algo cambia o no mejora.',
        'guidance.vet_soon': 'Pide cita con el veterinario en los próximos días.',
        'guidance.vet_24h': 'Pide cita con el veterinario en las próximas 24 horas.',
        'guidance.emergency_now': 'Esto necesita atención veterinaria urgente ahora. Contacta de inmediato con una clínica de urgencias.',
        'reason.symptom_guidance': 'La orientación existente para «{name}» fija este nivel mínimo de actuación. No es un diagnóstico de esa afección.',
        'reason.limited_content': 'Ninguna orientación coincide con el contexto disponible de la mascota. La consulta usa la opción prudente predeterminada.',
        'reason.life_stage': 'La orientación existente para «{name}» incluye un nivel de actuación más alto para la etapa de vida {life_stage}.',
        'reason.answer': '{prompt} Tu respuesta: {answer}. La regla existente para esta pregunta fija este nivel de actuación.',
        'reason.red_flag': 'Una respuesta coincide con esta señal de alarma existente: {flag}',
        'question_id': 'ID de la pregunta: {id}',
        'life_stage.puppy': 'cachorro', 'life_stage.kitten': 'gatito', 'life_stage.young_adult': 'adulto joven',
        'life_stage.mature_adult': 'adulto maduro', 'life_stage.senior': 'sénior',
        'recheck.monitor_home': 'Si tu mascota no mejora claramente en 24-48 horas, o si te preocupa en cualquier momento, contacta con tu veterinario.',
        'reason.missing_context': 'Parte de la orientación para este síntoma («{name}») solo se aplica a mascotas que sean: {scope}. No se indicó el {details} de tu mascota, así que esa orientación no se ha usado. Si esto describe a tu mascota, recomienda: {urgency}.',
        'reason.missing_life_stage': 'No se indicó la edad de tu mascota. Para un {life_stages}, la orientación para «{name}» recomienda: {urgency}.',
        'detail.sex': 'sexo', 'detail.neutered': 'estado de esterilización', 'detail.join': ' y ', 'list.or': ' o ',
        'scope.female': 'hembra', 'scope.male': 'macho', 'scope.intact': 'no esterilizado/a', 'scope.neutered': 'esterilizado/a',
        'urgency.monitor_home': 'Vigilar en casa', 'urgency.vet_soon': 'Pedir cita con el veterinario',
        'urgency.vet_24h': 'Contactar con un veterinario en 24 horas', 'urgency.emergency_now': 'Urgencia veterinaria ya',
    },
}


def normalize_language(value: str | None) -> str:
    """Return the first supported language in an Accept-Language style value."""
    for part in (value or '').split(','):
        tag = part.split(';')[0].strip().lower()
        base = tag.split('-')[0]
        if base in SUPPORTED_LANGUAGES:
            return base
    return DEFAULT_LANGUAGE


def request_language(request: Request) -> str:
    return normalize_language(request.headers.get('accept-language'))


def message(language: str, key: str, **values: str) -> str:
    template = _MESSAGES.get(language, {}).get(key) or _MESSAGES[DEFAULT_LANGUAGE][key]
    return template.format(**values)
