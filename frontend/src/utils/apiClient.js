import { logger } from './logger';
import { toast } from './toast';

// API 位址的決定順序：
//   1. VITE_API_URL（明確指定時最優先）
//   2. devtunnels：把 -5173 換成 -5000
//   3. localhost 開發：直接打本機後端 5000
//   4. 其他網域（外網）：走同源空字串，由 Vite / 反向代理把 /api 轉給後端
//      —— 不能寫死 localhost:5000，那會變成連到「訪客自己的電腦」
const hostname = window.location.hostname;
const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';

export const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  (hostname.includes('devtunnels.ms')
    ? `https://${window.location.host.replace('-5173', '-5000')}`
    : (isLocalhost ? 'http://localhost:5000' : ''));

/**
 * 統一的 API 請求工具
 * - 自動加上 Credentials (以便帶上 Session Cookie)
 * - 統一攔截錯誤與 401 狀態，並自動彈出 Toast
 * 
 * @param {string} endpoint 請求端點，如 '/api/explore'
 * @param {object} options fetch 參數選項
 * @returns {Promise<any>} 回傳 JSON 或拋出錯誤
 */
export const apiClient = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include', // 自動帶上 cookies
  };

  const finalOptions = { ...defaultOptions, ...options };

  try {
    const response = await fetch(url, finalOptions);
    
    // 若回應包含 json 格式的錯誤訊息，則拋出
    let data = null;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    }

    if (!response.ok) {
      const errorMsg = data?.error || data?.message || `請求失敗 (HTTP ${response.status})`;
      logger.error(`API 錯誤 [${options.method || 'GET'} ${endpoint}]:`, errorMsg);
      
      if (!options.suppressToast) {
        toast.error(errorMsg); // <--- 全域自動顯示錯誤 (除非被禁用)
      }
      
      const error = new Error(errorMsg);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (error) {
    if (!error.status) { // 只有在沒有 status 的時候（代表網路連線失敗或 fetch 拋出例外）才顯示
      logger.error(`網路或伺服器錯誤 [${options.method || 'GET'} ${endpoint}]:`, error.message);
      toast.error('無法連接到伺服器，請檢查網路狀態'); // <--- 全域自動顯示錯誤
    }
    throw error;
  }
};
