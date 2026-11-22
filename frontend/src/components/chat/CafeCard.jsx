import { useContext, useState } from 'react';
import { MapPin, Clock, Coffee, ExternalLink, Heart, Check } from 'lucide-react';
import { AuthContext } from '../../context/AuthContext';
import { useShopStates, toggleShopState } from '../../utils/shopState';
import WantTag from '../passport/WantTag';
import './CafeCard.css';

/**
 * CafeCard — 推薦結果的圖文卡片。
 * 圖片與店家資訊以卡片呈現；推薦理由則由 AI 的文字訊息負責。
 */
export default function CafeCard({ cafe }) {
  const [imgError, setImgError] = useState(false);
  const [busy, setBusy] = useState(false);
  const { user } = useContext(AuthContext);
  const isGuest = !user || user.isGuest;
  // 推薦卡片直接可以收藏／標記去過：「推薦 → 真的去了」是推薦成效最直接的訊號，
  // 以前要自己跑去探索頁找這家店，大部分人不會這樣做，這筆資料就收不到。
  const states = useShopStates(!isGuest);
  const mine = states[cafe.id] || { fav: false, visited: false };

  const toggle = async (type) => {
    if (busy || !cafe.id) return;
    setBusy(true);
    try {
      await toggleShopState(cafe.id, type, 'chat');
    } catch {
      // apiClient 已經跳過錯誤提示
    } finally {
      setBusy(false);
    }
  };
  const showImg = cafe.image && !imgError;

  // cafe.url 存的是 Google Maps 短碼（非完整網址），不能直接當連結（會導向空白頁）。
  // 改用 name+address 組 Google Maps 搜尋，和 ExplorePage 的地圖來源一致，永遠有效。
  const mapQuery = encodeURIComponent([cafe.name, cafe.address].filter(Boolean).join(' '));
  const mapLink = mapQuery ? `https://www.google.com/maps/search/?api=1&query=${mapQuery}` : null;
  const siteLink = cafe.website && /^https?:\/\//i.test(cafe.website) ? cafe.website : null;

  return (
    <div className="cafe-card">
      <div className="cafe-card-img">
        {/* 推薦卡片只有幾張且是當下的互動焦點，不用 lazy：
            lazy 在剛串流出現的捲動容器裡可能延遲觸發，造成空白卡 */}
        {showImg ? (
          <img src={cafe.image} alt={cafe.name} onError={() => setImgError(true)} />
        ) : (
          <div className="cafe-card-img-placeholder"><Coffee size={28} /></div>
        )}
      </div>

      <div className="cafe-card-body">
        <div className="cafe-card-name">{cafe.name} <WantTag cafeId={cafe.id} enabled={!isGuest} /></div>

        {cafe.cost && (
          <div className="cafe-card-meta"><Coffee size={13} /> {cafe.cost}</div>
        )}
        {cafe.address && (
          <div className="cafe-card-meta"><MapPin size={13} /> {cafe.address}</div>
        )}
        {cafe.hours && cafe.hours !== '未提供' && (
          <div className="cafe-card-meta cafe-card-hours"><Clock size={13} /> {cafe.hours}</div>
        )}

        {Array.isArray(cafe.tags) && cafe.tags.length > 0 && (
          <div className="cafe-card-tags">
            {cafe.tags.slice(0, 6).map((t, i) => (
              <span key={i} className="cafe-card-tag">{t}</span>
            ))}
          </div>
        )}

        {!isGuest && cafe.id && (
          <div className="cafe-card-actions">
            <button
              type="button"
              className={`cafe-card-action ${mine.fav ? 'active' : ''}`}
              onClick={() => toggle('fav')}
              disabled={busy}
              aria-pressed={mine.fav}
            >
              <Heart size={13} fill={mine.fav ? 'currentColor' : 'none'} /> {mine.fav ? '已收藏' : '收藏'}
            </button>
            <button
              type="button"
              className={`cafe-card-action ${mine.visited ? 'active' : ''}`}
              onClick={() => toggle('visited')}
              disabled={busy}
              aria-pressed={mine.visited}
              title="去過就在咖啡護照蓋一個章"
            >
              <Check size={13} /> {mine.visited ? '已去過' : '我去過了'}
            </button>
          </div>
        )}

        <div className="cafe-card-links">
          {mapLink && (
            <a className="cafe-card-link" href={mapLink} target="_blank" rel="noopener noreferrer">
              在地圖上查看 <ExternalLink size={13} />
            </a>
          )}
          {siteLink && (
            <a className="cafe-card-link" href={siteLink} target="_blank" rel="noopener noreferrer">
              官網 / 粉專 <ExternalLink size={13} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
