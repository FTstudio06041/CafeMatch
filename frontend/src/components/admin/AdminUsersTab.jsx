import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

import { toast } from '../../utils/toast';
import { logger } from '../../utils/logger';
export default function AdminUsersTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setUsers(data);
        // 如果當前有選中的用戶，也同步更新他的狀態
        if (selectedUser) {
          const updatedUser = data.find(u => u.id === selectedUser.id);
          if (updatedUser) setSelectedUser(updatedUser);
          else setSelectedUser(null);
        }
      }
    } catch (e) { logger.error(e); }
    setLoading(false);
  };

  const toggleAdmin = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/admin`, {
        method: 'PUT', credentials: 'include'
      });
      if (res.ok) fetchUsers();
      else { const d = await res.json(); toast.info(d.error); }
    } catch (e) { logger.error(e); }
  };

  const deleteUser = async (userId, email) => {
    if (!window.confirm(`確定要刪除用戶 ${email}？此操作無法復原。`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users/${userId}`, {
        method: 'DELETE', credentials: 'include'
      });
      if (res.ok) {
        fetchUsers();
        setSelectedUser(null);
      }
      else { const d = await res.json(); toast.info(d.error); }
    } catch (e) { logger.error(e); }
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
                <th>名稱</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length === 0 ? (
                <tr><td colSpan="2" style={{textAlign:'center',padding:'40px',color:'#999'}}>無匹配結果</td></tr>
              ) : filteredUsers.map(u => (
                <tr key={u.id} onClick={() => setSelectedUser(u)} style={{cursor: 'pointer'}}>
                  <td style={{fontWeight:600}}>{u.name}</td>
                  <td>{u.email}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 用戶詳情 Modal */}
      <div className={`admin-modal-overlay ${selectedUser ? 'active' : ''}`} onClick={() => setSelectedUser(null)}>
        <div className="admin-modal" onClick={e => e.stopPropagation()}>
          {selectedUser && (
            <>
              <div className="admin-modal-title">用戶詳情</div>
              
              <div className="admin-form-group">
                <span className="admin-form-label">ID</span>
                <div style={{color: 'var(--admin-text)'}}>{selectedUser.id}</div>
              </div>
              <div className="admin-form-group">
                <span className="admin-form-label">名稱</span>
                <div style={{color: 'var(--admin-text)'}}>{selectedUser.name}</div>
              </div>
              <div className="admin-form-group">
                <span className="admin-form-label">Email</span>
                <div style={{color: 'var(--admin-text)'}}>{selectedUser.email}</div>
              </div>
              <div className="admin-form-group">
                <span className="admin-form-label">角色</span>
                <div>
                  <span className={`role-badge ${selectedUser.is_admin ? 'admin' : 'user'}`}>
                    {selectedUser.is_admin ? '管理員' : '一般用戶'}
                  </span>
                </div>
              </div>

              <div className="admin-modal-actions">
                <button className={`admin-btn ${selectedUser.is_admin ? 'secondary' : 'success'}`} onClick={() => toggleAdmin(selectedUser.id)}>
                  {selectedUser.is_admin ? '取消管理員' : '設為管理員'}
                </button>
                <button className="admin-btn danger" onClick={() => deleteUser(selectedUser.id, selectedUser.email)}>
                  刪除
                </button>
                <button className="admin-btn secondary" onClick={() => setSelectedUser(null)}>
                  關閉
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
