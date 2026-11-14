import { useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Award, BookOpen, CakeSlice, CalendarCheck, Camera, Cat, Coffee, Coins, Compass,
  Crown, Droplets, Gift, House, Map as MapIcon, PlugZap, Sparkles, Stamp,
} from 'lucide-react';
import { AuthContext } from '../context/AuthContext';
import { apiClient } from '../utils/apiClient';
import { logger } from '../utils/logger';
import BlindBoxCard from '../components/passport/BlindBoxCard';
import '../PassportPage.css';

const fmtDate = (iso) => (iso
  ? new Date(iso).toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })
  : '早期紀錄');

// data/passport_badges.json 的 icon 欄位 → 元件。新增徽章用到新圖示時要加在這裡
// （不用 import * 是為了讓打包只帶用到的圖示）
const BADGE_ICONS = {
  Award, BookOpen, CakeSlice, CalendarCheck, Camera, Cat, Coffee, Coins, Compass,
  Crown, Droplets, Gift, House, Map: MapIcon, PlugZap, Sparkles, Stamp,
};

function BadgeIcon({ name, size = 22 }) {
  const Icon = BADGE_ICONS[name] || Award;
  return <Icon size={size} strokeWidth={1.75} />;
}

export default function PassportPage() {
  const { user } = useContext(AuthContext);
  const navigate = useNavigate();
  const isGuest = !user || user.isGuest;

  const [passport, setPassport] = useState(null);
  const [box, setBox] = useState(null);
  const [history, setHistory] = useState([]);
  const [filter, setFilter] = useState('all'); // all | stamped | empty
  const [error, setError] = useState('');

  const loadPassport = useCallback(async () => {
    try {
      setPassport(await apiClient('/api/passport', { suppressToast: true }));
    } catch (e) {
      logger.error('passport load failed', e);
      setError('護照載入失敗，請稍後再試');
    }
  }, []);

  const loadBox = useCallback(async () => {
    try {
      const data = await apiClient('/api/blindbox', { suppressToast: true });
      setBox(data.box);
      setHistory(data.history || []);
    } catch (e) {
      logger.error('blindbox load failed', e);
    }
  }, []);

  useEffect(() => {
    if (isGuest) return;
    Promise.resolve().then(() => { loadPassport(); loadBox(); });
    // 任何地方按了收藏／去過（包含盲盒卡片自己）都重抓，徽章進度才會即時更新
    const onChange = () => { loadPassport(); loadBox(); };
    window.addEventListener('passport:changed', onChange);
    return () => window.removeEventListener('passport:changed', onChange);
  }, [isGuest, loadPassport, loadBox]);

  const handleBoxChange = (next, opts = {}) => {
    setBox(next);
    if (opts.refreshHistory) loadBox();
  };

  if (isGuest) {
    return (
      <div className="passport-page">
        <div className="pp-guest">
          <Stamp size={40} strokeWidth={1.5} />
          <h2>咖啡護照</h2>
          <p>登入後，去過的每一家咖啡廳都會在這裡蓋一個章，還有每週一盒的咖啡盲盒。</p>
        </div>
      </div>
    );
  }

  const book = passport?.book || [];
  const shown = book
    .filter((c) => (filter === 'stamped' ? c.stamped : filter === 'empty' ? !c.stamped : true))
    // 蓋過章的排前面，最近蓋的最前面；沒蓋的照原本順序
    .sort((a, b) => (b.stamped - a.stamped)
      || ((b.visited_at || '').localeCompare(a.visited_at || '')));
  const pct = passport ? Math.round((passport.stamp_count / Math.max(1, passport.total_cafes)) * 100) : 0;
  const badges = passport?.badges || [];
  // 已解鎖的排前面；未解鎖的照進度高低排，快拿到的放前面
  const sortedBadges = [...badges].sort((a, b) => (b.unlocked - a.unlocked)
    || (b.progress / b.target - a.progress / a.target));

  return (
    <div className="passport-page">
      <header className="pp-header">
        <div>
          <div className="pp-eyebrow">CAFE PASSPORT</div>
          <h1 className="pp-title">{user.name} 的咖啡護照</h1>
        </div>
        {passport && (
          <div className="pp-stats">
            <div className="pp-stat"><span className="num">{passport.stamp_count}</span><span className="of">/ {passport.total_cafes}</span><span className="lbl">章</span></div>
            <div className="pp-stat"><span className="num">{passport.badge_count}</span><span className="of">/ {passport.badge_total}</span><span className="lbl">徽章</span></div>
          </div>
        )}
      </header>

      {passport && (
        <div className="pp-progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="集章進度">
          <div className="pp-progress-fill" style={{ width: `${pct}%` }} />
        </div>
      )}

      {error && <div className="pp-error">{error}</div>}

      <section className="pp-section">
        <BlindBoxCard box={box} history={history} onChange={handleBoxChange} />
      </section>

      <section className="pp-section">
        <h2 className="pp-section-title">徽章</h2>
        <div className="pp-badges">
          {sortedBadges.map((b) => (
            <div key={b.id} className={`pp-badge ${b.unlocked ? 'unlocked' : 'locked'}`} title={b.desc}>
              <div className="pp-badge-icon"><BadgeIcon name={b.icon} /></div>
              <div className="pp-badge-name">{b.name}</div>
              <div className="pp-badge-desc">{b.desc}</div>
              {b.unlocked ? (
                <div className="pp-badge-date">{fmtDate(b.unlocked_at)} 解鎖</div>
              ) : (
                <div className="pp-badge-progress" aria-label={`進度 ${b.progress}/${b.target}`}>
                  <div className="bar"><div style={{ width: `${(b.progress / b.target) * 100}%` }} /></div>
                  <span>{b.progress}/{b.target}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="pp-section">
        <div className="pp-section-head">
          <h2 className="pp-section-title">集章冊</h2>
          <div className="pp-filters">
            {[['all', '全部'], ['stamped', '已蓋章'], ['empty', '還沒去']].map(([k, label]) => (
              <button key={k} type="button" className={`pp-filter ${filter === k ? 'active' : ''}`} onClick={() => setFilter(k)}>{label}</button>
            ))}
          </div>
        </div>
        <div className="pp-book">
          {shown.map((c) => (
            <button
              key={c.cafe_id}
              type="button"
              className={`pp-stamp ${c.stamped ? 'stamped' : 'empty'} ${c.via_blindbox ? 'gold' : ''}`}
              onClick={() => navigate(`/explore?open_shop_id=${c.cafe_id}`)}
            >
              <div className="pp-stamp-ring">
                {c.stamped && c.image_url ? <img src={c.image_url} alt="" loading="lazy" /> : <Coffee size={22} strokeWidth={1.5} />}
                {c.stamped && <span className="pp-stamp-date">{fmtDate(c.visited_at)}</span>}
              </div>
              <div className="pp-stamp-name">{c.name}</div>
              {c.area && <div className="pp-stamp-area">{c.area}</div>}
            </button>
          ))}
          {passport && shown.length === 0 && (
            <div className="pp-empty">{filter === 'stamped' ? '還沒有蓋任何章。去過一家咖啡廳後，在探索頁或聊天推薦卡片按「去過」就會蓋章。' : '全部都去過了，太強了！'}</div>
          )}
        </div>
      </section>
    </div>
  );
}
