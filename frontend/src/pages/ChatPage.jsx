import React, { useState, useEffect, useContext, useRef } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../ChatPage.css';
import Navbar from '../components/Navbar';
import Sidebar from '../components/Sidebar';

export default function ChatPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // 狀態管理
  const [currentChat, setCurrentChat] = useState({ id: null, title: '新對話', messages: [] });
  const [inputMsg, setInputMsg] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  
  const chatWindowRef = useRef(null);
  const abortControllerRef = useRef(null);
  const currentChatRef = useRef(currentChat);

  // 同步 ref
  useEffect(() => {
    currentChatRef.current = currentChat;
  }, [currentChat]);

  // 自動捲動到底部
  useEffect(() => {
    if (chatWindowRef.current) {
      chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
    }
  }, [currentChat.messages, isTyping]);

  // 初始化與載入特定對話
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get('welcome') === 'true') {
      setShowWelcomeModal(true);
      // 清除 welcome param
      navigate('/chat', { replace: true });
      return;
    }

    const urlId = searchParams.get('id');

    // 處理測驗結果跳轉
    const rawQuizContext = localStorage.getItem('targetQuizContext');
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
      
      setCurrentChat({ id: null, title: '新對話', messages: [] });
      setTimeout(() => {
        executeChatStream(promptText, { customTitle: '我做完測驗，結果...' });
      }, 0);
      return;
    }

    // 正常載入對話
    if (!urlId || urlId === 'new') {
      setCurrentChat({ id: null, title: '新對話', messages: [] });
    } else {
      // 載入資料庫對話
      fetch(`${API_BASE_URL}/api/chat/sessions/${urlId}`, { credentials: 'include' })
        .then(res => res.json())
        .then(data => {
          if (data.id) {
            setCurrentChat(data);
          } else {
            // 找不到對話，回到新對話
            navigate('/chat?id=new', { replace: true });
          }
        })
        .catch(err => console.error('Failed to load session:', err));
    }
  }, [location.search, searchParams, API_BASE_URL]);

  // 保存對話到後端
  const saveSessionToBackend = async (chatState) => {
    try {
      const payload = {
        title: chatState.title,
        messages: chatState.messages
      };
      if (chatState.id) {
        payload.id = chatState.id;
      }
      const response = await fetch(`${API_BASE_URL}/api/chat/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (data.success && data.id) {
        const newId = data.id;
        // 如果是新建立的對話，更新 URL 和本地 state 的 id
        if (!chatState.id) {
          setCurrentChat(prev => ({ ...prev, id: newId }));
          navigate(`/chat?id=${newId}`, { replace: true });
        }
        window.dispatchEvent(new Event('chat-updated')); // 觸發 Sidebar 更新
      }
    } catch (e) {
      console.error("Failed to save session:", e);
    }
  };

  // ==========================================
  // 反饋與重試邏輯
  // ==========================================
  const handleFeedback = async (msgIdx, type) => {
    const msg = currentChat.messages[msgIdx];
    const userMsg = currentChat.messages[msgIdx - 1]?.content || '';
    if (!msg) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          feedback_type: type,
          user_message: userMsg,
          ai_response: msg.content
        })
      });
      if (response.ok) {
        // 更新 UI 狀態
        let updatedChat = null;
        setCurrentChat(prev => {
          const nc = { ...prev };
          const newMsgs = [...nc.messages];
          newMsgs[msgIdx] = { ...newMsgs[msgIdx], feedback: type };
          nc.messages = newMsgs;
          updatedChat = nc;
          return nc;
        });
        
        // 保存到後端
        if (updatedChat) {
           saveSessionToBackend(updatedChat);
        }
      }
    } catch (e) {
      console.error("Feedback failed:", e);
    }
  };

  const handleRetry = (msgIdx) => {
    if (isTyping || msgIdx <= 0) return;
    
    // 取出重試之前的 user 訊息
    const prevUserMsg = currentChat.messages[msgIdx - 1];
    if (!prevUserMsg || prevUserMsg.role !== 'user') return;

    // 將包含該 AI 訊息以及其後的所有訊息刪除
    const newMessages = currentChat.messages.slice(0, msgIdx - 1);
    
    setCurrentChat(prev => ({ ...prev, messages: newMessages }));
    
    // 重新發送
    executeChatStream(prevUserMsg.content);
  };

  // ==========================================
  // 核心發送與串流邏輯
  // ==========================================
  const executeChatStream = async (messageText, options = {}) => {
    const { customTitle = null } = options;
    if (!messageText.trim() || isTyping) return;
    
    setIsTyping(true);
    setInputMsg('');
    
    let chatTitle = currentChatRef.current.title;
    if (chatTitle === '新對話') {
      chatTitle = customTitle || messageText.substring(0, 10) + '...';
    }

    const updatedMessages = [
      ...currentChatRef.current.messages,
      { role: 'user', content: messageText },
      { role: 'ai', content: '', debug_info: null }
    ];

    // 更新 state (新增 user 和空白的 ai 訊息)
    setCurrentChat(prev => ({
      ...prev,
      title: chatTitle,
      messages: updatedMessages
    }));

    abortControllerRef.current = new AbortController();
    let currentAiContent = "";
    let currentDebugInfo = null;

    // 內部輔助函式：同步狀態，最後一次寫入後端
    const syncStreamState = async (content, debugInfo, appendText = '', isFinal = false) => {
      const finalContent = content + appendText;
      
      let finalChat = null;
      setCurrentChat(prev => {
        const nc = { ...prev };
        const msgs = [...nc.messages];
        const last = msgs[msgs.length - 1];
        if (last && last.role === 'ai') {
          msgs[msgs.length - 1] = { ...last, content: finalContent, debug_info: debugInfo ? { ...debugInfo } : last.debug_info };
        }
        nc.messages = msgs;
        finalChat = nc;
        return nc;
      });

      if (isFinal && finalChat) {
         await saveSessionToBackend(finalChat);
      }
    };

    // 準備歷史對話紀錄傳給後端 (只取最近 6 筆，排除剛才 push 的 user+ai)
    let historyToSend = [];
    if (updatedMessages.length >= 2) {
      const prevMsgs = updatedMessages.slice(0, -2);
      historyToSend = prevMsgs.slice(-6).map(m => ({
        role: m.role,
        content: m.content
      }));
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ 
          message: messageText, 
          history: historyToSend 
        }),
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
          await syncStreamState(currentAiContent, currentDebugInfo, '', true); // 結束並寫入後端
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
        
        // 串流途中只更新 React state
        syncStreamState(currentAiContent, currentDebugInfo, '', false);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        await syncStreamState(currentAiContent, currentDebugInfo, ' [已停止生成]', true);
      } else {
        console.error('AI Error:', error);
        await syncStreamState(currentAiContent, currentDebugInfo, '\n抱歉，連線發生錯誤：' + error.message, true);
      }
    } finally {
      setIsTyping(false);
      abortControllerRef.current = null;
    }
  };

  const sendMessage = () => executeChatStream(inputMsg);

  const handleStop = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsTyping(false);
  };

  // ==========================================
  // 渲染
  // ==========================================
  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
      <Sidebar />

      {/* --- 主內容區 --- */}
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>

        <div className="chat-window" ref={chatWindowRef}>
          {!currentChat.messages || currentChat.messages.length === 0 ? (
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
                    <>
                      <div className="message-text">{msg.content}</div>
                      {msg.role === 'ai' && !isTyping && msg.content !== '' && (
                        <div className="message-actions">
                          <button 
                            className="action-btn retry" 
                            title="重新傳送"
                            onClick={() => handleRetry(idx)}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2v6h-6"></path><path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M3 22v-6h6"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path></svg>
                          </button>
                          <button 
                            className={`action-btn like ${msg.feedback === 'like' ? 'active' : ''}`}
                            title="讚"
                            onClick={() => handleFeedback(idx, 'like')}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                          </button>
                          <button 
                            className={`action-btn dislike ${msg.feedback === 'dislike' ? 'active' : ''}`}
                            title="倒讚"
                            onClick={() => handleFeedback(idx, 'dislike')}
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path></svg>
                          </button>
                        </div>
                      )}
                    </>
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