import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { apiClient } from '../../utils/apiClient';
import { getPersonalityImage, readCachedQuizResult } from '../../utils/personality';
import { navigateWithTransition } from '../../utils/viewTransition';

// 沒做過測驗時當作預告的幾種咖啡人格
const TEASER_TYPES = ['work', 'social', 'taste', 'env'];

/**
 * 心理測驗入口。背景用人格插圖放大模糊，色調跟著插圖走，不是一整塊咖啡色：
 *   做過測驗 → 自己那張人格插圖
 *   沒做過   → 四種人格插圖拼起來
 */
export default function QuizEntryCard({ user }) {
  const navigate = useNavigate();
  const [latest, setLatest] = useState(() => readCachedQuizResult());

  useEffect(() => {
    if (!user) return undefined;
    let alive = true;
    apiClient('/api/quiz/latest', { suppressToast: true })
      .then((data) => { if (alive && data?.result) setLatest(data); })
      .catch(() => { /* 沒做過或未登入就維持原樣 */ });
    return () => { alive = false; };
  }, [user]);

  const title = latest?.result?.title;
  const art = getPersonalityImage(latest?.result?.type_key);
  const teaser = TEASER_TYPES.map(getPersonalityImage).filter(Boolean);
  const backdrop = art ? [art] : teaser;

  return (
    <section className={`home-block quiz-block ${art ? 'has-result' : ''}`} aria-labelledby="quiz-block-title">
      {backdrop.length > 0 && (
        <div className={`quiz-block-bg ${backdrop.length > 1 ? 'collage' : ''}`} aria-hidden="true">
          {backdrop.map((src) => <img key={src} src={src} alt="" />)}
        </div>
      )}

      <div className="home-block-text">
        <span className="home-block-eyebrow"><Sparkles size={14} aria-hidden="true" /> 咖啡人格測驗</span>
        <h3 id="quiz-block-title">{title ? `你是「${title}」` : '3 分鐘，找出你的咖啡人格'}</h3>
        <p>
          {title
            ? '想法變了嗎？重新測一次，「你可能會喜歡」也會跟著更新。'
            : '回答 9 道情境題，解析你的五維咖啡偏好，推薦會更懂你。'}
        </p>
        <button type="button" className="home-block-cta quiz-block-cta" onClick={() => navigateWithTransition(navigate, '/quiz', 'forward')}>
          {/* 測驗頁可能直接顯示快取的結果，所以不寫「重新測驗」 */}
          {title ? '前往測驗' : '開始測驗'} <ArrowRight size={16} aria-hidden="true" />
        </button>
      </div>

      {art ? (
        <img className="quiz-block-art" src={art} alt={`${title}的插畫`} />
      ) : teaser.length > 0 && (
        <div className="quiz-block-teaser" aria-hidden="true">
          {teaser.map((src) => <img key={src} src={src} alt="" />)}
        </div>
      )}
    </section>
  );
}
