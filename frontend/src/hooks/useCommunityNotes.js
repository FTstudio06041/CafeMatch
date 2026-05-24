import { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';

/**
 * 處理社群便利貼（Notes）狀態與 API 交互的自定義 Hook
 */
export default function useCommunityNotes() {
  const { user, API_BASE_URL } = useContext(AuthContext);

  const [notes, setNotes] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);  // 展開的便利貼
  const [showNoteComposer, setShowNoteComposer] = useState(false);
  const [editingNote, setEditingNote] = useState(null);    // 編輯中的自己的便利貼

  // 初始化時自動載入便利貼
  useEffect(() => {
    fetchNotes();
  }, [API_BASE_URL]);

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
        await fetchNotes(); // 重新載入
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
        await fetchNotes();
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

  return {
    notes,
    selectedNote,
    setSelectedNote,
    showNoteComposer,
    setShowNoteComposer,
    editingNote,
    setEditingNote,
    fetchNotes,
    handleCreateNote,
    handleDeleteNote,
    handleLikeUpdate,
  };
}
