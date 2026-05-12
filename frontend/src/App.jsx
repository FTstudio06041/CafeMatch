import React, { useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, AuthProvider } from './context/AuthContext';
import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage';
import ExplorePage from './pages/ExplorePage';
import ProfilePage from './pages/ProfilePage';
import QuizPage from './pages/QuizPage'; // 引入測驗頁

function AppContent() {
  const { user, isLoading } = useContext(AuthContext);

  if (isLoading) return <div style={{ padding: '2rem' }}>載入中...</div>;

  return (
    <Router>
      <Routes>
        <Route path="/" element={!user ? <LandingPage /> : <Navigate to="/chat" />} />
        <Route path="/chat" element={user ? <ChatPage /> : <Navigate to="/" />} />
        <Route path="/explore" element={user ? <ExplorePage /> : <Navigate to="/" />} />
        <Route path="/profile" element={user ? <ProfilePage /> : <Navigate to="/" />} />
        <Route path="/quiz" element={user ? <QuizPage /> : <Navigate to="/" />} />
      </Routes>
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