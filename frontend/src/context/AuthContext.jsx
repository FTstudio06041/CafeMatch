import React, { createContext, useState, useEffect } from 'react';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // 共用的 API 基礎路徑
  const API_BASE_URL = 'http://localhost:5000';

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
    // 導向 Flask 的登入路由
    window.location.href = `${API_BASE_URL}/login`;
  };

  const logout = () => {
    // 導向 Flask 的登出路由
    window.location.href = `${API_BASE_URL}/logout`;
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, API_BASE_URL }}>
      {children}
    </AuthContext.Provider>
  );
};