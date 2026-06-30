/* eslint-disable react-refresh/only-export-components */
import { createContext, useState, useCallback, useEffect } from 'react';
import { toastEmitter } from '../utils/toast';
import '../components/Toast.css';

export const ToastContext = createContext();

let toastIdCounter = 0;

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const removeToast = useCallback((id) => {
    // 先標記為 hiding 以觸發退場動畫
    setToasts(prev => prev.map(t => t.id === id ? { ...t, hiding: true } : t));
    
    // 等待動畫結束後移除
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 300); // 對應 CSS 轉場時間
  }, []);

  const addToast = useCallback((message, type = 'info', title = '') => {
    const id = ++toastIdCounter;
    setToasts(prev => [...prev, { id, message, type, title, hiding: false }]);

    // 自動隱藏計時器
    setTimeout(() => {
      removeToast(id);
    }, 4000);
  }, [removeToast]);

  useEffect(() => {
    const handleAddToast = (e) => {
      addToast(e.detail.message, e.detail.type, e.detail.title);
    };
    toastEmitter.addEventListener('add_toast', handleAddToast);
    return () => toastEmitter.removeEventListener('add_toast', handleAddToast);
  }, [addToast]);

  // 提供輔助函式
  const toast = {
    info: (msg, title) => addToast(msg, 'info', title),
    success: (msg, title) => addToast(msg, 'success', title),
    error: (msg, title) => addToast(msg, 'error', title),
  };

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast 渲染區塊 */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type} ${t.hiding ? 'hiding' : ''}`}>
            {t.type === 'success' && (
              <svg className="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
            )}
            {t.type === 'error' && (
              <svg className="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            )}
            {t.type === 'info' && (
              <svg className="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="16" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12.01" y2="8"></line>
              </svg>
            )}
            
            <div className="toast-content">
              {t.title && <div className="toast-title">{t.title}</div>}
              <div className="toast-message">{t.message}</div>
            </div>
            
            <button className="toast-close" onClick={() => removeToast(t.id)}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};
