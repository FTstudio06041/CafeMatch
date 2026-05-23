import React, { useState, useEffect, useContext, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../ChatPage.css';
import Navbar from '../components/Navbar';

export default function ChatPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();

  // 狀態管理
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [inputMsg, setInputMsg] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [loadingChatId, setLoadingChatId] = useState(null);
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  
  const chatWindowRef = useRef(null);
  const abortControllerRef = useRef(null);
  const currentChatIdRef = useRef(currentChatId);
  const isInitialized = useRef(false);

  // 同步 ref 供非同步函式使用
  useEffect(() => {
    currentChatIdRef.current = currentChatId;
  }, [currentChatId]);

  // 記住最後一個開啟的對話
  useEffect(() => {
    if (currentChatId) {
      localStorage.setItem('lastChatId', currentChatId);
    }
  }, [currentChatId]);

  // 自動捲動到底部
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [chats, currentChatId, isTyping]);

  // ==========================================
  // 初始化邏輯 (消除原有的 race condition)
  // ==========================================
  useEffect(() => {
    if (isInitialized.current) return;
    isInitialized.current = true;

    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    let initialChatId = null;

    // 1. 檢查歡迎彈窗
    const params = new URLSearchParams(location.search);
    if (params.get('welcome') === 'true') {
      setShowWelcomeModal(true);
      navigate(location.pathname, { replace: true });
    }

    // 2. 處理導航意圖 (測驗結果 > 指定對話 > 上次對話)
    const rawQuizContext = localStorage.getItem('targetQuizContext');
    const targetChatId = localStorage.getItem('targetChatId');
    const lastChatId = localStorage.getItem('lastChatId');

    if (rawQuizContext) {
      localStorage.removeItem('targetQuizContext');
      let promptText = '';
      try {
        const quizData = JSON.parse(rawQuizContext);
        const scoreParts = [];
        const scoreLabels = { work: '工作讀書', env: '空間氛圍', social: '社交舒適', taste: '餐飲口味', cp: 'CP值' };
        if (quizData.scores) {
          for (const [key, val] of Object.entries(quizData.scores)) {
            scoreParts.push(`${scoreLabels[key] || key}：${val}`);
          }
        }
        promptText = `我剛完成了咖啡人格測驗，以下是我的完整結果：\n`
          + `\n【咖啡人格】${quizData.title}`
          + (quizData.inner_voice ? `\n【內心獨白】${quizData.inner_voice}` : '')
          + (quizData.profile ? `\n【特質側寫】${quizData.profile}` : '')
          + (scoreParts.length > 0 ? `\n【五維分數】${scoreParts.join('、')}` : '')
          + (quizData.cafe_match ? `\n【氛圍對應】${quizData.cafe_match}` : '')
          + `\n\n請根據以上測驗結果，推薦適合我的花蓮咖啡廳，並說明為什麼適合我。`;
      } catch {
        promptText = `我剛做完測驗，結果適合「${rawQuizContext}」，請根據這個結果推薦我類似的咖啡廳或豆子。`;
      }
      
      setChats(savedChats);
      // 等待 React state 更新後，自動建立新對話並發送
      setTimeout(() => {
        executeChatStream(promptText, { forceNewChat: true, customTitle: '我做完測驗，結果...' });
      }, 0);
      return; // 提前返回，讓 executeChatStream 接手
    } 
    
    let updatedChats = [...savedChats];
    
    if (targetChatId) {
      if (targetChatId === 'new') {
        initialChatId = Date.now();
        updatedChats = [{ id: initialChatId, title: `新對話 ${savedChats.length + 1}`, messages: [] }, ...savedChats];
      } else {
        initialChatId = Number(targetChatId);
      }
      localStorage.removeItem('targetChatId');
    } else if (lastChatId) {
      initialChatId = Number(lastChatId);
      if (!updatedChats.find(c => c.id === initialChatId) && updatedChats.length > 0) {
        initialChatId = updatedChats[0].id;
      }
    } else if (updatedChats.length > 0) {
      initialChatId = updatedChats[0].id;
    }

    setChats(updatedChats);
    if (initialChatId) setCurrentChatId(initialChatId);
    
  }, [location.pathname, location.search, navigate]);

  // ==========================================
  // 對話管理
  // ==========================================
  const handleNewChat = () => {
    const newId = Date.now();
    const newChat = { id: newId, title: `新對話 ${chats.length + 1}`, messages: [] };
    const tempChats = [newChat, ...chats];
    setChats(tempChats);
    localStorage.setItem('allChats', JSON.stringify(tempChats));
    setCurrentChatId(newId);
  };

  const handleDeleteChat = (e, id) => {
    e.stopPropagation();
    if (window.confirm('確定要刪除此對話嗎？')) {
      const tempChats = chats.filter(c => c.id !== id);
      setChats(tempChats);
      localStorage.setItem('allChats', JSON.stringify(tempChats));
      if (currentChatIdRef.current === id) setCurrentChatId(null);
    }
  };

  // ==========================================
  // 核心發送與串流邏輯 (統一重構)
  // ==========================================
  const executeChatStream = async (messageText, options = {}) => {
    const { forceNewChat = false, customTitle = null } = options;
    if (!messageText.trim() || isTyping) return;
    
    setIsTyping(true);
    let targetChatId = currentChatIdRef.current;
    let currentSaved = JSON.parse(localStorage.getItem('allChats')) || [];

    // 若強制開新對話，或當前無對話，則建立
    if (forceNewChat || !targetChatId) {
      targetChatId = Date.now();
      const title = customTitle || messageText.substring(0, 10) + '...';
      currentSaved = [{ id: targetChatId, title, messages: [] }, ...currentSaved];
      setCurrentChatId(targetChatId);
    }

    // 處理「新對話」自動更名
    const chatIdx = currentSaved.findIndex(c => c.id === targetChatId);
    if (chatIdx !== -1 && currentSaved[chatIdx].title.startsWith('新對話')) {
      currentSaved[chatIdx].title = messageText.substring(0, 10) + '...';
    }

    // 插入使用者訊息與 AI 空白佔位符
    if (chatIdx !== -1) {
      currentSaved[chatIdx].messages.push({ role: 'user', content: messageText });
      currentSaved[chatIdx].messages.push({ role: 'ai', content: '', debug_info: null });
    }

    // 更新狀態並清空輸入
    setChats(currentSaved);
    localStorage.setItem('allChats', JSON.stringify(currentSaved));
    if (!forceNewChat) setInputMsg('');
    setLoadingChatId(targetChatId);
    
    abortControllerRef.current = new AbortController();
    let currentAiContent = "";
    let currentDebugInfo = null;

    // 內部輔助函式：同步 localStorage 與狀態
    const syncStreamState = (content, debugInfo, appendText = '') => {
      const finalContent = content + appendText;
      
      setChats(prev => {
        const nc = [...prev];
        const i = nc.findIndex(c => c.id === targetChatId);
        if (i !== -1) {
          const msgs = nc[i].messages;
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'ai') {
            last.content = finalContent;
            if (debugInfo) last.debug_info = { ...debugInfo };
          }
        }
        return nc;
      });

      const saved = JSON.parse(localStorage.getItem('allChats')) || [];
      const si = saved.findIndex(c => c.id === targetChatId);
      if (si !== -1) {
        const msgs = saved[si].messages;
        const last = msgs[msgs.length - 1];
        if (last && last.role === 'ai') {
          last.content = finalContent;
          last.debug_info = debugInfo;
          localStorage.setItem('allChats', JSON.stringify(saved));
        }
      }
    };

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: messageText }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: '伺服器回傳錯誤' }));
        throw new Error(errorData.error || '伺服器回傳錯誤');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          syncStreamState(currentAiContent, currentDebugInfo); // 最終確保寫入 localStorage
          break;
        }

        const chunkStr = decoder.decode(value, { stream: true });
        const lines = chunkStr.split('\n').filter(l => l.trim() !== '');

        for (const line of lines) {
          try {
            const data = JSON.parse(line);
            if (data.type === 'debug_info') {
              currentDebugInfo = {
                model: data.model, prompt: data.prompt,
                is_cafe_related: data.is_cafe_related ? '✅ 是 (已注入資料庫)' : '❌ 否 (一般聊天)',
                rag_context: data.rag_context || '',
                total_duration_ms: '...', eval_count: '...',
                eval_duration_ms: '...', tokens_per_sec: '...'
              };
            } else if (data.response) {
              currentAiContent += data.response;
            } else if (data.error) {
              currentAiContent += '\n[系統錯誤: ' + data.error + ']';
            }

            if (data.done && currentDebugInfo) {
              currentDebugInfo.total_duration_ms = (data.total_duration / 1e6).toFixed(2);
              currentDebugInfo.eval_count = data.eval_count;
              currentDebugInfo.eval_duration_ms = (data.eval_duration / 1e6).toFixed(2);
              currentDebugInfo.tokens_per_sec = data.eval_duration > 0
                ? (data.eval_count / (data.eval_duration / 1e9)).toFixed(2)
                : 0;
            }
          } catch (_) { /* 忽略不完整的 chunk */ }
        }
        
        // 串流途中只更新 React state（優化效能，最終 done 時再寫入 localStorage）
        setChats(prev => {
          const nc = [...prev];
          const i = nc.findIndex(c => c.id === targetChatId);
          if (i !== -1) {
            const msgs = nc[i].messages;
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'ai') {
              last.content = currentAiContent;
              if (currentDebugInfo) last.debug_info = { ...currentDebugInfo };
            }
          }
          return nc;
        });
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        syncStreamState(currentAiContent, currentDebugInfo, ' [已停止生成]');
      } else {
        console.error('AI Error:', error);
        syncStreamState(currentAiContent, currentDebugInfo, '\n抱歉，連線發生錯誤：' + error.message);
      }
    } finally {
      setIsTyping(false);
      setLoadingChatId(null);
      abortControllerRef.current = null;
    }
  };

  const sendMessage = () => executeChatStream(inputMsg);

  const handleStop = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsTyping(false);
    setLoadingChatId(null);
  };

  const currentChat = chats.find(c => c.id === currentChatId);

  // ==========================================
  // 渲染
  // ==========================================
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <button className="toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="9" y1="3" x2="9" y2="21"></line>
          </svg>
        </button>

        <button className="user-profile-btn" onClick={() => navigate('/profile')}>
          <div className="user-avatar" style={{ backgroundColor: user?.picture ? 'transparent' : 'var(--accent-color)' }}>
            {user?.picture ? <img src={user.picture} alt="avatar" style={{width: '100%', borderRadius: '50%'}} /> : 'U'}
          </div>
          <span className="user-name text-label">{user?.name || '使用者名稱'}</span>
        </button>

        <button className="new-chat-btn" onClick={handleNewChat}>
           <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
           <span className="text-label">新增對話</span>
        </button>

        <div className="history-label text-label">對話紀錄</div>
        <div className="chat-list">
          {chats.length === 0 ? (
            <div className="empty-sidebar-msg">尚無對話紀錄</div>
          ) : (
            chats.map(chat => (
              <div key={chat.id} className={`chat-item ${chat.id === currentChatId ? 'active' : ''}`} onClick={() => setCurrentChatId(chat.id)}>
                <div className="chat-icon">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                </div>
                <span className="chat-title text-label">{chat.title}</span>
                <button className="delete-btn" onClick={(e) => handleDeleteChat(e, chat.id)}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* --- 主內容區 --- */}
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>

        <div className="chat-window" ref={chatWindowRef}>
          {!currentChat || currentChat.messages.length === 0 ? (
            <div className="placeholder-zone">
              <h3>歡迎來到啡你莫屬</h3>
              <p>
                您可以直接輸入訊息諮詢，或是進行
                <span className="quiz-link" onClick={() => navigate('/quiz')}>心理測驗</span>
                以獲得更精準的咖啡推薦。
              </p>
            </div>
          ) : (
            currentChat.messages.map((msg, idx) => (
              <React.Fragment key={idx}>
                <div className={`message ${msg.role}`}>
                  {msg.role === 'ai' && msg.content === '' ? (
                    <div className="typing-indicator" style={{ margin: 0, padding: 0, background: 'transparent' }}>
                      <div className="typing-dot"></div><div className="typing-dot"></div><div className="typing-dot"></div>
                    </div>
                  ) : (
                    msg.content
                  )}
                </div>
                {isDebugMode && msg.debug_info && (
                  <div className="debug-console">
                    <div className="debug-header">Debug Console</div>
                    <div className="debug-content">
                      <div><strong>Model:</strong> {msg.debug_info.model}</div>
                      <div><strong>Intent (意圖分類):</strong> {msg.debug_info.is_cafe_related}</div>
                      <div><strong>Generation Speed:</strong> {msg.debug_info.tokens_per_sec} tokens/s ({msg.debug_info.eval_count} tokens in {msg.debug_info.eval_duration_ms} ms)</div>
                      <div><strong>Total Duration:</strong> {msg.debug_info.total_duration_ms} ms</div>
                      {msg.debug_info.rag_context && msg.debug_info.rag_context !== '(未注入資料庫資料)' && (
                        <div className="debug-prompt"><strong>RAG 注入資料:</strong><br/>{msg.debug_info.rag_context}</div>
                      )}
                      <div className="debug-prompt"><strong>完整 Prompt:</strong><br/>{msg.debug_info.prompt}</div>
                    </div>
                  </div>
                )}
              </React.Fragment>
            ))
          )}
        </div>

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

        {/* --- 歡迎彈窗 --- */}
        <div className={`welcome-modal-overlay ${showWelcomeModal ? 'active' : ''}`}>
           <div className="welcome-card">
              <h2 className="welcome-title">歡迎來到 啡你莫屬！</h2>
              <p className="welcome-text">這似乎是您第一次來訪。<br/>建議您先進行心理測驗，<br/>讓啡啡更了解您的喜好喔！</p>
              <div className="welcome-actions">
                  <button className="btn-secondary" onClick={() => setShowWelcomeModal(false)}>先不用</button>
                  <button className="btn-primary" onClick={() => navigate('/quiz')}>開始測驗</button>
              </div>
           </div>
        </div>
      </main>
    </div>
  );
}