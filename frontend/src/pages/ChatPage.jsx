import { useState, useEffect, useContext, useRef, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';

import '../ChatPage.css';
import MessageBubble from '../components/MessageBubble';
import ChatInputArea from '../components/chat/ChatInputArea';
import WelcomeModal from '../components/chat/WelcomeModal';

import { toast } from '../utils/toast';
import { logger } from '../utils/logger';
const EMPTY_CHAT = { id: null, title: '新對話', messages: [] };

const normalizeMessage = (msg) => {
  if (!msg || typeof msg !== 'object') {
    return { role: 'ai', content: String(msg ?? '') };
  }

  const roleSource = msg.role || msg.sender;
  const role = roleSource === 'user' ? 'user' : 'ai';
  const rawContent = msg.content ?? msg.text ?? '';

  return {
    ...msg,
    role,
    content: typeof rawContent === 'string' ? rawContent : String(rawContent ?? '')
  };
};

const normalizeChatSession = (chat) => ({
  ...EMPTY_CHAT,
  ...chat,
  title: chat?.title || EMPTY_CHAT.title,
  messages: Array.isArray(chat?.messages) ? chat.messages.map(normalizeMessage) : []
});

export default function ChatPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();

  // 狀態管理
  const [currentChat, setCurrentChat] = useState(EMPTY_CHAT);
  const [inputMsg, setInputMsg] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);
  const [isDebugMode, setIsDebugMode] = useState(false);
  const [showOptionsMenu, setShowOptionsMenu] = useState(false);
  
  const chatWindowRef = useRef(null);
  const abortControllerRef = useRef(null);
  const currentChatRef = useRef(currentChat);

  const setNormalizedCurrentChat = (updater) => {
    if (typeof updater !== 'function') {
      const normalized = normalizeChatSession(updater);
      currentChatRef.current = normalized;
      setCurrentChat(normalized);
      return normalized;
    }

    setCurrentChat(prev => {
      const nextValue = updater(prev);
      const normalized = normalizeChatSession(nextValue);
      currentChatRef.current = normalized;
      return normalized;
    });
  };

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

  // ==========================================
  // 保存對話到後端
  // ==========================================
  const saveSessionToBackend = useCallback(async (chatState) => {
    if (user?.isGuest) return;
    try {
      const normalizedChat = normalizeChatSession(chatState);
      const payload = {
        title: normalizedChat.title,
        messages: normalizedChat.messages
      };
      if (normalizedChat.id) {
        payload.id = normalizedChat.id;
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
        if (!normalizedChat.id) {
          setNormalizedCurrentChat(prev => ({ ...prev, id: newId }));
          navigate(`/chat?id=${newId}`, { replace: true });
        }
        window.dispatchEvent(new Event('chat-updated')); // 觸發 Sidebar 更新
      }
    } catch (e) {
      logger.error('Failed to save session:', e);
    }
  }, [API_BASE_URL, user?.isGuest, navigate]);

  // ==========================================
  // 核心發送與串流邏輯
  // ==========================================
  const executeChatStream = useCallback(async (messageText, options = {}) => {
    const { customTitle = null, hiddenPrompt = false, isQuizResult = false, replaceMsgIdx = null } = options;
    if (!messageText.trim() || isTyping) return;
    
    setIsTyping(true);
    setInputMsg('');
    
    let chatTitle = currentChatRef.current.title;
    if (chatTitle === '新對話') {
      chatTitle = customTitle || messageText.substring(0, 10) + '...';
    }

    let nextMessages = [...currentChatRef.current.messages];

    if (replaceMsgIdx !== null && replaceMsgIdx >= 0 && replaceMsgIdx < nextMessages.length) {
      nextMessages = nextMessages.slice(0, replaceMsgIdx);
    }

    if (!hiddenPrompt) {
      nextMessages.push({ role: 'user', content: messageText });
    }
    nextMessages.push({ role: 'ai', content: '', debug_info: null, status: null });

    // 更新 state
    const chatWithPendingAi = normalizeChatSession({
      ...currentChatRef.current,
      title: chatTitle,
      messages: nextMessages
    });
    currentChatRef.current = chatWithPendingAi;
    setCurrentChat(chatWithPendingAi);

    abortControllerRef.current = new AbortController();
    let currentAiContent = "";
    let currentDebugInfo = null;
    let currentStatus = null;

    // 內部輔助函式：同步狀態，最後一次寫入後端
    const syncStreamState = async (content, debugInfo, appendText = '', isFinal = false, status = null) => {
      if (status) currentStatus = status;
      const finalContent = content + appendText;
      const baseChat = currentChatRef.current;
      const msgs = [...baseChat.messages];
      const last = msgs[msgs.length - 1];

      if (last && last.role === 'ai') {
        msgs[msgs.length - 1] = {
          ...last,
          content: finalContent,
          debug_info: debugInfo ? { ...debugInfo } : last.debug_info,
          status: currentStatus || last.status
        };
      }

      const finalChat = normalizeChatSession({ ...baseChat, messages: msgs });
      currentChatRef.current = finalChat;
      setCurrentChat(finalChat);

      if (isFinal && finalChat) {
         await saveSessionToBackend(finalChat);
      }
    };

    // 準備歷史對話紀錄傳給後端 (只取最近 6 筆，排除剛才 push 的暫存訊息)
    let historyToSend = [];
    const excludeCount = hiddenPrompt ? 1 : 2;
    if (nextMessages.length >= excludeCount) {
      const prevMsgs = nextMessages.slice(0, -excludeCount);
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
          history: historyToSend,
          use_rag: true,
          is_quiz_result: isQuizResult
        }),
        signal: abortControllerRef.current.signal
      });

      if (!response.ok) throw new Error('Network response was not ok');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let ndjsonBuffer = '';

      const processParsed = async (parsed) => {
        if (parsed.status) {
          await syncStreamState(currentAiContent, currentDebugInfo, '', false, parsed.status);
        } else if (parsed.debug_info || parsed.type === 'debug_info') {
          currentDebugInfo = parsed.debug_info || parsed;
          await syncStreamState(currentAiContent, currentDebugInfo, '', false, currentStatus);
        } else if (parsed.content || parsed.response) {
          currentAiContent += (parsed.content || parsed.response);
          await syncStreamState(currentAiContent, currentDebugInfo, '', false, currentStatus);
        } else if (parsed.error) {
          toast.error(`錯誤：${parsed.error}`);
        }
        
        if (parsed.done) {
          await syncStreamState(currentAiContent, currentDebugInfo, '', true, currentStatus);
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          ndjsonBuffer += chunk;
          const lines = ndjsonBuffer.split('\n');
          ndjsonBuffer = lines.pop(); // keep the last potentially incomplete line

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const parsed = JSON.parse(line);
              await processParsed(parsed);
            } catch (e) {
              console.warn('Failed to parse NDJSON line:', line.substring(0, 50) + '...', e);
            }
          }
        }

        if (done) {
          if (ndjsonBuffer.trim()) {
            try {
              const parsed = JSON.parse(ndjsonBuffer);
              await processParsed(parsed);
            } catch (e) {
              console.warn('Failed to parse final NDJSON chunk:', ndjsonBuffer.substring(0, 50) + '...', e);
            }
          }
          break;
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        await syncStreamState(currentAiContent, currentDebugInfo, ' [已中斷]', true);
      } else {
        logger.error('Stream error:', error);
        toast.error('系統發生錯誤，請稍後再試。');
      }
    } finally {
      setIsTyping(false);
    }
  }, [API_BASE_URL, isTyping, saveSessionToBackend]);

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
      fetch(`${API_BASE_URL}/api/chat/sessions/${urlId}`, { credentials: 'include' })
        .then(res => res.json())
        .then(data => {
          if (data.id) {
            setNormalizedCurrentChat(data);
          } else {
            // 找不到對話，回到新對話
            navigate('/chat?id=new', { replace: true });
          }
        })
        .catch(err => logger.error('Failed to load session:', err));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search, API_BASE_URL, user?.isGuest, navigate]);



  // ==========================================
  // 反饋與重試邏輯
  // ==========================================
  const handleFeedback = async (msgIdx, type) => {
    if (user?.isGuest) {
      toast.info("訪客模式無法提供回饋，登入後就能完整體驗喔！");
      return;
    }
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
        const newMsgs = [...currentChatRef.current.messages];
        newMsgs[msgIdx] = { ...newMsgs[msgIdx], feedback: type };
        const updatedChat = { ...currentChatRef.current, messages: newMsgs };

        setNormalizedCurrentChat(updatedChat);
        saveSessionToBackend(updatedChat);
      }
    } catch (e) {
      logger.error("Feedback failed:", e);
    }
  };

  const handleRetry = (msgIdx) => {
    if (isTyping || msgIdx <= 0) return;
    
    // 取出重試之前的 user 訊息
    const prevUserMsg = currentChat.messages[msgIdx - 1];
    if (!prevUserMsg || prevUserMsg.role !== 'user') return;

    // 將包含該 AI 訊息以及其後的所有訊息刪除
    const newMessages = currentChat.messages.slice(0, msgIdx - 1);
    
    const retriedChat = normalizeChatSession({ ...currentChatRef.current, messages: newMessages });
    currentChatRef.current = retriedChat;
    setCurrentChat(retriedChat);
    
    // 重新發送
    executeChatStream(prevUserMsg.content);
  };

  const sendMessage = () => executeChatStream(inputMsg);

  const handleStop = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsTyping(false);
  };

  const handleQuizComplete = useCallback((quizData, msgIdx) => {
    const scoreParts = [];
    const scoreLabels = { work: '工作讀書', env: '空間氛圍', social: '社交舒適', taste: '餐飲口味', cp: 'CP值' };
    if (quizData.scores) {
      for (const [key, val] of Object.entries(quizData.scores)) {
        scoreParts.push(`${scoreLabels[key] || key}：${val}`);
      }
    }
    const promptText = `我剛完成了心理測驗，以下是我的結果：\n`
      + `\n【咖啡人格】${quizData.title}`
      + (quizData.profile ? `\n【特質側寫】${quizData.profile}` : '')
      + (scoreParts.length > 0 ? `\n【五維分數】${scoreParts.join('、')}` : '')
      + (quizData.cafe_match ? `\n【氛圍對應】${quizData.cafe_match}` : '')
      + `\n\n【任務】請用親切自然的語氣，先為我公佈並稍微分析一下我的咖啡人格與特質，接著再無縫地為我推薦適合的花蓮咖啡廳。`;
    
    setTimeout(() => {
      executeChatStream(promptText, { customTitle: '分析結果與推薦', hiddenPrompt: true, isQuizResult: true, replaceMsgIdx: msgIdx });
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
                handleRetry={handleRetry}
                handleFeedback={handleFeedback}
                isDebugMode={isDebugMode}
                onQuizComplete={handleQuizComplete}
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
