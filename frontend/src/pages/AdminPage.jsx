import React, { useState, useEffect, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import Navbar from '../components/Navbar';
import '../AdminPage.css';

export default function AdminPage() {
  const { user, API_BASE_URL } = useContext(AuthContext);
  const navigate = useNavigate();

  // --- Tab 狀態 ---
  const [activeTab, setActiveTab] = useState('users');

  // --- 各模組資料 ---
  const [users, setUsers] = useState([]);
  const [cafes, setCafes] = useState([]);
  const [logs, setLogs] = useState({ logs: [], total: 0, pages: 1, current_page: 1 });
  const [modelInfo, setModelInfo] = useState({ current_model: '', ollama_status: 'offline', installed_models: [] });

  // --- UI 狀態 ---
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingCafe, setEditingCafe] = useState(null);
  const [editForm, setEditForm] = useState({});

  // --- 側欄 ---
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [chats, setChats] = useState([]);

  useEffect(() => {
    const savedChats = JSON.parse(localStorage.getItem('allChats')) || [];
    setChats(savedChats);
  }, []);

  // --- 資料載入 ---
  useEffect(() => {
    if (activeTab === 'users') fetchUsers();
    if (activeTab === 'cafes') fetchCafes();
    if (activeTab === 'logs') fetchLogs(1);
    if (activeTab === 'model') fetchModel();
  }, [activeTab]);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/users`, { credentials: 'include' });
      if (res.ok) setUsers(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const fetchCafes = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/cafes`, { credentials: 'include' });
      if (res.ok) setCafes(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const fetchLogs = async (page) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/logs?page=${page}&per_page=30`, { credentials: 'include' });
      if (res.ok) setLogs(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const fetchModel = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/model`, { credentials: 'include' });
      if (res.ok) setModelInfo(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  // --- 用戶管理操作 ---
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

  const openEditCafe = (cafe) => {
    setEditingCafe(cafe);
    setEditForm({ name: cafe.name, address: cafe.address, phone: cafe.phone, website: cafe.website, cost: cafe.cost, image: cafe.image || '' });
  };

  const saveCafe = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/cafes/${editingCafe.id}`, {
        method: 'PUT', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm)
      });
      if (res.ok) { setEditingCafe(null); fetchCafes(); }
    } catch (e) { console.error(e); }
  };

  const deleteCafe = async (cafeId, name) => {
    if (!confirm(`確定要刪除店家「${name}」？此操作無法復原。`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/cafes/${cafeId}`, {
        method: 'DELETE', credentials: 'include'
      });
      if (res.ok) fetchCafes();
    } catch (e) { console.error(e); }
  };

  // --- 模型切換 ---
  const switchModel = async (modelName) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/model/switch`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      });
      if (res.ok) fetchModel();
    } catch (e) { console.error(e); }
  };

  // --- 搜尋過濾 ---
  const filteredUsers = users.filter(u =>
    u.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    u.email.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredCafes = cafes.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.address.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // --- 格式化檔案大小 ---
  const formatSize = (bytes) => {
    if (!bytes) return '未知';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  // --- 店家圖片上傳 ---
  const handleCafeImageUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      alert('圖片大小不可超過 5MB');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setEditForm(prev => ({ ...prev, image: reader.result }));
    };
    reader.readAsDataURL(file);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', width: '100%' }}>
      {/* --- 左側欄 --- */}
      <aside className={`sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <button className="toggle-sidebar-btn" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
        </button>
        <button className="user-profile-btn" onClick={() => navigate('/profile')} style={{ borderColor: 'var(--accent-color)', borderWidth: '2px', borderStyle: 'solid' }}>
          <div className="user-avatar" style={{ backgroundColor: user?.picture ? 'transparent' : 'var(--accent-color)' }}>
            {user?.picture ? <img src={user.picture} alt="avatar" style={{width: '100%', borderRadius: '50%'}} /> : 'U'}
          </div>
          <span className="user-name text-label">{user?.name}</span>
        </button>
        <button className="new-chat-btn" onClick={() => { localStorage.setItem('targetChatId', 'new'); navigate('/chat'); }}>
           <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
           <span className="text-label">新增對話</span>
        </button>
        <div className="history-label text-label">對話紀錄</div>
        <div className="chat-list">
           {chats.length === 0 ? <div className="empty-sidebar-msg">尚無對話紀錄</div> : 
             chats.map(chat => (
               <div key={chat.id} className="chat-item" onClick={() => {localStorage.setItem('targetChatId', chat.id); navigate('/chat');}}>
                 <div className="chat-icon"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></div>
                 <span className="chat-title text-label">{chat.title}</span>
               </div>
           ))}
        </div>
      </aside>

      {/* --- 主內容區 --- */}
      <main className="main-container">
        <nav className="navbar">
          <Navbar />
        </nav>

        <div className="admin-content">
          <div className="admin-page-title">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            管理後台
          </div>

          {/* Tab 切換 */}
          <div className="admin-tabs">
            {[
              { key: 'users', label: '用戶管理' },
              { key: 'cafes', label: '店家管理' },
              { key: 'logs', label: 'Log 檢視' },
              { key: 'model', label: '模型管理' },
            ].map(tab => (
              <button
                key={tab.key}
                className={`admin-tab ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => { setActiveTab(tab.key); setSearchTerm(''); }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* ===== 用戶管理 ===== */}
          {activeTab === 'users' && (
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
          )}

          {/* ===== 店家管理 ===== */}
          {activeTab === 'cafes' && (
            <>
              <div className="admin-stats">
                <div className="stat-card">
                  <div className="stat-label">總店家數</div>
                  <div className="stat-value">{cafes.length}</div>
                </div>
              </div>

              <div className="admin-search-bar">
                <input className="admin-search-input" placeholder="搜尋店家名稱或地址..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
              </div>

              {loading ? <div className="admin-loading">載入中</div> : (
                <div className="admin-table-wrapper">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>圖片</th>
                        <th>店名</th>
                        <th>地址</th>
                        <th>電話</th>
                        <th>標籤</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredCafes.length === 0 ? (
                        <tr><td colSpan="7" style={{textAlign:'center',padding:'40px',color:'#999'}}>無匹配結果</td></tr>
                      ) : filteredCafes.map(c => (
                        <tr key={c.id}>
                          <td>{c.id}</td>
                          <td>
                            {c.image ? (
                              <img src={c.image} alt={c.name} style={{width:'48px',height:'48px',borderRadius:'8px',objectFit:'cover'}} />
                            ) : (
                              <div style={{width:'48px',height:'48px',borderRadius:'8px',background:'#e0d6cc',display:'flex',alignItems:'center',justifyContent:'center',color:'#999',fontSize:'0.7rem'}}>無圖</div>
                            )}
                          </td>
                          <td style={{fontWeight:600}}>{c.name}</td>
                          <td style={{maxWidth:'200px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{c.address}</td>
                          <td>{c.phone}</td>
                          <td style={{maxWidth:'150px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{c.tags}</td>
                          <td>
                            <div className="admin-actions">
                              <button className="admin-btn primary" onClick={() => openEditCafe(c)}>編輯</button>
                              <button className="admin-btn danger" onClick={() => deleteCafe(c.id, c.name)}>刪除</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}

          {/* ===== Log 檢視 ===== */}
          {activeTab === 'logs' && (
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
          )}

          {/* ===== 模型管理 ===== */}
          {activeTab === 'model' && (
            <>
              {loading ? <div className="admin-loading">載入中</div> : (
                <>
                  <div className="model-status-card">
                    <div className="model-status-header">
                      <div className="model-status-title">Ollama 狀態</div>
                      <div>
                        <span className={`status-dot ${modelInfo.ollama_status}`}></span>
                        {modelInfo.ollama_status === 'online' ? '線上' : '離線'}
                      </div>
                    </div>
                    <div className="model-info-row">
                      <span className="model-info-label">目前使用模型</span>
                      <span className="model-info-value">{modelInfo.current_model}</span>
                    </div>
                    <div className="model-info-row">
                      <span className="model-info-label">已安裝模型數</span>
                      <span className="model-info-value">{modelInfo.installed_models.length}</span>
                    </div>
                  </div>

                  <div style={{fontWeight:700,color:'var(--admin-accent)',marginBottom:'12px',fontSize:'1.05rem'}}>已安裝的模型</div>
                  {modelInfo.installed_models.length === 0 ? (
                    <div className="admin-empty">{modelInfo.ollama_status === 'offline' ? 'Ollama 未啟動，無法取得模型列表' : '尚無安裝模型'}</div>
                  ) : (
                    <div className="model-list">
                      {modelInfo.installed_models.map(m => (
                        <div key={m.name} className={`model-card ${m.name === modelInfo.current_model ? 'active' : ''}`}>
                          <div>
                            <div className="model-name">
                              {m.name}
                              {m.name === modelInfo.current_model && <span style={{marginLeft:'8px',fontSize:'0.75rem',color:'var(--admin-success)',fontWeight:700}}>● 使用中</span>}
                            </div>
                            <div className="model-size">大小：{formatSize(m.size)}</div>
                          </div>
                          {m.name !== modelInfo.current_model && (
                            <button className="admin-btn primary" onClick={() => switchModel(m.name)}>切換至此模型</button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>

        {/* --- 編輯店家 Modal --- */}
        <div className={`admin-modal-overlay ${editingCafe ? 'active' : ''}`} onClick={() => setEditingCafe(null)}>
          <div className="admin-modal" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-title">編輯店家資訊</div>
            {['name', 'address', 'phone', 'website', 'cost'].map(field => (
              <div key={field} className="admin-form-group">
                <label className="admin-form-label">
                  {{ name: '店名', address: '地址', phone: '電話', website: '網站', cost: '消費' }[field]}
                </label>
                <input
                  className="admin-form-input"
                  value={editForm[field] || ''}
                  onChange={e => setEditForm({ ...editForm, [field]: e.target.value })}
                />
              </div>
            ))}
            {/* 圖片上傳區 */}
            <div className="admin-form-group">
              <label className="admin-form-label">店家圖片</label>
              {editForm.image && (
                <div style={{marginBottom:'10px',textAlign:'center'}}>
                  <img src={editForm.image} alt="預覽" style={{maxWidth:'100%',maxHeight:'150px',borderRadius:'10px',objectFit:'cover',border:'1px solid var(--admin-border)'}} />
                </div>
              )}
              <div style={{display:'flex',gap:'10px',alignItems:'center'}}>
                <input type="file" id="cafeImageUpload" accept="image/*" style={{display:'none'}} onChange={handleCafeImageUpload} />
                <button type="button" className="admin-btn secondary" onClick={() => document.getElementById('cafeImageUpload').click()}>
                  選擇圖片
                </button>
                {editForm.image && (
                  <button type="button" className="admin-btn danger" onClick={() => setEditForm(prev => ({...prev, image: ''}))}>
                    移除圖片
                  </button>
                )}
              </div>
            </div>
            <div className="admin-modal-actions">
              <button className="admin-btn secondary" onClick={() => setEditingCafe(null)}>取消</button>
              <button className="admin-btn primary" onClick={saveCafe}>儲存變更</button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
