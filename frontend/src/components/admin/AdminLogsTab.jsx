import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

import { logger } from '../../utils/logger';
export default function AdminLogsTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [logs, setLogs] = useState({ logs: [], total: 0, pages: 1, current_page: 1 });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchLogs(1);
  }, []);

  const fetchLogs = async (page) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/logs?page=${page}&per_page=30`, { credentials: 'include' });
      if (res.ok) setLogs(await res.json());
    } catch (e) { logger.error(e); }
    setLoading(false);
  };

  return (
    <>
      {loading ? <div className="admin-loading">載入中</div> : (
        <div className="log-container">
          <div className="log-toolbar">
            <span style={{fontWeight:600,color:'var(--admin-accent)'}}>共 {logs.total} 筆記錄</span>
            <button className="admin-btn secondary" onClick={() => fetchLogs(logs.current_page)}>
              重新整理
            </button>
          </div>
          {logs.logs.length === 0 ? (
            <div className="admin-empty">尚無 Log 記錄</div>
          ) : logs.logs.map(l => (
            <div key={l.id} className="log-entry">
              <span className="log-time">{l.created_at}</span>
              <span className="log-action">{l.action}</span>
              <span className="log-email">{l.user_email}</span>
              <span className="log-detail">{l.detail}</span>
            </div>
          ))}
          {logs.pages > 1 && (
            <div className="pagination">
              <button disabled={logs.current_page <= 1} onClick={() => fetchLogs(logs.current_page - 1)}>上一頁</button>
              <span>{logs.current_page} / {logs.pages}</span>
              <button disabled={logs.current_page >= logs.pages} onClick={() => fetchLogs(logs.current_page + 1)}>下一頁</button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
