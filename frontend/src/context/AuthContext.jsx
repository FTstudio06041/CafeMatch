import React, { createContext, useState, useEffect } from 'react';

export const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // 共用的 API 基礎路徑
  const API_BASE_URL = window.location.hostname.includes('devtunnels.ms')
    ? `https://${window.location.host.replace('-5173', '-5000')}`
    : 'http://localhost:5000';

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    const handleGuestFallback = () => {
      if (localStorage.getItem('guestMode') === 'true') {
        setUser({ isGuest: true, name: "訪客", email: "", picture: "", is_admin: false, is_logged_in: true });
      } else {
        setUser(null);
      }
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/me`, {
        credentials: 'include', // 重要：帶上跨域 Cookie
      });
      if (response.ok) {
        const data = await response.json();
        if (data.is_logged_in) {
          localStorage.removeItem('guestMode');
          setUser(data);
        } else {
          handleGuestFallback();
        }
      } else {
        handleGuestFallback();
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      handleGuestFallback();
    } finally {
      setIsLoading(false);
    }
  };

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