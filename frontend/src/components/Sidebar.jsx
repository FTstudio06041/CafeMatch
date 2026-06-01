import React, { useState, useEffect, useContext } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../ChatPage.css'; // 保留側欄的相關 CSS 樣式

export default function Sidebar() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(window.innerWidth <= 768);
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
    title: session?.title || '未命名對話'
  });

  // 取得對話紀錄清單
  const fetchSessions = async () => {
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
      console.error('載入對話紀錄失敗:', e);
    }
  };

  useEffect(() => {
    fetchSessions();

    const handleChatUpdated = () => fetchSessions();
    window.addEventListener('chat-updated', handleChatUpdated);
    
    const handleResize = () => {
      if (window.innerWidth <= 768) {
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
  }, [user, API_BASE_URL]);

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
        if (currentChatId === String(id)) {
          navigate('/chat');
        }
        window.dispatchEvent(new Event('chat-updated'));
      }
    } catch (err) {
      console.error('刪除對話失敗:', err);
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
        alert('回報提交成功！感謝您的支持與反饋 ❤️');
        setReportContent('');
        setShowReportModal(false);
      } else {
        alert('提交失敗，請稍後再試！');
      }
    } catch (err) {
      console.error('提交反饋錯誤:', err);
      alert('網路連線錯誤，請稍後再試！');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {/* 行動版專屬的頂部標題列 */}
      <div className="mobile-topbar">
        <button className="mobile-toggle-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        </button>
        <span className="mobile-topbar-title">CafeMatch</span>
      </div>

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
              onClick={() => {
                navigate(`/chat?id=${chat.id}`);
                if (window.innerWidth <= 768) setIsSidebarCollapsed(true);
              }}
            >
              <div className="chat-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
              <span className="chat-title text-label" title={chat.title}>{chat.title}</span>
              <button className="delete-btn" onClick={(e) => handleDelete(e, chat.id)}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              </button>
            </div>
          ))
        )}
      </div>

      {/* 底部：Bug 回報入口 */}
      <div className="sidebar-footer">
        <style>{`
          .sidebar-footer {
            margin-top: auto;
            padding: 12px 0 0;
            border-top: 1px solid rgba(139, 90, 43, 0.08);
          }
          .bug-report-trigger-btn {
            width: 100%;
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: transparent;
            border: none;
            border-radius: 12px;
            color: var(--text-light);
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: left;
            box-sizing: border-box;
          }
          .bug-report-trigger-btn:hover {
            background: rgba(139, 90, 43, 0.06);
            color: var(--accent-color);
          }
          .sidebar.collapsed .bug-report-trigger-btn {
            justify-content: center;
            padding: 12px 0;
          }
        `}</style>
        <button className="bug-report-trigger-btn" onClick={() => setShowReportModal(true)} title="回報 Bug / 建議">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <span className="text-label">回報 Bug / 建議</span>
        </button>
      </div>
    </aside>

    {/* --- Bug 回報彈窗 (Glassmorphism Modal) --- */}
    {showReportModal && (
      <div className="bug-report-overlay" onClick={() => setShowReportModal(false)}>
        <style>{`
          .bug-report-overlay {
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
            z-index: 9999999;
            animation: bugFadeIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) forwards;
          }
          .bug-report-modal {
            background: rgba(255, 253, 250, 0.88);
            backdrop-filter: blur(24px);
            border: 1px solid rgba(139, 90, 43, 0.15);
            border-radius: 24px;
            width: 90%;
            max-width: 440px;
            padding: 28px;
            box-shadow: 0 20px 50px rgba(43, 27, 8, 0.18);
            display: flex;
            flex-direction: column;
            gap: 18px;
            animation: bugModalUp 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
          }
          .bug-report-header {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #8b5a2b;
          }
          .bug-report-header h3 {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 700;
            letter-spacing: 0.5px;
          }
          .bug-report-form {
            display: flex;
            flex-direction: column;
            gap: 16px;
          }
          .bug-report-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
          }
          .bug-report-label {
            font-size: 0.85rem;
            font-weight: 600;
            color: rgba(139, 90, 43, 0.8);
          }
          .bug-report-select {
            padding: 10px 14px;
            border: 1.5px solid rgba(139, 90, 43, 0.15);
            border-radius: 12px;
            font-size: 0.92rem;
            color: #5c4033;
            background: #fffdfa;
            outline: none;
            cursor: pointer;
            transition: all 0.2s;
          }
          .bug-report-select:focus {
            border-color: #8b5a2b;
          }
          .bug-report-textarea {
            padding: 12px 14px;
            border: 1.5px solid rgba(139, 90, 43, 0.15);
            border-radius: 12px;
            font-size: 0.92rem;
            line-height: 1.5;
            color: #5c4033;
            background: #fffdfa;
            outline: none;
            resize: vertical;
            font-family: inherit;
            transition: all 0.25s ease;
          }
          .bug-report-textarea:focus {
            border-color: #8b5a2b;
            box-shadow: 0 0 8px rgba(139, 90, 43, 0.05);
          }
          .bug-report-actions {
            display: flex;
            justify-content: flex-end;
            gap: 12px;
            margin-top: 6px;
          }
          .bug-report-btn {
            padding: 10px 20px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
            border: none;
          }
          .bug-report-btn.cancel {
            background: rgba(139, 90, 43, 0.08);
            color: #5c4033;
          }
          .bug-report-btn.cancel:hover {
            background: rgba(139, 90, 43, 0.14);
          }
          .bug-report-btn.submit {
            background: #8b5a2b;
            color: #fffdfa;
            box-shadow: 0 4px 12px rgba(139, 90, 43, 0.25);
          }
          .bug-report-btn.submit:hover:not(:disabled) {
            background: #6f421e;
            transform: translateY(-1.5px);
            box-shadow: 0 6px 16px rgba(139, 90, 43, 0.35);
          }
          .bug-report-btn.submit:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          @keyframes bugFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @keyframes bugModalUp {
            from { transform: scale(0.92) translateY(30px); opacity: 0; }
            to { transform: scale(1) translateY(0); opacity: 1; }
          }
        `}</style>
        <div className="bug-report-modal" onClick={(e) => e.stopPropagation()}>
          <div className="bug-report-header">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <h3>回報問題與建議</h3>
          </div>
          <form className="bug-report-form" onSubmit={handleSubmitReport}>
            <div className="bug-report-group">
              <label className="bug-report-label">回報類型</label>
              <select 
                className="bug-report-select" 
                value={reportType} 
                onChange={(e) => setReportType(e.target.value)}
              >
                <option value="bug">🐞 程式出錯 (Bug)</option>
                <option value="suggest">💡 功能建議 / 意見反饋</option>
              </select>
            </div>
            <div className="bug-report-group">
              <label className="bug-report-label">具體描述</label>
              <textarea 
                className="bug-report-textarea" 
                placeholder="請具體描述您遇到的問題、操作步驟，或想給我們的建議..." 
                value={reportContent} 
                onChange={(e) => setReportContent(e.target.value)}
                maxLength={1000}
                rows={5}
                required
              />
            </div>
            <div className="bug-report-actions">
              <button type="button" className="bug-report-btn cancel" onClick={() => setShowReportModal(false)}>
                取消
              </button>
              <button type="submit" className="bug-report-btn submit" disabled={!reportContent.trim() || isSubmitting}>
                {isSubmitting ? '提交中...' : '提交回報'}
              </button>
            </div>
          </form>
        </div>
      </div>
    )}
    </>
  );
}
