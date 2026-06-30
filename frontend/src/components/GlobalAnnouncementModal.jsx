import { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from '../context/AuthContext';

import { logger } from '../utils/logger';
export default function GlobalAnnouncementModal() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const [announcement, setAnnouncement] = useState(null);
  const [showAnnouncement, setShowAnnouncement] = useState(false);

  const checkAnnouncement = useCallback(async () => {
    // 防衝突機制：如果當前 URL 包含 welcome=true 參數（新用戶初次歡迎小卡），先不跳出系統公告
    const params = new URLSearchParams(window.location.search);
    if (params.get('welcome') === 'true') {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/announcements/latest`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        if (data.show_popup && data.announcement) {
          setAnnouncement(data.announcement);
          setShowAnnouncement(true);
        }
      }
    } catch (e) {
      logger.error('檢查公告失敗:', e);
    }
    }, [API_BASE_URL]);

  useEffect(() => {
    if (user) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      checkAnnouncement();
    } else {
      setShowAnnouncement(false);
      setAnnouncement(null);
    }
  }, [user, checkAnnouncement]);

  const handleCloseAnnouncement = async () => {
    setShowAnnouncement(false);
    if (announcement) {
      try {
        await fetch(`${API_BASE_URL}/api/announcements/read`, {
          method: 'POST',
          credentials: 'include',
        });
      } catch (e) {
        logger.error('標記公告已讀失敗:', e);
      }
    }
  };

  const formatLocalTime = (timeStr) => {
    if (!timeStr) return '';
    let utcStr = timeStr.replace(' ', 'T');
    if (utcStr.length === 16) utcStr += ':00';
    if (!utcStr.endsWith('Z')) utcStr += 'Z';
    const d = new Date(utcStr);
    
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
  };

  if (!showAnnouncement || !announcement) return null;

  return (
    <div className="announcement-global-overlay">
      <div className="announcement-global-modal">
        <div className="announcement-global-header">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
          </svg>
          <h3>系統最新消息公告</h3>
        </div>
        <div className="announcement-global-body">
          {announcement.content}
        </div>
        <div className="announcement-global-footer">
          <span className="announcement-global-time">發布於 {formatLocalTime(announcement.created_at)}</span>
          <button className="announcement-global-btn" onClick={handleCloseAnnouncement}>
            我知道了
          </button>
        </div>
      </div>
    </div>
  );
}
