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
