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

export function useChatLogic(user, navigate) {
  const [currentChat, setCurrentChat] = useState(EMPTY_CHAT);
  const [isTyping, setIsTyping] = useState(false);
  const abortControllerRef = useRef(null);
  const currentChatRef = useRef(currentChat);

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
    const { customTitle = null, hiddenPrompt = false, isQuizResult = false, replaceMsgIdx = null, situationalContext = null } = options;
    if (isTyping) return;
    if (!situationalContext && !messageText.trim()) return;
    // 情境提交沒有使用者輸入文字，也視為隱藏 prompt（不顯示 user 泡泡）
    const isHidden = hiddenPrompt || !!situationalContext;
    
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
        content: m.content
      }));
    }

    try {
      const response = await chatService.streamChat({
        message: messageText,
        history: historyToSend,
        use_rag: true,
        is_quiz_result: isQuizResult,
        situational_context: situationalContext || undefined
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

      const processParsed = async (parsed) => {
        if (parsed.status) {
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
    EMPTY_CHAT
  };
}
