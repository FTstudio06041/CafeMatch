import React, { useState, useEffect, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, AuthProvider } from './context/AuthContext';
import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage';
import CommunityPage from './pages/CommunityPage'; // 引入社群頁
import ExplorePage from './pages/ExplorePage';
import ProfilePage from './pages/ProfilePage';
import QuizPage from './pages/QuizPage'; // 引入測驗頁
import AdminPage from './pages/AdminPage'; // 引入管理員頁

function AppContent() {
  const { user, isLoading, API_BASE_URL } = useContext(AuthContext);
  const [announcement, setAnnouncement] = useState(null);
  const [showAnnouncement, setShowAnnouncement] = useState(false);

  useEffect(() => {
    if (user) {
      checkAnnouncement();
    } else {
      setShowAnnouncement(false);
      setAnnouncement(null);
    }
  }, [user]);

  const checkAnnouncement = async () => {
    // 防衝突機制：如果當前 URL 包含 welcome=true 參數（新用戶初次歡迎小卡），先不跳出系統公告
    const params = new URLSearchParams(window.location.search);
    if (params.get('welcome') === 'true') {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/announcements/latest`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        if (data.show_popup && data.announcement) {
          setAnnouncement(data.announcement);
          setShowAnnouncement(true);
        }
      }
    } catch (e) {
      console.error('檢查公告失敗:', e);
    }
  };

  const handleCloseAnnouncement = async () => {
    setShowAnnouncement(false);
    if (announcement) {
      try {
        await fetch(`${API_BASE_URL}/api/announcements/read`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch (e) {
        console.error('標記公告已讀失敗:', e);
      }
    }
  };

  if (isLoading) return <div style={{ padding: '2rem' }}>載入中...</div>;

  return (
    <Router>
      <Routes>
        <Route path="/" element={!user ? <LandingPage /> : <Navigate to="/chat" />} />
        <Route path="/chat" element={user ? <ChatPage /> : <Navigate to="/" />} />
        <Route path="/community" element={user ? <CommunityPage /> : <Navigate to="/" />} />
        <Route path="/explore" element={user ? <ExplorePage /> : <Navigate to="/" />} />
        <Route path="/profile" element={user ? <ProfilePage /> : <Navigate to="/" />} />
        <Route path="/quiz" element={user ? <QuizPage /> : <Navigate to="/" />} />
        <Route path="/admin" element={user?.is_admin ? <AdminPage /> : <Navigate to="/" />} />
      </Routes>

      {/* --- 系統最新消息公告彈窗 (Glassmorphism Modal) --- */}
      {showAnnouncement && announcement && (
        <div className="announcement-global-overlay">
          <style>{`
            .announcement-global-overlay {
              position: fixed;
              top: 0;
              left: 0;
              width: 100vw;
              height: 100vh;
              background: rgba(43, 27, 8, 0.4);
              backdrop-filter: blur(12px);
              -webkit-backdrop-filter: blur(12px);
              display: flex;
              align-items: center;
              justify-content: center;
              z-index: 999999;
              animation: annFadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            }
            .announcement-global-modal {
              background: rgba(255, 253, 250, 0.85);
              backdrop-filter: blur(20px);
              border: 1px solid rgba(139, 90, 43, 0.15);
              border-radius: 24px;
              width: 90%;
              max-width: 480px;
              padding: 28px;
              box-shadow: 0 20px 40px rgba(43, 27, 8, 0.15);
              display: flex;
              flex-direction: column;
              gap: 20px;
              animation: annModalUp 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
            }
            .announcement-global-header {
              display: flex;
              align-items: center;
              gap: 12px;
              color: #8b5a2b;
            }
            .announcement-global-header svg {
              animation: annBellRing 2s infinite ease-in-out;
            }
            .announcement-global-header h3 {
              margin: 0;
              font-size: 1.25rem;
              font-weight: 700;
              letter-spacing: 0.5px;
            }
            .announcement-global-body {
              font-size: 1rem;
              line-height: 1.65;
              color: #5c4033;
              white-space: pre-wrap;
              max-height: 240px;
              overflow-y: auto;
              padding-right: 4px;
            }
            .announcement-global-body::-webkit-scrollbar {
              width: 5px;
            }
            .announcement-global-body::-webkit-scrollbar-thumb {
              background: rgba(139, 90, 43, 0.2);
              border-radius: 10px;
            }
            .announcement-global-footer {
              display: flex;
              align-items: center;
              justify-content: space-between;
              border-top: 1px solid rgba(139, 90, 43, 0.08);
              padding-top: 16px;
              margin-top: 4px;
            }
            .announcement-global-time {
              font-size: 0.8rem;
              color: rgba(139, 90, 43, 0.6);
            }
            .announcement-global-btn {
              background: #8b5a2b;
              color: #fffdfa;
              border: none;
              padding: 10px 24px;
              border-radius: 12px;
              font-weight: 600;
              font-size: 0.92rem;
              cursor: pointer;
              transition: all 0.25s ease;
              box-shadow: 0 4px 12px rgba(139, 90, 43, 0.25);
            }
            .announcement-global-btn:hover {
              background: #6f421e;
              transform: translateY(-2px);
              box-shadow: 0 6px 16px rgba(139, 90, 43, 0.35);
            }
            .announcement-global-btn:active {
              transform: translateY(0);
            }
            @keyframes annFadeIn {
              from { opacity: 0; }
              to { opacity: 1; }
            }
            @keyframes annModalUp {
              from { transform: scale(0.9) translateY(40px); opacity: 0; }
              to { transform: scale(1) translateY(0); opacity: 1; }
            }
            @keyframes annBellRing {
              0%, 100% { transform: rotate(0); }
              10%, 30% { transform: rotate(15deg); }
              20%, 40% { transform: rotate(-15deg); }
              50% { transform: rotate(0); }
            }
          `}</style>
          <div className="announcement-global-modal">
            <div className="announcement-global-header">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
              </svg>
              <h3>系統最新消息公告</h3>
            </div>
            <div className="announcement-global-body">
              {announcement.content}
            </div>
            <div className="announcement-global-footer">
              <span className="announcement-global-time">發布於 {announcement.created_at}</span>
              <button className="announcement-global-btn" onClick={handleCloseAnnouncement}>
                我知道了
              </button>
            </div>
          </div>
        </div>
      )}
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