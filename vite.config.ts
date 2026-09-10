import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import cesium from 'vite-plugin-cesium'

export default defineConfig({
  plugins: [vue(), cesium()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8200',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8200',
        ws: true,
        changeOrigin: true,
      }
    }
  }
})
