import React, { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../context/AuthContext';

import { toast } from '../../utils/toast';
import { logger } from '../../utils/logger';
export default function AdminGuideTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [strategy, setStrategy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');

  useEffect(() => {
    fetchStrategy();
  }, []);

  const fetchStrategy = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/guide-strategy`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setStrategy(data);
      }
    } catch (e) {
      logger.error('Failed to fetch guide strategy:', e);
    }
    setLoading(false);
  };

  const handleChange = (key, value) => {
    const numValue = Math.max(0, Math.min(parseInt(value) || 0, FIELD_CONFIG[key].max));
    setStrategy(prev => ({ ...prev, [key]: numValue }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/guide-strategy`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(strategy)
      });
      if (res.ok) {
        setToast('✅ 策略參數已儲存');
        setTimeout(() => setToast(''), 2500);
      } else {
        setToast('❌ 儲存失敗');
        setTimeout(() => setToast(''), 2500);
      }
    } catch (e) {
      logger.error('Failed to save guide strategy:', e);
      setToast('❌ 儲存失敗：連線錯誤');
      setTimeout(() => setToast(''), 2500);
    }
    setSaving(false);
  };

  const FIELD_CONFIG = {
    max_questions: {
      label: 'AI 最多提問次數',
      description: 'AI 在推薦之前最多可以主動提問幾次。超過此數字後，不管蒐集到多少資訊都會直接推薦。',
      min: 1,
      max: 5
    },
    min_dimensions_to_recommend: {
      label: '最少蒐集維度數',
      description: '至少需要蒐集到幾個偏好維度（造訪目的、氛圍、口味、預算、特殊需求）才能推薦。設為 0 代表不問直接推薦，設為 1 代表至少問一題。',
      min: 0,
      max: 5
    },
    recommend_after_rounds: {
      label: '最大對話輪數',
      description: '使用者發送超過幾輪訊息後，無論蒐集到多少資訊，AI 都會強制推薦。這是防止對話迴圈的安全閥。',
      min: 2,
      max: 8
    }
  };

  if (loading) return <div className="admin-loading">載入中</div>;
  if (!strategy) return <div className="admin-empty">無法載入策略設定</div>;

  return (
    <>
      <div className="model-status-card">
        <div className="model-status-header">
          <div className="model-status-title">對話引導策略</div>
          <div style={{ fontSize: '0.85rem', color: 'var(--admin-text-secondary)' }}>
            控制 AI 在推薦咖啡廳之前的引導提問行為
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '16px' }}>
          {Object.entries(FIELD_CONFIG).map(([key, config]) => (
            <div key={key} style={{
              padding: '16px',
              borderRadius: '10px',
              background: 'var(--admin-card-bg, rgba(255,255,255,0.03))',
              border: '1px solid var(--admin-border, rgba(255,255,255,0.08))'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, color: 'var(--admin-text, #e0e0e0)', fontSize: '0.95rem' }}>
                  {config.label}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    className="admin-btn"
                    style={{ padding: '4px 10px', fontSize: '0.85rem', minWidth: 'auto' }}
                    onClick={() => handleChange(key, (strategy[key] || 0) - 1)}
                    disabled={strategy[key] <= config.min}
                  >
                    −
                  </button>
                  <span style={{
                    display: 'inline-block',
                    minWidth: '36px',
                    textAlign: 'center',
                    fontSize: '1.2rem',
                    fontWeight: 700,
                    color: 'var(--admin-accent, #f9a825)'
                  }}>
                    {strategy[key]}
                  </span>
                  <button
                    className="admin-btn"
                    style={{ padding: '4px 10px', fontSize: '0.85rem', minWidth: 'auto' }}
                    onClick={() => handleChange(key, (strategy[key] || 0) + 1)}
                    disabled={strategy[key] >= config.max}
                  >
                    +
                  </button>
                </div>
              </div>
              <div style={{
                fontSize: '0.82rem',
                color: 'var(--admin-text-secondary, #999)',
                lineHeight: '1.5'
              }}>
                {config.description}
                <span style={{ marginLeft: '6px', opacity: 0.7 }}>
                  （範圍：{config.min} ~ {config.max}）
                </span>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '20px' }}>
          <button
            className="admin-btn primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? '儲存中...' : '儲存設定'}
          </button>
          {toast && (
            <span style={{
              fontSize: '0.88rem',
              color: toast.includes('✅') ? 'var(--admin-success, #66bb6a)' : 'var(--admin-danger, #ef5350)',
              fontWeight: 600,
              animation: 'fadeIn 0.3s ease'
            }}>
              {toast}
            </span>
          )}
        </div>
      </div>

      <div className="model-status-card" style={{ marginTop: '16px' }}>
        <div className="model-status-header">
          <div className="model-status-title">運作原理</div>
        </div>
        <div style={{
          fontSize: '0.88rem',
          color: 'var(--admin-text-secondary, #999)',
          lineHeight: '1.7',
          marginTop: '8px'
        }}>
          <p style={{ margin: '0 0 8px 0' }}>
            當使用者發送與咖啡廳相關的訊息時，系統會在呼叫 AI 之前先分析對話歷史：
          </p>
          <ol style={{ margin: 0, paddingLeft: '20px' }}>
            <li>掃描使用者已提到的偏好關鍵字（造訪目的、氛圍、口味、預算、特殊需求）</li>
            <li>計算 AI 已提問的次數</li>
            <li>根據上方的策略參數，決定 AI 應該「繼續引導提問」還是「直接推薦」</li>
          </ol>
          <p style={{ margin: '8px 0 0 0' }}>
            這個機制確保 AI 不會無止盡提問（由程式碼硬性控制），也不會在資訊不足時就倉促推薦。
          </p>
        </div>
      </div>
    </>
  );
}
