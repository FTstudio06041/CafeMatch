import { useContext, useEffect, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ChatProvider } from './context/ChatContext';
import './App.css';
import GlobalAnnouncementModal from './components/GlobalAnnouncementModal';
import AppShell from './components/layout/AppShell';

// 延遲載入 (Lazy Loading) 頁面元件
const loadHomePage = () => import('./pages/HomePage');
const loadQuizPage = () => import('./pages/QuizPage');
const HomePage = lazy(loadHomePage);
const QuizPage = lazy(loadQuizPage);
const AdminPage = lazy(() => import('./pages/AdminPage'));

function AppContent() {
  const { user, isLoading } = useContext(AuthContext);

  // 首頁與測驗頁在閒置時先載好：切頁動畫才不會卡在「載入頁面中」
  useEffect(() => {
    const preload = () => { loadHomePage(); loadQuizPage(); };
    if ('requestIdleCallback' in window) {
      const id = window.requestIdleCallback(preload, { timeout: 3000 });
      return () => window.cancelIdleCallback(id);
    }
    const timer = setTimeout(preload, 1500);
    return () => clearTimeout(timer);
  }, []);

  if (isLoading) return <div style={{ padding: '2rem' }}>載入中...</div>;

  return (
    <Router>
      <ChatProvider>
        <Routes>
          {/* 首頁公開：不登入也能看地圖、店家、和 AI 聊天 */}
          <Route element={<AppShell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/quiz" element={<QuizPage />} />
            <Route path="/admin" element={user?.is_admin ? <AdminPage /> : <Navigate to="/" replace />} />
          </Route>
          {/* 舊網址（/chat、/explore、/community、/profile、/post/:id…）一律回首頁 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <GlobalAnnouncementModal />
      </ChatProvider>
    </Router>
  );
}

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ToastProvider>
  );
}

export default App;
