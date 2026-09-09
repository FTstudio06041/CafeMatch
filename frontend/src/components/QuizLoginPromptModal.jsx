/**
 * 測驗結果要帶去諮詢 AI 之前，先問訪客要不要登入。
 *
 * 帶結果去諮詢本來就必須登入；原本訪客一按就被直接丟去 Google 登入頁，
 * 沒有選擇餘地。改成先問過，並順帶說明登入還能保存對話紀錄。
 */
export default function QuizLoginPromptModal({ open, onLogin, onClose }) {
  if (!open) return null;

  return (
    <div className="quiz-login-overlay" onClick={onClose}>
      <div
        className="quiz-login-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="quiz-login-title"
      >
        <h3 id="quiz-login-title" className="quiz-login-title">要前往登入嗎？</h3>
        <p className="quiz-login-body">
          把測驗結果帶去諮詢 AI 需要先登入。
          <br />
          登入後，這次的對話紀錄也會一併保存，下次回來還看得到。
        </p>
        <div className="quiz-login-actions">
          <button type="button" className="btn-outline" onClick={onClose}>
            稍後再說
          </button>
          <button type="button" className="btn-primary" onClick={onLogin}>
            前往登入
          </button>
        </div>
      </div>
    </div>
  );
}
