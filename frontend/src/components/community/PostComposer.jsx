import React, { useState, useEffect, useContext, useRef } from 'react';
import { AuthContext } from '../../context/AuthContext';

/**
 * 正常貼文編輯器
 * 文字 + 圖片上傳 + 店家選擇
 */
export default function PostComposer({ onSubmit }) {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const [content, setContent] = useState('');
  const [image, setImage] = useState(null); // Base64
  const [cafeId, setCafeId] = useState('');
  const [cafes, setCafes] = useState([]);
  const [showCafeSelector, setShowCafeSelector] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef(null);

  // 載入咖啡廳列表
  useEffect(() => {
    fetchCafes();
  }, []);

  const fetchCafes = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/cafes`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setCafes(data);
      }
    } catch (err) {
      console.error('載入咖啡廳列表失敗:', err);
    }
  };

  // 圖片上傳處理
  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // 限制檔案大小（5MB）
    if (file.size > 5 * 1024 * 1024) {
      alert('圖片大小不可超過 5MB');
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      setImage(event.target.result);
    };
    reader.readAsDataURL(file);
  };

  // 發布貼文
  const handleSubmit = async () => {
    if (user?.isGuest) {
      alert("請先登入才能發布貼文喔！");
      return;
    }
    if (!content.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onSubmit({
        content: content.trim(),
        image: image || null,
        cafe_id: cafeId ? parseInt(cafeId) : null,
      });
      // 清空表單
      setContent('');
      setImage(null);
      setCafeId('');
      setShowCafeSelector(false);
    } catch (err) {
      console.error('發布貼文失敗:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  const canSubmit = content.trim().length > 0 && !isSubmitting;

  return (
    <div className="community-compose-section">
      <div className="post-composer-card">
        {/* 頂部：頭像 + 輸入框 */}
        <div className="post-composer-header">
          <div className="post-composer-avatar">
            {user?.picture ? (
              <img src={user.picture} alt={user.name} />
            ) : (
              <div className="post-composer-avatar-placeholder">
                {(user?.name || 'U').charAt(0)}
              </div>
            )}
          </div>
          <span style={{ color: 'var(--text-light)', fontSize: '0.9rem', fontWeight: 600 }}>
            {user?.name || '使用者'}
          </span>
        </div>

        <textarea
          className="post-composer-textarea"
          placeholder="分享你今天的咖啡體驗..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />

        {/* 圖片預覽 */}
        {image && (
          <div className="post-composer-image-preview">
            <img src={image} alt="預覽" />
            <button
              className="post-composer-image-remove"
              onClick={() => setImage(null)}
            >
              ✕
            </button>
          </div>
        )}

        {/* 店家選擇器 */}
        {showCafeSelector && (
          <div className="cafe-selector">
            <select
              value={cafeId}
              onChange={(e) => setCafeId(e.target.value)}
            >
              <option value="">不關聯店家</option>
              {cafes.map((cafe) => (
                <option key={cafe.id} value={cafe.id}>
                  {cafe.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* 底部工具列 */}
        <div className="post-composer-toolbar">
          <div className="post-composer-tools">
            {/* 圖片上傳按鈕 */}
            <button
              className={`post-tool-btn ${image ? 'active' : ''}`}
              onClick={() => fileInputRef.current?.click()}
              title="上傳圖片"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
              </svg>
              <span>圖片</span>
            </button>
            <input
              type="file"
              ref={fileInputRef}
              accept="image/*"
              style={{ display: 'none' }}
              onChange={handleImageUpload}
            />

            {/* 店家關聯按鈕 */}
            <button
              className={`post-tool-btn ${showCafeSelector ? 'active' : ''}`}
              onClick={() => setShowCafeSelector(!showCafeSelector)}
              title="關聯店家"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                <circle cx="12" cy="10" r="3"></circle>
              </svg>
              <span>店家</span>
            </button>

            {/* 發布按鈕 */}
            <button
              className="post-composer-submit"
              onClick={handleSubmit}
              disabled={!canSubmit}
            >
              {isSubmitting ? '發布中...' : '發布'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
