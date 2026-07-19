import { useState, useEffect, useContext, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

import '../ChatPage.css';
import MessageBubble from '../components/MessageBubble';
import ChatInputArea from '../components/chat/ChatInputArea';

import { logger } from '../utils/logger';
import { useChat } from '../context/ChatContext';
import { chatService } from '../services/chatService';

export default function ChatPage() {
  const { user } = useContext(AuthContext);
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
    EMPTY_CHAT,
    progressPercent,
    resetProgress
  } = useChat();

  const [inputMsg, setInputMsg] = useState('');
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
    // 新用戶強制測驗：完成心理測驗前不得進入聊天
    if (localStorage.getItem('forceQuiz') === 'true') {
      navigate('/quiz', { replace: true });
      return;
    }

    const params = new URLSearchParams(location.search);
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
          // 保存五維分數，供「直接推薦」時作為 GNN 推薦的基礎向量
          localStorage.setItem('latestQuizScores', JSON.stringify(quizData.scores));
          for (const [key, val] of Object.entries(quizData.scores)) {
            scoreParts.push(`${scoreLabels[key] || key}：${val}`);
          }
        }
        promptText = `我剛完成了咖啡人格測驗，以下是我的完整結果：\n`
          + `\n【咖啡人格】${quizData.title}`
          + (quizData.inner_voice ? `\n【內心獨白】${quizData.inner_voice}` : '')
          + (quizData.profile ? `\n【特質側寫】${quizData.profile}` : '')
          + (scoreParts.length > 0 ? `\n【五維分數】${scoreParts.join('、')}` : '')
          + (quizData.cafe_match ? `\n【氛圍對應】${quizData.cafe_match}` : '');
      } catch {
        promptText = `我剛完成了咖啡人格測驗，結果是「${rawQuizContext}」。`;
      }

      // 測驗結果不直接推薦：以隱藏訊息送出，讓 AI 先根據結果確認這次的實際需求，
      // 確認後的偏好再交由狀態機決定何時推薦
      setNormalizedCurrentChat(EMPTY_CHAT);
      setTimeout(() => {
        executeChatStream(promptText, {
          customTitle: '測驗結果諮詢',
          hiddenPrompt: true,
          isQuizResult: true,
        });
      }, 0);
      return;
    }

    // 存檔後的網址同步（/chat → /chat?id=X）：還是同一個對話，
    // 不重新載入、也不重置偏好掌握度
    if (urlId && currentChatRef.current?.id && String(currentChatRef.current.id) === String(urlId)) {
      return;
    }

    // 正常載入對話：偏好掌握度重新起算
    resetProgress(0);
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

  // 「直接推薦」：跳過確認需求，立刻以目前掌握的偏好推薦
  const handleForceRecommend = () => {
    if (isTyping) return;
    executeChatStream('請直接根據目前的資訊推薦咖啡廳', {
      customTitle: '直接推薦',
      forceRecommend: true,
    });
  };

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
                onQuickReply={(text) => executeChatStream(text)}
              />
            ))
          )}
        </div>

        {currentChat.messages && currentChat.messages.length > 0 && (
          <div className="pref-progress-strip">
            <div className="pref-progress-main">
              <div className="pref-progress-labels">
                <span className="pref-progress-percent">偏好掌握度 {progressPercent}%</span>
                <span className="pref-progress-hint">越接近 100%，推薦結果越準確</span>
              </div>
              <div className="pref-progress-track" role="progressbar" aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100} aria-label="偏好掌握度">
                <div className="pref-progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
            <button
              className="pref-recommend-btn"
              onClick={handleForceRecommend}
              disabled={isTyping}
            >
              直接推薦咖啡廳
            </button>
          </div>
        )}

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
    </>
  );
}
