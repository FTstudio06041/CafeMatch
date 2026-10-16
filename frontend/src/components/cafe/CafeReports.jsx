import { useEffect, useState } from 'react';
import { Radio, Trash2 } from 'lucide-react';
import { cafeService } from '../../services/cafeService';
import { formatTime } from '../../utils/formatters';
import { logger } from '../../utils/logger';
import { toast } from '../../utils/toast';

const MAX_LENGTH = 100;

/** 24 小時現況回報：「現在人很多」「還有插座位」之類，一天後自動消失 */
export default function CafeReports({ cafe, user, onLogin, onCountChange }) {
  const [reports, setReports] = useState([]);
  const [quick, setQuick] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    cafeService.fetchReports(cafe.id)
      .then((data) => {
        if (!alive) return;
        setReports(data?.reports || []);
        setQuick(data?.quick_reports || []);
      })
      .catch((err) => logger.error('載入現況回報失敗:', err));
    return () => { alive = false; };
  }, [cafe.id]);

  const submit = async (content) => {
    const value = (content ?? text).trim();
    if (!value || busy) return;
    setBusy(true);
    try {
      const data = await cafeService.saveReport(cafe.id, value);
      if (data?.report) {
        // 每人每店只有一則有效回報：新的蓋掉自己舊的
        const next = [data.report, ...reports.filter((r) => !r.is_mine)];
        setReports(next);
        onCountChange(next.length);
        setText('');
        toast.success('謝謝回報！其他人 24 小時內都看得到');
      }
    } catch (err) {
      logger.error('送出現況回報失敗:', err);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (report) => {
    if (!user) {
      toast.info('登入後才能回應現況回報');
      return;
    }
    try {
      const data = await cafeService.toggleReportConfirm(report.id);
      setReports((prev) => prev.map((r) => (r.id === report.id
        ? { ...r, is_confirmed: data.confirmed, confirm_count: data.confirm_count } : r)));
    } catch (err) {
      logger.error('回應現況回報失敗:', err);
    }
  };

  const remove = async (report) => {
    try {
      await cafeService.deleteReport(report.id);
      const next = reports.filter((r) => r.id !== report.id);
      setReports(next);
      onCountChange(next.length);
    } catch (err) {
      logger.error('刪除現況回報失敗:', err);
    }
  };

  return (
    <section className="detail-section" aria-labelledby="reports-title">
      <h3 id="reports-title" className="detail-section-title">
        <Radio size={16} aria-hidden="true" /> 現況回報
        <span className="detail-section-hint">24 小時內</span>
      </h3>

      {reports.length === 0 ? (
        <p className="detail-muted">最近 24 小時還沒有人回報這家店的狀況。</p>
      ) : (
        <ul className="report-list">
          {reports.map((r) => (
            <li key={r.id} className="report-item">
              <div className="report-content">{r.content}</div>
              <div className="report-meta">
                <span>{r.author.name} · {formatTime(r.created_at)}</span>
                <button
                  type="button"
                  className={`report-confirm ${r.is_confirmed ? 'on' : ''}`}
                  onClick={() => confirm(r)}
                  aria-pressed={r.is_confirmed}
                  disabled={r.is_mine}
                >
                  我也看到了{r.confirm_count > 0 ? ` · ${r.confirm_count}` : ''}
                </button>
                {(r.is_mine || user?.is_admin) && (
                  <button type="button" className="mini-icon-btn" onClick={() => remove(r)} aria-label="刪除這則回報">
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {user ? (
        <div className="report-composer">
          <div className="report-quick" aria-label="快速回報">
            {quick.map((q) => (
              <button key={q} type="button" className="report-quick-btn" onClick={() => submit(q)} disabled={busy}>{q}</button>
            ))}
          </div>
          <form className="inline-form" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <label htmlFor="report-input" className="sr-only">回報現況</label>
            <input
              id="report-input"
              type="text"
              value={text}
              maxLength={MAX_LENGTH}
              placeholder="或自己寫，例如：今天有新口味司康"
              onChange={(e) => setText(e.target.value)}
            />
            <button type="submit" className="btn-primary" disabled={!text.trim() || busy}>回報</button>
          </form>
        </div>
      ) : (
        <button type="button" className="detail-login-hint" onClick={onLogin}>登入後可以回報這家店的現況</button>
      )}
    </section>
  );
}
