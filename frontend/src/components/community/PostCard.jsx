import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { encodeId } from '../../utils/hashId';
import { formatTime } from '../../utils/formatters';

// 子元件
import OriginalPostQuote from './OriginalPostQuote';
import CommentSection from './CommentSection';
import ShareModal from './ShareModal';
import RepostModal from './RepostModal';

/**
 * 單則貼文卡片
 * 重構後：僅保留核心狀態管理與卡片主體結構，子功能抽離至各獨立元件。
 */
export default function PostCard({ 
  post, 
  currentUserEmail, 
  onDelete,
  onLike,
  onComment,
  onRepost,
  fetchComments, // (postId) => Promise<Array>
  defaultShowComments = false
}) {
  const navigate = useNavigate();
  const isOwner = currentUserEmail && post.user_email === currentUserEmail;

  // --- 狀態管理 ---
  const [showComments, setShowComments] = useState(defaultShowComments);
  const [commentsList, setCommentsList] = useState([]);
  const [commentText, setCommentText] = useState('');
  const [loadingComments, setLoadingComments] = useState(false);

  const [showRepostModal, setShowRepostModal] = useState(false);
  const [repostText, setRepostText] = useState('');

  const [showShareModal, setShowShareModal] = useState(false);
  const [copied, setCopied] = useState(false);

  // --- 初始載入 ---
  useEffect(() => {
    if (defaultShowComments && fetchComments) {
      const loadInitialComments = async () => {
        setLoadingComments(true);
        const data = await fetchComments(post.id);
        setCommentsList(data);
        setLoadingComments(false);
      };
      loadInitialComments();
    }
  }, [defaultShowComments, fetchComments, post.id]);

  // --- 互動邏輯 ---
  const handleCafeClick = () => {
    if (post.cafe_id) {
      navigate(`/explore?open_shop_id=${post.cafe_id}`);
    }
  };

  const handleToggleComments = async () => {
    if (!showComments) {
      if (fetchComments) {
        setLoadingComments(true);
        const data = await fetchComments(post.id);
        setCommentsList(data);
        setLoadingComments(false);
      }
    }
    setShowComments(!showComments);
  };

  const submitComment = async () => {
    if (!commentText.trim()) return;
    if (onComment) {
      await onComment(commentText);
      setCommentText('');
      if (fetchComments) {
        const data = await fetchComments(post.id);
        setCommentsList(data);
      }
    }
  };

  const submitRepost = async () => {
    if (onRepost) {
      await onRepost(repostText);
      setShowRepostModal(false);
      setRepostText('');
    }
  };

  const getPostUrl = () => `${window.location.origin}/post/${encodeId(post.id)}`;

  const handleShareClick = () => {
    setShowShareModal(true);
    setCopied(false);
  };

  const handleCopyLink = () => {
    navigator.clipboard.writeText(getPostUrl()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  // --- UI 渲染 ---
  return (
    <div className="post-card" style={{ position: 'relative' }}>
      {/* 轉發標示 */}
      {post.original_post && (
        <div style={{ fontSize: '0.85rem', color: '#8b5a2b', marginBottom: '8px', display: 'flex', alignItems: 'center', fontWeight: 'bold' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '6px' }}>
            <polyline points="17 1 21 5 17 9"></polyline>
            <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
            <polyline points="7 23 3 19 7 15"></polyline>
            <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
          </svg>
          {post.user_name} 轉發了貼文
        </div>
      )}

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
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        )}
      </div>

      {/* 貼文文字 */}
      <div className="post-card-content">
        {post.content}
      </div>

      {/* 嵌套原貼文預覽 */}
      {post.original_post && <OriginalPostQuote orig={post.original_post} />}

      {/* 貼文圖片 */}
      {!post.original_post && post.image && (
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

      {/* 互動列 (Action Bar) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '16px', paddingTop: '12px', borderTop: '1px solid rgba(139, 90, 43, 0.1)', color: '#8b5a2b' }}>
        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '6px' }} onClick={() => onLike && onLike()}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill={post.is_liked ? '#e74c3c' : 'none'} stroke={post.is_liked ? '#e74c3c' : 'currentColor'} strokeWidth="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
          <span style={{ fontSize: '0.9rem' }}>{post.like_count || 0}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '6px' }} onClick={handleToggleComments}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path>
          </svg>
          <span style={{ fontSize: '0.9rem' }}>{post.comment_count || 0}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '6px' }} onClick={() => setShowRepostModal(true)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="17 1 21 5 17 9"></polyline>
            <path d="M3 11V9a4 4 0 0 1 4-4h14"></path>
            <polyline points="7 23 3 19 7 15"></polyline>
            <path d="M21 13v2a4 4 0 0 1-4 4H3"></path>
          </svg>
          <span style={{ fontSize: '0.9rem' }}>{post.repost_count || 0}</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', cursor: 'pointer', gap: '6px' }} onClick={handleShareClick} title="分享貼文連結">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
            <polyline points="16 6 12 2 8 6"></polyline>
            <line x1="12" y1="2" x2="12" y2="15"></line>
          </svg>
          <span style={{ fontSize: '0.9rem' }}>分享</span>
        </div>
      </div>

      {/* 拆分後的子元件區塊 */}
      <CommentSection 
        showComments={showComments} 
        loadingComments={loadingComments} 
        commentsList={commentsList} 
        commentText={commentText} 
        setCommentText={setCommentText} 
        submitComment={submitComment} 
      />

      <RepostModal 
        showRepostModal={showRepostModal} 
        setShowRepostModal={setShowRepostModal} 
        repostText={repostText} 
        setRepostText={setRepostText} 
        submitRepost={submitRepost} 
      />

      <ShareModal 
        showShareModal={showShareModal} 
        setShowShareModal={setShowShareModal} 
        postUrl={getPostUrl()} 
        copied={copied} 
        handleCopyLink={handleCopyLink} 
      />

    </div>
  );
}
