import { useState } from 'react';
import { Star } from 'lucide-react';

/** 唯讀星等（可顯示小數，例如 4.5 → 四顆半） */
export function StarDisplay({ value, size = 14 }) {
  const rounded = Math.round((Number(value) || 0) * 2) / 2;
  return (
    <span className="stars" role="img" aria-label={`${value ?? 0} 顆星`}>
      {[1, 2, 3, 4, 5].map((n) => {
        const fill = rounded >= n ? 'full' : rounded >= n - 0.5 ? 'half' : 'empty';
        return (
          <span key={n} className={`star star-${fill}`} style={{ width: size, height: size }}>
            <Star size={size} aria-hidden="true" />
            {fill !== 'empty' && <Star size={size} className="star-fill" fill="currentColor" aria-hidden="true" />}
          </span>
        );
      })}
    </span>
  );
}

const LABELS = ['', '很失望', '普通偏差', '還可以', '很不錯', '超推薦'];

/** 評分輸入：一組 radio，鍵盤方向鍵也能選 */
export function StarInput({ value, onChange, size = 28, name = 'rating' }) {
  const [hover, setHover] = useState(0);
  const shown = hover || value;
  return (
    <div className="star-input" onMouseLeave={() => setHover(0)}>
      <div role="radiogroup" aria-label="評分" className="star-input-row">
        {[1, 2, 3, 4, 5].map((n) => (
          <label
            key={n}
            className={`star-input-star ${shown >= n ? 'on' : ''}`}
            onMouseEnter={() => setHover(n)}
          >
            <input
              type="radio"
              name={name}
              value={n}
              checked={value === n}
              onChange={() => onChange(n)}
              className="sr-only"
            />
            <Star size={size} fill={shown >= n ? 'currentColor' : 'none'} aria-hidden="true" />
            <span className="sr-only">{n} 顆星</span>
          </label>
        ))}
      </div>
      <span className="star-input-label" aria-hidden="true">{LABELS[shown] || '點星星評分'}</span>
    </div>
  );
}
