import { Suspense, useContext, useLayoutEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AuthContext } from '../../context/AuthContext';
import { SIDEBAR_UI_TEXTS } from '../../utils/constants';
import { toast } from '../../utils/toast';
import { logger } from '../../utils/logger';
import { notifyRouteCommitted } from '../../utils/viewTransition';
import BugReportModal from '../BugReportModal';
import AccountSettingsModal from './AccountSettingsModal';
import TopNav from './TopNav';
import './AppShell.css';

const pageFallback = <div className="page-loading">載入頁面中...</div>;

/** 全站外框：上方導覽列 + 頁面內容；帳號設定與問題回報彈窗也掛在這裡 */
export default function AppShell() {
  const { API_BASE_URL } = useContext(AuthContext);
  const location = useLocation();

  // 換頁提交到 DOM 之後、瀏覽器畫出來之前：通知切頁動畫可以拍「新畫面」了
  useLayoutEffect(() => {
    notifyRouteCommitted();
  }, [location.key]);
  const [showAccount, setShowAccount] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [reportType, setReportType] = useState('bug');
  const [reportContent, setReportContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const submitReport = async (e) => {
    e.preventDefault();
    if (!reportContent.trim() || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/bug_reports`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ content: reportContent.trim(), report_type: reportType }),
      });
      if (res.ok) {
        toast.info(SIDEBAR_UI_TEXTS.reportSuccess);
        setReportContent('');
        setShowReport(false);
      } else {
        toast.info(SIDEBAR_UI_TEXTS.reportFail);
      }
    } catch (err) {
      logger.error('提交反饋錯誤:', err);
      toast.info(SIDEBAR_UI_TEXTS.networkError);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="app-shell">
      <TopNav onOpenAccount={() => setShowAccount(true)} onOpenBugReport={() => setShowReport(true)} />
      <main className="app-main" id="main">
        <Suspense fallback={pageFallback}>
          <Outlet />
        </Suspense>
      </main>

      {showAccount && <AccountSettingsModal onClose={() => setShowAccount(false)} />}
      <BugReportModal
        showReportModal={showReport}
        setShowReportModal={setShowReport}
        reportType={reportType}
        setReportType={setReportType}
        reportContent={reportContent}
        setReportContent={setReportContent}
        handleSubmitReport={submitReport}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
