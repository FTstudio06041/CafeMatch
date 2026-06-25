import { useState, useRef, useCallback } from 'react';
import { chatService } from '../services/chatService';
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
      
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/api/chat/sessions`, {
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
    const { customTitle = null, hiddenPrompt = false, isQuizResult = false, replaceMsgIdx = null } = options;
    if (!messageText.trim() || isTyping) return;
    
    setIsTyping(true);
    
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
      setNormalizedCurrentChat(finalChat);

      if (isFinal && finalChat) {
         await saveSessionToBackend(finalChat);
      }
    };

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
      const response = await chatService.streamChat({
        message: messageText,
        history: historyToSend,
        use_rag: true,
        is_quiz_result: isQuizResult
      }, abortControllerRef.current.signal);

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
  }, [isTyping, saveSessionToBackend]);

  const handleFeedback = async (msgIdx, type) => {
    if (user?.isGuest) {
      toast.info("訪客模式無法提供回饋，登入後就能完整體驗喔！");
      return;
    }
    const msg = currentChatRef.current.messages[msgIdx];
    const userMsg = currentChatRef.current.messages[msgIdx - 1]?.content || '';
    if (!msg) return;
    
    try {
      await chatService.submitFeedback({
        feedback_type: type,
        user_message: userMsg,
        ai_response: msg.content
      });
      const newMsgs = [...currentChatRef.current.messages];
      newMsgs[msgIdx] = { ...newMsgs[msgIdx], feedback: type };
      const updatedChat = { ...currentChatRef.current, messages: newMsgs };

      setNormalizedCurrentChat(updatedChat);
      saveSessionToBackend(updatedChat);
    } catch (e) {
      logger.error("Feedback failed:", e);
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) abortControllerRef.current.abort();
    setIsTyping(false);
  };

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
