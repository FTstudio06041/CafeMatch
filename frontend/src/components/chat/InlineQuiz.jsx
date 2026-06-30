import { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from '../../context/AuthContext';
import { X, Check } from 'lucide-react';
import { logger } from '../../utils/logger';
import './InlineQuiz.css';

export default function InlineQuiz({ onComplete, onCancel }) {
  const { API_BASE_URL } = useContext(AuthContext);

  const [quizState, setQuizState] = useState('loading'); // 'loading', 'question', 'submitting', 'error'
  const [questions, setQuestions] = useState([]);               
  const [currentStep, setCurrentStep] = useState(0);            
  const [selectedAnswers, setSelectedAnswers] = useState({});   
  const [errorMsg, setErrorMsg] = useState('');                 

  // 初始化直接抓取題目
  useEffect(() => {
    let isMounted = true;
    const fetchQuestions = async () => {
      setQuizState('loading');
      setErrorMsg('');
      try {
        const res = await fetch(`${API_BASE_URL}/api/quiz/questions`, {
          credentials: 'include',
        });
        if (!res.ok) throw new Error(`伺服器回應錯誤 (${res.status})`);
        const data = await res.json();
        if (!data.questions || data.questions.length === 0) {
          throw new Error('未取得任何題目');
        }
        const sorted = [...data.questions].sort((a, b) => a.order - b.order);
        if (isMounted) {
          setQuestions(sorted);
          setCurrentStep(0);
          setSelectedAnswers({});
          setQuizState('question');
        }
      } catch (err) {
        logger.error('取得題目失敗：', err);
        if (isMounted) {
          setErrorMsg(err.message || '無法取得題目，請稍後再試');
          setQuizState('error');
        }
      }
    };
    fetchQuestions();
    return () => { isMounted = false; };
  }, [API_BASE_URL]);

  const submitAnswers = useCallback(async () => {
    setQuizState('submitting');
    setErrorMsg('');
    try {
      const answers = [];
      const filters = [];

      questions.forEach((q) => {
        const ans = selectedAnswers[q.id];
        if (q.is_multiple) {
          if (Array.isArray(ans)) filters.push(...ans);
        } else {
          if (ans !== undefined && ans !== null) answers.push(ans);
        }
      });

      const res = await fetch(`${API_BASE_URL}/api/quiz/submit`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers, filters }),
      });

      if (!res.ok) throw new Error(`提交失敗 (${res.status})`);
      const data = await res.json();
      
      // 直接把結果傳回給外層，不要停留在結果頁
      if (onComplete) {
        onComplete({
          title: data.result?.title || '',
          profile: data.result?.profile || '',
          cafe_match: data.result?.cafe_match || '',
          scores: data.scores || {},
        });
      }
    } catch (err) {
      logger.error('提交答案失敗：', err);
      setErrorMsg(err.message || '提交失敗，請稍後再試');
      setQuizState('error');
    }
  }, [API_BASE_URL, questions, selectedAnswers, onComplete]);

  const handleSingleSelect = (questionId, optionId) => {
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    
    // 稍微延遲自動下一題，讓使用者看到選中效果
    setTimeout(() => {
      if (currentStep + 1 < questions.length) {
        setCurrentStep((prev) => prev + 1);
      } else {
        submitAnswers();
      }
    }, 250);
  };

  const handleMultiToggle = (questionId, optionId) => {
    setSelectedAnswers((prev) => {
      const current = prev[questionId] || [];
      if (current.includes(optionId)) {
        return { ...prev, [questionId]: current.filter((id) => id !== optionId) };
      }
      if (current.length >= 3) return prev;
      return { ...prev, [questionId]: [...current, optionId] };
    });
  };

  const totalQuestions = questions.length;
  const currentQ = questions[currentStep];

  return (
    <div className="inline-quiz-container">
      {onCancel && quizState !== 'submitting' && (
        <button className="inline-quiz-close-btn" onClick={onCancel}>
          <X size={18} />
        </button>
      )}

      {/* 載入中狀態 */}
      {(quizState === 'loading' || quizState === 'submitting') && (
        <div className="inline-quiz-status">
          <div>
            {quizState === 'loading' ? '準備題目中...' : '正在將結果傳送給 AI...'}
          </div>
        </div>
      )}

      {/* 錯誤狀態 */}
      {quizState === 'error' && (
        <div className="inline-quiz-status">
          <p className="inline-quiz-error-msg">{errorMsg}</p>
          <button className="inline-quiz-cancel-btn" onClick={onCancel}>
            取消測驗
          </button>
        </div>
      )}

      {/* 答題狀態 */}
      {quizState === 'question' && currentQ && (
        <div className="inline-quiz-content">
          <div className="inline-quiz-step">
            問題 {currentStep + 1} <span>/ {totalQuestions}</span>
          </div>
          <div className="inline-quiz-question-text">
            {currentQ.question_text}
          </div>

          <div className="inline-quiz-options">
            {currentQ.options.map((opt) => {
              const isChecked = currentQ.is_multiple 
                ? (selectedAnswers[currentQ.id] || []).includes(opt.id)
                : selectedAnswers[currentQ.id] === opt.id;

              return (
                <div 
                  key={opt.id} 
                  className={`inline-quiz-option ${isChecked ? 'selected' : ''}`}
                  onClick={() => currentQ.is_multiple ? handleMultiToggle(currentQ.id, opt.id) : handleSingleSelect(currentQ.id, opt.id)}
                >
                  <div className="inline-quiz-option-text">{opt.text}</div>
                  {currentQ.is_multiple && isChecked && <Check size={18} color="var(--bg-main)" />}
                </div>
              );
            })}
          </div>

          {currentQ.is_multiple && (
            <button 
              className="inline-quiz-submit-btn"
              onClick={() => {
                if (currentStep + 1 < questions.length) {
                  setCurrentStep(prev => prev + 1);
                } else {
                  submitAnswers();
                }
              }}
            >
              {currentStep + 1 < questions.length ? '下一題' : '完成測驗'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
