import { formatTime } from '../../utils/formatters';

export default function CommentSection({
  showComments,
  loadingComments,
  commentsList,
  commentText,
  setCommentText,
  submitComment
}) {
  if (!showComments) return null;

  return (
    <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px dashed rgba(139, 90, 43, 0.2)' }}>
      {loadingComments ? (
        <div style={{ textAlign: 'center', color: '#8b5a2b', fontSize: '0.9rem' }}>載入留言中...</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '16px' }}>
          {commentsList.map(c => (
            <div key={c.id} style={{ display: 'flex', gap: '8px' }}>
              <div style={{ width: '28px', height: '28px', borderRadius: '50%', overflow: 'hidden', backgroundColor: '#e2d5c8', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: '0.8rem' }}>
                {c.user_picture ? <img src={c.user_picture} alt="avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }}/> : c.user_name.charAt(0)}
              </div>
              <div style={{ backgroundColor: 'rgba(255,255,255,0.6)', padding: '8px 12px', borderRadius: '12px', flexGrow: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 'bold', fontSize: '0.85rem', color: '#4a3b32' }}>{c.user_name}</span>
                  <span style={{ fontSize: '0.75rem', color: 'rgba(139, 90, 43, 0.6)' }}>{formatTime(c.created_at)}</span>
                </div>
                <div style={{ fontSize: '0.9rem', color: '#4a3b32' }}>{c.content}</div>
              </div>
            </div>
          ))}
          {commentsList.length === 0 && <div style={{ textAlign: 'center', color: '#a0a0a0', fontSize: '0.9rem' }}>目前還沒有留言，來當第一個留言的人吧！</div>}
        </div>
      )}
      {/* 輸入框 */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <input 
          type="text" 
          placeholder="新增留言..." 
          value={commentText}
          onChange={e => setCommentText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submitComment()}
          style={{ flexGrow: 1, padding: '8px 12px', borderRadius: '20px', border: '1px solid rgba(139, 90, 43, 0.2)', outline: 'none' }}
        />
        <button 
          onClick={submitComment}
          style={{ backgroundColor: '#8b5a2b', color: 'white', border: 'none', borderRadius: '20px', padding: '0 16px', cursor: 'pointer' }}
        >
          送出
        </button>
      </div>
    </div>
  );
}
