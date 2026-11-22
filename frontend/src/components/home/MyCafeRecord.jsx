import { useCallback, useEffect, useState } from 'react';
import { Bookmark, CheckCircle2, MessageCircle, Star, Trash2 } from 'lucide-react';
import { chatService } from '../../services/chatService';
import { formatTime } from '../../utils/formatters';
import { logger } from '../../utils/logger';
import CafePhoto from '../cafe/CafePhoto';

const TABS = [
  { key: 'fav', label: '收藏', icon: Bookmark },
  { key: 'visited', label: '去過', icon: CheckCircle2 },
  { key: 'chats', label: 'AI 對話', icon: MessageCircle },
];

const EMPTY_TEXT = {
  fav: '還沒有收藏的店。打開店家詳情按「收藏」就會出現在這裡。',
  visited: '還沒有標記去過的店。',
  chats: '還沒有 AI 對話紀錄，從下方輸入框開始聊聊吧。',
};

/** 我的咖啡紀錄：收藏、去過、AI 對話（原本散在探索頁、個人頁與側欄） */
export default function MyCafeRecord({ user, cafes, activeChatId, onSelectCafe, onOpenChat, onLogin }) {
  const [tab, setTab] = useState('fav');
  const [sessions, setSessions] = useState([]);

  const loadSessions = useCallback(async () => {
    if (!user) return;
    try {
      const data = await chatService.fetchSessions();
      setSessions(Array.isArray(data) ? data : []);
    } catch (err) {
      logger.error('載入對話紀錄失敗:', err);
    }
  }, [user]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSessions();
    window.addEventListener('chat-updated', loadSessions);
    return () => window.removeEventListener('chat-updated', loadSessions);
  }, [loadSessions]);

  const removeSession = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('確定要刪除這段對話嗎？')) return;
    try {
      await chatService.deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
    } catch (err) {
      logger.error('刪除對話失敗:', err);
    }
  };

  if (!user) {
    return (
      <section className="home-block record-block record-guest" aria-labelledby="record-block-title">
        <div className="home-block-text">
          <span className="home-block-eyebrow"><Bookmark size={14} aria-hidden="true" /> 我的咖啡紀錄</span>
          <h3 id="record-block-title">登入後，幫你記住每一間店</h3>
          <p>收藏想去的店、標記去過的店，和 AI 的對話也會保存下來，換台裝置也找得到。</p>
          <button type="button" className="home-block-cta" onClick={onLogin}>使用 Google 登入</button>
        </div>
      </section>
    );
  }

  const favs = cafes.filter((c) => c.is_fav);
  const visited = cafes.filter((c) => c.is_visited);
  const counts = { fav: favs.length, visited: visited.length, chats: sessions.length };
  const list = tab === 'fav' ? favs : visited;

  return (
    <section className="home-block record-block" aria-labelledby="record-block-title">
      <div className="record-head">
        <h3 id="record-block-title" className="record-title">
          <Bookmark size={16} aria-hidden="true" /> 我的咖啡紀錄
        </h3>
        <div className="record-tabs" role="tablist" aria-label="紀錄類型">
          {TABS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={`record-tab ${tab === key ? 'active' : ''}`}
              onClick={() => setTab(key)}
            >
              <Icon size={15} aria-hidden="true" /> {label}
              <span className="record-count">{counts[key]}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="record-list" role="tabpanel">
        {tab === 'chats' ? (
          sessions.length === 0 ? (
            <p className="record-empty">{EMPTY_TEXT.chats}</p>
          ) : (
            sessions.map((s) => (
              <div key={s.id} className={`record-item ${String(s.id) === String(activeChatId) ? 'active' : ''}`}>
                <button type="button" className="record-item-main" onClick={() => onOpenChat(s.id)}>
                  <span className="record-chat-icon"><MessageCircle size={16} aria-hidden="true" /></span>
                  <span className="record-item-text">
                    <span className="record-item-title">{s.title || '未命名對話'}</span>
                    {s.updated_at && <span className="record-item-sub">{formatTime(s.updated_at)}</span>}
                  </span>
                </button>
                <button type="button" className="record-item-delete" onClick={(e) => removeSession(e, s.id)} aria-label={`刪除對話「${s.title || '未命名對話'}」`}>
                  <Trash2 size={15} />
                </button>
              </div>
            ))
          )
        ) : list.length === 0 ? (
          <p className="record-empty">{EMPTY_TEXT[tab]}</p>
        ) : (
          list.map((cafe) => (
            <div key={cafe.id} className="record-item">
              <button type="button" className="record-item-main" onClick={() => onSelectCafe(cafe.id)}>
                <CafePhoto cafe={cafe} className="record-thumb" alt="" />
                <span className="record-item-text">
                  <span className="record-item-title">{cafe.name}</span>
                  <span className="record-item-sub">
                    {cafe.google_rating != null && (
                      <><Star size={11} fill="currentColor" aria-hidden="true" /> {cafe.google_rating.toFixed(1)} · </>
                    )}
                    {cafe.today_hours || '營業時間請洽店家'}
                  </span>
                </span>
              </button>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
