import React, { createContext, useState, useEffect } from 'react';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  // 判斷是否為 Vercel 雲端環境
  const isProduction = import.meta.env.PROD;

  // 1. 抓資料用的路徑：雲端用 AWS IP，地端用空字串 (配合 Vite Proxy)
  const API_BASE_URL = isProduction
    ? 'http://32.236.46.23:5000'
    : '';

  // 2. 登入跳轉用的絕對路徑：不管地端還雲端，都必須直接飛去 AWS
  const AWS_REAL_URL = 'http://32.236.46.23:5000';

  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/me`, {
        credentials: 'include', // 重要：帶上跨域 Cookie
      });
      if (response.ok) {
        const data = await response.json();
        if (data.is_logged_in) {
          setUser(data);
        } else {
          setUser(null);
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  const login = () => {
    // 導向 Flask 的登入路由 (強制使用 AWS 絕對路徑)
    window.location.href = `${AWS_REAL_URL}/login`;
  };

  const logout = () => {
    // 導向 Flask 的登出路由 (強制使用 AWS 絕對路徑)
    window.location.href = `${AWS_REAL_URL}/logout`;
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, API_BASE_URL }}>
      {children}
    </AuthContext.Provider>
  );
};