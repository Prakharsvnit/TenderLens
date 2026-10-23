import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // amazon-cognito-identity-js expects a Node-style global.
  define: { global: 'globalThis' },
  server: { port: 5173 },
})
