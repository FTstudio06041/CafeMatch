
export default function RepostModal({
  showRepostModal,
  setShowRepostModal,
  repostText,
  setRepostText,
  submitRepost
}) {
  if (!showRepostModal) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
      backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, 
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div style={{ backgroundColor: '#fdfbf7', padding: '24px', borderRadius: '16px', width: '90%', maxWidth: '500px' }}>
        <h3 style={{ marginTop: 0, color: '#4a3b32' }}>轉發貼文</h3>
        <textarea 
          placeholder="新增轉發心得 (選填)..."
          value={repostText}
          onChange={e => setRepostText(e.target.value)}
          style={{ width: '100%', height: '100px', padding: '12px', borderRadius: '8px', border: '1px solid rgba(139, 90, 43, 0.2)', marginBottom: '16px', resize: 'none', outline: 'none' }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button onClick={() => setShowRepostModal(false)} style={{ padding: '8px 16px', border: '1px solid #8b5a2b', borderRadius: '20px', backgroundColor: 'transparent', color: '#8b5a2b', cursor: 'pointer' }}>取消</button>
          <button onClick={submitRepost} style={{ padding: '8px 16px', border: 'none', borderRadius: '20px', backgroundColor: '#8b5a2b', color: 'white', cursor: 'pointer' }}>轉發</button>
        </div>
      </div>
    </div>
  );
}
