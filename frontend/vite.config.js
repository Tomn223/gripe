import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backend = process.env.GRIPE_BACKEND_URL || 'http://127.0.0.1:8000'

// The frontend only ever talks to /api; Vite proxies it to the FastAPI backend.
// No API keys live in the frontend.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: Number(process.env.GRIPE_FRONTEND_PORT || 5173),
    proxy: { '/api': { target: backend, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') } },
  },
  preview: {
    proxy: { '/api': { target: backend, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') } },
  },
})
