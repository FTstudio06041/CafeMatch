import { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';

import { toast } from '../utils/toast';
import { logger } from '../utils/logger';
export default function CafeCard({ cafe }) {
  const { user, API_BASE_URL } = useContext(AuthContext);
  // 使用本地狀態來達到即時 UI 更新 (Optimistic UI update)
  const [isFav, setIsFav] = useState(cafe.is_fav);
  const [isVisited, setIsVisited] = useState(cafe.is_visited);

  const toggleState = async (type) => {
    if (!user || user.isGuest) {
      toast.info("請先登入才能使用此功能！");
      return;
    }

    // 先切換本地狀態，讓使用者感覺反應很快
    if (type === 'fav') setIsFav(!isFav);
    if (type === 'visited') setIsVisited(!isVisited);

    try {
      const response = await fetch(`${API_BASE_URL}/api/user/shop_state`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ cafe_id: cafe.id, type: type }),
      });
      const data = await response.json();
      
      // 若後端更新失敗，再把狀態還原
      if (!data.success) {
        if (type === 'fav') setIsFav(!isFav);
        if (type === 'visited') setIsVisited(!isVisited);
        logger.error("更新失敗", data.message);
      }
    } catch (error) {
      logger.error('Error updating state:', error);
    }
  };

  return (
    <div style={{ ...styles.card, borderTop: `4px solid ${cafe.color}` }}>
      <h3>{cafe.name}</h3>
      <p style={{ fontSize: '0.9rem', color: '#666' }}>{cafe.tags}</p>
      <p>🕒 {cafe.hours}</p>
      <p>📍 {cafe.address}</p>
      
      <div style={styles.actions}>
        <button 
          style={{ ...styles.actionBtn, color: isFav ? 'red' : 'gray' }}
          onClick={() => toggleState('fav')}
        >
          {isFav ? '❤️ 已收藏' : '🤍 收藏'}
        </button>
        <button 
          style={{ ...styles.actionBtn, color: isVisited ? 'green' : 'gray' }}
          onClick={() => toggleState('visited')}
        >
          {isVisited ? '✅ 已去過' : '✔️ 去過'}
        </button>
      </div>
    </div>
  );
}

const styles = {
  card: { border: '1px solid #ddd', borderRadius: '8px', padding: '15px', marginBottom: '15px', backgroundColor: 'white', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' },
  actions: { display: 'flex', gap: '10px', marginTop: '10px' },
  actionBtn: { background: 'none', border: '1px solid #ccc', padding: '5px 10px', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }
};