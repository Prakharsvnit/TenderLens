import { execSync } from 'node:child_process'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import pkg from './package.json' with { type: 'json' }

function gitSha(): string {
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return 'local'
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // amazon-cognito-identity-js expects a Node-style global.
    global: 'globalThis',
    __BUILD__: JSON.stringify({ version: pkg.version, sha: gitSha(), time: new Date().toISOString() }),
  },
  server: { port: 5173 },
})
