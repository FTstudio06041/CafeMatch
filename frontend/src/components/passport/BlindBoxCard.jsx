import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Gift, MapPin, RefreshCw, Star, Check, Coffee } from 'lucide-react';
import { apiClient } from '../../utils/apiClient';
import { toggleShopState } from '../../utils/shopState';
import { toast } from '../../utils/toast';
import WantTag from './WantTag';

// 跟後端 blindbox_service.SKIP_REASONS 對應
const SKIP_REASONS = [
  { key: 'too_far', label: '太遠了' },
  { key: 'not_my_type', label: '不是我的菜' },
  { key: 'been_there', label: '其實去過了' },
  { key: 'no_time', label: '最近沒空' },
  { key: 'other', label: '其他' },
];

// opened：以前拆開、還在保留期內等你去的盒子
const STATUS_LABEL = { completed: '完成', expired: '錯過', skipped: '換掉', opened: '待去' };

// 後端 blindbox_service.OPENED_KEEP_DAYS
const OPENED_KEEP_DAYS = 7;

function hoursLeft(endsAt) {
  if (!endsAt) return null;
  const ms = new Date(endsAt) - new Date();
  return Math.max(0, Math.ceil(ms / 3600000));
}

const fmtDay = (key) => {
  const [, m, d] = (key || '').split('-');
  return m ? `${Number(m)}/${Number(d)}` : key;
};

export default function BlindBoxCard({ box, history, onChange }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [askReason, setAskReason] = useState(false);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
    } catch {
      // apiClient 會自己跳錯誤提示
    } finally {
      setBusy(false);
    }
  };

  const openBox = () => run(async () => {
    const data = await apiClient('/api/blindbox/open', { method: 'POST' });
    onChange(data.box);
  });

  const reroll = (reason) => run(async () => {
    const data = await apiClient('/api/blindbox/reroll', { method: 'POST', body: JSON.stringify({ reason }) });
    setAskReason(false);
    onChange(data.box, { refreshHistory: true });
    toast.info('換了一盒新的，今天不能再換囉');
  });

  const markVisited = () => run(async () => {
    await toggleShopState(box.cafe.id, 'visited', 'blindbox');
    // 護照頁會收到 passport:changed 事件自己重抓
  });

  const submitRating = () => run(async () => {
    if (!rating) return;
    const data = await apiClient(`/api/blindbox/${box.id}/rate`, {
      method: 'POST',
      body: JSON.stringify({ rating, comment }),
    });
    onChange(data.box);
    toast.success('謝謝你的回饋，下一盒會挑得更準');
  });

  if (!box) return <div className="blindbox-card loading">盲盒準備中…</div>;

  if (box.status === 'empty') {
    return (
      <div className="blindbox-card">
        <div className="blindbox-empty">
          <Coffee size={28} />
          <p>收錄的店你都認識了，盲盒暫時抽不出新店。等我們收錄更多店家吧！</p>
        </div>
      </div>
    );
  }

  const left = hoursLeft(box.ends_at);
  const hints = box.hints || {};

  return (
    <div className={`blindbox-card status-${box.status}`}>
      <div className="blindbox-head">
        <div>
          <div className="blindbox-eyebrow">今日咖啡盲盒 · {fmtDay(box.day_key)}</div>
          <h3 className="blindbox-title">
            {box.status === 'sealed' && '一家你大概不會自己挑、但可能會愛上的店'}
            {box.status === 'opened' && box.cafe?.name}
            {box.status === 'completed' && `完成！${box.cafe?.name ?? ''}`}
            {box.cafe && <> <WantTag cafeId={box.cafe.id} /></>}
          </h3>
        </div>
        {box.status === 'sealed' && left !== null && (
          <div className="blindbox-countdown">{left <= 1 ? '快換盒了' : `${left} 小時後換新盒`}</div>
        )}
        {box.status === 'opened' && (
          <div className="blindbox-countdown">{OPENED_KEEP_DAYS} 天內去都算</div>
        )}
      </div>

      {box.status === 'sealed' && (
        <div className="blindbox-sealed">
          <div className="blindbox-gift" aria-hidden="true"><Gift size={44} strokeWidth={1.5} /></div>
          <div className="blindbox-hints">
            <div className="blindbox-hint-label">線索</div>
            <div className="blindbox-hint-chips">
              {hints.area && <span className="blindbox-chip"><MapPin size={12} /> {hints.area}</span>}
              {hints.cost && <span className="blindbox-chip">{hints.cost}</span>}
              {(hints.tags || []).map((t) => <span key={t} className="blindbox-chip">#{t}</span>)}
            </div>
            <p className="blindbox-note">拆開才看得到是哪一家。今天沒拆，明天就換新的一盒；拆開後 {OPENED_KEEP_DAYS} 天內去過，就能在護照蓋一個金色的盲盒章。</p>
          </div>
        </div>
      )}

      {(box.status === 'opened' || box.status === 'completed') && box.cafe && (
        <div className="blindbox-revealed">
          <div className="blindbox-img">
            {box.cafe.image_url ? <img src={box.cafe.image_url} alt={box.cafe.name} /> : <Coffee size={28} />}
          </div>
          <div className="blindbox-info">
            {box.cafe.address && <div className="blindbox-meta"><MapPin size={13} /> {box.cafe.address}</div>}
            <div className="blindbox-hint-chips">
              {box.cafe.cost && <span className="blindbox-chip">{box.cafe.cost}</span>}
              {box.cafe.tags.map((t) => <span key={t} className="blindbox-chip">#{t}</span>)}
            </div>
          </div>
        </div>
      )}

      {box.status === 'completed' && (
        <div className="blindbox-rate">
          {box.rating ? (
            <div className="blindbox-rated">
              你給了 {Array.from({ length: box.rating }, (_, i) => <Star key={i} size={14} fill="currentColor" />)}
              ，明天會有新的盒子
            </div>
          ) : (
            <>
              <div className="blindbox-hint-label">這家合你胃口嗎？</div>
              <div className="blindbox-stars" role="radiogroup" aria-label="評分">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    role="radio"
                    aria-checked={rating === n}
                    aria-label={`${n} 分`}
                    className={n <= rating ? 'on' : ''}
                    onClick={() => setRating(n)}
                  >
                    <Star size={22} fill={n <= rating ? 'currentColor' : 'none'} />
                  </button>
                ))}
              </div>
              <div className="blindbox-comment-row">
                <input
                  className="blindbox-comment"
                  maxLength={200}
                  placeholder="一句話心得（選填）"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                />
                <button type="button" className="pp-btn primary" disabled={!rating || busy} onClick={submitRating}>送出</button>
              </div>
            </>
          )}
        </div>
      )}

      {(box.status === 'sealed' || box.status === 'opened') && (
        <div className="blindbox-actions">
          {box.status === 'sealed' ? (
            <button type="button" className="pp-btn primary" disabled={busy} onClick={openBox}>
              <Gift size={16} /> 拆開盲盒
            </button>
          ) : (
            <>
              <button type="button" className="pp-btn primary" disabled={busy} onClick={markVisited}>
                <Check size={16} /> 我去過了
              </button>
              <button type="button" className="pp-btn" onClick={() => navigate(`/explore?open_shop_id=${box.cafe.id}`)}>
                看店家資訊
              </button>
            </>
          )}
          {box.rerolls_left > 0 && !askReason && (
            <button type="button" className="pp-btn ghost" disabled={busy} onClick={() => setAskReason(true)}>
              <RefreshCw size={14} /> 換一盒
            </button>
          )}
        </div>
      )}

      {askReason && (
        <div className="blindbox-reasons">
          <div className="blindbox-hint-label">為什麼想換？（幫我們下次挑得更準）</div>
          <div className="blindbox-hint-chips">
            {SKIP_REASONS.map((r) => (
              <button key={r.key} type="button" className="blindbox-chip button" disabled={busy} onClick={() => reroll(r.key)}>
                {r.label}
              </button>
            ))}
            <button type="button" className="blindbox-chip button subtle" onClick={() => setAskReason(false)}>算了</button>
          </div>
        </div>
      )}

      {history?.length > 0 && (
        <div className="blindbox-history">
          <div className="blindbox-hint-label">過去的盒子</div>
          <ul>
            {history.map((h) => (
              <li key={h.id}>
                <span className="wk">{fmtDay(h.day_key)}</span>
                <span className={`st st-${h.status}`}>{STATUS_LABEL[h.status]}</span>
                <span className="nm">{h.cafe_name || '（沒拆開）'}</span>
                {h.cafe_id && <WantTag cafeId={h.cafe_id} />}
                {h.rating && <span className="rt">{'★'.repeat(h.rating)}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
