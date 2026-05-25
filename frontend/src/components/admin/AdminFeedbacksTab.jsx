import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

export default function AdminFeedbacksTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [feedbacks, setFeedbacks] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchFeedbacks();
  }, []);

  const fetchFeedbacks = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/feedbacks`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setFeedbacks(data.feedbacks || []);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  return (
    <>
      {loading ? <div className="admin-loading">載入中</div> : (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>使用者</th>
                <th>評價</th>
                <th>使用者問題</th>
                <th>AI 回覆</th>
                <th>時間</th>
              </tr>
            </thead>
            <tbody>
              {feedbacks.length === 0 ? (
                <tr><td colSpan="6" style={{textAlign:'center',padding:'40px',color:'#999'}}>尚無反饋紀錄</td></tr>
              ) : feedbacks.map(f => (
                <tr key={f.id}>
                  <td>{f.id}</td>
                  <td>{f.user}</td>
                  <td style={{fontSize:'1.2rem'}}>{f.feedback_type === 'like' ? '👍' : '👎'}</td>
                  <td style={{maxWidth:'200px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={f.user_message}>{f.user_message}</td>
                  <td style={{maxWidth:'300px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={f.ai_response}>{f.ai_response}</td>
                  <td>{f.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
