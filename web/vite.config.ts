import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') } } },
  plugins: [react(), VitePWA({
    // Registered in src/pwa.ts, which only reloads automatically before the person
    // has interacted, so an update cannot interrupt an active symptom assessment.
    registerType: 'prompt',
    injectRegister: false,
    manifest: {
      id: '/', start_url: '/', scope: '/', lang: 'en',
      name: 'PETAdvice', short_name: 'PETAdvice',
      description: 'Urgency and preventive care guidance for cats and dogs.',
      theme_color: '#1d5b4b', background_color: '#fbfcf8', display: 'standalone',
      icons: [{ src: '/petadvice-logo.png', sizes: '1254x1254', type: 'image/png', purpose: 'any' }],
    },
    workbox: {
      globPatterns: ['**/*.{js,css,html,ico,woff2}'],
      navigateFallbackDenylist: [/^\/api\//],
      // A waiting worker would keep serving an old build until every tab closes (iOS
      // Safari rarely closes tabs). Activate new builds immediately; src/pwa.ts then
      // reloads or offers a refresh.
      skipWaiting: true,
      clientsClaim: true,
      cleanupOutdatedCaches: true,
      // Private responses and medical checks must never use an offline API cache.
      runtimeCaching: [],
    },
  })],
})
