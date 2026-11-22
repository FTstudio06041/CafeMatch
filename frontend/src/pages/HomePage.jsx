import { Suspense, lazy, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { MessageCircle } from 'lucide-react';
import { AuthContext } from '../context/AuthContext';
import { useChat } from '../context/ChatContext';
import { useHomeCafes } from '../hooks/useHomeCafes';
import { useMediaQuery } from '../hooks/useMediaQuery';
import { resumeQuizConsultation, takeQueuedQuizConsultation } from '../utils/quizHandoff';
import { canAnimateTransitions, runViewTransition } from '../utils/viewTransition';
import CafeRail from '../components/home/CafeRail';
import MapToolbar from '../components/home/MapToolbar';
import QuizEntryCard from '../components/home/QuizEntryCard';
import MyCafeRecord from '../components/home/MyCafeRecord';
import { ChatBar, ChatPanel } from '../components/home/ChatDock';
import CafeFocusView from '../components/cafe/CafeFocusView';
import '../HomePage.css';

// 地圖套件約 1MB，延後載入，先把頁面其他部分畫出來
const CafeMap = lazy(() => import('../components/home/CafeMap'));

// 這個寬度以上，AI 對話常駐在左欄（草圖第二版）；以下改成浮動輸入列＋全螢幕對話
const DOCKED_CHAT_QUERY = '(min-width: 1100px)';

function filterCafes(cafes, filter, keepIds) {
  if (filter === 'all') return cafes;
  return cafes.filter((c) => {
    if (keepIds.has(c.id)) return true;
    if (filter === 'open') return c.is_open_now === true;
    if (filter === 'top') return c.google_rating >= 4.6;
    if (filter === 'fav') return c.is_fav;
    return true;
  });
}

/** 對話裡最新一次推薦的店家 id（依推薦順序），只留首頁認得的店 */
function latestRecommendedIds(messages, byId) {
  const last = [...messages].reverse()
    .find((m) => m.role === 'ai' && Array.isArray(m.cafes) && m.cafes.length > 0);
  return last ? last.cafes.map((c) => c.id).filter((id) => byId.has(id)) : [];
}

/**
 * 首頁（資訊整合平台，草圖第二、三版）：
 *   左欄：AI 對話（桌機常駐）
 *   右側：地圖 → 你可能會喜歡／為你推薦 → 心理測驗入口＋我的咖啡紀錄
 *   點開店家：右側下半部換成那一家的專屬畫面（店家資訊＋評論區），AI 主動問要不要介紹
 */
export default function HomePage() {
  const { user, login } = useContext(AuthContext);
  const { currentChat, executeChatStream, newChat, openSession, resumeActiveSession } = useChat();
  const { cafes, byId, isLoading, suggestions, toggleShopState, patchCafe } = useHomeCafes(user);
  const chatDocked = useMediaQuery(DOCKED_CHAT_QUERY);

  const [selectedId, setSelectedId] = useState(null);
  // 打開／關閉店家時要變形的那張店家卡照片（見 changeSelection）
  const [morphId, setMorphId] = useState(null);
  const selectedIdRef = useRef(null);
  const [hoveredId, setHoveredId] = useState(null);
  const [sheetOpen, setSheetOpen] = useState(false); // 只有手機／平板的全螢幕對話會用到
  const [filter, setFilter] = useState('all');
  const [isDebugMode, setIsDebugMode] = useState(false);
  // 已經介紹過、或使用者說「不用了」的店，不再重複邀請
  const [introHandled, setIntroHandled] = useState(() => new Set());
  const bootedRef = useRef(false);

  // 進首頁時：測驗頁交過來的結果直接開成對話；不然就接回這個分頁上一段對話
  useEffect(() => {
    if (bootedRef.current) return; // StrictMode 會重跑 effect，只做一次
    bootedRef.current = true;
    resumeQuizConsultation(user);
    const handoff = takeQueuedQuizConsultation();
    if (handoff) {
      newChat();
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (!window.matchMedia(DOCKED_CHAT_QUERY).matches) setSheetOpen(true);
      setTimeout(() => {
        executeChatStream(handoff.promptText, {
          customTitle: '測驗結果諮詢',
          hiddenPrompt: true,
          isQuizResult: true,
          quizScores: handoff.quizScores,
        });
      }, 0);
      return;
    }
    if ((currentChat.messages || []).length === 0) resumeActiveSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const messages = useMemo(() => currentChat.messages || [], [currentChat.messages]);
  const hasConversation = messages.length > 0;

  // 對話裡最新一次推薦的店：地圖上的大頭針、「為你推薦」排最前面
  const aiRecommended = useMemo(() => latestRecommendedIds(messages, byId), [messages, byId]);

  // 只有 AI 推薦的店貼「AI 推薦 N」；其他店的來由（熱門／依測驗）寫在標題旁，不在每張卡重複
  const railItems = useMemo(() => {
    const seen = new Set(aiRecommended);
    const items = aiRecommended.map((id, i) => ({ cafe: byId.get(id), badge: `AI 推薦 ${i + 1}` }));
    for (const { cafe_id: id } of suggestions.items) {
      const cafe = byId.get(id);
      if (!cafe || seen.has(id)) continue;
      seen.add(id);
      items.push({ cafe, badge: null });
    }
    return items;
  }, [aiRecommended, suggestions, byId]);

  // AI 推薦的店、開著詳情的店不受篩選影響，一定留在地圖上
  const keepOnMap = useMemo(
    () => new Set(selectedId != null ? [...aiRecommended, selectedId] : aiRecommended),
    [aiRecommended, selectedId],
  );
  const mapCafes = useMemo(() => filterCafes(cafes, filter, keepOnMap), [cafes, filter, keepOnMap]);

  /**
   * 切換目前開著的店家（null = 回到首頁），支援的瀏覽器帶轉場動畫。
   * 拍舊畫面之前先把要變形的店家卡標好：打開時是被點的那張，關閉時是要回去的那張；
   * 店家頁標頭的照片一直掛著同名，瀏覽器就會把照片從卡片位置變形過去（或縮回來）。
   */
  const changeSelection = useCallback((id) => {
    const prev = selectedIdRef.current;
    if (id === prev) return;
    const apply = () => {
      selectedIdRef.current = id;
      setSelectedId(id);
    };
    if (!canAnimateTransitions()) {
      apply();
      return;
    }
    flushSync(() => setMorphId(id ?? prev));
    runViewTransition('focus', () => flushSync(apply));
  }, []);
  const selectCafe = changeSelection;
  const closeDetail = useCallback(() => changeSelection(null), [changeSelection]);
  const selectedCafe = selectedId != null ? byId.get(selectedId) : null;

  // 全螢幕對話只存在於單欄模式；桌機的對話欄本來就開著，不必（也不該）標成打開，
  // 否則之後視窗變窄會突然整片蓋上來
  const revealChat = () => { if (!chatDocked) setSheetOpen(true); };

  const openSavedChat = async (id) => {
    if (await openSession(id)) revealChat();
  };

  const introCafe = selectedCafe && !introHandled.has(selectedCafe.id) ? selectedCafe : null;
  const markIntroHandled = useCallback((id) => {
    setIntroHandled((prev) => new Set(prev).add(id));
  }, []);
  const requestIntro = (cafe) => {
    markIntroHandled(cafe.id);
    revealChat();
    executeChatStream(`請幫我介紹「${cafe.name}」`, { introCafeId: cafe.id });
  };

  const showSheet = !chatDocked && sheetOpen;
  const railTitle = aiRecommended.length > 0 ? '為你推薦' : '你可能會喜歡';
  let railHint = '花蓮評價最好的店';
  if (aiRecommended.length > 0) railHint = `AI 推薦的 ${aiRecommended.length} 家已標在地圖上`;
  else if (suggestions.basis === 'quiz') railHint = '依你的咖啡人格挑選';

  const chatProps = {
    onSelectCafe: selectCafe,
    recommendedCount: aiRecommended.length,
    isDebugMode,
    setIsDebugMode,
    introCafe,
    onIntro: requestIntro,
    onDismissIntro: markIntroHandled,
  };

  return (
    <div className={`home ${chatDocked ? 'with-chat' : 'stacked'}`}>
      {chatDocked && (
        <aside className="home-chat-col">
          <ChatPanel variant="docked" {...chatProps} />
        </aside>
      )}

      <div className={`home-main ${selectedCafe ? 'focus' : ''}`}>
        <section className="home-map-card" aria-label="咖啡廳地圖">
          <Suspense fallback={<div className="home-map-loading">地圖載入中…</div>}>
            <CafeMap
              cafes={mapCafes}
              recommendedIds={aiRecommended}
              selectedId={selectedId}
              hoveredId={hoveredId}
              onSelect={selectCafe}
              onHover={setHoveredId}
            />
          </Suspense>
          <MapToolbar cafes={cafes} filter={filter} onFilter={setFilter} onPick={selectCafe} user={user} />
        </section>

        {selectedCafe ? (
          <CafeFocusView
            cafe={selectedCafe}
            user={user}
            onClose={closeDetail}
            onToggleState={toggleShopState}
            onStatsChange={(patch) => patchCafe(selectedCafe.id, patch)}
            onLogin={login}
          />
        ) : (
          <>
            <CafeRail
              title={railTitle}
              hint={railHint}
              action={!chatDocked && hasConversation && (
                <button type="button" className="home-rail-chat" onClick={() => setSheetOpen(true)}>
                  <MessageCircle size={16} aria-hidden="true" /> 回到對話
                </button>
              )}
              items={railItems}
              isLoading={isLoading}
              activeId={hoveredId ?? selectedId}
              morphId={morphId}
              onSelect={selectCafe}
              onHover={setHoveredId}
              emptyText="暫時沒有推薦，先用上方地圖逛逛吧"
            />

            <div className="home-blocks">
              <QuizEntryCard user={user} />
              <MyCafeRecord
                user={user}
                cafes={cafes}
                activeChatId={currentChat.id}
                onSelectCafe={selectCafe}
                onOpenChat={openSavedChat}
                onLogin={login}
              />
            </div>
          </>
        )}
      </div>

      {!chatDocked && !showSheet && (
        <ChatBar
          onOpen={() => setSheetOpen(true)}
          hasConversation={hasConversation}
          introCafe={introCafe}
          onIntro={requestIntro}
        />
      )}
      {showSheet && (
        <div className="home-chat-sheet">
          <ChatPanel variant="sheet" onClose={() => setSheetOpen(false)} {...chatProps} />
        </div>
      )}

    </div>
  );
}
