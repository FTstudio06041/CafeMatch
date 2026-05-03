import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import '../QuizPage.css';
import Navbar from '../components/Navbar';

// 定義測驗題目
const QUESTIONS = [
  {
    question: "早晨醒來，你最希望聞到什麼樣的香氣？",
    options: [
      { text: "清新的柑橘或花香", type: "light" },
      { text: "濃郁的焦糖或堅果香", type: "dark" },
      { text: "淡淡的茶香", type: "light" }
    ]
  },
  {
    question: "喝咖啡時，你通常習慣怎麼喝？",
    options: [
      { text: "什麼都不加，喝黑咖啡", type: "light" },
      { text: "一定要加牛奶做成拿鐵", type: "dark" },
      { text: "偶爾會加點糖", type: "medium" }
    ]
  },
  {
    question: "你比較喜歡哪種口感？",
    options: [
      { text: "像果汁一樣酸甜清爽", type: "light" },
      { text: "像巧克力一樣醇厚苦甜", type: "dark" }
    ]
  }
];

export default function QuizPage() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();

  // --- 側欄狀態 ---
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [chats, setChats] = useState([]);

  // --- 測驗核心狀態 ---
  const [quizState, setQuizState] = useState('intro'); // 'intro', 'question', 'result'
  const [currentStep, setCurrentStep] = useState(0);
  const [scores, setScores] = useState({ light: 0, dark: 0, medium: 0 });
  const [quizResult, setQuizResult] = useState(null);

  // 動畫過渡狀態 (用來做題目切換的淡入淡出)
  const [isFading, setIsFading] = useState(false);

  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    setChats(savedChats);
  }, []);

  // 開始測驗
  const handleStart = () => {
    setQuizState('question');
    setCurrentStep(0);
    setScores({ light: 0, dark: 0, medium: 0 });
  };

  // 選擇答案
  const handleAnswer = (type) => {
    const newScores = { ...scores, [type]: (scores[type] || 0) + 1 };
    setScores(newScores);

    if (currentStep + 1 < QUESTIONS.length) {
      // 觸發淡出動畫，然後換題
      setIsFading(true);
      setTimeout(() => {
        setCurrentStep(prev => prev + 1);
        setIsFading(false);
      }, 200);
    } else {
      calculateResult(newScores);
    }
  };

  // 計算並顯示結果
  const calculateResult = (finalScores) => {
    let rName = "", rDesc = "";

    if (finalScores.light >= finalScores.dark) {
      rName = "衣索比亞 耶加雪菲 (淺焙)";
      rDesc = "測驗顯示你偏好清爽、帶有果酸與花香的風味。這款豆子如同水果茶般的回甘口感，絕對能給你驚喜！";
    } else {
      rName = "黃金曼特寧 (深焙)";
      rDesc = "測驗顯示你喜歡濃郁、厚實且低酸度的口感。這款豆子帶有藥草與香料的沈穩香氣，非常適合搭配牛奶。";
    }

    const resultData = { name: rName, desc: rDesc };
    setQuizResult(resultData);
    setQuizState('result');

    // 儲存至歷史紀錄 (個人頁面會讀取)
    const newRecord = {
      id: Date.now(),
      date: new Date().toLocaleDateString(),
      resultName: rName,
      resultDesc: rDesc
    };
    const history = JSON.parse(localStorage.getItem('quizHistory')) || [];
    localStorage.setItem('quizHistory', JSON.stringify([newRecord, ...history]));
  };

  // 帶著結果去聊天
  const handleConsultAI = () => {
    localStorage.setItem('targetQuizContext', quizResult.name);
    navigate('/chat');
  };

  const progressPercentage = (currentStep / QUESTIONS.length) * 100;
  const currentQ = QUESTIONS[currentStep];

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
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

        <div className="quiz-content">
          <div className="quiz-card">
            
            {/* 進度條 (只要不是介紹頁就顯示) */}
            {quizState !== 'intro' && (
              <div className="progress-container" style={{ display: 'block' }}>
                <div className="progress-bar" style={{ width: quizState === 'result' ? '100%' : `${progressPercentage}%` }}></div>
              </div>
            )}

            {/* --- 介紹畫面 --- */}
            {quizState === 'intro' && (
              <div className="intro-view">
                <div className="view-title">咖啡喜好探索</div>
                <div className="view-highlight">找到你的命定風味</div>
                <div className="view-desc">
                  透過簡單的心理測驗，分析您的味蕾偏好。<br />
                  完成後，AI 將能為您提供更精準、個人化的咖啡廳推薦。
                </div>
                <button className="btn-primary" onClick={handleStart}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"></circle><polygon points="10 8 16 12 10 16 10 8"></polygon>
                  </svg>
                  開始測驗
                </button>
              </div>
            )}

            {/* --- 答題畫面 --- */}
            {quizState === 'question' && (
              <div style={{ width: '100%', opacity: isFading ? 0 : 1, transition: 'opacity 0.2s' }}>
                <h2 className="question-text">{currentQ.question}</h2>
                <div className="options-grid">
                  {currentQ.options.map((opt, idx) => (
                    <button key={idx} className="option-btn" onClick={() => handleAnswer(opt.type)}>
                      {opt.text}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* --- 結果畫面 --- */}
            {quizState === 'result' && quizResult && (
              <div className="result-view" style={{ display: 'flex' }}>
                <div className="view-title">測驗結果出爐！最適合你的咖啡是...</div>
                <div className="view-highlight">{quizResult.name}</div>
                <div className="view-desc">{quizResult.desc}</div>

                <div style={{ display: 'flex', gap: '15px' }}>
                  <button className="btn-primary" style={{ backgroundColor: 'transparent', border: '2px solid var(--text-main)', color: 'var(--text-main)' }} onClick={handleStart}>
                    再測一次
                  </button>
                  <button className="btn-primary" onClick={handleConsultAI}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    帶著結果去諮詢 AI
                  </button>
                </div>
              </div>
            )}

          </div>
        </div>
      </main>
    </div>
  );
}