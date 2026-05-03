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
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);
  
  const chatWindowRef = useRef(null);

  // 初始化載入 LocalStorage 的對話紀錄
  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    setChats(savedChats);

    // 檢查 URL 參數是否需要顯示歡迎彈窗
    const params = new URLSearchParams(location.search);
    if (params.get('welcome') === 'true') {
      setShowWelcomeModal(true);
      // 清除 URL 參數
      navigate(location.pathname, { replace: true });
    }
  }, [location, navigate]);

  // 當 chats 變動時，存回 LocalStorage
  useEffect(() => {
    localStorage.setItem('allChats', JSON.stringify(chats));
  }, [chats]);

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
    setChats([newChat, ...chats]);
    setCurrentChatId(newId);
  };

  // 刪除對話
  const handleDeleteChat = (e, id) => {
    e.stopPropagation();
    if (window.confirm('確定要刪除此對話嗎？')) {
      setChats(chats.filter(c => c.id !== id));
      if (currentChatId === id) setCurrentChatId(null);
    }
  };

  // 發送訊息
  const sendMessage = async () => {
    if (!inputMsg.trim() || isTyping) return;

    let targetChatId = currentChatId;
    let updatedChats = [...chats];

    // 如果沒有選中對話，先建立一個新的
    if (!targetChatId) {
      targetChatId = Date.now();
      updatedChats = [{ id: targetChatId, title: inputMsg.substring(0, 10) + '...', messages: [] }, ...updatedChats];
      setCurrentChatId(targetChatId);
    }

    const currentChatIndex = updatedChats.findIndex(c => c.id === targetChatId);
    
    // 更新標題 (如果是新對話)
    if (updatedChats[currentChatIndex].title.startsWith('新對話')) {
       updatedChats[currentChatIndex].title = inputMsg.substring(0, 10) + '...';
    }

    // 加入使用者訊息
    updatedChats[currentChatIndex].messages.push({ role: 'user', content: inputMsg });
    setChats(updatedChats);
    setInputMsg('');
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: inputMsg })
      });
      const data = await response.json();
      
      // 確保拿到最新的 chats 狀態再來更新
      setChats(prevChats => {
        const newChats = [...prevChats];
        const idx = newChats.findIndex(c => c.id === targetChatId);
        if (idx !== -1) {
          newChats[idx].messages.push({ role: 'ai', content: data.reply || data.error });
        }
        return newChats;
      });

    } catch (error) {
      console.error("AI Error:", error);
      setChats(prevChats => {
        const newChats = [...prevChats];
        const idx = newChats.findIndex(c => c.id === targetChatId);
        if (idx !== -1) {
          newChats[idx].messages.push({ role: 'ai', content: "抱歉，連線發生錯誤。" });
        }
        return newChats;
      });
    } finally {
      setIsTyping(false);
    }
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
    setChats(prev => [newChat, ...prev]);
    setCurrentChatId(newId);

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ message: text })
        });
        const data = await response.json();
        
        setChats(prev => {
        const newChats = [...prev];
        const idx = newChats.findIndex(c => c.id === newId);
        if (idx !== -1) {
            newChats[idx].messages.push({ role: 'ai', content: data.reply || data.error });
        }
        return newChats;
        });
    } catch (error) {
        console.error("AI Error:", error);
    } finally {
        setIsTyping(false);
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
              <div key={idx} className={`message ${msg.role}`}>
                {msg.content}
              </div>
            ))
          )}
          
          {isTyping && (
             <div className="typing-indicator">
               <div className="typing-dot"></div><div className="typing-dot"></div><div class="typing-dot"></div>
             </div>
          )}
        </div>

        <div className="input-area">
          <div className="input-wrapper">
            <input 
              type="text" 
              className="chat-input" 
              placeholder={isTyping ? "AI 正在思考中..." : "輸入訊息..."} 
              value={inputMsg}
              onChange={(e) => setInputMsg(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              disabled={isTyping}
            />
            <button className="send-btn" onClick={sendMessage} disabled={isTyping}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
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