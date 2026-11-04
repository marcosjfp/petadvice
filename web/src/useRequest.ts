import { useCallback, useRef, useState } from 'react'
import { translations } from './i18n'

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : translations().errors.generic
}

// The ref blocks a second submission even before React paints disabled controls.
export function useRequest() {
  const active = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = useCallback(async (action: () => Promise<void>) => {
    if (active.current) return
    active.current = true
    setBusy(true)
    setError('')
    try { await action() } catch (failure) { setError(errorMessage(failure)) }
    finally { active.current = false; setBusy(false) }
  }, [])
  return { busy, error, run, setError }
}
