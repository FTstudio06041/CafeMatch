import React, { useEffect, useState, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import PostCard from '../components/community/PostCard';
import useCommunityPosts from '../hooks/useCommunityPosts';
import { decodeId } from '../utils/hashId';

export default function PostViewPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useContext(AuthContext);
  const { fetchSinglePost, handleLikePost, handleCommentPost, handleRepostPost, handleDeletePost, fetchPostComments } = useCommunityPosts();
  
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);

  // 因為 fetchSinglePost 是依賴 API_BASE_URL 的 callback，這裡不用 useCallback 可能會無限迴圈
  // 比較安全的做法是不將 fetchSinglePost 放入 dependency array，或是我們依賴 id 即可
  useEffect(() => {
    const loadPost = async () => {
      setLoading(true);
      const realId = decodeId(id);
      if (realId) {
        const data = await fetchSinglePost(realId);
        setPost(data);
      } else {
        setPost(null);
      }
      setLoading(false);
    };
    loadPost();
    // eslint-disable-next-line
  }, [id]);

  const refreshPost = async () => {
    const realId = decodeId(id);
    if (realId) {
      const data = await fetchSinglePost(realId);
      setPost(data);
    }
  };

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', marginTop: '50px', color: '#8b5a2b' }}>載入貼文中...</div>;
  }

  if (!post) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: '50px', color: '#8b5a2b' }}>
        <h2>找不到此貼文或已被刪除</h2>
        <button 
          onClick={() => navigate('/')} 
          style={{ 
            marginTop: '20px', 
            padding: '10px 24px',
            backgroundColor: '#8b5a2b',
            color: 'white',
            border: 'none',
            borderRadius: '20px',
            cursor: 'pointer'
          }}
        >
          回首頁
        </button>
      </div>
    );
  }

  return (
    <div style={{ 
      maxWidth: '600px', 
      margin: '0 auto', 
      padding: '20px',
      minHeight: '100vh',
      backgroundColor: 'transparent' // 與全局咖啡色背景融合
    }}>
      <div 
        style={{ 
          display: 'flex', 
          alignItems: 'center', 
          marginBottom: '20px', 
          cursor: 'pointer',
          color: '#8b5a2b'
        }} 
        onClick={() => navigate('/community')}
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: '8px' }}>
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        <span style={{ fontWeight: 'bold', fontSize: '1.1rem' }}>返回社群</span>
      </div>
      
      <PostCard 
        post={post}
        currentUserEmail={user?.email}
        defaultShowComments={true}
        fetchComments={fetchPostComments}
        onDelete={async (postId) => {
          await handleDeletePost(postId);
          navigate('/community');
        }}
        onLike={async () => {
          await handleLikePost(post.id);
          await refreshPost();
        }}
        onComment={async (content) => {
          await handleCommentPost(post.id, content);
          await refreshPost();
        }}
        onRepost={async (content) => {
          await handleRepostPost(post.id, content);
          // 轉發後可能導回首頁或維持原樣
          alert('已成功轉發貼文！');
        }}
      />
    </div>
  );
}
