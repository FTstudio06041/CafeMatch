import { useState } from 'react';
import { Coffee } from 'lucide-react';
import './CafePhoto.css';

/**
 * 店家照片的來源順序：
 *   1. 後台手動設定的 cafes.image
 *   2. 專案內建的 /cafes/<id>.jpg（scripts/sync_cafe_photos.py 同步進來的）
 *   3. Google 照片（每張都要打一次付費 API，所以排最後）
 * 全部失敗就顯示店家色塊。
 */
function photoSources(cafe) {
  const sources = [cafe.image, `/cafes/${cafe.id}.jpg`];
  if (cafe.image_source === 'google' && cafe.image_url) sources.push(cafe.image_url);
  return [...new Set(sources.filter(Boolean))];
}

export default function CafePhoto({ cafe, className = '', alt, eager = false, style }) {
  const sources = photoSources(cafe);
  // 換店家時從頭試；以 cafe.id 當 key 的一部分，避免沿用上一家的失敗進度
  const [failed, setFailed] = useState({ id: cafe.id, count: 0 });
  const count = failed.id === cafe.id ? failed.count : 0;
  const src = sources[count];

  return (
    <div className={`cafe-photo ${className}`} style={{ backgroundColor: cafe.color, ...style }}>
      {src ? (
        <img
          key={src}
          src={src}
          alt={alt ?? cafe.name}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          onError={() => setFailed({ id: cafe.id, count: count + 1 })}
        />
      ) : (
        <Coffee className="cafe-photo-fallback" size={28} aria-hidden="true" />
      )}
    </div>
  );
}
