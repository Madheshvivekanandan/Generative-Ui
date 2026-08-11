import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The /api proxy means the frontend talks to a same-origin URL in dev, so
// nothing here has to know the backend's port.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
