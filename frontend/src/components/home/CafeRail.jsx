import { useRef } from 'react';
import { ChevronLeft, ChevronRight, Star } from 'lucide-react';
import CafePhoto from '../cafe/CafePhoto';

function openLabel(cafe) {
  if (cafe.is_open_now === true) return '營業中';
  if (cafe.today_hours === '今日公休') return '今日公休';
  if (cafe.is_open_now === false) return '休息中';
  return '';
}

/** 方形店家卡：照片鋪滿，店名與評分壓在下緣的漸層上 */
export function CafeTile({ cafe, badge, active, morph, onSelect, onHover }) {
  const status = openLabel(cafe);
  return (
    <button
      type="button"
      className={`cafe-tile ${active ? 'active' : ''}`}
      onClick={() => onSelect(cafe.id)}
      onMouseEnter={() => onHover(cafe.id)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(cafe.id)}
      onBlur={() => onHover(null)}
      aria-label={`${badge ? `${badge}，` : ''}${cafe.name}${cafe.google_rating != null ? `，Google ${cafe.google_rating.toFixed(1)} 顆星` : ''}${status ? `，${status}` : ''}`}
    >
      <CafePhoto
        cafe={cafe}
        className="cafe-tile-photo"
        alt=""
        // 和店家頁標頭的照片同名：打開／關閉店家時，瀏覽器把這張照片變形過去
        style={morph ? { viewTransitionName: 'cafe-photo' } : undefined}
      />
      {badge && <span className="cafe-tile-badge" aria-hidden="true">{badge}</span>}
      <span className="cafe-tile-body" aria-hidden="true">
        <span className="cafe-tile-name">{cafe.name}</span>
        <span className="cafe-tile-meta">
          {cafe.google_rating != null && (
            <span className="cafe-tile-rating">
              <Star size={12} fill="currentColor" /> {cafe.google_rating.toFixed(1)}
            </span>
          )}
          {status && <span className={`cafe-tile-status ${cafe.is_open_now ? 'open' : ''}`}>{status}</span>}
        </span>
      </span>
    </button>
  );
}

/**
 * 「你可能會喜歡／為你推薦」：標題列（含左右捲動鈕）＋一排方形店家卡。
 * items: [{ cafe, badge }]，badge 只給 AI 推薦的店（例如「AI 推薦 1」），其他店不貼標籤。
 */
export default function CafeRail({ title, hint, action, items, isLoading, activeId, morphId, onSelect, onHover, emptyText }) {
  const scrollerRef = useRef(null);

  const scrollBy = (dir) => {
    const el = scrollerRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: 'smooth' });
  };

  return (
    <section className="home-rail" aria-labelledby="home-rail-title">
      <div className="home-rail-head">
        <h2 id="home-rail-title">{title}</h2>
        {hint && <span className="home-rail-hint">{hint}</span>}
        <span className="home-rail-actions">
          {action}
          <button type="button" className="rail-arrow" onClick={() => scrollBy(-1)} aria-label="往左看更多店家">
            <ChevronLeft size={20} />
          </button>
          <button type="button" className="rail-arrow" onClick={() => scrollBy(1)} aria-label="往右看更多店家">
            <ChevronRight size={20} />
          </button>
        </span>
      </div>

      <div className="cafe-rail-scroller" ref={scrollerRef}>
        {isLoading ? (
          Array.from({ length: 6 }, (_, i) => <span key={i} className="cafe-tile skeleton" aria-hidden="true" />)
        ) : items.length === 0 ? (
          <div className="cafe-rail-empty">{emptyText}</div>
        ) : (
          items.map(({ cafe, badge }) => (
            <CafeTile
              key={cafe.id}
              cafe={cafe}
              badge={badge}
              active={activeId === cafe.id}
              morph={morphId === cafe.id}
              onSelect={onSelect}
              onHover={onHover}
            />
          ))
        )}
      </div>
    </section>
  );
}
