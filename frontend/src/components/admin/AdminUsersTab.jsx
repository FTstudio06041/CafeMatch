import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

export default function AdminUsersTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users`, { credentials: 'include' });
      if (res.ok) setUsers(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const toggleAdmin = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/toggle_admin`, {
        method: 'POST', credentials: 'include'
      });
      if (res.ok) fetchUsers();
      else { const d = await res.json(); alert(d.error); }
    } catch (e) { console.error(e); }
  };

  const deleteUser = async (userId, email) => {
    if (!confirm(`確定要刪除用戶 ${email}？此操作無法復原。`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
        method: 'DELETE', credentials: 'include'
      });
      if (res.ok) fetchUsers();
      else { const d = await res.json(); alert(d.error); }
    } catch (e) { console.error(e); }
  };

  const filteredUsers = users.filter(u =>
    u.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <>
      <div className="admin-stats">
        <div className="stat-card">
          <div className="stat-label">總用戶數</div>
          <div className="stat-value">{users.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">管理員數</div>
          <div className="stat-value">{users.filter(u => u.is_admin).length}</div>
        </div>
      </div>

      <div className="admin-search-bar">
        <input className="admin-search-input" placeholder="搜尋用戶名稱或 Email..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
      </div>

      {loading ? <div className="admin-loading">載入中</div> : (
        <div className="admin-table-wrapper">
          <table className="admin-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>名稱</th>
                <th>Email</th>
                <th>角色</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr><td colSpan="5" style={{textAlign:'center',padding:'40px',color:'#999'}}>無匹配結果</td></tr>
              ) : filteredUsers.map(u => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td style={{fontWeight:600}}>{u.name}</td>
                  <td>{u.email}</td>
                  <td>
                    <span className={`role-badge ${u.is_admin ? 'admin' : 'user'}`}>
                      {u.is_admin ? '管理員' : '一般用戶'}
                    </span>
                  </td>
                  <td>
                    <div className="admin-actions">
                      <button className={`admin-btn ${u.is_admin ? 'secondary' : 'success'}`} onClick={() => toggleAdmin(u.id)}>
                        {u.is_admin ? '取消管理員' : '設為管理員'}
                      </button>
                      <button className="admin-btn danger" onClick={() => deleteUser(u.id, u.email)}>刪除</button>
                    </div>
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
