import { useState, useEffect, useContext, useCallback } from 'react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, AreaChart, Area
} from 'recharts';
import { AuthContext } from '../../context/AuthContext';

// 自訂 Tooltip 元件
function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="overview-tooltip">
      <p className="overview-tooltip-label">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color }}>
          {entry.name}：{entry.value.toLocaleString()}
        </p>
      ))}
    </div>
  );
}

export default function AdminOverviewTab() {
  const { API_BASE_URL } = useContext(AuthContext);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/admin/overview`, { credentials: 'include' });
      if (!res.ok) throw new Error('載入失敗');
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [API_BASE_URL]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchOverview();
  }, [fetchOverview]);


  if (loading) return <div className="admin-loading">載入總覽數據中</div>;
  if (error) return <div className="admin-empty">{error}</div>;
  if (!data) return null;

  const { kpi, chart_data, top_keywords, top_users } = data;

  return (
    <div className="overview-container">
      {/* === KPI 卡片 === */}
      <div className="overview-kpi-grid">
        <KpiCard
          label="總註冊人數"
          value={kpi.total_users}
          color="#6366f1"
        />
        <KpiCard
          label="收錄店家數"
          value={kpi.total_cafes}
          color="#f59e0b"
        />
        <KpiCard
          label="今日 AI 請求"
          value={kpi.today_queries}
          suffix="次"
          color="#10b981"
        />
        <KpiCard
          label="今日 Token 消耗"
          value={kpi.today_tokens.toLocaleString()}
          color="#ef4444"
        />
        <KpiCard
          label="平均回應時間"
          value={kpi.avg_response_sec}
          suffix="秒"
          color="#8b5cf6"
        />
      </div>

      {/* === 折線圖區 === */}
      <div className="overview-charts-row">
        {/* 請求量趨勢 */}
        <div className="overview-chart-card">
          <h3 className="overview-chart-title">
            近七天請求量趨勢
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chart_data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="queryGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0d6cc" />
              <XAxis dataKey="date" stroke="#795548" fontSize={12} />
              <YAxis stroke="#795548" fontSize={12} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="queries"
                name="請求次數"
                stroke="#6366f1"
                fill="url(#queryGradient)"
                strokeWidth={2.5}
                dot={{ r: 4, fill: '#6366f1' }}
                activeDot={{ r: 6 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Token 消耗趨勢 */}
        <div className="overview-chart-card">
          <h3 className="overview-chart-title">
            近七天 Token 消耗趨勢
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={chart_data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="promptGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="completionGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0d6cc" />
              <XAxis dataKey="date" stroke="#795548" fontSize={12} />
              <YAxis stroke="#795548" fontSize={12} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Area
                type="monotone"
                dataKey="prompt_tokens"
                name="輸入 Token"
                stroke="#f59e0b"
                fill="url(#promptGradient)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
              <Area
                type="monotone"
                dataKey="completion_tokens"
                name="生成 Token"
                stroke="#ef4444"
                fill="url(#completionGradient)"
                strokeWidth={2}
                dot={{ r: 3 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* === 排行榜區 === */}
      <div className="overview-rankings-row">
        {/* 熱門關鍵字 */}
        <div className="overview-ranking-card">
          <h3 className="overview-chart-title">
            熱門搜尋需求 <span className="overview-subtitle">（近 7 天）</span>
          </h3>
          {top_keywords.length > 0 ? (
            <div className="overview-ranking-list">
              {top_keywords.map((item, i) => (
                <div className="overview-ranking-item" key={item.keyword}>
                  <span className={`overview-rank ${i < 3 ? 'top' : ''}`}>{i + 1}</span>
                  <span className="overview-keyword-tag">#{item.keyword}</span>
                  <div className="overview-bar-wrapper">
                    <div
                      className="overview-bar"
                      style={{
                        width: `${Math.min((item.count / (top_keywords[0]?.count || 1)) * 100, 100)}%`
                      }}
                    />
                  </div>
                  <span className="overview-count">{item.count} 次</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="admin-empty" style={{ padding: '30px' }}>暫無關鍵字數據</div>
          )}
        </div>

        {/* 活躍使用者 */}
        <div className="overview-ranking-card">
          <h3 className="overview-chart-title">
            高頻使用者排行 <span className="overview-subtitle">（近 7 天）</span>
          </h3>
          {top_users.length > 0 ? (
            <div className="admin-table-wrapper" style={{ border: 'none' }}>
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>排名</th>
                    <th>使用者</th>
                    <th>請求次數</th>
                    <th>Token 消耗</th>
                  </tr>
                </thead>
                <tbody>
                  {top_users.map((user, i) => (
                    <tr key={user.email}>
                      <td>
                        <span className={`overview-rank ${i < 3 ? 'top' : ''}`}>{i + 1}</span>
                      </td>
                      <td>
                        <div className="overview-user-name">{user.name}</div>
                        <div className="overview-user-email">{user.email}</div>
                      </td>
                      <td><strong>{user.query_count}</strong> 次</td>
                      <td>{user.total_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="admin-empty" style={{ padding: '30px' }}>暫無使用者數據</div>
          )}
        </div>
      </div>
    </div>
  );
}

// KPI 卡片子元件
function KpiCard({ icon, label, value, suffix = '', color }) {
  return (
    <div className="overview-kpi-card" style={{ '--kpi-accent': color }}>
      {icon && <div className="overview-kpi-icon">{icon}</div>}
      <div className="overview-kpi-info">
        <div className="overview-kpi-label">{label}</div>
        <div className="overview-kpi-value">
          {value}{suffix && <span className="overview-kpi-suffix">{suffix}</span>}
        </div>
      </div>
      <div className="overview-kpi-glow" style={{ background: color }} />
    </div>
  );
}
