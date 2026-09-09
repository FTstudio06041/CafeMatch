/* eslint-disable react-refresh/only-export-components */
import { createContext, useState, useEffect, useCallback } from 'react';
import { apiClient, API_BASE_URL as ApiUrl } from '../utils/apiClient';
import { logger } from '../utils/logger';
export const AuthContext = createContext();

// 這些瀏覽器暫存都是綁定「某一個使用者」的，換人就必須清掉。
// 否則同一台機器／同一個分頁換帳號後，下一個人會看到上一個人的測驗結果，
// 甚至拿他的五維分數去跑推薦（latestQuizScores 會被當成 GNN 輸入）。
// 注意不含 forceQuiz：那是新用戶強制測驗的旗標，由 QuizPage 在
// ?welcome=true 時同步設定，而這裡的檢查是 async 的、會晚一步到，
// 清掉會把剛設好的旗標抹掉。它也不含個人資料，殘留最多是讓下一個
// 人也被要求做一次測驗。
const PERSONAL_SESSION_KEYS = ['quizResultCache'];
const PERSONAL_LOCAL_KEYS = ['latestQuizScores', 'targetQuizContext'];
// 上一次登入者的識別，用來判斷「是不是換人了」
const LAST_IDENTITY_KEY = 'lastUserIdentity';

const clearPersonalCache = () => {
  try {
    PERSONAL_SESSION_KEYS.forEach((k) => sessionStorage.removeItem(k));
    PERSONAL_LOCAL_KEYS.forEach((k) => localStorage.removeItem(k));
  } catch {
    // 隱私模式等情況下 storage 可能不可用，忽略即可
  }
};

/**
 * 比對這次的登入身分與上一次，不同就把個人暫存清乾淨。
 *
 * 綁在身分變更而不是只綁登出：使用者可能直接關瀏覽器、或 session 過期，
 * 那些情況下 logout() 根本不會被呼叫。
 */
const syncPersonalCache = (identity) => {
  const next = identity || '';
  try {
    if (localStorage.getItem(LAST_IDENTITY_KEY) !== next) {
      clearPersonalCache();
      localStorage.setItem(LAST_IDENTITY_KEY, next);
    }
  } catch {
    // 同上，storage 不可用時直接略過
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // 共用的 API 基礎路徑 (已移至 apiClient)
  const API_BASE_URL = ApiUrl;

  const checkAuthStatus = useCallback(async () => {
    const handleGuestFallback = () => {
      // 訪客與未登入都算「沒有身分」，與上一個登入者不同就會清掉他的暫存
      syncPersonalCache('');
      if (localStorage.getItem('guestMode') === 'true') {
        setUser({ isGuest: true, name: "訪客", email: "", picture: "", is_admin: false, is_logged_in: true });
      } else {
        setUser(null);
      }
    };

    try {
      const data = await apiClient('/api/me', { suppressToast: true });
      if (data && data.is_logged_in) {
        localStorage.removeItem('guestMode');
        syncPersonalCache(data.email);
        setUser(data);
      } else {
        handleGuestFallback();
      }
    } catch (error) {
      logger.error('Auth check failed:', error);
      handleGuestFallback();
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkAuthStatus();
  }, [checkAuthStatus]);

  const login = () => {
    // 導向 Flask 的登入路由
    window.location.href = `${API_BASE_URL}/login`;
  };

  const logout = () => {
    localStorage.removeItem('guestMode');
    // 登出當下就清掉個人暫存，不要留到下一個人登入才處理
    clearPersonalCache();
    localStorage.removeItem(LAST_IDENTITY_KEY);
    // 導向 Flask 的登出路由
    window.location.href = `${API_BASE_URL}/logout`;
  };

  const loginAsGuest = () => {
    localStorage.setItem('guestMode', 'true');
    setUser({ isGuest: true, name: "訪客", email: "", picture: "", is_admin: false, is_logged_in: true });
    window.location.href = '/chat';
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, loginAsGuest, API_BASE_URL }}>
      {children}
    </AuthContext.Provider>
  );
};