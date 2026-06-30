import { useContext, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthContext, AuthProvider } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import { ChatProvider } from './context/ChatContext';
import './App.css';
import GlobalAnnouncementModal from './components/GlobalAnnouncementModal';
import MainLayout from './layouts/MainLayout';

// 延遲載入 (Lazy Loading) 頁面元件
const LandingPage = lazy(() => import('./pages/LandingPage'));
const ChatPage = lazy(() => import('./pages/ChatPage'));
const CommunityPage = lazy(() => import('./pages/CommunityPage'));
const ExplorePage = lazy(() => import('./pages/ExplorePage'));
const ProfilePage = lazy(() => import('./pages/ProfilePage'));
const QuizPage = lazy(() => import('./pages/QuizPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const PostViewPage = lazy(() => import('./pages/PostViewPage'));


function MainLayoutWrapper() {
  return (
    <MainLayout>
      <Outlet />
    </MainLayout>
  );
}

function AppContent() {
  const { user, isLoading } = useContext(AuthContext);

  if (isLoading) return <div style={{ padding: '2rem' }}>載入中...</div>;

  return (
    <Router>
      <ChatProvider>
      <Suspense fallback={<div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: 'var(--text-color)' }}>載入頁面中...</div>}>
        <Routes>
          <Route path="/" element={!user ? <LandingPage /> : <Navigate to="/chat" />} />
          
          {/* 需要 MainLayout 的路由群組 */}
          <Route element={user ? <MainLayoutWrapper /> : <Navigate to="/" />}>
            <Route path="/post/:id" element={<PostViewPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/community" element={<CommunityPage />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/quiz" element={<QuizPage />} />
            <Route path="/admin" element={user?.is_admin ? <AdminPage /> : <Navigate to="/" />} />
          </Route>
        </Routes>
      </Suspense>
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