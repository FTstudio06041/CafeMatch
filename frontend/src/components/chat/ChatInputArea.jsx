
export default function ChatInputArea({
  user,
  inputMsg,
  setInputMsg,
  isTyping,
  sendMessage,
  handleStop,
  showOptionsMenu,
  setShowOptionsMenu,
  isDebugMode,
  setIsDebugMode
}) {
  return (
    <div className="input-area">
      <div className="input-wrapper">
        {user?.is_admin && (
          <div style={{ position: 'relative' }}>
            <button 
              className="options-btn" 
              onClick={() => setShowOptionsMenu(!showOptionsMenu)}
              title="選項"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1"></circle><circle cx="12" cy="5" r="1"></circle><circle cx="12" cy="19" r="1"></circle></svg>
            </button>
            {showOptionsMenu && (
              <div className="options-menu">
                <button className="options-menu-item" onClick={() => { setIsDebugMode(!isDebugMode); setShowOptionsMenu(false); }}>
                  {isDebugMode ? '關閉 Debug 模式' : '開啟 Debug 模式'}
                </button>
              </div>
            )}
          </div>
        )}
        <input 
          type="text" 
          className="chat-input" 
          placeholder={isTyping ? "AI 正在思考中..." : "輸入訊息..."} 
          value={inputMsg}
          onChange={(e) => setInputMsg(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && !isTyping && sendMessage()}
          disabled={isTyping}
        />
        {isTyping ? (
          <button className="send-btn" onClick={handleStop} style={{ backgroundColor: '#D32F2F' }} title="停止生成">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="6" y="6" width="12" height="12"></rect></svg>
          </button>
        ) : (
          <button className="send-btn" onClick={sendMessage} disabled={!inputMsg.trim()}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        )}
      </div>
      <div className="disclaimer-text">AI 生成內容可能含有錯誤，請斟酌採納生成內容。</div>
    </div>
  );
}
