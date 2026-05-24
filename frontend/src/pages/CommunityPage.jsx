import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../CommunityPage.css';
import Navbar from '../components/Navbar';
import NoteStrip from '../components/community/NoteStrip';
import NotePopup from '../components/community/NotePopup';
import NoteComposer from '../components/community/NoteComposer';
import PostComposer from '../components/community/PostComposer';
import PostFeed from '../components/community/PostFeed';

export default function CommunityPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();

  // 側欄狀態
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [chats, setChats] = useState([]);

  // 便利貼狀態
  const [notes, setNotes] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);  // 展開的便利貼
  const [showNoteComposer, setShowNoteComposer] = useState(false);
  const [editingNote, setEditingNote] = useState(null);    // 編輯中的自己的便利貼

  // 貼文狀態
  const [posts, setPosts] = useState([]);

  // =========================================
  // 初始化
  // =========================================
  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    setChats(savedChats);
    fetchNotes();
    fetchPosts();
  }, []);

  // =========================================
  // 便利貼 API
  // =========================================
  const fetchNotes = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/notes`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setNotes(data.notes || []);
      }
    } catch (err) {
      console.error('載入便利貼失敗:', err);
    }
  };

  const handleCreateNote = async ({ content, color_index }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content, color_index }),
      });
      if (res.ok) {
        fetchNotes(); // 重新載入
      }
    } catch (err) {
      console.error('發布便利貼失敗:', err);
    }
  };

  const handleDeleteNote = async (noteId) => {
    if (!window.confirm('確定要刪除這張便利貼嗎？')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/notes/${noteId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) {
        setSelectedNote(null);
        fetchNotes();
      }
    } catch (err) {
      console.error('刪除便利貼失敗:', err);
    }
  };

  const handleLikeUpdate = (noteId, isLiked, likeCount) => {
    setNotes(prev => prev.map(n =>
      n.id === noteId ? { ...n, is_liked: isLiked, like_count: likeCount } : n
    ));
  };

  // =========================================
  // 貼文 API
  // =========================================
  const fetchPosts = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setPosts(data.posts || data);
      }
    } catch (err) {
      console.error('載入貼文失敗:', err);
    }
  };

  const handleCreatePost = async ({ content, image, cafe_id }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content, image, cafe_id }),
      });
      if (res.ok) {
        fetchPosts();
      }
    } catch (err) {
      console.error('發布貼文失敗:', err);
    }
  };

  const handleDeletePost = async (postId) => {
    if (!window.confirm('確定要刪除這則貼文嗎？')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts/${postId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) {
        fetchPosts();
      }
    } catch (err) {
      console.error('刪除貼文失敗:', err);
    }
  };

  // =========================================
  // 渲染
  // =========================================
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
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

        <button className="new-chat-btn" onClick={() => { localStorage.setItem('targetChatId', 'new'); navigate('/chat'); }}>
           <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
           <span className="text-label">新增對話</span>
        </button>

        <div className="history-label text-label">對話紀錄</div>
        <div className="chat-list">
          {chats.length === 0 ? (
            <div className="empty-sidebar-msg">尚無對話紀錄</div>
          ) : (
            chats.map(chat => (
              <div key={chat.id} className="chat-item" onClick={() => { localStorage.setItem('targetChatId', chat.id); navigate('/chat'); }}>
                <div className="chat-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                </div>
                <span className="chat-title text-label">{chat.title}</span>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* --- 主內容區 --- */}
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>

        <div className="community-content">
          {/* 便利貼橫向列 */}
          <NoteStrip
            notes={notes}
            currentUser={user}
            onNoteClick={(note) => setSelectedNote(note)}
            onEditClick={(note) => {
              setEditingNote(note);
              setShowNoteComposer(true);
            }}
          />

          {/* 發文區 */}
          <PostComposer onSubmit={handleCreatePost} />

          {/* 貼文動態牆 */}
          <PostFeed
            posts={posts}
            currentUserEmail={user?.email}
            onDelete={handleDeletePost}
          />
        </div>
      </main>

      {/* --- 彈窗層 --- */}
      {/* 便利貼小視窗 */}
      {selectedNote && (
        <NotePopup
          note={selectedNote}
          onClose={() => setSelectedNote(null)}
          onDelete={handleDeleteNote}
          onLikeUpdate={handleLikeUpdate}
        />
      )}

      {/* 便利貼 Composer */}
      {showNoteComposer && (
        <NoteComposer
          initialNote={editingNote}
          onSubmit={handleCreateNote}
          onDelete={handleDeleteNote}
          onClose={() => {
            setShowNoteComposer(false);
            setEditingNote(null);
          }}
        />
      )}
    </div>
  );
}
