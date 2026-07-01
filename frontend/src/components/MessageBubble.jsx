import React from 'react';
import { useState, useEffect } from 'react';
import SituationalPicker from './chat/SituationalPicker';
import CafeCard from './chat/CafeCard';
import { THINKING_TEXTS } from '../utils/thinkingTexts';
import { CHAT_UI_TEXTS } from '../utils/constants';

export default function MessageBubble({ msg, idx, isTyping, isLastMessage, handleRetry, handleFeedback, isDebugMode, onSituationalComplete }) {
  const role = msg?.role === 'user' ? 'user' : 'ai';
  let content = msg?.content ?? msg?.text ?? '';
  let safeContent = typeof content === 'string' ? content : String(content ?? '');

  const [isQuizActive, setIsQuizActive] = useState(false);
  const [textIndex, setTextIndex] = useState(0);
  const [fade, setFade] = useState(true);

  const statusKey = msg?.status || 'default';
  const currentTexts = THINKING_TEXTS[statusKey] || THINKING_TEXTS.default;

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTextIndex(0);
    setFade(true);
  }, [statusKey]);

  useEffect(() => {
    if (role === 'ai' && safeContent === '') {
      const interval = setInterval(() => {
        setFade(false);
        setTimeout(() => {
          setTextIndex(prev => (prev + 1) % currentTexts.length);
          setFade(true);
        }, 400); // 讓文字有足夠時間淡出
      }, 3500); // 每 3.5 秒輪換一次文字

      return () => clearInterval(interval);
    }
  }, [role, safeContent, currentTexts.length]);

  const hasQuizCard = safeContent.includes('[SHOW_QUIZ_CARD]');
  if (hasQuizCard) {
    safeContent = safeContent.replace('[SHOW_QUIZ_CARD]', '').trim();
  }

  const isGenerating = isTyping && isLastMessage && role === 'ai' && safeContent === '' && !hasQuizCard;

  return (
    <React.Fragment>
      <div className={`message ${role}`}>
        {isGenerating ? (
          <div className="typing-indicator" style={{ margin: 0, padding: 0, background: 'transparent', display: 'flex', alignItems: 'center' }}>
            <span className={`thinking-text ${fade ? 'fade-in' : 'fade-out'}`}>
              {currentTexts[textIndex]}
            </span>
          </div>
        ) : (
          <>
            {safeContent && <div className="message-text">{safeContent}</div>}
            {!safeContent && role === 'ai' && !hasQuizCard && (
               <div className="message-text" style={{ color: '#aaa', fontStyle: 'italic' }}>生成中斷或無回應</div>
            )}
            {role === 'ai' && Array.isArray(msg?.cafes) && msg.cafes.length > 0 && (
              <div className="cafe-card-list">
                {msg.cafes.map((c) => <CafeCard key={c.id} cafe={c} />)}
              </div>
            )}
            {hasQuizCard && !isTyping && (
              <div className="quiz-container" style={{ marginTop: '10px' }}>
                {!isQuizActive ? (
                  <div className="quiz-invite-card">
                    <div className="quiz-invite-title">{CHAT_UI_TEXTS.quizTitle}</div>
                    <div className="quiz-invite-desc">{CHAT_UI_TEXTS.quizDesc}</div>
                    <button 
                      className="quiz-start-btn"
                      onClick={() => setIsQuizActive(true)} 
                    >
                      {CHAT_UI_TEXTS.startQuiz}
                    </button>
                  </div>
                ) : (
                  <SituationalPicker
                    onComplete={(situationalContext) => {
                      setIsQuizActive(false);
                      if(onSituationalComplete) onSituationalComplete(situationalContext, idx);
                    }}
                    onCancel={() => setIsQuizActive(false)}
                  />
                )}
              </div>
            )}
            {role === 'ai' && !isGenerating && (
              <div className="message-actions">
                <button 
                  className="action-btn retry" 
                  title={CHAT_UI_TEXTS.retryBtn}
                  onClick={() => handleRetry(idx)}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 2v6h-6"></path>
                    <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path>
                    <path d="M3 22v-6h6"></path>
                    <path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path>
                  </svg>
                </button>
                <button 
                  className={`action-btn like ${msg?.feedback === 'like' ? 'active' : ''}`}
                  title={CHAT_UI_TEXTS.likeBtn}
                  onClick={() => handleFeedback(idx, 'like')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                  </svg>
                </button>
                <button 
                  className={`action-btn dislike ${msg?.feedback === 'dislike' ? 'active' : ''}`}
                  title={CHAT_UI_TEXTS.dislikeBtn}
                  onClick={() => handleFeedback(idx, 'dislike')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </div>
      {isDebugMode && msg?.debug_info && (
        <div className="debug-console">
          <div className="debug-header">{CHAT_UI_TEXTS.debugConsole}</div>
          <div className="debug-content">
            <div><strong>{CHAT_UI_TEXTS.debugModel}</strong> {msg.debug_info.model}</div>
            <div><strong>{CHAT_UI_TEXTS.debugIntent}</strong> {msg.debug_info.is_cafe_related}</div>
            <div><strong>{CHAT_UI_TEXTS.debugSpeed}</strong> {msg.debug_info.tokens_per_sec} tokens/s ({msg.debug_info.eval_count} tokens in {msg.debug_info.eval_duration_ms} ms)</div>
            <div><strong>{CHAT_UI_TEXTS.debugTotalDuration}</strong> {msg.debug_info.total_duration_ms} ms</div>
            {msg.debug_info.rag_context && msg.debug_info.rag_context !== '(未注入資料庫資料)' && (
              <div className="debug-prompt"><strong>{CHAT_UI_TEXTS.debugRag}</strong><br/>{msg.debug_info.rag_context}</div>
            )}
            <div className="debug-prompt"><strong>{CHAT_UI_TEXTS.debugPrompt}</strong><br/>{msg.debug_info.prompt}</div>
          </div>
        </div>
      )}
    </React.Fragment>
  );
}
