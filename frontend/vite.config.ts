import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'
import { fileURLToPath } from 'node:url'
import { appLocation } from './config/appLocation.ts'

const sharedEnvDir = fileURLToPath(new URL('..', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, sharedEnvDir, '')
  const app = appLocation(env.VITE_APP_URL)

  return {
    envDir: sharedEnvDir,
    base: app.base,
    plugins: [react(), tailwindcss()],
    server: {
      host: app.host,
      port: app.port,
      strictPort: true,
      origin: app.origin,
      proxy: {
        '/api': {
          target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
