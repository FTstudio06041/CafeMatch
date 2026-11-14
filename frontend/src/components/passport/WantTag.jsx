import { Bookmark } from 'lucide-react';
import { useShopStates } from '../../utils/shopState';
import { SWIPE_UI_TEXTS } from '../../utils/constants';
import './WantTag.css';

/**
 * 「想去」標籤：這家店在滑卡時被右滑過，之後不管在盲盒、AI 推薦卡片哪裡出現都會標出來。
 * enabled=false（訪客）時不打 API、也不顯示。
 */
export default function WantTag({ cafeId, enabled = true }) {
  const states = useShopStates(enabled);
  if (!enabled || !cafeId || !states[cafeId]?.want) return null;
  return (
    <span className="want-tag" title="你在滑卡時對這家有興趣">
      <Bookmark size={11} fill="currentColor" strokeWidth={2} /> {SWIPE_UI_TEXTS.want}
    </span>
  );
}
