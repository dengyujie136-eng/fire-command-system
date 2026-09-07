import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import cesium from 'vite-plugin-cesium'

export default defineConfig({
  plugins: [vue(), cesium()],
  server: {
    proxy: {
      '/api/agent': {
        target: 'http://localhost:8100',
        changeOrigin: true
      },
      '/agent': {
        target: 'http://localhost:8100',
        changeOrigin: true
      },
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/hotspot': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})
