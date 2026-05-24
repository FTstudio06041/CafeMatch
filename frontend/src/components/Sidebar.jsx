import React, { useState, useEffect, useContext } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../ChatPage.css'; // 保留側欄的相關 CSS 樣式

export default function Sidebar() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [sessions, setSessions] = useState([]);

  // 解析 URL 以取得當前的 active 狀態
  const query = new URLSearchParams(location.search);
  const currentChatId = query.get('id');

  // 取得對話紀錄清單
  const fetchSessions = async () => {
    if (!user) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/sessions`, {
        credentials: 'include'
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error('載入對話紀錄失敗:', e);
    }
  };

  useEffect(() => {
    fetchSessions();

    // 監聽全局自訂事件，當 ChatPage 更新或新增對話時重新抓取清單
    const handleChatUpdated = () => fetchSessions();
    window.addEventListener('chat-updated', handleChatUpdated);
    return () => window.removeEventListener('chat-updated', handleChatUpdated);
  }, [user]);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('確定要刪除此對話嗎？')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/sessions/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (currentChatId === id) {
          navigate('/chat');
        }
        window.dispatchEvent(new Event('chat-updated'));
      }
    } catch (err) {
      console.error('刪除對話失敗:', err);
    }
  };

  return (
    <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
      <button className="toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="9" y1="3" x2="9" y2="21"></line>
        </svg>
      </button>

      <button className="user-profile-btn" onClick={() => navigate('/profile')}>
        <div className="user-avatar" style={{ backgroundColor: user?.picture ? 'transparent' : 'var(--accent-color)' }}>
          {user?.picture ? <img src={user.picture} alt="avatar" style={{width: '100%', borderRadius: '50%'}} /> : 'U'}
        </div>
        <span className="user-name text-label">{user?.name || '使用者名稱'}</span>
      </button>

      <button className="new-chat-btn" onClick={() => navigate('/chat?id=new')}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        <span className="text-label">新增對話</span>
      </button>

      <div className="history-label text-label">對話紀錄</div>
      <div className="chat-list">
        {sessions.length === 0 ? (
          <div className="empty-sidebar-msg">尚無對話紀錄</div>
        ) : (
          sessions.map(chat => (
            <div 
              key={chat.id} 
              className={`chat-item ${chat.id === currentChatId ? 'active' : ''}`} 
              onClick={() => navigate(`/chat?id=${chat.id}`)}
            >
              <div className="chat-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
              <span className="chat-title text-label">{chat.title}</span>
              <button className="delete-btn" onClick={(e) => handleDelete(e, chat.id)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
