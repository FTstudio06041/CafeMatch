import { useState, useRef, useCallback } from 'react';
import { chatService } from '../services/chatService';
import { API_BASE_URL } from '../utils/apiClient';
import { logger } from '../utils/logger';
import { toast } from '../utils/toast';

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

export const normalizeChatSession = (chat) => ({
  ...EMPTY_CHAT,
  ...chat,
  title: chat?.title || EMPTY_CHAT.title,
  messages: Array.isArray(chat?.messages) ? chat.messages.map(normalizeMessage) : []
});

const DEFAULT_PREF_TARGET = 3; // 後端未回報時的預設目標維度數

export function useChatLogic(user, navigate) {
  const [currentChat, setCurrentChat] = useState(EMPTY_CHAT);
  const [isTyping, setIsTyping] = useState(false);
  // 偏好掌握度：
  //   base   = 起始值（做完心理測驗進場為 50，一般對話為 0）
  //   dims   = 已掌握的偏好維度數（只增不減）
  //   target = 這次打算問到幾維（後端依測驗信任度決定）
  // 分母用 target 而不是固定 5：狀態機本來就不會問滿五題，
  // 固定除以 5 會讓 100% 永遠達不到。
  const [chatProgress, setChatProgress] = useState({
    base: 0, dims: 0, target: DEFAULT_PREF_TARGET,
  });
  // 推薦門檻：掌握的維度太少時，推薦等於亂猜（後端實測不同需求會拿到幾乎一樣的結果），
  // 所以後端會擋下推薦改成再問一題，前端同步把按鈕鎖起來並說明還差多少。
  const [recommendGate, setRecommendGate] = useState({
    ready: false, needs: Math.ceil(DEFAULT_PREF_TARGET / 2),
  });
  const abortControllerRef = useRef(null);
  const currentChatRef = useRef(currentChat);

  const progressPercent = Math.min(
    100,
    Math.round(
      chatProgress.base +
      chatProgress.dims * ((100 - chatProgress.base) / Math.max(1, chatProgress.target))
    )
  );

  const resetProgress = useCallback((base = 0, dims = 0, target = DEFAULT_PREF_TARGET) => {
    const safeTarget = target || DEFAULT_PREF_TARGET;
    setChatProgress({ base, dims, target: safeTarget });
    const needs = Math.max(1, Math.ceil(safeTarget / 2));
    setRecommendGate({ ready: dims >= needs, needs });
  }, []);

  const setNormalizedCurrentChat = useCallback((updater) => {
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
  }, []);

  const saveSessionToBackend = useCallback(async (chatState) => {
    if (user?.isGuest) return;
    try {
      const normalizedChat = normalizeChatSession(chatState);
      const payload = {
        title: normalizedChat.title,
        messages: normalizedChat.messages,
        pref_state: normalizedChat.pref_state || undefined
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
        if (!normalizedChat.id) {
          setNormalizedCurrentChat(prev => ({ ...prev, id: newId }));
          navigate(`/chat?id=${newId}`, { replace: true });
        }
        window.dispatchEvent(new Event('chat-updated'));
      }
    } catch (e) {
      logger.error('Failed to save session:', e);
    }
  }, [user?.isGuest, navigate]);

  const executeChatStream = useCallback(async (messageText, options = {}) => {
    const { customTitle = null, hiddenPrompt = false, isQuizResult = false, replaceMsgIdx = null, forceRecommend = false } = options;
    if (isTyping) return;
    if (!messageText.trim()) return;
    const isHidden = hiddenPrompt;

    // 心理測驗結果進場：偏好掌握度從 50% 起跳
    if (isQuizResult) {
      setChatProgress({ base: 50, dims: 0 });
    }
    
    setIsTyping(true);
    
    let chatTitle = currentChatRef.current.title;
    if (chatTitle === '新對話') {
      chatTitle = customTitle || messageText.substring(0, 10) + '...';
    }

    let nextMessages = [...currentChatRef.current.messages];
    if (replaceMsgIdx !== null && replaceMsgIdx >= 0 && replaceMsgIdx < nextMessages.length) {
      nextMessages = nextMessages.slice(0, replaceMsgIdx);
    }

    if (!isHidden) {
      nextMessages.push({ role: 'user', content: messageText });
    }
    nextMessages.push({ role: 'ai', content: '', debug_info: null, status: null });

    const chatWithPendingAi = normalizeChatSession({
      ...currentChatRef.current,
      // 測驗流程進場：把 50% 起始值記進對話狀態，重開對話也能還原
      ...(isQuizResult
        ? { pref_state: { ...(currentChatRef.current.pref_state || {}), progress_base: 50 } }
        : {}),
      title: chatTitle,
      messages: nextMessages
    });
    setNormalizedCurrentChat(chatWithPendingAi);

    abortControllerRef.current = new AbortController();
    let currentAiContent = "";
    let currentDebugInfo = null;
    let currentStatus = null;
    let currentCafes = null;

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
          status: currentStatus || last.status,
          cafes: currentCafes || last.cafes
        };
      }

      const finalChat = normalizeChatSession({ ...baseChat, messages: msgs });
      setNormalizedCurrentChat(finalChat);

      if (isFinal && finalChat) {
         await saveSessionToBackend(finalChat);
      }
    };

    let historyToSend = [];
    const excludeCount = isHidden ? 1 : 2;
    if (nextMessages.length >= excludeCount) {
      const prevMsgs = nextMessages.slice(0, -excludeCount);
      historyToSend = prevMsgs.slice(-6).map(m => ({
        role: m.role,
        // 附有推薦卡片的 AI 訊息加上標記，讓後端狀態機知道「已經推薦過」
        content: (m.role === 'ai' && Array.isArray(m.cafes) && m.cafes.length > 0)
          ? `${m.content}\n[已推薦店家卡片]`
          : m.content
      }));
    }

    try {
      // 「直接推薦」時附上最近一次心理測驗五維分數，作為 GNN 推薦的基礎向量；
      // 並收集本對話已推薦過的店家 id，讓「換一批」真的換一批
      let quizScores;
      let excludeCafeIds;
      // 測驗結果進場那輪也帶上分數，後端終端除錯輸出才看得到原始五維
      if (forceRecommend || isQuizResult) {
        try {
          quizScores = JSON.parse(localStorage.getItem('latestQuizScores') || 'null') || undefined;
        } catch {
          quizScores = undefined;
        }
      }
      // 本對話已出現過的店家 id：按鈕推薦時用來「換一批」，
      // 平常則讓後端在推薦後追問時能拿資料回答（地址、價位等）
      {
        const seen = new Set();
        for (const m of currentChatRef.current.messages || []) {
          for (const c of m.cafes || []) {
            if (c && c.id != null) seen.add(c.id);
          }
        }
        excludeCafeIds = seen.size > 0 ? [...seen] : undefined;
      }

      const response = await chatService.streamChat({
        message: messageText,
        history: historyToSend,
        use_rag: true,
        is_quiz_result: isQuizResult,
        force_recommend: forceRecommend,
        quiz_scores: quizScores,
        exclude_cafe_ids: excludeCafeIds,
        // 帶回累積偏好，後端會與本輪萃取合併（長對話不失憶）
        pref_state: currentChatRef.current.pref_state || undefined
      }, abortControllerRef.current.signal);

      if (response.status === 429) {
        const rateLimitMsg = '請求過於頻繁，請稍候片刻再試 🙏';
        toast.error(rateLimitMsg);
        await syncStreamState(rateLimitMsg, currentDebugInfo, '', true, currentStatus);
        return;
      }
      if (!response.ok) throw new Error('Network response was not ok');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let ndjsonBuffer = '';

      // 本次串流回報的進度基準與目標，供後續 pref_state 一併存進對話
      let streamTarget = null;
      let streamBase = null;

      const processParsed = async (parsed) => {
        if (parsed.progress_dims !== undefined) {
          // 基準值與目標值都由後端決定：
          //   有測驗 → base 50、目標 3~5 維（看使用者說測驗準不準）
          //   沒測驗 → base 0、目標 5 維（系統對他一無所知，要問滿）
          if (parsed.progress_target) streamTarget = parsed.progress_target;
          if (parsed.progress_base !== undefined) streamBase = parsed.progress_base;
          setChatProgress((prev) => ({
            base: parsed.progress_base !== undefined ? parsed.progress_base : prev.base,
            dims: Math.max(prev.dims, parsed.progress_dims),
            target: parsed.progress_target || prev.target,
          }));
          if (parsed.recommend_ready !== undefined) {
            setRecommendGate((prev) => ({
              ready: parsed.recommend_ready,
              needs: parsed.recommend_needs || prev.needs,
            }));
          }
        } else if (parsed.pref_state) {
          // 後端合併後的累積偏好：掛在對話物件上，隨對話儲存、重開可還原
          setNormalizedCurrentChat((prev) => ({
            ...prev,
            pref_state: {
              ...(prev.pref_state || {}),
              ...(streamTarget ? { progress_target: streamTarget } : {}),
              ...(streamBase !== null ? { progress_base: streamBase } : {}),
              preferences: parsed.pref_state.preferences || {}
            }
          }));
        } else if (parsed.status) {
          await syncStreamState(currentAiContent, currentDebugInfo, '', false, parsed.status);
        } else if (parsed.debug_info || parsed.type === 'debug_info') {
          currentDebugInfo = parsed.debug_info || parsed;
          await syncStreamState(currentAiContent, currentDebugInfo, '', false, currentStatus);
        } else if (parsed.cafes) {
          currentCafes = parsed.cafes;
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
          ndjsonBuffer = lines.pop(); 

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
  }, [isTyping, saveSessionToBackend, setNormalizedCurrentChat]);

  const handleFeedback = useCallback(async (msgIdx, type) => {
    try {
      const newMsgs = [...currentChatRef.current.messages];
      if (!newMsgs[msgIdx]) return;
      
      const payload = {
        session_id: currentChatRef.current.id,
        message_idx: msgIdx,
        user_message: newMsgs[msgIdx - 1]?.content || '',
        ai_response: newMsgs[msgIdx].content,
        feedback_type: type
      };
      
      await fetch(`${API_BASE_URL}/api/chat/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      
      newMsgs[msgIdx] = { ...newMsgs[msgIdx], feedback: type };
      const updatedChat = { ...currentChatRef.current, messages: newMsgs };

      setNormalizedCurrentChat(updatedChat);
      saveSessionToBackend(updatedChat);
    } catch (e) {
      logger.error("Feedback failed:", e);
    }
  }, [saveSessionToBackend, setNormalizedCurrentChat]);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsTyping(false);
  }, []);

  return {
    currentChat,
    setNormalizedCurrentChat,
    isTyping,
    executeChatStream,
    handleFeedback,
    handleStop,
    currentChatRef,
    EMPTY_CHAT,
    progressPercent,
    resetProgress,
    recommendGate,
    chatProgress
  };
}
