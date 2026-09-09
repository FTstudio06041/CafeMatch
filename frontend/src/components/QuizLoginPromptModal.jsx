/**
 * 測驗結果要帶去諮詢 AI 之前，先問訪客要不要登入。
 *
 * 原本訪客一按就被直接丟去 Google 登入頁，沒有選擇餘地；
 * 改成先說明登入的差別（能不能保存對話），讓使用者自己決定。
 */
export default function QuizLoginPromptModal({ open, onLogin, onContinue }) {
  if (!open) return null;

  return (
    <div className="quiz-login-overlay" onClick={onContinue}>
      <div
        className="quiz-login-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="quiz-login-title"
      >
        <h3 id="quiz-login-title" className="quiz-login-title">要先登入嗎？</h3>
        <p className="quiz-login-body">
          登入後才能保存這次的對話紀錄，下次回來還看得到。
          <br />
          不登入也可以直接帶著測驗結果去諮詢，只是聊完就不會留下紀錄。
        </p>
        <div className="quiz-login-actions">
          <button type="button" className="btn-outline" onClick={onContinue}>
            先不用，直接諮詢
          </button>
          <button type="button" className="btn-primary" onClick={onLogin}>
            前往登入
          </button>
        </div>
      </div>
    </div>
  );
}
