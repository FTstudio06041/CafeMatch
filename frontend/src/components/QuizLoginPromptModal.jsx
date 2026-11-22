/**
 * 測驗結果要帶去諮詢 AI 之前，問訪客要不要先登入。
 *
 * 首頁公開之後，不登入也能直接諮詢，只是對話不會保存；
 * 登入的好處（保存對話、之後的推薦記得你的測驗）在這裡講清楚，讓訪客自己選。
 */
export default function QuizLoginPromptModal({ open, onLogin, onContinue, onClose }) {
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
        <h3 id="quiz-login-title" className="quiz-login-title">要先登入嗎？</h3>
        <p className="quiz-login-body">
          不登入也能直接帶著結果諮詢 AI，但對話不會保存。
          <br />
          登入後，這次的對話會一併保存，首頁的推薦也會記得你的測驗結果。
        </p>
        <div className="quiz-login-actions">
          <button type="button" className="btn-outline" onClick={onContinue}>
            直接諮詢
          </button>
          <button type="button" className="btn-primary" onClick={onLogin}>
            登入後諮詢
          </button>
        </div>
      </div>
    </div>
  );
}
