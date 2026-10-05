import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // The homepage's evaluation numbers are checked against the recorded results in the repo root.
  // Test-only: the dev server keeps Vite's default file access.
  server: { fs: { allow: ['.', '../evaluation/results'] } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
    css: true,
  },
})
