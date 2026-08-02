import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // jsdom não é preferência de estilo: o DOMPurify precisa de um DOM de verdade
  // para sanitizar, e sem `window` ele devolveria a entrada intacta.
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
  },
})
