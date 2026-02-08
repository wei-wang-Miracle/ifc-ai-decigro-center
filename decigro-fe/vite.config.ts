import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
        '/api/dg': {
            target: 'http://127.0.0.1:8080',
            changeOrigin: true
        },
        '/api/v1/workflow': {
            target: 'http://127.0.0.1:8001',
            changeOrigin: true
        }
    }
  }
})
