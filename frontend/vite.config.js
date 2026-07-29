import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 後端位置（可用 BACKEND_ORIGIN 覆寫，例如後端跑在別台機器時）
const BACKEND = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:5000'

// 對外開放的網域：Vite 預設只允許 localhost，外網網域要在這裡列出，
// 否則會回「Blocked request. This host is not allowed.」
// 多個網域用逗號分隔寫在 ALLOWED_HOSTS 環境變數即可。
const allowedHosts = [
  'cafematch.sumo0711.top',
  ...(process.env.ALLOWED_HOSTS || '').split(',').map(h => h.trim()).filter(Boolean),
]

// 後端路徑代理：讓外網訪客的 API 請求走同源（/api/...），
// 由 Vite 轉發到本機後端 —— 不必把 5000 埠也對外開放，也沒有 CORS 問題。
const backendPaths = ['/api', '/login', '/logout', '/auth']
const proxy = Object.fromEntries(
  backendPaths.map(path => [path, { target: BACKEND, changeOrigin: true }])
)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,        // 綁定 0.0.0.0，外部連線才進得來
    allowedHosts,
    proxy,
  },
  preview: {
    host: true,
    allowedHosts,
    proxy,
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router-dom')) {
              return 'vendor';
            }
            if (id.includes('lucide-react')) {
              return 'ui';
            }
          }
        }
      }
    }
  }
})
