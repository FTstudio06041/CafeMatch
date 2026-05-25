import React, { useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, AuthProvider } from './context/AuthContext';
import './App.css';
import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage';
import CommunityPage from './pages/CommunityPage';
import ExplorePage from './pages/ExplorePage';
import ProfilePage from './pages/ProfilePage';
import QuizPage from './pages/QuizPage';
import AdminPage from './pages/AdminPage';
import PostViewPage from './pages/PostViewPage';
import GlobalAnnouncementModal from './components/GlobalAnnouncementModal';

function AppContent() {
  const { user, isLoading } = useContext(AuthContext);

  if (isLoading) return <div style={{ padding: '2rem' }}>載入中...</div>;

  return (
    <Router>
      <Routes>
        <Route path="/" element={!user ? <LandingPage /> : <Navigate to="/chat" />} />
        <Route path="/post/:id" element={<PostViewPage />} />
        <Route path="/chat" element={user ? <ChatPage /> : <Navigate to="/" />} />
        <Route path="/community" element={user ? <CommunityPage /> : <Navigate to="/" />} />
        <Route path="/explore" element={user ? <ExplorePage /> : <Navigate to="/" />} />
        <Route path="/profile" element={user ? <ProfilePage /> : <Navigate to="/" />} />
        <Route path="/quiz" element={user ? <QuizPage /> : <Navigate to="/" />} />
        <Route path="/admin" element={user?.is_admin ? <AdminPage /> : <Navigate to="/" />} />
      </Routes>
      <GlobalAnnouncementModal />
    </Router>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;