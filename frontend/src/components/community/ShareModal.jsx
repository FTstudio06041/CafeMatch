
export default function ShareModal({
  showShareModal,
  setShowShareModal,
  postUrl,
  copied,
  handleCopyLink
}) {
  if (!showShareModal) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
      backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 1000, 
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backdropFilter: 'blur(4px)'
    }}>
      <div style={{ 
        backgroundColor: '#fdfbf7', 
        padding: '24px', 
        borderRadius: '16px', 
        width: '90%', 
        maxWidth: '500px',
        boxShadow: '0 10px 25px rgba(139, 90, 43, 0.15)',
        border: '1px solid rgba(139, 90, 43, 0.1)'
      }}>
        <h3 style={{ marginTop: 0, color: '#4a3b32', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#8b5a2b" strokeWidth="2">
            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path>
            <polyline points="16 6 12 2 8 6"></polyline>
            <line x1="12" y1="2" x2="12" y2="15"></line>
          </svg>
          分享貼文連結
        </h3>
        <p style={{ color: '#6a5a4e', fontSize: '0.9rem', marginBottom: '16px' }}>複製以下連結分享給你的好友，讓他們也能查看這篇精彩的貼文！</p>
        
        <div style={{ 
          display: 'flex', 
          gap: '8px', 
          alignItems: 'center', 
          backgroundColor: 'rgba(139, 90, 43, 0.05)', 
          padding: '8px 12px', 
          borderRadius: '12px', 
          border: '1px solid rgba(139, 90, 43, 0.15)',
          marginBottom: '20px'
        }}>
          <input 
            type="text" 
            readOnly 
            value={postUrl}
            style={{ 
              flexGrow: 1, 
              background: 'none', 
              border: 'none', 
              outline: 'none', 
              color: '#4a3b32', 
              fontSize: '0.9rem',
              textOverflow: 'ellipsis'
            }}
            onClick={e => e.target.select()}
          />
          <button 
            onClick={handleCopyLink}
            style={{ 
              backgroundColor: copied ? '#2ecc71' : '#8b5a2b', 
              color: 'white', 
              border: 'none', 
              borderRadius: '20px', 
              padding: '6px 14px', 
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 'bold',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              transition: 'background-color 0.2s',
              minWidth: '70px',
              justifyContent: 'center'
            }}
          >
            {copied ? (
              <>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" style={{ marginRight: '2px' }}>
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                已複製
              </>
            ) : '複製'}
          </button>
        </div>
        
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button 
            onClick={() => setShowShareModal(false)} 
            style={{ 
              padding: '8px 20px', 
              border: '1px solid rgba(139, 90, 43, 0.4)', 
              borderRadius: '20px', 
              backgroundColor: 'transparent', 
              color: '#8b5a2b', 
              cursor: 'pointer',
              fontWeight: 'bold',
              transition: 'background-color 0.2s'
            }}
            onMouseEnter={e => e.target.style.backgroundColor = 'rgba(139, 90, 43, 0.05)'}
            onMouseLeave={e => e.target.style.backgroundColor = 'transparent'}
          >
            關閉
          </button>
        </div>
      </div>
    </div>
  );
}
