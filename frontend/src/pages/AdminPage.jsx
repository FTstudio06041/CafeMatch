import { useState } from 'react';
import '../AdminPage.css';

import AdminOverviewTab from '../components/admin/AdminOverviewTab';
import AdminUsersTab from '../components/admin/AdminUsersTab';
import AdminCafesTab from '../components/admin/AdminCafesTab';
import AdminFeedbacksTab from '../components/admin/AdminFeedbacksTab';
import AdminLogsTab from '../components/admin/AdminLogsTab';
import AdminModelTab from '../components/admin/AdminModelTab';
import AdminAnnouncementsTab from '../components/admin/AdminAnnouncementsTab';
import AdminBugReportsTab from '../components/admin/AdminBugReportsTab';
import AdminGuideTab from '../components/admin/AdminGuideTab';

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <>
        <div className="admin-content">
          <div className="admin-page-title">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            管理後台
          </div>

          {/* Tab 切換 */}
          <div className="admin-tabs">
            {[
              { key: 'overview', label: '總覽' },
              { key: 'users', label: '用戶管理' },
              { key: 'cafes', label: '店家管理' },
              { key: 'feedbacks', label: 'AI 反饋' },
              { key: 'logs', label: 'Log 檢視' },
              { key: 'model', label: '模型管理' },
              { key: 'announcement', label: '系統公告' },
              { key: 'bug_report', label: 'Bug 反饋' },
              { key: 'guide', label: '對話引導' },
            ].map(tab => (
              <button
                key={tab.key}
                className={`admin-tab ${activeTab === tab.key ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'overview' && <AdminOverviewTab />}
          {activeTab === 'users' && <AdminUsersTab />}
          {activeTab === 'cafes' && <AdminCafesTab />}
          {activeTab === 'feedbacks' && <AdminFeedbacksTab />}
          {activeTab === 'logs' && <AdminLogsTab />}
          {activeTab === 'model' && <AdminModelTab />}
          {activeTab === 'announcement' && <AdminAnnouncementsTab />}
          {activeTab === 'bug_report' && <AdminBugReportsTab />}
          {activeTab === 'guide' && <AdminGuideTab />}
        </div>
    </>
  );
}
