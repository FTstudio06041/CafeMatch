import { useState, useEffect, useContext, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../ChatPage.css'; // 保留側欄的相關 CSS 樣式
import './Sidebar.css';
import { SIDEBAR_UI_TEXTS } from '../utils/constants';
import BugReportModal from './BugReportModal';

import { toast } from '../utils/toast';
import { logger } from '../utils/logger';
export default function Sidebar() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(window.innerWidth <= 1366);
  const [sessions, setSessions] = useState([]);

  // Bug 回報狀態
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportType, setReportType] = useState('bug');
  const [reportContent, setReportContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 解析 URL 以取得當前的 active 狀態
  const query = new URLSearchParams(location.search);
  const currentChatId = query.get('id');

  const normalizeSession = (session) => ({
    ...session,
    id: String(session?.id ?? ''),
    title: session?.title || SIDEBAR_UI_TEXTS.unnamedChat
  });

  // 取得對話紀錄清單
  const fetchSessions = useCallback(async () => {
    if (!user || user.isGuest) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/sessions`, {
        credentials: 'include'
      });
      if (res.ok) {
        const data = await res.json();
        // 兼容 API 回傳陣列或 { sessions: [...] } 的情況
        const rawSessions = Array.isArray(data) ? data : (data.sessions || []);
        setSessions(rawSessions.map(normalizeSession).filter(session => session.id));
      }
    } catch (e) {
      logger.error('載入對話紀錄失敗:', e);
    }
  }, [user, API_BASE_URL]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSessions();

    const handleChatUpdated = () => fetchSessions();
    window.addEventListener('chat-updated', handleChatUpdated);
    
    const handleResize = () => {
      if (window.innerWidth <= 1366) {
        setIsSidebarCollapsed(true);
      } else {
        setIsSidebarCollapsed(false);
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('chat-updated', handleChatUpdated);
      window.removeEventListener('resize', handleResize);
    };
  }, [fetchSessions]);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm(SIDEBAR_UI_TEXTS.confirmDelete)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/sessions/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (currentChatId === String(id)) {
          navigate('/chat');
        }
        window.dispatchEvent(new Event('chat-updated'));
      }
    } catch (err) {
      logger.error('刪除對話失敗:', err);
    }
  };

  // 提交 Bug 回報或建議
  const handleSubmitReport = async (e) => {
    e.preventDefault();
    if (!reportContent.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/bug_reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          content: reportContent.trim(),
          report_type: reportType
        })
      });
      if (res.ok) {
        toast.info(SIDEBAR_UI_TEXTS.reportSuccess);
        setReportContent('');
        setShowReportModal(false);
      } else {
        toast.info(SIDEBAR_UI_TEXTS.reportFail);
      }
    } catch (err) {
      logger.error('提交反饋錯誤:', err);
      toast.info(SIDEBAR_UI_TEXTS.networkError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {/* 行動版專屬的頂部標題列 */}
      <div className="mobile-topbar">
        <button className="mobile-toggle-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)} aria-label="開啟或關閉側邊欄" aria-expanded={!isSidebarCollapsed}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        </button>
        <span className="mobile-topbar-title">{SIDEBAR_UI_TEXTS.appTitle}</span>
      </div>

      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
      <button className="toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)} aria-label="收合或展開側邊欄" aria-expanded={!isSidebarCollapsed}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="9" y1="3" x2="9" y2="21"></line>
        </svg>
      </button>

      <button className="user-profile-btn" onClick={() => navigate('/profile')}>
        <div className="user-avatar" style={{ backgroundColor: user?.picture ? 'transparent' : 'var(--accent-color)' }}>
          {user?.picture ? <img src={user.picture} alt="avatar" style={{width: '100%', borderRadius: '50%'}} /> : 'U'}
        </div>
        <span className="user-name text-label">{user?.name || SIDEBAR_UI_TEXTS.defaultUserName}</span>
      </button>

      <button className="new-chat-btn" onClick={() => navigate('/chat?id=new')}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        <span className="text-label">{SIDEBAR_UI_TEXTS.newChat}</span>
      </button>

      <div className="history-label text-label">{SIDEBAR_UI_TEXTS.chatHistory}</div>
      <div className="chat-list">
        {sessions.length === 0 ? (
          <div className="empty-sidebar-msg">{SIDEBAR_UI_TEXTS.noHistory}</div>
        ) : (
          sessions.map(chat => (
            <div 
              key={chat.id} 
              className={`chat-item ${chat.id === currentChatId ? 'active' : ''}`} 
              onClick={() => {
                navigate(`/chat?id=${chat.id}`);
                if (window.innerWidth <= 1366) setIsSidebarCollapsed(true);
              }}
            >
              <div className="chat-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
              <span className="chat-title text-label" title={chat.title}>{chat.title}</span>
              <button className="delete-btn" onClick={(e) => handleDelete(e, chat.id)} aria-label="刪除這則對話">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          ))
        )}
      </div>

      {/* 底部：Bug 回報入口 */}
      <div className="sidebar-footer">
        <button className="bug-report-trigger-btn" onClick={() => setShowReportModal(true)} title={SIDEBAR_UI_TEXTS.reportBug}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span className="text-label">{SIDEBAR_UI_TEXTS.reportBug}</span>
        </button>
      </div>
    </aside>

    {/* --- Bug 回報彈窗 (Glassmorphism Modal) --- */}
    <BugReportModal 
      showReportModal={showReportModal}
      setShowReportModal={setShowReportModal}
      reportType={reportType}
      setReportType={setReportType}
      reportContent={reportContent}
      setReportContent={setReportContent}
      handleSubmitReport={handleSubmitReport}
      isSubmitting={isSubmitting}
    />
    </>
  );
}
