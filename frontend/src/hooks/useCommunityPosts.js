import { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from '../context/AuthContext';

import { logger } from '../utils/logger';
/**
 * 處理社群貼文（Posts）狀態與 API 交互的自定義 Hook
 */
export default function useCommunityPosts() {
  const { API_BASE_URL } = useContext(AuthContext);

  const [posts, setPosts] = useState([]);

  const fetchPosts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        // 後端 API 可能直接回傳陣列或包含 posts 欄位的物件
        setPosts(data.posts || data || []);
      }
    } catch (err) {
      logger.error('載入貼文失敗:', err);
    }
  }, [API_BASE_URL]);

  // 初始化時自動載入貼文
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchPosts();
  }, [fetchPosts]);

  const handleCreatePost = async ({ content, image, cafe_id }) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content, image, cafe_id }),
      });
      if (res.ok) {
        await fetchPosts();
      }
    } catch (err) {
      logger.error('發布貼文失敗:', err);
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
        await fetchPosts();
      }
    } catch (err) {
      logger.error('刪除貼文失敗:', err);
    }
  };

  const handleLikePost = async (postId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts/${postId}/like`, {
        method: 'POST',
        credentials: 'include',
      });
      if (res.ok) {
        // 可以考慮直接更新 state，但簡單做法是重新 fetch
        await fetchPosts();
      }
    } catch (err) {
      logger.error('按讚失敗:', err);
    }
  };

  const handleCommentPost = async (postId, content) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts/${postId}/comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        await fetchPosts();
        return true;
      }
    } catch (err) {
      logger.error('留言失敗:', err);
    }
    return false;
  };

  const handleRepostPost = async (postId, content) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts/${postId}/repost`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        await fetchPosts();
        return true;
      }
    } catch (err) {
      logger.error('轉發失敗:', err);
    }
    return false;
  };

  const fetchPostComments = async (postId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts/${postId}/comments`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        return data.comments || [];
      }
    } catch (err) {
      logger.error('取得留言失敗:', err);
    }
    return [];
  };

  const fetchSinglePost = async (postId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/community/posts/${postId}`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        return data.post;
      }
    } catch (err) {
      logger.error('取得單一貼文失敗:', err);
    }
    return null;
  };

  return {
    posts,
    fetchPosts,
    handleCreatePost,
    handleDeletePost,
    handleLikePost,
    handleCommentPost,
    handleRepostPost,
    fetchPostComments,
    fetchSinglePost
  };
}
