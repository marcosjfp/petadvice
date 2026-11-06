import { describe, expect, test } from 'vitest'
import { buildCareReminderIcs, escapeIcsText, foldIcsLine, recurrenceRule, reminderFileName, tomorrow } from './careReminders'

const now = new Date(Date.UTC(2026, 10, 6, 14, 5, 9))
const start = new Date(2026, 10, 7)

describe('escapeIcsText', () => {
  test('escapes backslashes, semicolons, commas and every newline style', () => {
    expect(escapeIcsText('a\\b; c, d\ne\r\nf\rg')).toBe('a\\\\b\\; c\\, d\\ne\\nf\\ng')
  })
})

describe('recurrenceRule', () => {
  test.each([
    [1, 'RRULE:FREQ=DAILY'], [3, 'RRULE:FREQ=DAILY;INTERVAL=3'], [7, 'RRULE:FREQ=WEEKLY'], [14, 'RRULE:FREQ=WEEKLY;INTERVAL=2'],
    [21, 'RRULE:FREQ=WEEKLY;INTERVAL=3'], [30, 'RRULE:FREQ=MONTHLY'], [91, 'RRULE:FREQ=MONTHLY;INTERVAL=3'],
    [182, 'RRULE:FREQ=MONTHLY;INTERVAL=6'], [365, 'RRULE:FREQ=YEARLY'], [730, 'RRULE:FREQ=YEARLY;INTERVAL=2'], [45, 'RRULE:FREQ=DAILY;INTERVAL=45'],
  ])('%i days -> %s', (days, rule) => expect(recurrenceRule(days)).toBe(rule))

  test('rejects intervals below one day', () => {
    expect(() => recurrenceRule(0)).toThrow(RangeError)
  })
})

describe('foldIcsLine', () => {
  test('folds at 75 octets without splitting multi-byte characters', () => {
    const line = `SUMMARY:${'é'.repeat(80)}`
    const folded = foldIcsLine(line)
    const parts = folded.split('\r\n')
    expect(parts.length).toBeGreaterThan(1)
    for (const [index, part] of parts.entries()) {
      expect(new TextEncoder().encode(part).length).toBeLessThanOrEqual(75)
      if (index > 0) expect(part.startsWith(' ')).toBe(true)
    }
    expect(parts.map((part, index) => index ? part.slice(1) : part).join('')).toBe(line)
  })

  test('leaves short lines alone', () => {
    expect(foldIcsLine('VERSION:2.0')).toBe('VERSION:2.0')
  })
})

describe('buildCareReminderIcs', () => {
  test('creates a recurring all-day VEVENT with CRLF line endings, DTSTAMP and UID', () => {
    const ics = buildCareReminderIcs({ id: 'prevent-008', title: 'Rex: Trim nails, check paws', description: 'Step 1; clip tips.\nStep 2', intervalDays: 14, start }, now, 'fixed-uid@petadvice')
    expect(ics.endsWith('\r\n')).toBe(true)
    expect(ics.replace(/\r\n/g, '')).not.toMatch(/[\r\n]/)
    const lines = ics.split('\r\n')
    expect(lines.slice(0, 2)).toEqual(['BEGIN:VCALENDAR', 'VERSION:2.0'])
    expect(lines).toContain('PRODID:-//PETAdvice//Care reminders//EN')
    expect(lines).toContain('UID:fixed-uid@petadvice')
    expect(lines).toContain('DTSTAMP:20261106T140509Z')
    expect(lines).toContain('DTSTART;VALUE=DATE:20261107')
    expect(lines).toContain('DTEND;VALUE=DATE:20261108')
    expect(lines).toContain('RRULE:FREQ=WEEKLY;INTERVAL=2')
    expect(lines).toContain('SUMMARY:Rex: Trim nails\\, check paws')
    expect(lines).toContain('DESCRIPTION:Step 1\\; clip tips.\\nStep 2')
    expect(lines.filter((line) => line.startsWith('BEGIN:'))).toEqual(['BEGIN:VCALENDAR', 'BEGIN:VEVENT', 'BEGIN:VALARM'])
    expect(lines.at(-2)).toBe('END:VCALENDAR')
  })

  test('one-off reminders are a single event without RRULE', () => {
    const ics = buildCareReminderIcs({ id: 'prevent-016', title: 'Puppy essentials', description: 'Book a first vet check.', intervalDays: null, start }, now)
    expect(ics).not.toContain('RRULE')
    expect(ics).toMatch(/UID:prevent-016-.+@petadvice/)
  })

  test('uses a fresh UID per download', () => {
    const reminder = { id: 'prevent-013', title: 'Brush teeth', description: 'Daily.', intervalDays: 1, start }
    const uid = (ics: string) => ics.split('\r\n').find((line) => line.startsWith('UID:'))
    expect(uid(buildCareReminderIcs(reminder, now))).not.toBe(uid(buildCareReminderIcs(reminder, now)))
  })
})

test('helpers produce safe file names and a next-day local start', () => {
  expect(reminderFileName('prevent-001')).toBe('petadvice-prevent-001.ics')
  expect(reminderFileName('../x y')).toBe('petadvice-xy.ics')
  const next = tomorrow(new Date(2026, 11, 31, 22, 30))
  expect([next.getFullYear(), next.getMonth(), next.getDate(), next.getHours()]).toEqual([2027, 0, 1, 0])
})

test('a limited reminder series ends after its occurrence count', () => {
  expect(recurrenceRule(7, 8)).toBe('RRULE:FREQ=WEEKLY;COUNT=8')
  expect(recurrenceRule(182, null)).toBe('RRULE:FREQ=MONTHLY;INTERVAL=6')
})
