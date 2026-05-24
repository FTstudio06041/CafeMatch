import React, { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import '../CommunityPage.css';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';
import NoteStrip from '../components/community/NoteStrip';
import NotePopup from '../components/community/NotePopup';
import NoteComposer from '../components/community/NoteComposer';
import PostComposer from '../components/community/PostComposer';
import PostFeed from '../components/community/PostFeed';

// 引入自定義 Hooks
import useCommunityNotes from '../hooks/useCommunityNotes';
import useCommunityPosts from '../hooks/useCommunityPosts';

export default function CommunityPage() {
  const { user } = useContext(AuthContext);

  // 使用自定義 Hooks 取得便利貼與貼文的狀態和操作
  const {
    notes,
    selectedNote,
    setSelectedNote,
    showNoteComposer,
    setShowNoteComposer,
    editingNote,
    setEditingNote,
    handleCreateNote,
    handleDeleteNote,
    handleLikeUpdate,
  } = useCommunityNotes();

  const {
    posts,
    handleCreatePost,
    handleDeletePost,
  } = useCommunityPosts();

  // =========================================
  // 渲染
  // =========================================
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
      <Sidebar />

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
