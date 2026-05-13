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

  // 初始化載入 LocalStorage 的對話紀錄
  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    let updatedChats = [...savedChats];
    
    // 檢查從其他頁面傳來的目標對話 ID
    const targetChatId = localStorage.getItem('targetChatId');
    const lastChatId = localStorage.getItem('lastChatId');

    if (targetChatId) {
      if (targetChatId === 'new') {
        const newId = Date.now();
        updatedChats = [{ id: newId, title: `新對話 ${savedChats.length + 1}`, messages: [] }, ...savedChats];
        setCurrentChatId(newId);
      } else {
        setCurrentChatId(Number(targetChatId));
      }
      localStorage.removeItem('targetChatId');
    } else if (lastChatId) {
      const id = Number(lastChatId);
      if (updatedChats.find(c => c.id === id)) {
        setCurrentChatId(id);
      } else if (updatedChats.length > 0) {
        setCurrentChatId(updatedChats[0].id);
      }
    } else if (updatedChats.length > 0) {
      // 預設打開第一個對話
      setCurrentChatId(updatedChats[0].id);
    }

    setChats(updatedChats);

    // 檢查 URL 參數是否需要顯示歡迎彈窗
    const params = new URLSearchParams(location.search);
    if (params.get('welcome') === 'true') {
      setShowWelcomeModal(true);
      // 清除 URL 參數
      navigate(location.pathname, { replace: true });
    }
  }, [location, navigate]);

  // (已移除原先依賴 useEffect 的 allChats 同步機制，改採各行為強制同步寫入)

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

  // 新增對話
  const handleNewChat = () => {
    const newId = Date.now();
    const newChat = { id: newId, title: `新對話 ${chats.length + 1}`, messages: [] };
    const tempChats = [newChat, ...chats];
    setChats(tempChats);
    localStorage.setItem('allChats', JSON.stringify(tempChats));
    setCurrentChatId(newId);
  };

  // 刪除對話
  const handleDeleteChat = (e, id) => {
    e.stopPropagation();
    if (window.confirm('確定要刪除此對話嗎？')) {
      const tempChats = chats.filter(c => c.id !== id);
      setChats(tempChats);
      localStorage.setItem('allChats', JSON.stringify(tempChats));
      if (currentChatId === id) setCurrentChatId(null);
    }
  };

  // 發送訊息
  const sendMessage = async () => {
    if (!inputMsg.trim() || isTyping) return;

    const messageToSend = inputMsg.trim();
    let targetChatId = currentChatId;
    let currentAiContent = "";
    let currentDebugInfo = null;

    // --- 同步區塊：建立對話與使用者訊息 ---
    let updatedChats = [...chats];

    if (!targetChatId) {
      targetChatId = Date.now();
      updatedChats = [{ id: targetChatId, title: messageToSend.substring(0, 10) + '...', messages: [] }, ...updatedChats];
      setCurrentChatId(targetChatId);
    }

    const currentChatIndex = updatedChats.findIndex(c => c.id === targetChatId);

    if (currentChatIndex !== -1 && updatedChats[currentChatIndex].title && updatedChats[currentChatIndex].title.startsWith('新對話')) {
      updatedChats[currentChatIndex].title = messageToSend.substring(0, 10) + '...';
    }

    if (currentChatIndex !== -1) {
      updatedChats[currentChatIndex].messages.push({ role: 'user', content: messageToSend });
    } else {
      updatedChats = [{ id: targetChatId, title: messageToSend.substring(0, 10) + '...', messages: [{ role: 'user', content: messageToSend }] }, ...updatedChats];
      setCurrentChatId(targetChatId);
    }

    // 預先插入一個空的 AI 訊息佔位，方便後續串流即時更新
    const chatIdx = updatedChats.findIndex(c => c.id === targetChatId);
    if (chatIdx !== -1) {
      updatedChats[chatIdx].messages.push({ role: 'ai', content: '', debug_info: null });
    }

    setChats(updatedChats);
    localStorage.setItem('allChats', JSON.stringify(updatedChats));
    setInputMsg('');
    setIsTyping(true);
    setLoadingChatId(targetChatId);
    abortControllerRef.current = new AbortController();

    // --- 非同步區塊：串流讀取 AI 回覆 ---
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: messageToSend }),
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
        if (done) break;

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

        // 即時更新畫面
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

      // 串流正常結束 → 寫入 LocalStorage
      const saved = JSON.parse(localStorage.getItem('allChats')) || [];
      const si = saved.findIndex(c => c.id === targetChatId);
      if (si !== -1) {
        const msgs = saved[si].messages;
        const last = msgs[msgs.length - 1];
        if (last && last.role === 'ai') {
          last.content = currentAiContent;
          last.debug_info = currentDebugInfo;
          localStorage.setItem('allChats', JSON.stringify(saved));
        }
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        // 使用者按了停止 → 保存已生成的部分
        const saved = JSON.parse(localStorage.getItem('allChats')) || [];
        const si = saved.findIndex(c => c.id === targetChatId);
        if (si !== -1) {
          const msgs = saved[si].messages;
          const last = msgs[msgs.length - 1];
          if (last && last.role === 'ai') {
            last.content = currentAiContent + ' [已停止生成]';
            last.debug_info = currentDebugInfo;
            localStorage.setItem('allChats', JSON.stringify(saved));
          }
        }
        // 同步更新 React 畫面
        setChats(prev => {
          const nc = [...prev];
          const i = nc.findIndex(c => c.id === targetChatId);
          if (i !== -1) {
            const msgs = nc[i].messages;
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'ai') {
              last.content = currentAiContent + ' [已停止生成]';
              last.debug_info = currentDebugInfo;
            }
          }
          return nc;
        });
      } else {
        console.error('AI Error:', error);
        // 連線錯誤 → 顯示錯誤訊息
        setChats(prev => {
          const nc = [...prev];
          const i = nc.findIndex(c => c.id === targetChatId);
          if (i !== -1) {
            const msgs = nc[i].messages;
            const last = msgs[msgs.length - 1];
            if (last && last.role === 'ai') {
              last.content = '抱歉，連線發生錯誤：' + error.message;
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
            last.content = '抱歉，連線發生錯誤：' + error.message;
            localStorage.setItem('allChats', JSON.stringify(saved));
          }
        }
      }
    } finally {
      setIsTyping(false);
      setLoadingChatId(null);
      abortControllerRef.current = null;
    }
  };

  // 停止生成
  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setIsTyping(false);
    setLoadingChatId(null);
  };

  const hasProcessedQuiz = useRef(false);

    useEffect(() => {
    // 確保使用者已登入，且還沒處理過這次的測驗結果
    if (user && !hasProcessedQuiz.current) {
        const quizContext = localStorage.getItem('targetQuizContext');
        
        if (quizContext) {
        hasProcessedQuiz.current = true; // 標記為已處理
        localStorage.removeItem('targetQuizContext'); // 隨即移除，避免重新整理頁面時又跑一次

        const promptText = `我剛做完測驗，結果適合「${quizContext}」，請根據這個結果推薦我類似的咖啡廳或豆子。`;
        
        // 自動執行發送邏輯
        handleAutoSendMessage(promptText);
        }
    }
    }, [user]); // 當 user 狀態確認後執行

    // 2. 建立一個專門給自動觸發使用的發送函式（邏輯與你的 sendMessage 類似）
    const handleAutoSendMessage = async (text) => {
    setIsTyping(true);
    
    // 建立新對話
    const newId = Date.now();
    const newChat = { 
        id: newId, 
        title: text.substring(0, 10) + '...', 
        messages: [{ role: 'user', content: text }] 
    };
    
    // 更新狀態
    const currentSaved = JSON.parse(localStorage.getItem('allChats')) || [];
    const tempChats = [newChat, ...currentSaved];
    setChats(tempChats);
    localStorage.setItem('allChats', JSON.stringify(tempChats));

    setCurrentChatId(newId);
    setLoadingChatId(newId);

    abortControllerRef.current = new AbortController();

    let currentAiContent = "";
    let currentDebugInfo = null;

    try {
        setChats(prev => {
            const newChats = [...prev];
            const idx = newChats.findIndex(c => c.id === newId);
            if (idx !== -1) {
                newChats[idx].messages.push({ role: 'ai', content: "", debug_info: null });
            }
            return newChats;
        });

        const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: text }),
        signal: abortControllerRef.current.signal
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
                const savedIdx = savedChats.findIndex(c => c.id === newId);
                if (savedIdx !== -1) {
                    const msgs = savedChats[savedIdx].messages;
                    if (msgs.length > 0) {
                        msgs[msgs.length - 1].content = currentAiContent;
                        msgs[msgs.length - 1].debug_info = currentDebugInfo;
                        localStorage.setItem('allChats', JSON.stringify(savedChats));
                    }
                }
                break;
            }
            
            const chunkStr = decoder.decode(value, { stream: true });
            const lines = chunkStr.split('\n').filter(line => line.trim() !== '');
            
            for (const line of lines) {
                try {
                    const data = JSON.parse(line);
                    if (data.type === "debug_info") {
                        currentDebugInfo = {
                            model: data.model,
                            prompt: data.prompt,
                            total_duration_ms: "...",
                            eval_count: "...",
                            eval_duration_ms: "...",
                            tokens_per_sec: "..."
                        };
                    } else if (data.response) {
                        currentAiContent += data.response;
                    } else if (data.error) {
                        currentAiContent += "\n[系統錯誤: " + data.error + "]";
                    }
                    
                    if (data.done && currentDebugInfo) {
                        currentDebugInfo.total_duration_ms = (data.total_duration / 1000000).toFixed(2);
                        currentDebugInfo.eval_count = data.eval_count;
                        currentDebugInfo.eval_duration_ms = (data.eval_duration / 1000000).toFixed(2);
                        if (data.eval_duration > 0) {
                            currentDebugInfo.tokens_per_sec = (data.eval_count / (data.eval_duration / 1000000000)).toFixed(2);
                        } else {
                            currentDebugInfo.tokens_per_sec = 0;
                        }
                    }
                } catch (e) {}
            }
            
            setChats(prev => {
                const newChats = [...prev];
                const idx = newChats.findIndex(c => c.id === newId);
                if (idx !== -1) {
                    const msgs = newChats[idx].messages;
                    if (msgs.length > 0) {
                        const lastMsg = msgs[msgs.length - 1];
                        lastMsg.content = currentAiContent;
                        if (currentDebugInfo) lastMsg.debug_info = {...currentDebugInfo};
                    }
                }
                return newChats;
            });
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
            const savedIdx = savedChats.findIndex(c => c.id === newId);
            if (savedIdx !== -1) {
                const msgs = savedChats[savedIdx].messages;
                if (msgs.length > 0) {
                    msgs[msgs.length - 1].content = currentAiContent + " [已停止生成]";
                    msgs[msgs.length - 1].debug_info = currentDebugInfo;
                    localStorage.setItem('allChats', JSON.stringify(savedChats));
                }
            }
            return;
        }
        console.error("AI Error:", error);
        
        const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
        const savedIdx = savedChats.findIndex(c => c.id === newId);
        if (savedIdx !== -1) {
          savedChats[savedIdx].messages.push({ role: 'ai', content: "抱歉，連線發生錯誤。" });
          localStorage.setItem('allChats', JSON.stringify(savedChats));
        }
    } finally {
        setIsTyping(false);
        setLoadingChatId(null);
        abortControllerRef.current = null;
    }
    };

  const currentChat = chats.find(c => c.id === currentChatId);

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