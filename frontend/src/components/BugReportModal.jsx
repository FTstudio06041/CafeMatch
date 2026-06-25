
import { SIDEBAR_UI_TEXTS } from '../utils/constants';

export default function BugReportModal({ 
  showReportModal, 
  setShowReportModal, 
  reportType, 
  setReportType, 
  reportContent, 
  setReportContent, 
  handleSubmitReport, 
  isSubmitting 
}) {
  if (!showReportModal) return null;

  return (
    <div className="bug-report-overlay" onClick={() => setShowReportModal(false)}>
      <div className="bug-report-modal" onClick={(e) => e.stopPropagation()}>
        <div className="bug-report-header">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          <h3>{SIDEBAR_UI_TEXTS.bugReportTitle}</h3>
        </div>
        <form className="bug-report-form" onSubmit={handleSubmitReport}>
          <div className="bug-report-group">
            <label className="bug-report-label">回報類型</label>
            <select 
              className="bug-report-select" 
              value={reportType} 
              onChange={(e) => setReportType(e.target.value)}
            >
              <option value="bug">{SIDEBAR_UI_TEXTS.typeBug}</option>
              <option value="suggest">{SIDEBAR_UI_TEXTS.typeFeature}</option>
            </select>
          </div>
          <div className="bug-report-group">
            <label className="bug-report-label">具體描述</label>
            <textarea 
              className="bug-report-textarea" 
              placeholder={SIDEBAR_UI_TEXTS.placeholder} 
              value={reportContent} 
              onChange={(e) => setReportContent(e.target.value)}
              maxLength={1000}
              rows={5}
              required
            />
          </div>
          <div className="bug-report-actions">
            <button type="button" className="bug-report-btn cancel" onClick={() => setShowReportModal(false)}>
              {SIDEBAR_UI_TEXTS.cancel}
            </button>
            <button type="submit" className="bug-report-btn submit" disabled={!reportContent.trim() || isSubmitting}>
              {isSubmitting ? '提交中...' : SIDEBAR_UI_TEXTS.submit}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
