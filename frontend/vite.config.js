import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  server: {
    proxy: {
      // API 請求維持 changeOrigin: true
      '/api': {
        target: 'http://ec2-15-135-237-120.ap-southeast-2.compute.amazonaws.com:5000',
        changeOrigin: true,
      },
      // 登入相關的路由設為 false，保留 localhost 的 Host 標頭
      '/login': {
        target: 'http://ec2-15-135-237-120.ap-southeast-2.compute.amazonaws.com:5000',
        changeOrigin: false,
      },
      '/logout': {
        target: 'http://ec2-15-135-237-120.ap-southeast-2.compute.amazonaws.com:5000',
        changeOrigin: false,
      },
      '/auth': {
        target: 'http://ec2-15-135-237-120.ap-southeast-2.compute.amazonaws.com:5000',
        changeOrigin: false,
      }
    }
  },
  plugins: [react()],
})