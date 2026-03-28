import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import b24ui from '@bitrix24/b24ui-nuxt/vite'
import { resolve } from 'node:path'

export default defineConfig({
  base: './',
  plugins: [
    vue(),
    tailwindcss(),
    b24ui({
      colorMode: false,
    }),
  ],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
