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

const SCORE_LABELS = { work: '工作讀書', env: '空間氛圍', social: '社交舒適', taste: '餐飲口味', cp: 'CP值' };

/**
 * 取出測驗頁交過來的結果（取了就清掉，重複執行不會送兩次），
 * 組成給 AI 的隱藏提示。沒有待處理的結果時回傳 null。
 */
export function takeQueuedQuizConsultation() {
  const raw = localStorage.getItem('targetQuizContext');
  if (!raw) return null;
  localStorage.removeItem('targetQuizContext');
  try {
    const quiz = JSON.parse(raw);
    const scoreParts = [];
    if (quiz.scores) {
      // 保存五維分數，供「直接推薦」與首頁推薦作為 GNN 的基礎向量
      localStorage.setItem('latestQuizScores', JSON.stringify(quiz.scores));
      for (const [key, val] of Object.entries(quiz.scores)) {
        scoreParts.push(`${SCORE_LABELS[key] || key}：${val}`);
      }
    }
    const promptText = '我剛完成了咖啡人格測驗，以下是我的完整結果：\n'
      + `\n【咖啡人格】${quiz.title}`
      + (quiz.inner_voice ? `\n【內心獨白】${quiz.inner_voice}` : '')
      + (quiz.profile ? `\n【特質側寫】${quiz.profile}` : '')
      + (scoreParts.length > 0 ? `\n【五維分數】${scoreParts.join('、')}` : '')
      + (quiz.cafe_match ? `\n【氛圍對應】${quiz.cafe_match}` : '');
    return { promptText, quizScores: quiz.scores };
  } catch {
    return { promptText: `我剛完成了咖啡人格測驗，結果是「${raw}」。`, quizScores: undefined };
  }
}
