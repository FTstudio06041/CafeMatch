import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'framer-motion';
import { Bookmark, Coffee, MapPin, RotateCcw, X } from 'lucide-react';
import { apiClient } from '../../utils/apiClient';
import { setWant } from '../../utils/shopState';
import { toast } from '../../utils/toast';
import { SWIPE_UI_TEXTS as T } from '../../utils/constants';

// 拖超過這個距離（px）或甩得夠快（px/s）就算滑出去
const SWIPE_DISTANCE = 110;
const SWIPE_VELOCITY = 600;
// 手上剩幾張時先跟後端要下一批
const REFILL_AT = 3;

/**
 * 護照頁的滑卡。隨機出還沒滑過、沒去過、不在想去清單的店。
 * 右滑 → 加進想去清單；左滑 → 沒興趣（不會進盲盒）。
 * 拖曳、按鈕、鍵盤 ← → 三種操作都可以。
 *
 * onWantChange：想去清單有變動時通知護照頁重抓。
 */
export default function SwipeDeck({ onWantChange }) {
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();
  const [cards, setCards] = useState([]);
  const [remaining, setRemaining] = useState(0);
  const [passed, setPassed] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [canUndo, setCanUndo] = useState(false);
  const [leaving, setLeaving] = useState(false);
  // 送出中的滑動：要等它們都寫進後端，再跟後端要下一批，否則剛滑掉的會又發回來
  const pending = useRef(Promise.resolve());
  const fetching = useRef(false);
  // 這次已經滑過的店：補牌時就算後端還沒寫進去，也不能再發回來
  const swiped = useRef(new Set());

  const x = useMotionValue(0);
  const rotate = useTransform(x, [-240, 240], [-14, 14]);
  const wantOpacity = useTransform(x, [20, SWIPE_DISTANCE], [0, 1]);
  const passOpacity = useTransform(x, [-SWIPE_DISTANCE, -20], [1, 0]);

  /** replace=true：整副重抓（第一次、重新看略過的）；否則補在手上的牌後面 */
  const loadDeck = useCallback(async ({ replace = false } = {}) => {
    if (fetching.current) return;
    fetching.current = true;
    try {
      await pending.current;
      const data = await apiClient('/api/swipe/deck', { suppressToast: true });
      const fresh = (data.cards || []).filter((c) => !swiped.current.has(c.cafe_id));
      setCards((cs) => {
        if (replace) return fresh;
        const held = new Set(cs.map((c) => c.cafe_id));
        return [...cs, ...fresh.filter((c) => !held.has(c.cafe_id))];
      });
      if (replace) {
        setRemaining(data.remaining ?? 0);
        setPassed(data.passed ?? 0);
      }
    } catch {
      // 牌堆抓不到就顯示空的，不擋整個護照頁
    } finally {
      fetching.current = false;
      setLoaded(true);
    }
  }, []);

  useEffect(() => { loadDeck({ replace: true }); }, [loadDeck]);

  const top = cards[0];

  const commit = useCallback(async (direction) => {
    if (!top || leaving) return;
    setLeaving(true);
    const card = top;
    swiped.current.add(card.cafe_id);
    if (!reduceMotion) {
      await animate(x, direction === 'right' ? 520 : -520, { duration: 0.22, ease: 'easeIn' });
    }
    const rest = cards.slice(1);
    setCards((cs) => cs.filter((c) => c.cafe_id !== card.cafe_id));
    setRemaining((n) => Math.max(0, n - 1));
    if (direction === 'left') setPassed((n) => n + 1);
    x.set(0);
    setLeaving(false);
    setCanUndo(true);
    if (direction === 'right') setWant(card.cafe_id, true);

    const req = apiClient('/api/swipe', {
      method: 'POST',
      body: JSON.stringify({ cafe_id: card.cafe_id, direction }),
    }).then(() => {
      if (direction === 'right') onWantChange?.();
    }).catch(() => {
      // 沒寫進去：把卡放回最上面，狀態也還原（apiClient 已經跳錯誤提示）
      swiped.current.delete(card.cafe_id);
      setCards((cs) => [card, ...cs.filter((c) => c.cafe_id !== card.cafe_id)]);
      setRemaining((n) => n + 1);
      if (direction === 'left') setPassed((n) => Math.max(0, n - 1));
      if (direction === 'right') setWant(card.cafe_id, false);
    });
    pending.current = pending.current.then(() => req);

    if (rest.length <= REFILL_AT) loadDeck();
  }, [top, leaving, reduceMotion, x, cards, onWantChange, loadDeck]);

  const undo = async () => {
    if (leaving) return;
    setLeaving(true);
    try {
      await pending.current;
      const data = await apiClient('/api/swipe/undo', { method: 'POST' });
      const card = data.card;
      swiped.current.delete(card.cafe_id);
      setCards((cs) => [card, ...cs.filter((c) => c.cafe_id !== card.cafe_id)]);
      setRemaining((n) => n + 1);
      if (data.direction === 'left') setPassed((n) => Math.max(0, n - 1));
      if (data.direction === 'right') {
        setWant(card.cafe_id, false);
        onWantChange?.();
      }
      x.set(data.direction === 'right' ? 320 : -320);
      if (!reduceMotion) animate(x, 0, { type: 'spring', stiffness: 400, damping: 32 });
      else x.set(0);
    } catch {
      setCanUndo(false);
    } finally {
      setLeaving(false);
    }
  };

  const resetPassed = async () => {
    try {
      const data = await apiClient('/api/swipe/reset', { method: 'POST' });
      toast.info(T.resetDone(data.restored));
      setCanUndo(false);
      setLoaded(false);
      swiped.current = new Set();
      await loadDeck({ replace: true });
    } catch {
      // apiClient 已經跳錯誤提示
    }
  };

  const onDragEnd = (_, info) => {
    const { offset, velocity } = info;
    if (offset.x > SWIPE_DISTANCE || velocity.x > SWIPE_VELOCITY) commit('right');
    else if (offset.x < -SWIPE_DISTANCE || velocity.x < -SWIPE_VELOCITY) commit('left');
    else animate(x, 0, { type: 'spring', stiffness: 500, damping: 30 });
  };

  const onKeyDown = (e) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); commit('right'); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); commit('left'); }
  };

  return (
    <div className="swipe">
      <div
        className="swipe-stack"
        tabIndex={top ? 0 : -1}
        onKeyDown={onKeyDown}
        aria-label={top ? `${top.name}。${T.keyboardHint}` : undefined}
      >
        {!loaded && <div className="swipe-empty">{T.loading}</div>}

        {loaded && !top && (
          <div className="swipe-empty">
            <Coffee size={32} strokeWidth={1.5} />
            <strong>{T.doneTitle}</strong>
            <span>{T.doneBody}</span>
            {passed > 0 && (
              <button type="button" className="pp-btn" onClick={resetPassed}>
                <RotateCcw size={14} /> {T.resetPassed(passed)}
              </button>
            )}
          </div>
        )}

        {/* 下一張墊在底下，滑走時才不會一片空白 */}
        {cards[1] && <SwipeCard key={cards[1].cafe_id} card={cards[1]} under />}

        {top && (
          <motion.div
            key={top.cafe_id}
            className="swipe-card-wrap"
            style={{ x, rotate }}
            drag={leaving ? false : 'x'}
            dragElastic={0.9}
            dragMomentum={false}
            onDragEnd={onDragEnd}
            whileDrag={{ cursor: 'grabbing' }}
          >
            <SwipeCard
              card={top}
              onInfo={() => navigate(`/explore?open_shop_id=${top.cafe_id}`)}
            />
            <motion.div className="swipe-stamp want" style={{ opacity: wantOpacity }} aria-hidden="true">{T.want}</motion.div>
            <motion.div className="swipe-stamp pass" style={{ opacity: passOpacity }} aria-hidden="true">{T.pass}</motion.div>
          </motion.div>
        )}
      </div>

      <div className="swipe-controls">
        <button type="button" className="swipe-btn pass" onClick={() => commit('left')} disabled={!top || leaving} aria-label={T.pass}>
          <X size={26} strokeWidth={2.5} />
        </button>
        <button type="button" className="swipe-btn undo" onClick={undo} disabled={!canUndo || leaving} aria-label={T.undo} title={T.undo}>
          <RotateCcw size={18} />
        </button>
        <button type="button" className="swipe-btn want" onClick={() => commit('right')} disabled={!top || leaving} aria-label={T.want}>
          <Bookmark size={24} strokeWidth={2.5} />
        </button>
      </div>
      <div className="swipe-meta">
        {top && <span>{T.remaining(remaining)}</span>}
        {top && <span className="swipe-meta-keys"> · {T.keyboardHint}</span>}
      </div>
    </div>
  );
}

function SwipeCard({ card, under = false, onInfo }) {
  const [imgError, setImgError] = useState(false);
  return (
    <div className={`swipe-card ${under ? 'under' : ''}`} aria-hidden={under || undefined}>
      <div className="swipe-card-img">
        {card.image_url && !imgError
          ? <img src={card.image_url} alt="" draggable={false} onError={() => setImgError(true)} />
          : <Coffee size={36} strokeWidth={1.5} />}
      </div>
      <div className="swipe-card-body">
        <div className="swipe-card-name">{card.name}</div>
        <div className="swipe-card-meta">
          {card.area && <span><MapPin size={12} /> {card.area}</span>}
          {card.cost && <span>{card.cost}</span>}
        </div>
        {card.tags?.length > 0 && (
          <div className="swipe-card-tags">
            {card.tags.map((t) => <span key={t} className="blindbox-chip">#{t}</span>)}
          </div>
        )}
        {onInfo && (
          <button
            type="button"
            className="swipe-card-info"
            // 拖曳時不要被當成點擊
            onPointerDown={(e) => e.stopPropagation()}
            onClick={onInfo}
          >
            {T.moreInfo}
          </button>
        )}
      </div>
    </div>
  );
}
