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

// 預先宣告所有實際用到的相依套件，強迫 Vite 在啟動時一次打包完。
// 不宣告的話，頁面是 lazy 載入的（App.jsx 的 lazy()），每進一個 chunk 才發現
// 新套件，Vite 就重跑一次 optimize 並換掉模組 URL 的 ?v= hash。本機幾十毫秒
// 內就結束所以看不出來，但穿過 Cloudflare 隧道時模組請求慢，同一次載入會混到
// 不同世代的 chunk —— 出現兩份 React，hooks 的 dispatcher 是 null，
// 畫面直接掛在 "Cannot read properties of null (reading 'useState')"。
const optimizeDeps = {
  include: [
    'react',
    'react-dom',
    'react-dom/client',
    'react/jsx-runtime',
    'react/jsx-dev-runtime',
    'react-router-dom',
    'lucide-react',
    'framer-motion',
    'typewriter-effect',
    'recharts',
    'react-cropper',
  ],
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps,
  server: {
    host: true,        // 綁定 0.0.0.0，外部連線才進得來
    allowedHosts,
    proxy,
    // dev 模式的模組一律不准快取。掛在 Cloudflare 後面時，CF 的 Browser Cache TTL
    // 會把 max-age=14400 蓋到 /src/** 上（實測如此），訪客的瀏覽器就會抱著最多
    // 四小時前的模組不放；那些舊模組裡的 import 寫死了過期的 ?v= hash，
    // 一旦 Vite 重新 optimize 換了 hash，同一次載入就會混到兩份 React，
    // 掛在 "Cannot read properties of null (reading 'useState')"。
    // 註：這條只讓來源明確表態，CF 那邊仍要設成 Respect Existing Headers 才會生效。
    headers: {
      'Cache-Control': 'no-store',
    },
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
