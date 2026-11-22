import { useCallback, useEffect, useState } from 'react';
import { Heart, MessageCircle, Pencil, Trash2 } from 'lucide-react';
import { cafeService } from '../../services/cafeService';
import { formatTime } from '../../utils/formatters';
import { logger } from '../../utils/logger';
import { toast } from '../../utils/toast';
import { StarDisplay, StarInput } from './Stars';

const REVIEW_MAX = 1000;
const COMMENT_MAX = 300;

function Avatar({ author }) {
  return (
    <span className="review-avatar" aria-hidden="true">
      {author.picture ? <img src={author.picture} alt="" /> : (author.name || '?').charAt(0)}
    </span>
  );
}

function Comments({ review, user, onCountChange }) {
  const [comments, setComments] = useState(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    cafeService.fetchComments(review.id)
      .then((data) => { if (alive) setComments(data?.comments || []); })
      .catch((err) => logger.error('載入留言失敗:', err));
    return () => { alive = false; };
  }, [review.id]);

  const submit = async (e) => {
    e.preventDefault();
    const value = text.trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      const data = await cafeService.addComment(review.id, value);
      if (data?.comment) {
        const next = [...(comments || []), data.comment];
        setComments(next);
        onCountChange(next.length);
        setText('');
      }
    } catch (err) {
      logger.error('留言失敗:', err);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (comment) => {
    try {
      await cafeService.deleteComment(review.id, comment.id);
      const next = comments.filter((c) => c.id !== comment.id);
      setComments(next);
      onCountChange(next.length);
    } catch (err) {
      logger.error('刪除留言失敗:', err);
    }
  };

  return (
    <div className="review-comments">
      {comments === null ? (
        <p className="detail-muted">載入中…</p>
      ) : (
        comments.map((c) => (
          <div key={c.id} className="review-comment">
            <Avatar author={c.author} />
            <div className="review-comment-body">
              <span className="review-comment-name">{c.author.name}</span>
              <span className="review-comment-time">{formatTime(c.created_at)}</span>
              <p>{c.content}</p>
            </div>
            {(c.is_mine || user?.is_admin) && (
              <button type="button" className="mini-icon-btn" onClick={() => remove(c)} aria-label="刪除這則留言">
                <Trash2 size={14} />
              </button>
            )}
          </div>
        ))
      )}
      {user && (
        <form className="inline-form" onSubmit={submit}>
          <label htmlFor={`comment-${review.id}`} className="sr-only">回覆這則評論</label>
          <input
            id={`comment-${review.id}`}
            type="text"
            value={text}
            maxLength={COMMENT_MAX}
            placeholder="回覆這則評論…"
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={!text.trim() || busy}>回覆</button>
        </form>
      )}
    </div>
  );
}

function ReviewItem({ review, user, onChange, onEdit, onDelete }) {
  const [showComments, setShowComments] = useState(false);

  const like = async () => {
    if (!user) {
      toast.info('登入後才能按讚');
      return;
    }
    try {
      const data = await cafeService.toggleReviewLike(review.id);
      onChange({ ...review, is_liked: data.liked, like_count: data.like_count });
    } catch (err) {
      logger.error('按讚失敗:', err);
    }
  };

  return (
    <article className={`review-item ${review.is_mine ? 'mine' : ''}`}>
      <header className="review-head">
        <Avatar author={review.author} />
        <div className="review-who">
          <span className="review-name">{review.is_mine ? '你的評論' : review.author.name}</span>
          <span className="review-when">
            <StarDisplay value={review.rating} size={13} />
            {formatTime(review.created_at)}{review.updated_at ? '（已編輯）' : ''}
          </span>
        </div>
        {review.is_mine && (
          <button type="button" className="mini-icon-btn" onClick={onEdit} aria-label="編輯我的評論">
            <Pencil size={15} />
          </button>
        )}
        {(review.is_mine || user?.is_admin) && (
          <button type="button" className="mini-icon-btn" onClick={() => onDelete(review)} aria-label="刪除這則評論">
            <Trash2 size={15} />
          </button>
        )}
      </header>
      {review.content && <p className="review-text">{review.content}</p>}
      <div className="review-actions">
        <button type="button" className={`review-action ${review.is_liked ? 'on' : ''}`} onClick={like} aria-pressed={review.is_liked}>
          <Heart size={15} fill={review.is_liked ? 'currentColor' : 'none'} aria-hidden="true" />
          {review.like_count > 0 ? review.like_count : '讚'}
        </button>
        <button
          type="button"
          className="review-action"
          onClick={() => setShowComments((v) => !v)}
          aria-expanded={showComments}
        >
          <MessageCircle size={15} aria-hidden="true" />
          {review.comment_count > 0 ? `${review.comment_count} 則回覆` : '回覆'}
        </button>
      </div>
      {showComments && (
        <Comments
          review={review}
          user={user}
          onCountChange={(count) => onChange({ ...review, comment_count: count })}
        />
      )}
    </article>
  );
}

function Distribution({ summary }) {
  if (!summary.count) return null;
  return (
    <div className="review-dist" aria-label="本站評分分布">
      {[5, 4, 3, 2, 1].map((star) => {
        const n = summary.distribution[String(star)] || 0;
        return (
          <div key={star} className="review-dist-row">
            <span>{star}</span>
            <span className="review-dist-track"><span style={{ width: `${(n / summary.count) * 100}%` }} /></span>
            <span className="review-dist-n">{n}</span>
          </div>
        );
      })}
    </div>
  );
}

/** 評論分頁：評論即社群——每人每店一則星等評論，其他人按讚、回覆 */
export default function CafeReviewsTab({ cafe, user, onLogin, onStatsChange }) {
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(0);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (nextPage = 1) => {
    try {
      const res = await cafeService.fetchReviews(cafe.id, nextPage);
      setData((prev) => (nextPage === 1 || !prev ? res : { ...res, reviews: [...prev.reviews, ...res.reviews] }));
      setPage(nextPage);
    } catch (err) {
      logger.error('載入評論失敗:', err);
    }
  }, [cafe.id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(1);
  }, [load]);

  const startEdit = () => {
    setRating(data?.my_review?.rating || 0);
    setText(data?.my_review?.content || '');
    setEditing(true);
  };

  const save = async (e) => {
    e.preventDefault();
    if (!rating) {
      toast.info('請先選擇星等');
      return;
    }
    setBusy(true);
    try {
      const res = await cafeService.saveReview(cafe.id, rating, text.trim());
      if (res?.review) {
        setData((prev) => ({ ...prev, my_review: res.review, summary: res.summary }));
        onStatsChange({ rating: res.summary.average, review_count: res.summary.count });
        setEditing(false);
        toast.success('評論已送出');
      }
    } catch (err) {
      logger.error('送出評論失敗:', err);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (review) => {
    if (!window.confirm('確定要刪除這則評論嗎？底下的回覆也會一起刪除。')) return;
    try {
      await cafeService.deleteReview(review.id);
      const res = await cafeService.fetchReviews(cafe.id, 1);
      setData(res);
      setPage(1);
      onStatsChange({ rating: res.summary.average, review_count: res.summary.count });
    } catch (err) {
      logger.error('刪除評論失敗:', err);
    }
  };

  const replaceReview = (updated) => {
    setData((prev) => {
      if (prev.my_review?.id === updated.id) return { ...prev, my_review: updated };
      return { ...prev, reviews: prev.reviews.map((r) => (r.id === updated.id ? updated : r)) };
    });
  };

  if (!data) return <p className="detail-muted detail-pad">載入評論中…</p>;

  const { summary, my_review: mine, reviews } = data;
  const showComposer = user && (!mine || editing);

  return (
    <div className="reviews-tab">
      {summary.count > 0 ? (
        <div className="review-summary">
          <div className="review-summary-score">
            <span className="review-summary-big">{summary.average.toFixed(1)}</span>
            <StarDisplay value={summary.average} size={16} />
            <span className="detail-muted">本站 {summary.count} 則評論</span>
          </div>
          <Distribution summary={summary} />
          {cafe.google_rating != null && (
            <p className="review-google">
              Google 地圖評價 {cafe.google_rating.toFixed(1)} ★（{cafe.google_review_count.toLocaleString()} 則）
            </p>
          )}
        </div>
      ) : (
        <p className="review-empty-summary">
          本站還沒有人評論這家店
          {cafe.google_rating != null && `；Google 地圖上是 ${cafe.google_rating.toFixed(1)} ★（${cafe.google_review_count.toLocaleString()} 則）`}
        </p>
      )}

      {showComposer && (
        <form className="review-composer" onSubmit={save}>
          <StarInput value={rating} onChange={setRating} />
          <label htmlFor="review-text" className="sr-only">評論內容</label>
          <textarea
            id="review-text"
            rows={3}
            maxLength={REVIEW_MAX}
            value={text}
            placeholder="分享你的體驗：座位、插座、飲料、氣氛…（可不填）"
            onChange={(e) => setText(e.target.value)}
          />
          <div className="review-composer-actions">
            <span className="detail-muted">{text.length}/{REVIEW_MAX}</span>
            {editing && <button type="button" className="btn-secondary" onClick={() => setEditing(false)}>取消</button>}
            <button type="submit" className="btn-primary" disabled={busy || !rating}>
              {mine ? '更新評論' : '送出評論'}
            </button>
          </div>
        </form>
      )}

      {!user && (
        <button type="button" className="detail-login-hint" onClick={onLogin}>登入後就能留下評論、按讚和回覆</button>
      )}

      {mine && !editing && (
        <ReviewItem review={mine} user={user} onChange={replaceReview} onEdit={startEdit} onDelete={remove} />
      )}

      {reviews.length === 0 && !mine ? (
        user && <p className="detail-muted detail-pad">來當第一個留下評論的人吧！</p>
      ) : (
        reviews.map((r) => (
          <ReviewItem key={r.id} review={r} user={user} onChange={replaceReview} onEdit={startEdit} onDelete={remove} />
        ))
      )}

      {page < data.pages && (
        <button type="button" className="btn-secondary review-more" onClick={() => load(page + 1)}>載入更多評論</button>
      )}
    </div>
  );
}
