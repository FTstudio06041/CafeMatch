import React from 'react';
import PostCard from './PostCard';

/**
 * 貼文動態牆
 * 瀑布流排版渲染 PostCard 列表
 */
export default function PostFeed({ posts, currentUserEmail, onDelete }) {
  if (!posts || posts.length === 0) {
    return (
      <div className="post-feed">
        <div className="feed-empty">
          <div className="feed-empty-icon">☕</div>
          <div className="feed-empty-text">還沒有人分享貼文，成為第一個吧！</div>
        </div>
      </div>
    );
  }

  return (
    <div className="post-feed">
      <div className="post-feed-grid">
        {posts.map((post) => (
          <PostCard
            key={post.id}
            post={post}
            currentUserEmail={currentUserEmail}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}
