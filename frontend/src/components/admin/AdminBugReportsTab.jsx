import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

export default function AdminBugReportsTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [bugReports, setBugReports] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchBugReports();
  }, []);

  const fetchBugReports = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/bug_reports`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setBugReports(data.reports || []);
      }
    } catch (e) {
      console.error('載入 Bug 回報失敗:', e);
    }
    setLoading(false);
  };

  const deleteBugReport = async (reportId) => {
    if (!confirm('確定要刪除/標記處理此回報嗎？此操作會將其移出列表。')) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/bug_reports/${reportId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      if (res.ok) {
        fetchBugReports();
      } else {
        alert('刪除失敗');
      }
    } catch (e) {
      console.error('刪除 Bug 失敗:', e);
    }
  };

  return (
    <>
      <div className="admin-stats">
        <div className="stat-card">
          <div className="stat-label">未處理解決數</div>
          <div className="stat-value">{bugReports.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Bug 程式出錯</div>
          <div className="stat-value">{bugReports.filter(r => r.report_type === 'bug').length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">功能意見建議</div>
          <div className="stat-value">{bugReports.filter(r => r.report_type === 'suggest').length}</div>
        </div>
      </div>

      {loading ? <div className="admin-loading">載入中</div> : (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{width:'60px'}}>ID</th>
                <th style={{width:'120px'}}>類型</th>
                <th>回報內容</th>
                <th style={{width:'150px'}}>回報者</th>
                <th style={{width:'150px'}}>回報時間</th>
                <th style={{width:'120px'}}>操作</th>
              </tr>
            </thead>
            <tbody>
              {bugReports.length === 0 ? (
                <tr><td colSpan="6" style={{textAlign:'center',padding:'40px',color:'#999'}}>尚無未處理的 Bug 回報</td></tr>
              ) : bugReports.map(r => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>
                    <span className={`role-badge ${r.report_type === 'bug' ? 'admin' : 'user'}`} style={{fontSize:'0.75rem'}}>
                      {r.report_type === 'bug' ? '🐞 程式出錯' : '💡 意見建議'}
                    </span>
                  </td>
                  <td style={{whiteSpace:'pre-wrap',lineHeight:1.5,fontSize:'0.9rem'}}>{r.content}</td>
                  <td>
                    <div style={{fontWeight:600}}>{r.user_name}</div>
                    <div style={{fontSize:'0.75rem',color:'#888'}}>{r.user_email}</div>
                  </td>
                  <td>{r.created_at}</td>
                  <td>
                    <button className="admin-btn success" onClick={() => deleteBugReport(r.id)}>
                      已處理解決
                    </button>
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
