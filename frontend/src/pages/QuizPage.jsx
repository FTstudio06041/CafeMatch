import React, { useState, useEffect, useContext, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import { ClipboardList, BarChart3, MapPin, Play, Store } from 'lucide-react';
import '../QuizPage.css';
import Navbar from '../components/Navbar';

// =============================================
// 五維雷達圖元件（純 SVG，無外部套件）
// =============================================
function RadarChart({ scores }) {
  // 五維度定義
  const dimensions = [
    { key: 'work', label: '工作讀書' },
    { key: 'env', label: '空間氛圍' },
    { key: 'social', label: '社交舒適' },
    { key: 'taste', label: '餐飲口味' },
    { key: 'cp', label: 'CP值' },
  ];

  const cx = 160; // 中心 X
  const cy = 160; // 中心 Y
  const maxRadius = 110; // 最大半徑
  const labelRadius = maxRadius + 45; // 標籤距離
  const levels = 4; // 背景網格層數

  // 計算各軸最大值（取所有分數的最大值，至少為 1）
  const maxScore = Math.max(...Object.values(scores), 1);

  // 計算五角形頂點座標（從頂部 -90° 開始順時針）
  const getPoint = (index, radius) => {
    const angle = ((2 * Math.PI) / 5) * index - Math.PI / 2;
    return {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  };

  // 生成多角形頂點字串
  const getPolygonPoints = (radiusFn) =>
    dimensions.map((_, i) => {
      const p = getPoint(i, radiusFn(i));
      return `${p.x},${p.y}`;
    }).join(' ');

  // 背景同心五角形
  const gridPolygons = Array.from({ length: levels }, (_, level) => {
    const r = (maxRadius / levels) * (level + 1);
    return getPolygonPoints(() => r);
  });

  // 資料多角形
  const dataPoints = getPolygonPoints((i) => {
    const score = scores[dimensions[i].key] || 0;
    return (score / maxScore) * maxRadius;
  });

  return (
    <div className="radar-container">
      <div className="radar-title">五維度側寫</div>
      <svg className="radar-svg" viewBox="-40 -40 400 400">
        {/* 背景網格 */}
        {gridPolygons.map((points, i) => (
          <polygon key={`grid-${i}`} points={points} className="radar-grid-polygon" />
        ))}

        {/* 軸線 */}
        {dimensions.map((_, i) => {
          const p = getPoint(i, maxRadius);
          return (
            <line
              key={`axis-${i}`}
              x1={cx}
              y1={cy}
              x2={p.x}
              y2={p.y}
              className="radar-axis-line"
            />
          );
        })}

        {/* 資料多角形 */}
        <polygon points={dataPoints} className="radar-data-polygon" />

        {/* 資料頂點圓點 */}
        {dimensions.map((dim, i) => {
          const score = scores[dim.key] || 0;
          const r = (score / maxScore) * maxRadius;
          const p = getPoint(i, r);
          return <circle key={`dot-${i}`} cx={p.x} cy={p.y} className="radar-dot" />;
        })}

        {/* 軸標籤 */}
        {dimensions.map((dim, i) => {
          const p = getPoint(i, labelRadius);
          return (
            <text key={`label-${i}`} x={p.x} y={p.y} className="radar-label">
              {dim.label}
            </text>
          );
        })}

        {/* 分數標籤 */}
        {dimensions.map((dim, i) => {
          const score = scores[dim.key] || 0;
          const r = (score / maxScore) * maxRadius;
          const p = getPoint(i, Math.max(r + 20, 25));
          return (
            <text key={`score-${i}`} x={p.x} y={p.y + 14} className="radar-score">
              {score}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

// =============================================
// QuizPage 主元件
// =============================================
export default function QuizPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();

  // --- 側欄狀態 ---
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [chats, setChats] = useState([]);

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

  // 初始化：讀取聊天紀錄
  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    setChats(savedChats);
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
      // 依照 order 排序
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
      // 將 selectedAnswers 轉換為 API 格式
      const answers = [];
      const filters = [];

      questions.forEach((q) => {
        const ans = selectedAnswers[q.id];
        if (q.is_multiple) {
          // Q9 多選：放入 filters
          if (Array.isArray(ans)) {
            filters.push(...ans);
          }
        } else {
          // 單選：放入 answers
          if (ans !== undefined && ans !== null) {
            answers.push(ans);
          }
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
    fetchQuestions();
  };

  // 單選：選擇後短暫動畫，然後切換下一題或提交
  const handleSingleSelect = (questionId, optionId) => {
    // 先記錄答案
    setSelectedAnswers((prev) => ({ ...prev, [questionId]: optionId }));
    setSelectedAnim(optionId);

    // 短暫選中動畫，然後切換
    setTimeout(() => {
      setSelectedAnim(null);
      if (currentStep + 1 < questions.length) {
        // 淡出
        setIsFading(true);
        setTimeout(() => {
          setCurrentStep((prev) => prev + 1);
          setIsFading(false);
        }, 250);
      }
      // 若是最後一題且為單選，不自動提交（除非後面沒有多選題）
    }, 400);
  };

  // 多選：切換 checkbox
  const handleMultiToggle = (questionId, optionId) => {
    setSelectedAnswers((prev) => {
      const current = prev[questionId] || [];
      const isSelected = current.includes(optionId);
      let updated;
      if (isSelected) {
        updated = current.filter((id) => id !== optionId);
      } else {
        // 最多選 3 個
        if (current.length >= 3) return prev;
        updated = [...current, optionId];
      }
      return { ...prev, [questionId]: updated };
    });
  };

  // 完成測驗
  const handleFinish = () => {
    submitAnswers();
  };

  // 再測一次
  const handleRetry = () => {
    setQuizState('intro');
    setQuestions([]);
    setCurrentStep(0);
    setSelectedAnswers({});
    setQuizResult(null);
    setErrorMsg('');
  };

  // 帶著結果去諮詢 AI
  const handleConsultAI = () => {
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
    navigate('/chat');
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
    <div className="quiz-page-container" style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄（保持原樣） --- */}
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <button className="toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
        </button>

        <button className="user-profile-btn" onClick={() => navigate('/profile')}>
          <div className="user-avatar" style={{ backgroundColor: user?.picture ? 'transparent' : 'var(--accent-color)' }}>
            {user?.picture ? <img src={user.picture} alt="avatar" style={{width: '100%', borderRadius: '50%', objectFit: 'cover'}} /> : 'U'}
          </div>
          <span className="user-name text-label">{user?.name || '使用者名稱'}</span>
        </button>

        <button className="new-chat-btn" onClick={() => { localStorage.setItem('targetChatId', 'new'); navigate('/chat'); }}>
           <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
           <span className="text-label">新增對話</span>
        </button>

        <div className="history-label text-label">對話紀錄</div>
        <div className="chat-list">
           {chats.length === 0 ? <div className="empty-sidebar-msg">尚無對話紀錄</div> : 
             chats.map(chat => (
               <div key={chat.id} className="chat-item" onClick={() => {localStorage.setItem('targetChatId', chat.id); navigate('/chat');}}>
                 <div className="chat-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></div>
                 <span className="chat-title text-label">{chat.title}</span>
               </div>
           ))}
        </div>
      </aside>

      {/* --- 主內容區 --- */}
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>

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
                        <button className="btn-primary" onClick={handleFinish}>
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
      </main>
    </div>
  );
}