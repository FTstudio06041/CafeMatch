import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

export default function AdminCafesTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [cafes, setCafes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  
  const [editingCafe, setEditingCafe] = useState(null);
  const [editForm, setEditForm] = useState({});

  useEffect(() => {
    fetchCafes();
  }, []);

  const fetchCafes = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/cafes`, { credentials: 'include' });
      if (res.ok) setCafes(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
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

  const filteredCafes = cafes.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.address.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
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
    </>
  );
}
