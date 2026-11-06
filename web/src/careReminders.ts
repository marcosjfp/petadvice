// Client-side calendar reminders for care guides (RFC 5545 iCalendar). Nothing is sent to the server.

export type CareReminder = {
  /** Care item id, used for a stable UID prefix and the file name. */
  id: string
  title: string
  description: string
  /** Repeat every N days; null or undefined creates a single event. */
  intervalDays?: number | null
  /** First occurrence (all-day, in the user's local calendar). */
  start: Date
}

const CRLF = '\r\n'
const AVERAGE_MONTH_DAYS = 365.25 / 12

/** Escape a TEXT value: backslash, semicolon, comma and newlines (RFC 5545 §3.3.11). */
export function escapeIcsText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r\n|\r|\n/g, '\\n')
}

/** Fold content lines longer than 75 octets (RFC 5545 §3.1) without splitting UTF-8 characters. */
export function foldIcsLine(line: string): string {
  const encoder = new TextEncoder()
  const parts: string[] = []
  let current = ''
  let size = 0
  for (const character of line) {
    const bytes = encoder.encode(character).length
    const limit = parts.length === 0 ? 75 : 74 // continuation lines start with a space
    if (size + bytes > limit) {
      parts.push(current)
      current = ''
      size = 0
    }
    current += character
    size += bytes
  }
  parts.push(current)
  return parts.join(`${CRLF} `)
}

/** Map a day interval to the most natural RRULE: daily, weekly, monthly or yearly. */
export function recurrenceRule(intervalDays: number): string {
  const days = Math.round(intervalDays)
  if (!Number.isFinite(days) || days < 1) throw new RangeError('Reminder interval must be at least one day')
  const withInterval = (frequency: string, count: number) => `RRULE:FREQ=${frequency}${count > 1 ? `;INTERVAL=${count}` : ''}`
  if (days % 365 === 0) return withInterval('YEARLY', days / 365)
  // Prefer months when the interval is within two days of a whole number of months (30, 91, 182…).
  const months = Math.round(days / AVERAGE_MONTH_DAYS)
  if (months >= 1 && Math.abs(months * AVERAGE_MONTH_DAYS - days) <= 2) return withInterval('MONTHLY', months)
  if (days % 7 === 0) return withInterval('WEEKLY', days / 7)
  return withInterval('DAILY', days)
}

const pad = (value: number) => String(value).padStart(2, '0')
const formatDate = (date: Date) => `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`
const formatUtc = (date: Date) => `${date.getUTCFullYear()}${pad(date.getUTCMonth() + 1)}${pad(date.getUTCDate())}T${pad(date.getUTCHours())}${pad(date.getUTCMinutes())}${pad(date.getUTCSeconds())}Z`

function randomId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto ? crypto.randomUUID() : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

/** The next calendar day at local midnight: a sensible default first reminder. */
export function tomorrow(now = new Date()): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
}

export function buildCareReminderIcs(reminder: CareReminder, now = new Date(), uid = `${reminder.id}-${randomId()}@petadvice`): string {
  const end = new Date(reminder.start.getFullYear(), reminder.start.getMonth(), reminder.start.getDate() + 1)
  const lines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//PETAdvice//Care reminders//EN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `UID:${uid}`,
    `DTSTAMP:${formatUtc(now)}`,
    `DTSTART;VALUE=DATE:${formatDate(reminder.start)}`,
    `DTEND;VALUE=DATE:${formatDate(end)}`,
    ...(reminder.intervalDays ? [recurrenceRule(reminder.intervalDays)] : []),
    `SUMMARY:${escapeIcsText(reminder.title)}`,
    `DESCRIPTION:${escapeIcsText(reminder.description)}`,
    'TRANSP:TRANSPARENT',
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    'TRIGGER:PT9H', // 09:00 on the day of an all-day event
    `DESCRIPTION:${escapeIcsText(reminder.title)}`,
    'END:VALARM',
    'END:VEVENT',
    'END:VCALENDAR',
  ]
  return lines.map(foldIcsLine).join(CRLF) + CRLF
}

export function reminderFileName(id: string) {
  return `petadvice-${id.replace(/[^a-z0-9-]/gi, '')}.ics`
}
