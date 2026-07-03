import { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from '../../context/AuthContext';

import { toast } from '../../utils/toast';
import { logger } from '../../utils/logger';
/**
 * 便利貼展開小視窗
 * 顯示完整內容 + 愛心按鈕 + 留言功能
 */
export default function NotePopup({ note, onClose, onDelete, onLikeUpdate }) {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const [isLiked, setIsLiked] = useState(note.is_liked || false);
  const [likeCount, setLikeCount] = useState(note.like_count || 0);
  const [comments, setComments] = useState([]);
  const [commentText, setCommentText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchComments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/notes/${note.id}/comments`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setComments(data.comments || []);
      }
    } catch (err) {
      logger.error('載入留言失敗:', err);
    }
  }, [API_BASE_URL, note.id]);

  // 載入留言
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchComments();
  }, [fetchComments]);

  // 按愛心 / 取消愛心
  const handleLike = async () => {
    if (!user || user.isGuest) {
      toast.info("請先登入才能按讚喔！");
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/notes/${note.id}/like`, {
        method: 'POST',
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setIsLiked(data.is_liked);
        setLikeCount(data.like_count);
        onLikeUpdate?.(note.id, data.is_liked, data.like_count);
      }
    } catch (err) {
      logger.error('愛心操作失敗:', err);
    }
  };

  // 發送留言
  const handleSubmitComment = async () => {
    if (!commentText.trim() || isSubmitting || !user) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/notes/${note.id}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: commentText.trim() }),
      });
      if (res.ok) {
        setCommentText('');
        fetchComments(); // 重新載入留言
      }
    } catch (err) {
      logger.error('留言失敗:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // 判斷是否為本人
  const isOwner = user && user.email && note.user_email === user.email;

  // 按 Enter 發送留言
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmitComment();
    }
  };

  // 格式化時間
  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    let utcStr = timeStr.replace(' ', 'T');
    if (utcStr.length === 16) utcStr += ':00';
    if (!utcStr.endsWith('Z')) utcStr += 'Z';
    const d = new Date(utcStr);
    const now = new Date();
    const diff = Math.floor((now - d) / 1000);
    if (diff < 60) return '剛剛';
    if (diff < 3600) return `${Math.floor(diff / 60)} 分鐘前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小時前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
    return d.toLocaleDateString('zh-TW');
  };

  return (
    <div className="note-popup-overlay" onClick={onClose}>
      <div className="note-popup-card" onClick={(e) => e.stopPropagation()}>
        {/* 頂部：使用者資訊 */}
        <div className="note-popup-header">
          <div className="note-popup-user">
            <div className="note-popup-user-avatar">
              {note.user_picture ? (
                <img src={note.user_picture} alt={note.user_name} />
              ) : (
                <div className="note-popup-user-avatar-placeholder">
                  {(note.user_name || 'U').charAt(0)}
                </div>
              )}
            </div>
            <div className="note-popup-user-info">
              <span className="note-popup-user-name">{note.user_name || '匿名'}</span>
              <span className="note-popup-time">{formatTime(note.created_at)}</span>
            </div>
          </div>
          <button className="note-popup-close" onClick={onClose} aria-label="關閉">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {/* 便利貼內容 */}
        <div className={`note-popup-body color-${note.color_index ?? 0}`}>
          {note.content}
        </div>

        {/* 愛心 + 刪除 */}
        <div className="note-popup-actions">
          <button
            className={`note-popup-like-btn ${isLiked ? 'liked' : ''}`}
            onClick={handleLike}
            aria-pressed={isLiked}
            aria-label={`${isLiked ? '取消讚' : '按讚'}，目前 ${likeCount} 個讚`}
          >
            <svg className="like-icon" width="18" height="18" viewBox="0 0 24 24"
              fill={isLiked ? '#e74c6f' : 'none'}
              stroke={isLiked ? '#e74c6f' : 'currentColor'}
              strokeWidth="2">
              <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
            </svg>
            <span className="note-popup-like-count">{likeCount}</span>
          </button>

          {isOwner && (
            <button
              className="note-popup-delete-btn"
              onClick={() => onDelete(note.id)}
              title="刪除便利貼"
              aria-label="刪除便利貼"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          )}
        </div>

        {/* 留言列表 */}
        <div className="note-popup-comments">
          {comments.length === 0 ? (
            <div className="comment-empty">還沒有留言，來說點什麼吧 ☕</div>
          ) : (
            comments.map((c) => (
              <div key={c.id} className="comment-item">
                <div className="comment-avatar">
                  {c.user_picture ? (
                    <img src={c.user_picture} alt={c.user_name} />
                  ) : (
                    <div className="comment-avatar-placeholder">
                      {(c.user_name || 'U').charAt(0)}
                    </div>
                  )}
                </div>
                <div className="comment-body">
                  <div>
                    <span className="comment-user-name">{c.user_name}</span>
                    <span className="comment-text">{c.content}</span>
                  </div>
                  <div className="comment-time">{formatTime(c.created_at)}</div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* 留言輸入框 */}
        {user && !user.isGuest && (
          <div className="note-popup-comment-input">
            <input
              type="text"
              placeholder="留言..."
              value={commentText}
              onChange={(e) => setCommentText(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={200}
            />
            <button
              className="note-popup-comment-send"
              onClick={handleSubmitComment}
              disabled={!commentText.trim() || isSubmitting}
              aria-label="送出留言"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
