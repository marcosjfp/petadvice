import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), VitePWA({ registerType: 'autoUpdate', manifest: { name: 'PETAdvice', short_name: 'PETAdvice', description: 'Urgency and preventive care guidance for cats and dogs.', theme_color: '#1d5b4b', background_color: '#fbfcf8', display: 'standalone' } })],
})
