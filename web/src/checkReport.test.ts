import { expect, test } from 'vitest'
import { reportHtml } from './checkReport'

test('downloaded report escapes stored text and has no executable scripts or external dependencies', () => {
  const html = reportHtml({ resulting_urgency: 'emergency_now', resulting_guidance: '<script>alert("token")</script>', possible_causes: ['<img src=x onerror=alert(1)>'], recommended_examinations: [], matched_condition_ids: [], pet: { name: '<a href="javascript:alert(1)">Rex</a>', species: 'dog', date_of_birth: null, life_stage: null, sex: null, neutered: null, breed_size: null }, reasons: [{ kind: 'answer', detail: '<b>Danger</b>', urgency: 'emergency_now' }], answers: [{ question_id: 'q', prompt: 'Any <changes>?', answer: '<iframe src="https://tracker.example">' }], sources: ['https://reference.example?a=1&b=2'], content_version: 'test-version' })
  expect(html).toContain('&lt;script&gt;')
  expect(html).toContain('&lt;iframe')
  expect(html).not.toContain('<script>')
  expect(html).not.toContain('<img')
  expect(html).not.toContain('<iframe')
  expect(html).toContain("default-src 'none'")
  expect(html).toContain('Emergency veterinary care now')
  expect(html).toContain('test-version')
})

test('downloaded report includes signs to watch for, re-check advice and context notes in the recorded language', () => {
  const html = reportHtml({ resulting_urgency: 'monitor_home', resulting_guidance: 'Vigila.', possible_causes: ['Primero', 'Segundo'], recommended_examinations: [], matched_condition_ids: [], language: 'es', watch_for: [{ description: 'Sangre en el <vómito>', urgency: 'emergency_now' }], recheck_advice: 'Si no mejora en 24-48 horas, contacta con tu veterinario.', context_notes: [{ kind: 'missing_context', detail: 'No se indicó el sexo.', urgency: 'emergency_now' }] })
  expect(html).toContain('Vigila estos signos')
  expect(html).toContain('Sangre en el &lt;vómito&gt; — Urgencia veterinaria ya')
  expect(html).toContain('Si no mejora en 24-48 horas')
  expect(html).toContain('No se indicó el sexo.')
  expect(html.indexOf('Primero')).toBeLessThan(html.indexOf('Segundo'))
})

test('source labels tell pages on the same site apart', async () => {
  const { sourceHost } = await import('./checkReport')
  expect(sourceHost('https://www.pdsa.org.uk/pet-help-and-advice/pet-health-hub/conditions/fleas-on-cats')).toBe('pdsa.org.uk · fleas on cats')
  expect(sourceHost('https://www.pdsa.org.uk/media/5834/phh_dog_c_fleas-on-dogs.pdf')).toBe('pdsa.org.uk · phh dog c fleas on dogs')
  expect(sourceHost('https://vethelpdirect.com/?p=7623')).toBe('vethelpdirect.com')
  expect(sourceHost('https://vetmed.illinois.edu/5580')).toBe('vetmed.illinois.edu')
  expect(sourceHost('not a url')).toBe('not a url')
})
