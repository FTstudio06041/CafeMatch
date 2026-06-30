/* eslint-disable react-refresh/only-export-components */
import { createContext, useState, useEffect, useCallback } from 'react';
import { apiClient, API_BASE_URL as ApiUrl } from '../utils/apiClient';
import { logger } from '../utils/logger';
export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // 共用的 API 基礎路徑 (已移至 apiClient)
  const API_BASE_URL = ApiUrl;

  const checkAuthStatus = useCallback(async () => {
    const handleGuestFallback = () => {
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