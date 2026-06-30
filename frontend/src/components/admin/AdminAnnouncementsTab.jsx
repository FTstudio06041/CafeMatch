import { useState, useEffect, useContext, useCallback } from 'react';
import { AuthContext } from '../../context/AuthContext';

import { toast } from '../../utils/toast';
import { logger } from '../../utils/logger';
export default function AdminAnnouncementsTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [announcements, setAnnouncements] = useState([]);
  const [announcementText, setAnnouncementText] = useState('');
  const [loading, setLoading] = useState(false);

  const fetchAnnouncements = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/announcements`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAnnouncements(data.announcements || []);
      }
    } catch (e) {
      logger.error('載入公告失敗:', e);
    }
    setLoading(false);
    }, [API_BASE_URL]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchAnnouncements();
  }, [fetchAnnouncements]);

  const publishAnnouncement = async () => {
    if (!announcementText.trim()) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/announcements`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: announcementText.trim() }),
      });
      if (res.ok) {
        setAnnouncementText('');
        fetchAnnouncements();
        toast.info('公告發布成功！');
      } else {
        const data = await res.json();
        toast.info(data.message || '發布失敗');
      }
    } catch (e) {
      logger.error('發布公告失敗:', e);
    }
  };

  const deleteAnnouncement = async (annId) => {
    if (!confirm('確定要刪除此公告嗎？')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/announcements/${annId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) {
        fetchAnnouncements();
      } else {
        toast.info('刪除失敗');
      }
    } catch (e) {
      logger.error('刪除公告失敗:', e);
    }
  };

  return (
    <>
      <div className="announcement-manage-card">
        <div style={{fontWeight:700,color:'var(--admin-accent)',marginBottom:'12px',fontSize:'1.05rem'}}>發布全新消息公告</div>
        <textarea
          className="announcement-textarea"
          placeholder="輸入您想向所有使用者公布的最新消息..."
          value={announcementText}
          onChange={e => setAnnouncementText(e.target.value)}
          maxLength={1000}
          rows={5}
        />
        <div style={{textAlign:'right',marginTop:'10px'}}>
          <button
            className="admin-btn primary"
            onClick={publishAnnouncement}
            disabled={!announcementText.trim()}
          >
            立即發布公告
          </button>
        </div>
      </div>

      <div style={{fontWeight:700,color:'var(--admin-accent)',marginTop:'28px',marginBottom:'12px',fontSize:'1.05rem'}}>歷史發布公告</div>
      {loading ? <div className="admin-loading">載入中</div> : (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{width:'80px'}}>ID</th>
                <th>公告內容</th>
                <th style={{width:'180px'}}>發布時間</th>
                <th style={{width:'100px'}}>操作</th>
              </tr>
            </thead>
            <tbody>
              {announcements.length === 0 ? (
                <tr><td colSpan="4" style={{textAlign:'center',padding:'40px',color:'#999'}}>尚無發布公告紀錄</td></tr>
              ) : announcements.map(a => (
                <tr key={a.id}>
                  <td>{a.id}</td>
                  <td style={{whiteSpace:'pre-wrap',lineHeight:1.5,fontSize:'0.92rem'}}>{a.content}</td>
                  <td>{a.created_at}</td>
                  <td>
                    <button className="admin-btn danger" onClick={() => deleteAnnouncement(a.id)}>刪除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
