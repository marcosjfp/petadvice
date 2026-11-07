export const UPDATE_READY_EVENT = 'petadvice:update-ready'

// The service worker serves the cached build first and installs a new one in the
// background (skipWaiting/clientsClaim), so without this the new version only shows
// on the next visit. Reload straight away if the person has not touched the page;
// otherwise a reload could discard an in-progress check, so offer it instead.
export function registerServiceWorker() {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  let interacted = false
  const markInteracted = () => { interacted = true }
  window.addEventListener('pointerdown', markInteracted, { once: true, capture: true })
  window.addEventListener('keydown', markInteracted, { once: true, capture: true })
  const replacingOldVersion = Boolean(navigator.serviceWorker.controller)
  let reloading = false
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (!replacingOldVersion || reloading) return
    if (!interacted) { reloading = true; window.location.reload(); return }
    window.dispatchEvent(new Event(UPDATE_READY_EVENT))
  })
  navigator.serviceWorker.register('/sw.js', { scope: '/', updateViaCache: 'none' }).then((registration) => {
    const check = () => { registration.update().catch(() => { /* Offline; try again later. */ }) }
    window.setInterval(check, 30 * 60 * 1000)
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') check() })
  }).catch(() => { /* The app works without offline support. */ })
}
