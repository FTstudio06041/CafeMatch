const PENDING_QUIZ_KEY = 'pendingQuizConsultation';
const SCORE_KEYS = ['work', 'env', 'social', 'taste', 'cp'];

export function queueQuizConsultation(quizResult, afterLogin = false) {
  if (!quizResult) return false;
  const context = {
    title: quizResult.result?.title || '',
    inner_voice: quizResult.result?.inner_voice || '',
    profile: quizResult.result?.profile || '',
    cafe_match: quizResult.result?.cafe_match || '',
    scores: quizResult.scores || {},
  };
  if (afterLogin) {
    // OAuth 會離開此頁，待登入的結果留在同一分頁，避免被其他訪客對話取走。
    sessionStorage.setItem(PENDING_QUIZ_KEY, JSON.stringify(context));
  } else {
    sessionStorage.removeItem(PENDING_QUIZ_KEY);
    localStorage.setItem('targetQuizContext', JSON.stringify(context));
  }
  return true;
}

export function resumeQuizConsultation(user) {
  if (!user?.is_logged_in || user.isGuest) return false;
  const raw = sessionStorage.getItem(PENDING_QUIZ_KEY);
  if (!raw) return false;
  let context;
  try {
    context = JSON.parse(raw);
  } catch {
    sessionStorage.removeItem(PENDING_QUIZ_KEY);
    return false;
  }
  if (!context || !SCORE_KEYS.every(key => Number.isFinite(context.scores?.[key]))) {
    sessionStorage.removeItem(PENDING_QUIZ_KEY);
    return false;
  }
  localStorage.setItem('targetQuizContext', JSON.stringify(context));
  localStorage.removeItem('forceQuiz');
  sessionStorage.removeItem(PENDING_QUIZ_KEY);
  return true;
}
