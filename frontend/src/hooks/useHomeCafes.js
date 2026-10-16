import { useCallback, useEffect, useMemo, useState } from 'react';
import { cafeService } from '../services/cafeService';
import { logger } from '../utils/logger';
import { readCachedQuizResult } from '../utils/personality';
import { toast } from '../utils/toast';

/** 未登入者在這台裝置做過的測驗分數：帶去諮詢過的、或剛做完還在測驗頁快取裡的 */
function readGuestQuizScores() {
  try {
    const handedOff = JSON.parse(localStorage.getItem('latestQuizScores') || 'null');
    if (handedOff) return handedOff;
  } catch {
    // 壞掉的暫存就當沒有
  }
  return readCachedQuizResult()?.scores || null;
}

// 跨次掛載保留上一次的結果：從測驗頁切回首頁時先顯示舊資料、背景再更新，
// 不必再閃一次骨架畫面。收藏狀態與個人化推薦因人而異，所以以使用者區分。
const cache = { userKey: null, cafes: null, suggestions: null };

/**
 * 首頁的店家資料：全部店家（地圖、詳情）＋「你可能會喜歡」＋收藏/去過切換。
 * user 變動（登入、登出）時重新抓，收藏狀態與個人化推薦都跟著換。
 */
export function useHomeCafes(user) {
  const userKey = user?.email || '';
  const cached = cache.userKey === userKey ? cache : null;
  const [cafes, setCafesState] = useState(() => cached?.cafes || []);
  const [isLoading, setIsLoading] = useState(() => !cached?.cafes);
  const [suggestions, setSuggestionsState] = useState(
    () => cached?.suggestions || { basis: 'popular', items: [] },
  );

  // 寫入 state 的同時更新快取（收藏切換、評論數變動也要記得）
  const setCafes = useCallback((next) => {
    setCafesState((prev) => {
      const value = typeof next === 'function' ? next(prev) : next;
      if (cache.userKey !== userKey) cache.suggestions = null;
      cache.userKey = userKey;
      cache.cafes = value;
      return value;
    });
  }, [userKey]);
  const setSuggestions = useCallback((value) => {
    if (cache.userKey !== userKey) cache.cafes = null;
    cache.userKey = userKey;
    cache.suggestions = value;
    setSuggestionsState(value);
  }, [userKey]);

  const reload = useCallback(async () => {
    try {
      const data = await cafeService.fetchCafes();
      setCafes(Array.isArray(data) ? data : []);
    } catch (err) {
      logger.error('載入店家失敗:', err);
      toast.error('店家資料載入失敗，請重新整理頁面');
    } finally {
      setIsLoading(false);
    }
  }, [setCafes]);

  const reloadSuggestions = useCallback(async () => {
    try {
      const guestScores = userKey ? null : readGuestQuizScores();
      const data = await cafeService.fetchRecommended(guestScores);
      if (data?.items) setSuggestions(data);
    } catch (err) {
      logger.error('載入推薦失敗:', err);
    }
  }, [userKey, setSuggestions]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
    reloadSuggestions();
  }, [reload, reloadSuggestions]);

  const byId = useMemo(() => new Map(cafes.map((c) => [c.id, c])), [cafes]);

  const patchCafe = useCallback((cafeId, patch) => {
    setCafes((prev) => prev.map((c) => (c.id === cafeId ? { ...c, ...patch } : c)));
  }, [setCafes]);

  /** 收藏 / 去過：type 為 'fav' | 'visited' */
  const toggleShopState = useCallback(async (cafeId, type) => {
    try {
      const result = await cafeService.toggleShopState(cafeId, type);
      if (result?.success) {
        patchCafe(cafeId, { is_fav: Boolean(result.fav), is_visited: Boolean(result.visited) });
      }
    } catch (err) {
      logger.error('更新收藏狀態失敗:', err);
    }
  }, [patchCafe]);

  return { cafes, byId, isLoading, suggestions, toggleShopState, patchCafe, reload, reloadSuggestions };
}
