import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

export default function AdminModelTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [modelInfo, setModelInfo] = useState({ current_model: '', ollama_status: 'offline', installed_models: [] });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchModel();
  }, []);

  const fetchModel = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/model`, { credentials: 'include' });
      if (res.ok) setModelInfo(await res.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

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

  const deleteModel = async (modelName) => {
    if (!confirm(`確定要刪除模型 ${modelName} 嗎？此操作無法復原。`)) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/model/delete`, {
        method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelName })
      });
      if (res.ok) fetchModel();
      else {
        const data = await res.json();
        alert(data.error || '刪除失敗');
      }
    } catch (e) { console.error(e); }
  };

  const formatSize = (bytes) => {
    if (!bytes) return '未知';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  return (
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
                  <div className="admin-actions">
                    {m.name !== modelInfo.current_model && (
                      <>
                        <button className="admin-btn primary" onClick={() => switchModel(m.name)}>切換至此模型</button>
                        <button className="admin-btn danger" onClick={() => deleteModel(m.name)}>刪除模型</button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
