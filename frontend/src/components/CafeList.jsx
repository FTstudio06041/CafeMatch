import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import CafeCard from './CafeCard';

import { logger } from '../utils/logger';
export default function CafeList() {
  const [cafes, setCafes] = useState([]);
  const [loading, setLoading] = useState(true);
  const { API_BASE_URL, user } = useContext(AuthContext);

  useEffect(() => {
    fetchCafes();
  }, [user]); // 當 user 狀態改變(登入/登出)時，重新抓取以更新亮燈狀態

  const fetchCafes = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/cafes`, {
        credentials: 'include',
      });
      const data = await response.json();
      setCafes(data);
    } catch (error) {
      logger.error('Failed to fetch cafes:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div style={{ padding: '2rem' }}>載入中...</div>;

  return (
    <div style={{ padding: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
      {cafes.map(cafe => (
        <CafeCard key={cafe.id} cafe={cafe} />
      ))}
    </div>
  );
}