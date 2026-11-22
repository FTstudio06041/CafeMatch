import { useEffect, useRef } from 'react';
import {
  ArrowLeft, Bookmark, CheckCircle2, Clock, ExternalLink, Globe, MapPin, Navigation, Phone, Wallet,
} from 'lucide-react';
import CafePhoto from './CafePhoto';
import CafeReports from './CafeReports';
import CafeReviewsTab from './CafeReviewsTab';
import { StarDisplay } from './Stars';
import { toast } from '../../utils/toast';
import './CafeDetail.css';
import './CafeFocus.css';

const TODAY = ((new Date().getDay() + 6) % 7) + 1; // 1~7 = 週一~週日，和後端一致

function websiteLabel(url) {
  if (/facebook\.com/i.test(url)) return 'Facebook 粉專';
  if (/instagram\.com/i.test(url)) return 'Instagram';
  if (/lin\.ee|line\.me/i.test(url)) return 'LINE';
  return '官方網站';
}

function OpenBadge({ cafe }) {
  if (cafe.is_open_now === true) return <span className="focus-open open">營業中</span>;
  if (cafe.today_hours === '今日公休') return <span className="focus-open">今日公休</span>;
  if (cafe.is_open_now === false) return <span className="focus-open">休息中</span>;
  return null;
}

/**
 * 店家專屬畫面（草圖第三版）：點開店家後，右側的店家列與方塊換成這一家，
 * 讓注意力集中在單一店家上。
 *   標頭：店家照片＋資訊與星數＋收藏／去過／導航
 *   內容：評論區為主（評論即社群），旁邊放現況回報、一週營業時間、聯絡方式、店家特色
 */
export default function CafeFocusView({ cafe, user, onClose, onToggleState, onStatsChange, onLogin }) {
  const rootRef = useRef(null);
  const titleRef = useRef(null);
  const website = /^https?:\/\//i.test(cafe.website) ? cafe.website : '';

  // 換店時：焦點移到店名（鍵盤與螢幕閱讀器知道畫面換了）。
  // 單欄版面捲到地圖頂端，圖釘和店家資訊一起看得到；桌機一屏放得下，捲動不會發生
  useEffect(() => {
    titleRef.current?.focus({ preventScroll: true });
    const top = rootRef.current?.closest('.home-main') || rootRef.current;
    top?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [cafe.id]);

  useEffect(() => {
    const onKey = (e) => {
      // 在輸入框裡按 Esc 只是想取消輸入，不要把整個店家頁關掉
      if (e.key === 'Escape' && !e.target.closest?.('input, textarea')) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const toggle = (type) => {
    if (!user) {
      toast.info('登入後就能收藏店家、標記去過');
      return;
    }
    onToggleState(cafe.id, type);
  };

  return (
    <section className="cafe-focus" ref={rootRef} aria-labelledby="cafe-focus-name">
      <header className="cafe-focus-head">
        <CafePhoto
          cafe={cafe}
          className="cafe-focus-photo"
          alt={`${cafe.name}的照片`}
          eager
          style={{ viewTransitionName: 'cafe-photo' }}
        />

        <div className="cafe-focus-info">
          <div className="cafe-focus-titlerow">
            <h2 id="cafe-focus-name" ref={titleRef} tabIndex={-1}>{cafe.name}</h2>
            <OpenBadge cafe={cafe} />
          </div>
          <div className="cafe-focus-ratings">
            {cafe.google_rating != null && (
              <span className="focus-rating">
                <StarDisplay value={cafe.google_rating} size={16} />
                <b>{cafe.google_rating.toFixed(1)}</b>
                <span className="focus-muted">Google {cafe.google_review_count.toLocaleString()} 則</span>
              </span>
            )}
            {cafe.rating != null ? (
              <span className="focus-rating">
                <b>{cafe.rating.toFixed(1)}</b>
                <span className="focus-muted">本站 {cafe.review_count} 則</span>
              </span>
            ) : (
              <span className="focus-muted">本站尚無評論</span>
            )}
          </div>
          <ul className="cafe-focus-facts">
            <li><Clock size={15} aria-hidden="true" /> 今天 {cafe.today_hours || '營業時間請洽店家'}</li>
            {cafe.cost && <li><Wallet size={15} aria-hidden="true" /> {cafe.cost}</li>}
            {cafe.address && <li className="focus-address"><MapPin size={15} aria-hidden="true" /> {cafe.address}</li>}
          </ul>
        </div>

        <div className="cafe-focus-actions">
          <button
            type="button"
            className={`focus-action ${cafe.is_fav ? 'on' : ''}`}
            onClick={() => toggle('fav')}
            aria-pressed={cafe.is_fav}
          >
            <Bookmark size={16} fill={cafe.is_fav ? 'currentColor' : 'none'} aria-hidden="true" />
            {cafe.is_fav ? '已收藏' : '收藏'}
          </button>
          <button
            type="button"
            className={`focus-action ${cafe.is_visited ? 'on' : ''}`}
            onClick={() => toggle('visited')}
            aria-pressed={cafe.is_visited}
          >
            <CheckCircle2 size={16} aria-hidden="true" />
            {cafe.is_visited ? '去過了' : '去過'}
          </button>
          {cafe.map_url && (
            <a className="focus-action" href={cafe.map_url} target="_blank" rel="noopener noreferrer">
              <Navigation size={16} aria-hidden="true" /> 導航
            </a>
          )}
          <button type="button" className="cafe-focus-back" onClick={onClose} aria-label="返回首頁">
            <ArrowLeft size={17} aria-hidden="true" /> 返回
          </button>
        </div>
      </header>

      <div className="cafe-focus-body">
        <div className="cafe-focus-main">
          <h3 className="focus-section-title">評論</h3>
          <CafeReviewsTab cafe={cafe} user={user} onLogin={onLogin} onStatsChange={onStatsChange} />
        </div>

        <aside className="cafe-focus-side" aria-label="店家資訊">
          <CafeReports
            cafe={cafe}
            user={user}
            onLogin={onLogin}
            onCountChange={(n) => onStatsChange({ report_count: n })}
          />

          {cafe.weekly_hours?.length > 0 && (
            <section className="detail-section" aria-labelledby="focus-hours-title">
              <h3 id="focus-hours-title" className="detail-section-title"><Clock size={16} aria-hidden="true" /> 營業時間</h3>
              <table className="week-table">
                <tbody>
                  {cafe.weekly_hours.map((d) => (
                    <tr key={d.day} className={d.day === TODAY ? 'today' : ''}>
                      <th scope="row">{d.label}</th>
                      <td>{d.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {(cafe.phone || website || cafe.map_url) && (
            <section className="detail-section" aria-labelledby="focus-contact-title">
              <h3 id="focus-contact-title" className="detail-section-title">聯絡與連結</h3>
              <ul className="info-list">
                {cafe.phone && (
                  <li>
                    <Phone size={16} aria-hidden="true" />
                    <a href={`tel:${cafe.phone.replace(/[^\d+]/g, '')}`}>{cafe.phone}</a>
                  </li>
                )}
                {website && (
                  <li>
                    <Globe size={16} aria-hidden="true" />
                    <a href={website} target="_blank" rel="noopener noreferrer">
                      {websiteLabel(website)} <ExternalLink size={13} aria-hidden="true" />
                    </a>
                  </li>
                )}
                {cafe.map_url && (
                  <li>
                    <MapPin size={16} aria-hidden="true" />
                    <a href={cafe.map_url} target="_blank" rel="noopener noreferrer">
                      在 Google 地圖開啟 <ExternalLink size={13} aria-hidden="true" />
                    </a>
                  </li>
                )}
              </ul>
            </section>
          )}

          {cafe.tag_list?.length > 0 && (
            <section className="detail-section" aria-labelledby="focus-tags-title">
              <h3 id="focus-tags-title" className="detail-section-title">店家特色</h3>
              <div className="tag-cloud">
                {cafe.tag_list.map((t) => <span key={t} className="tag-chip">{t}</span>)}
              </div>
            </section>
          )}
        </aside>
      </div>
    </section>
  );
}
