import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  build: {
    outDir: '../web/modern', emptyOutDir: true,
    lib: { entry: 'src/main.tsx', name: 'PLUPModern', formats: ['iife'], fileName: () => 'modern.js', cssFileName: 'modern' },
  },
})
