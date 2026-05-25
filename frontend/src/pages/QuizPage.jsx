import React, { useState, useEffect, useContext, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { ClipboardList, BarChart3, MapPin, Play, Store } from 'lucide-react';
import RadarChart from '../components/RadarChart';
import MainLayout from '../layouts/MainLayout';
import '../QuizPage.css';

// sessionStorage key — 用來在頁面切換時保留測驗結果
const QUIZ_RESULT_CACHE_KEY = 'quizResultCache';

// =============================================
// QuizPage 主元件
// =============================================
export default function QuizPage() {
  const { user, API_BASE_URL, login } = useContext(AuthContext);
  const navigate = useNavigate();

  // --- 測驗核心狀態 ---
  const [quizState, setQuizState] = useState('intro');        // 'intro' | 'loading' | 'question' | 'submitting' | 'result'
  const [questions, setQuestions] = useState([]);               // 從 API 取得的題目陣列
  const [currentStep, setCurrentStep] = useState(0);            // 當前題目索引（0 起算）
  const [selectedAnswers, setSelectedAnswers] = useState({});   // {questionId: optionId} 或多選 {questionId: [optionId, ...]}
  const [quizResult, setQuizResult] = useState(null);           // 後端回傳的結果物件
  const [errorMsg, setErrorMsg] = useState('');                 // 錯誤訊息

  // 動畫過渡狀態
  const [isFading, setIsFading] = useState(false);
  const [selectedAnim, setSelectedAnim] = useState(null);       // 正在播放選中動畫的 optionId

  // 初始化：恢復測驗結果快取
  useEffect(() => {
    // 從 sessionStorage 恢復測驗結果（使用者切頁再回來時不會重置）
    const cached = sessionStorage.getItem(QUIZ_RESULT_CACHE_KEY);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        setQuizResult(parsed);
        setQuizState('result');
      } catch {
        sessionStorage.removeItem(QUIZ_RESULT_CACHE_KEY);
      }
    }
  }, []);

  // =============================================
  // API 呼叫
  // =============================================

  // 取得題目
  const fetchQuestions = useCallback(async () => {
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
      // 依照 order 排序（防禦性排序，即使後端已排序）
      const sorted = [...data.questions].sort((a, b) => a.order - b.order);
      setQuestions(sorted);
      setCurrentStep(0);
      setSelectedAnswers({});
      setQuizResult(null);
      setQuizState('question');
    } catch (err) {
      console.error('取得題目失敗：', err);
      setErrorMsg(err.message || '無法取得題目，請稍後再試');
      setQuizState('intro');
    }
  }, [API_BASE_URL]);

  // 提交答案
  const submitAnswers = useCallback(async () => {
    setQuizState('submitting');
    setErrorMsg('');
    try {
      // 將 selectedAnswers 分為一般答案和篩選條件
      const answers = [];
      const filters = [];

      questions.forEach((q) => {
        const ans = selectedAnswers[q.id];
        if (q.is_multiple) {
          // Q9 多選：放入 filters
          if (Array.isArray(ans)) filters.push(...ans);
        } else {
          // 單選：放入 answers
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
      setQuizResult(data);
      setQuizState('result');

      // 持久化到 sessionStorage，頁面切換後仍能顯示結果
      sessionStorage.setItem(QUIZ_RESULT_CACHE_KEY, JSON.stringify(data));
    } catch (err) {
      console.error('提交答案失敗：', err);
      setErrorMsg(err.message || '提交失敗，請稍後再試');
      setQuizState('question');
    }
  }, [API_BASE_URL, questions, selectedAnswers]);

  // =============================================
  // 事件處理
  // =============================================

  // 開始測驗（從介紹頁進入）
  const handleStart = () => {
    // 清除舊的快取，準備全新測驗
    sessionStorage.removeItem(QUIZ_RESULT_CACHE_KEY);
    fetchQuestions();
  };

  // 單選：選擇後短暫動畫，然後切換下一題
  const handleSingleSelect = (questionId, optionId) => {
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    setSelectedAnim(optionId);

    // 短暫選中動畫，然後切換
    setTimeout(() => {
      setSelectedAnim(null);
      if (currentStep + 1 < questions.length) {
        // 淡出後切換題目
        setIsFading(true);
        setTimeout(() => {
          setCurrentStep((prev) => prev + 1);
          setIsFading(false);
        }, 250);
      }
      // 若是最後一題且為單選，不自動提交（等待多選題完成）
    }, 400);
  };

  // 多選：切換 checkbox（最多 3 個）
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

  // 再測一次：重置所有狀態並清除快取
  const handleRetry = () => {
    setQuizState('intro');
    setQuestions([]);
    setCurrentStep(0);
    setSelectedAnswers({});
    setQuizResult(null);
    setErrorMsg('');
    sessionStorage.removeItem(QUIZ_RESULT_CACHE_KEY);
  };

  // 帶著結果去諮詢 AI
  const handleConsultAI = () => {
    if (user?.isGuest) {
      alert("請先登入才能將測驗結果帶去詢問 AI 喔！");
      login();
      return;
    }
    if (quizResult) {
      // 將完整測驗結果存入 localStorage，供 ChatPage 讀取
      const quizData = {
        title: quizResult.result?.title || '',
        inner_voice: quizResult.result?.inner_voice || '',
        profile: quizResult.result?.profile || '',
        cafe_match: quizResult.result?.cafe_match || '',
        scores: quizResult.scores || {},
      };
      localStorage.setItem('targetQuizContext', JSON.stringify(quizData));
    }
    navigate('/chat?id=new');
  };

  // =============================================
  // 衍生計算
  // =============================================
  const totalQuestions = questions.length;
  const currentQ = questions[currentStep];
  const progressPercentage = totalQuestions > 0 ? ((currentStep + 1) / totalQuestions) * 100 : 0;

  // =============================================
  // 渲染
  // =============================================
  return (
    <MainLayout>
        <div className={`quiz-content ${quizState === 'intro' ? 'intro-active' : ''}`}>

          {/* ===== 介紹頁：直接渲染在 quiz-content 內（全版佈滿） ===== */}
          {quizState === 'intro' && (
            <div className="intro-view">
              {/* 上半部：深色區域 */}
              <div className="intro-upper">
                <h1 className="intro-title">啡你莫屬人格解析</h1>
                <p className="intro-subtitle">找到最適合你的花蓮咖啡廳</p>
                {/* 波浪分隔線 */}
                <svg className="intro-wave" viewBox="0 0 1440 120" preserveAspectRatio="none">
                  <path d="M0,60 C240,120 480,0 720,60 C960,120 1200,0 1440,60 L1440,120 L0,120 Z" />
                </svg>
              </div>

              {/* 下半部：淺色區域 */}
              <div className="intro-lower">
                <div className="step-cards">
                  <div className="step-card step-card-1">
                    <div className="step-card-bg">
                      <ClipboardList size={120} strokeWidth={1.2} />
                    </div>
                    <div className="step-badge">第 1 步</div>
                    <h3 className="step-card-title">完成情境測驗</h3>
                    <p className="step-card-desc">回答 9 道情境題，依照直覺選出最符合你內心的答案。</p>
                  </div>
                  <div className="step-card step-card-2">
                    <div className="step-card-bg">
                      <BarChart3 size={120} strokeWidth={1.2} />
                    </div>
                    <div className="step-badge">第 2 步</div>
                    <h3 className="step-card-title">解析咖啡人格</h3>
                    <p className="step-card-desc">透過五維度分析，揭曉你獨有的咖啡人格類型與特質側寫。</p>
                  </div>
                  <div className="step-card step-card-3">
                    <div className="step-card-bg">
                      <MapPin size={120} strokeWidth={1.2} />
                    </div>
                    <div className="step-badge">第 3 步</div>
                    <h3 className="step-card-title">配對理想咖啡廳</h3>
                    <p className="step-card-desc">根據你的人格特質，找到花蓮最契合你的命中注定咖啡廳。</p>
                  </div>
                </div>

                {errorMsg && (
                  <p style={{ color: '#c0392b', marginBottom: '16px', fontSize: '0.95rem' }}>{errorMsg}</p>
                )}

                <button className="btn-primary btn-start" onClick={handleStart}>
                  <Play size={18} strokeWidth={2.5} />
                  開始測驗
                </button>
              </div>
            </div>
          )}

          {/* ===== 非 intro 狀態：包在 quiz-card 內 ===== */}
          {quizState !== 'intro' && (
            <div className={`quiz-card ${quizState === 'result' ? 'result-mode' : ''}`}>

              {/* ===== 進度條（答題中顯示） ===== */}
              {quizState === 'question' && currentQ && (
                <div className="progress-container">
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${progressPercentage}%` }} />
                  </div>
                  <div className="progress-label">{currentStep + 1} / {totalQuestions}</div>
                </div>
              )}

              {/* ===== 載入中 ===== */}
              {quizState === 'loading' && (
                <div className="loading-view">
                  <div className="spinner-cup" />
                  <div className="loading-text">正在準備你的專屬題目⋯</div>
                </div>
              )}

              {/* ===== 答題頁 ===== */}
              {quizState === 'question' && currentQ && (
                <div className="question-wrapper">
                  <div className={`question-slide ${isFading ? 'fading-out' : ''}`} key={currentQ.id}>
                    
                    {/* 情境標籤 */}
                    {currentQ.scenario_tag && (
                      <div className="scenario-tag">{currentQ.scenario_tag}</div>
                    )}

                    {/* 題目文案 */}
                    <h2 className="question-text">{currentQ.question_text}</h2>

                    {/* 判斷單選或多選 */}
                    {currentQ.is_multiple ? (
                      /* === Q9 多選 === */
                      <>
                        <p className="multi-select-hint">可選擇 0 至 3 個偏好條件</p>
                        <div className="multi-select-grid">
                          {currentQ.options.map((opt) => {
                            const currentSelections = selectedAnswers[currentQ.id] || [];
                            const isChecked = currentSelections.includes(opt.id);
                            return (
                              <div
                                key={opt.id}
                                className={`checkbox-card ${isChecked ? 'checked' : ''}`}
                                onClick={() => handleMultiToggle(currentQ.id, opt.id)}
                              >
                                <div className="custom-checkbox" />
                                <div className="checkbox-label">
                                  <span className="checkbox-main-text">{opt.text}</span>
                                  {opt.subtext && (
                                    <span className="checkbox-subtext">{opt.subtext}</span>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        <button className="btn-primary" onClick={submitAnswers}>
                          完成測驗
                        </button>
                      </>
                    ) : (
                      /* === Q1-Q8 單選 === */
                      <div className="options-grid">
                        {currentQ.options.map((opt) => (
                          <div
                            key={opt.id}
                            className={`option-card ${selectedAnim === opt.id ? 'selected' : ''}`}
                            onClick={() => handleSingleSelect(currentQ.id, opt.id)}
                          >
                            <span className="option-main-text">
                              {opt.code && <>{opt.code}. </>}
                              {opt.text}
                            </span>
                            {opt.subtext && (
                              <span className="option-subtext">{opt.subtext}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ===== 提交中 ===== */}
              {quizState === 'submitting' && (
                <div className="loading-view">
                  <div className="spinner-cup" />
                  <div className="loading-text">正在分析你的咖啡人格⋯</div>
                </div>
              )}

              {/* ===== 結果頁 ===== */}
              {quizState === 'result' && quizResult && (
                <div className="result-view">
                  {/* 專屬稱號 */}
                  <div className="result-title-badge">你的咖啡人格</div>
                  <h1 className="result-title">{quizResult.result?.title}</h1>

                  {/* 內心獨白 */}
                  {quizResult.result?.inner_voice && (
                    <div className="result-quote">
                      <p>「{quizResult.result.inner_voice}」</p>
                    </div>
                  )}

                  {/* 主體內容區：左右並排 */}
                  <div className="result-body">
                    {/* 左側：文字內容 */}
                    <div className="result-body-left">
                      {/* 特質側寫 */}
                      {quizResult.result?.profile && (
                        <div className="result-profile">
                          <div className="result-section-label">特質側寫</div>
                          <p>{quizResult.result.profile}</p>
                        </div>
                      )}

                      {/* 花蓮隱藏氛圍對應 */}
                      {quizResult.result?.cafe_match && (
                        <div className="result-cafe-match">
                          <div className="match-title">
                            <Store size={18} strokeWidth={2} />
                            花蓮隱藏氛圍對應
                          </div>
                          <p>{quizResult.result.cafe_match}</p>
                        </div>
                      )}
                    </div>

                    {/* 右側：雷達圖 */}
                    <div className="result-body-right">
                      {quizResult.scores && (
                        <RadarChart scores={quizResult.scores} />
                      )}
                    </div>
                  </div>

                  {/* 底部操作按鈕 */}
                  <div className="result-actions">
                    <button className="btn-outline" onClick={handleRetry}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="1 4 1 10 7 10"></polyline>
                        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path>
                      </svg>
                      再測一次
                    </button>
                    <button className="btn-primary" onClick={handleConsultAI}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                      </svg>
                      帶著結果去諮詢 AI
                    </button>
                  </div>
                </div>
              )}

              {/* ===== 錯誤提示（在 question 狀態下顯示） ===== */}
              {quizState === 'question' && errorMsg && (
                <div className="error-view">
                  <div className="error-icon">⚠️</div>
                  <p className="error-message">{errorMsg}</p>
                  <button className="btn-outline" onClick={handleRetry}>返回首頁</button>
                </div>
              )}

            </div>
          )}
        </div>
    </MainLayout>
  );
}