import { useState, useEffect, useContext, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

import '../ChatPage.css';
import MessageBubble from '../components/MessageBubble';
import ChatInputArea from '../components/chat/ChatInputArea';
import WelcomeModal from '../components/chat/WelcomeModal';

import { toast } from '../utils/toast';
import { logger } from '../utils/logger';
import { useChat } from '../context/ChatContext';
import { chatService } from '../services/chatService';

export default function ChatPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();

  const {
    currentChat,
    setNormalizedCurrentChat,
    isTyping,
    executeChatStream,
    handleFeedback,
    handleStop,
    currentChatRef,
    EMPTY_CHAT
  } = useChat();

  const [inputMsg, setInputMsg] = useState('');
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  const chatWindowRef = useRef(null);

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
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowWelcomeModal(true);
      // 清除 welcome param
      navigate('/chat', { replace: true });
      return;
    }

    const urlId = params.get('id');

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
      
      setNormalizedCurrentChat(EMPTY_CHAT);
      setTimeout(() => {
        executeChatStream(promptText, { customTitle: '我做完測驗，結果...' });
      }, 0);
      return;
    }

    // 正常載入對話
    if (!urlId || urlId === 'new') {
      setNormalizedCurrentChat(EMPTY_CHAT);
    } else {
      if (user?.isGuest) {
        navigate('/chat?id=new', { replace: true });
        return;
      }
      // 載入資料庫對話
      chatService.fetchSessionDetail(urlId)
        .then(data => {
          if (data.id) {
            setNormalizedCurrentChat(data);
          } else {
            navigate('/chat?id=new', { replace: true });
          }
        })
        .catch(err => logger.error('Failed to load session:', err));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, user?.isGuest, navigate]);





  const handleRetry = (msgIdx) => {
    if (isTyping || msgIdx <= 0) return;
    
    // 取出重試之前的 user 訊息
    const prevUserMsg = currentChat.messages[msgIdx - 1];
    if (!prevUserMsg || prevUserMsg.role !== 'user') return;

    // 將包含該 AI 訊息以及其後的所有訊息刪除
    const newMessages = currentChat.messages.slice(0, msgIdx - 1);
    
    setNormalizedCurrentChat({ ...currentChatRef.current, messages: newMessages });
    
    // 重新發送
    executeChatStream(prevUserMsg.content);
  };

  const sendMessage = () => {
    setInputMsg('');
    executeChatStream(inputMsg);
  };

  const handleSituationalComplete = useCallback((situationalContext, msgIdx) => {
    // 情境元件不算分、不產生人格結果；直接把結構化情境偏好送進推薦管線
    setTimeout(() => {
      executeChatStream('', {
        customTitle: '情境推薦',
        hiddenPrompt: true,
        situationalContext,
        replaceMsgIdx: msgIdx,
      });
    }, 300);
  }, [executeChatStream]);

  // ==========================================
  // 渲染
  // ==========================================
  return (
    <>
      <div style={{ position: 'relative', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
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
              <MessageBubble
                key={idx}
                msg={msg}
                idx={idx}
                isTyping={isTyping}
                isLastMessage={idx === currentChat.messages.length - 1}
                handleRetry={handleRetry}
                handleFeedback={handleFeedback}
                isDebugMode={isDebugMode}
                onSituationalComplete={handleSituationalComplete}
              />
            ))
          )}
        </div>
        
        <ChatInputArea
          user={user}
          inputMsg={inputMsg}
          setInputMsg={setInputMsg}
          isTyping={isTyping}
          sendMessage={sendMessage}
          handleStop={handleStop}
          showOptionsMenu={showOptionsMenu}
          setShowOptionsMenu={setShowOptionsMenu}
          isDebugMode={isDebugMode}
          setIsDebugMode={setIsDebugMode}
        />

      </div>

      <WelcomeModal show={showWelcomeModal} onClose={() => setShowWelcomeModal(false)} />
    </>
  );
}
