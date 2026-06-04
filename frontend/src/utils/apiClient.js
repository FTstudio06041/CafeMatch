import { logger } from './logger';

// 判斷是否在 devtunnels 或 localhost
export const API_BASE_URL = window.location.hostname.includes('devtunnels.ms')
  ? `https://${window.location.host.replace('-5173', '-5000')}`
  : (import.meta.env.VITE_API_URL || 'http://localhost:5000');

/**
 * 統一的 API 請求工具
 * - 自動加上 Credentials (以便帶上 Session Cookie)
 * - 統一攔截錯誤與 401 狀態
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
      
      // 可以自訂一個 Error 物件帶上 status
      const error = new Error(errorMsg);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  } catch (error) {
    logger.error(`網路或伺服器錯誤 [${options.method || 'GET'} ${endpoint}]:`, error.message);
    throw error;
  }
};
