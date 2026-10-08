import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'
import vercel from './vercel.json' with { type: 'json' }

// `vite preview` serves the same headers as Vercel (vercel.json). For a local check against a
// local backend, PREVIEW_API_ORIGIN (e.g. http://127.0.0.1:8001) replaces the Render address in
// connect-src; unset = exactly the vercel.json headers.
const RENDER_API_ORIGIN = 'https://firemap-api-91u5.onrender.com'
const previewHeaders = Object.fromEntries(vercel.headers[0].headers.map(({ key, value }) => [
  key,
  key === 'Content-Security-Policy' && process.env.PREVIEW_API_ORIGIN
    ? value.replace(RENDER_API_ORIGIN, process.env.PREVIEW_API_ORIGIN)
    : value,
]))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  preview: { headers: previewHeaders },
})
