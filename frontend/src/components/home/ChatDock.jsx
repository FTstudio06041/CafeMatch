import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronUp, Coffee, MapPinned, MoreVertical, Plus, Send, Sparkles, Square, X } from 'lucide-react';
import { AuthContext } from '../../context/AuthContext';
import { useChat } from '../../context/ChatContext';
import { CHAT_UI_TEXTS } from '../../utils/constants';
import MessageBubble from '../MessageBubble';
import './ChatDock.css';

// 第一次來的人不知道可以問什麼：給幾個點了就送出的例子
const EXAMPLE_PROMPTS = ['想找安靜、能讀書的店', '週末下午想吃甜點', '可以帶寵物的咖啡廳', '晚上還有開的店'];

/** 輸入框：桌機在對話欄底部，手機在對話全螢幕面板底部（以及收合時的浮動列） */
export function ChatComposer({ onSent, onFocus, isDebugMode, setIsDebugMode, autoFocus = false, trailing = null }) {
  const { user } = useContext(AuthContext);
  const { isTyping, executeChatStream, handleStop } = useChat();
  const [input, setInput] = useState('');
  const [showOptions, setShowOptions] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus({ preventScroll: true });
  }, [autoFocus]);

  const send = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || isTyping) return;
    setInput('');
    onSent?.();
    executeChatStream(text);
  };

  return (
    <form className="chat-composer" onSubmit={send}>
      {user?.is_admin && setIsDebugMode && (
        <div className="chat-composer-options">
          <button
            type="button"
            className="icon-btn"
            onClick={() => setShowOptions((v) => !v)}
            aria-label="選項"
            aria-expanded={showOptions}
          >
            <MoreVertical size={20} />
          </button>
          {showOptions && (
            <div className="options-menu">
              <button
                type="button"
                className="options-menu-item"
                onClick={() => { setIsDebugMode(!isDebugMode); setShowOptions(false); }}
              >
                {isDebugMode ? CHAT_UI_TEXTS.disableDebug : CHAT_UI_TEXTS.enableDebug}
              </button>
            </div>
          )}
        </div>
      )}
      <label htmlFor="home-chat-input" className="sr-only">與 AI 對話</label>
      <input
        ref={inputRef}
        id="home-chat-input"
        type="text"
        className="chat-composer-input"
        placeholder={isTyping ? CHAT_UI_TEXTS.typingPlaceholder : '在這邊輸入文字與 AI 對話'}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onFocus={onFocus}
        disabled={isTyping}
        autoComplete="off"
      />
      {trailing}
      {isTyping ? (
        <button type="button" className="chat-composer-send stop" onClick={handleStop} aria-label="停止生成">
          <Square size={15} fill="currentColor" />
        </button>
      ) : (
        <button type="submit" className="chat-composer-send" disabled={!input.trim()} aria-label="送出訊息">
          <Send size={18} />
        </button>
      )}
    </form>
  );
}

function ChatWelcome({ onPick }) {
  return (
    <div className="chat-welcome">
      <span className="chat-welcome-icon" aria-hidden="true"><Coffee size={30} strokeWidth={2.2} /></span>
      <h2 className="chat-welcome-title">歡迎來到啡你莫屬</h2>
      <p className="chat-welcome-text">告訴我你想找什麼樣的咖啡廳，推薦的店會直接標在地圖上。</p>
      <div className="chat-welcome-prompts">
        {EXAMPLE_PROMPTS.map((p) => (
          <button key={p} type="button" className="chat-welcome-prompt" onClick={() => onPick(p)}>{p}</button>
        ))}
      </div>
    </div>
  );
}

/** 點開店家時，AI 主動問要不要介紹這家店（草圖第三版） */
function IntroOffer({ cafe, disabled, onAccept, onDecline }) {
  return (
    <div className="chat-offer" role="group" aria-label={`要不要請 AI 介紹${cafe.name}`}>
      <p className="chat-offer-text">
        <Sparkles size={16} aria-hidden="true" /> 你正在看「{cafe.name}」，要我幫你介紹一下嗎？
      </p>
      <div className="chat-offer-actions">
        <button type="button" className="chat-offer-yes" onClick={onAccept} disabled={disabled}>好，介紹一下</button>
        <button type="button" className="chat-offer-no" onClick={onDecline}>不用了</button>
      </div>
    </div>
  );
}

/**
 * AI 對話面板。
 *   variant="docked"  桌機：首頁左欄，一直開著（草圖第二版）
 *   variant="sheet"   手機／平板：全螢幕面板，可以關掉回首頁看地圖
 */
export function ChatPanel({
  variant = 'docked', onClose, onSelectCafe, recommendedCount, isDebugMode, setIsDebugMode,
  introCafe = null, onIntro, onDismissIntro,
}) {
  const { user } = useContext(AuthContext);
  const {
    currentChat, setNormalizedCurrentChat, currentChatRef, isTyping, executeChatStream,
    handleFeedback, progressPercent, recommendGate, chatProgress, newChat,
  } = useChat();
  const listRef = useRef(null);
  const messages = useMemo(() => currentChat.messages || [], [currentChat.messages]);
  const hasMessages = messages.length > 0;
  const isSheet = variant === 'sheet';

  // 新訊息、串流進來、或出現介紹邀請時捲到底
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isTyping, introCafe?.id]);

  const handleRetry = (msgIdx) => {
    if (isTyping || msgIdx <= 0) return;
    const prevUserMsg = messages[msgIdx - 1];
    if (!prevUserMsg || prevUserMsg.role !== 'user') return;
    setNormalizedCurrentChat({ ...currentChatRef.current, messages: messages.slice(0, msgIdx - 1) });
    executeChatStream(prevUserMsg.content);
  };

  // 還差幾項需求才允許推薦（資料太少就推薦等於亂猜，按鈕在此之前鎖住）
  const missingDims = Math.max(0, recommendGate.needs - chatProgress.dims);
  const canRecommend = recommendGate.ready || missingDims === 0;
  const forceRecommend = () => {
    if (isTyping || !canRecommend) return;
    executeChatStream('請直接根據目前的資訊推薦咖啡廳', { customTitle: '直接推薦', forceRecommend: true });
  };

  const title = hasMessages && currentChat.title && currentChat.title !== '新對話' ? currentChat.title : 'AI 咖啡顧問';

  return (
    <section className={`chat-panel ${variant}`} aria-label="AI 對話">
      <header className="chat-panel-head">
        <h2 className="chat-panel-title" title={title}>{title}</h2>
        {hasMessages && (
          <button type="button" className="chat-panel-btn" onClick={newChat} disabled={isTyping}>
            <Plus size={16} aria-hidden="true" /> 新對話
          </button>
        )}
        {isSheet && (
          <button type="button" className="icon-btn" onClick={onClose} aria-label="關閉對話">
            <X size={22} />
          </button>
        )}
      </header>

      <div className="chat-panel-messages" ref={listRef} aria-live="polite">
        {hasMessages && messages.map((msg, idx) => (
          <MessageBubble
            key={idx}
            msg={msg}
            idx={idx}
            isTyping={isTyping}
            isLastMessage={idx === messages.length - 1}
            handleRetry={handleRetry}
            handleFeedback={handleFeedback}
            isDebugMode={isDebugMode}
            onQuickReply={(text) => executeChatStream(text)}
            onSelectCafe={onSelectCafe}
          />
        ))}
        {!hasMessages && !introCafe && <ChatWelcome onPick={(text) => executeChatStream(text)} />}
        {introCafe && (
          <IntroOffer
            cafe={introCafe}
            disabled={isTyping}
            onAccept={() => onIntro(introCafe)}
            onDecline={() => onDismissIntro(introCafe.id)}
          />
        )}
      </div>

      <div className="chat-panel-foot">
        {isSheet && recommendedCount > 0 && !isTyping && (
          <button type="button" className="chat-see-results" onClick={onClose}>
            <MapPinned size={16} aria-hidden="true" /> 在地圖上看推薦的 {recommendedCount} 家
          </button>
        )}
        {hasMessages && (
          <div className="pref-progress-strip">
            <div className="pref-progress-main">
              <div className="pref-progress-labels">
                <span className="pref-progress-percent">偏好掌握度 {progressPercent}%</span>
                <span className="pref-progress-hint">越高推薦越準</span>
              </div>
              <div className="pref-progress-track" role="progressbar" aria-valuenow={progressPercent} aria-valuemin={0} aria-valuemax={100} aria-label="偏好掌握度">
                <div className="pref-progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
            <button
              type="button"
              className="pref-recommend-btn"
              onClick={forceRecommend}
              disabled={isTyping || !canRecommend}
              title={canRecommend ? '以目前掌握的偏好推薦咖啡廳' : `還不夠了解你的需求，再確認 ${missingDims} 項就能推薦`}
            >
              {canRecommend ? '直接推薦' : `再確認 ${missingDims} 項`}
            </button>
          </div>
        )}
        <ChatComposer isDebugMode={isDebugMode} setIsDebugMode={setIsDebugMode} autoFocus={isSheet} />
        <p className="chat-panel-disclaimer">
          {user ? CHAT_UI_TEXTS.disclaimer : '登入後對話會自動保存；AI 內容可能有誤，請斟酌參考。'}
        </p>
      </div>
    </section>
  );
}

/** 手機／平板收合時浮在底部的輸入列：送出或點展開就打開全螢幕對話 */
export function ChatBar({ onOpen, hasConversation, introCafe = null, onIntro }) {
  const { isTyping } = useChat();
  return (
    <div className="chat-bar-wrap">
      {introCafe && (
        <button type="button" className="chat-bar-intro" onClick={() => onIntro(introCafe)} disabled={isTyping}>
          <Sparkles size={15} aria-hidden="true" /> 請 AI 介紹「{introCafe.name}」
        </button>
      )}
      <ChatComposer
        onSent={onOpen}
        onFocus={() => { if (hasConversation) onOpen(); }}
        trailing={hasConversation ? (
          <button type="button" className="icon-btn chat-bar-expand" onClick={onOpen} aria-label="展開對話">
            <ChevronUp size={22} />
          </button>
        ) : null}
      />
    </div>
  );
}
