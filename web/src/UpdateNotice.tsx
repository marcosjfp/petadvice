import { useEffect, useState } from 'react'
import { useI18n } from './i18n'
import { UPDATE_READY_EVENT } from './pwa'

export default function UpdateNotice() {
  const { t } = useI18n()
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const show = () => setReady(true)
    window.addEventListener(UPDATE_READY_EVENT, show)
    return () => window.removeEventListener(UPDATE_READY_EVENT, show)
  }, [])
  if (!ready) return null
  return <div className="update-notice" role="status"><span>{t.update.ready}</span><button type="button" onClick={() => window.location.reload()}>{t.update.refresh}</button><button type="button" className="update-dismiss" aria-label={t.update.dismiss} onClick={() => setReady(false)}>×</button></div>
}
