import { useState } from 'react';
import { MapPin, Clock, Coffee, ExternalLink } from 'lucide-react';
import './CafeCard.css';

/**
 * CafeCard — 推薦結果的圖文卡片。
 * 圖片與店家資訊以卡片呈現；推薦理由則由 AI 的文字訊息負責。
 */
export default function CafeCard({ cafe }) {
  const [imgError, setImgError] = useState(false);
  const link = cafe.url || cafe.website;
  const showImg = cafe.image && !imgError;

  return (
    <div className="cafe-card">
      <div className="cafe-card-img">
        {showImg ? (
          <img src={cafe.image} alt={cafe.name} loading="lazy" onError={() => setImgError(true)} />
        ) : (
          <div className="cafe-card-img-placeholder"><Coffee size={28} /></div>
        )}
      </div>

      <div className="cafe-card-body">
        <div className="cafe-card-name">{cafe.name}</div>

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

        {link && (
          <a className="cafe-card-link" href={link} target="_blank" rel="noopener noreferrer">
            查看地圖 / 更多 <ExternalLink size={13} />
          </a>
        )}
      </div>
    </div>
  );
}
