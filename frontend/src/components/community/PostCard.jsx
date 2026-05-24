import React from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * 單則貼文卡片
 * 顯示使用者頭像、內容、圖片、關聯店家
 */
export default function PostCard({ post, currentUserEmail, onDelete }) {
  const navigate = useNavigate();
  const isOwner = currentUserEmail && post.user_email === currentUserEmail;

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

  // 點擊關聯店家，導航至探索頁
  const handleCafeClick = () => {
    if (post.cafe_id) {
      navigate(`/explore?open_shop_id=${post.cafe_id}`);
    }
  };

  return (
    <div className="post-card">
      {/* 頂部：使用者資訊 */}
      <div className="post-card-header">
        <div className="post-card-user">
          <div className="post-card-avatar">
            {post.user_picture ? (
              <img src={post.user_picture} alt={post.user_name} />
            ) : (
              <div className="post-card-avatar-placeholder">
                {(post.user_name || 'U').charAt(0)}
              </div>
            )}
          </div>
          <div>
            <div className="post-card-user-name">{post.user_name || '匿名'}</div>
            <div className="post-card-time">{formatTime(post.created_at)}</div>
          </div>
        </div>

        {/* 本人可刪除 */}
        {isOwner && (
          <button
            className="post-card-delete"
            onClick={() => onDelete(post.id)}
            title="刪除貼文"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        )}
      </div>

      {/* 貼文文字 */}
      <div className="post-card-content">
        {post.content}
      </div>

      {/* 貼文圖片 */}
      {post.image && (
        <div className="post-card-image">
          <img src={post.image} alt="貼文圖片" />
        </div>
      )}

      {/* 關聯店家 */}
      {post.cafe_name && (
        <div className="post-card-cafe" onClick={handleCafeClick}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
            <circle cx="12" cy="10" r="3"></circle>
          </svg>
          {post.cafe_name}
        </div>
      )}
    </div>
  );
}
