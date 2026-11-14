import { useEffect, useSyncExternalStore } from 'react';
import { apiClient } from './apiClient';
import { toast } from './toast';

/**
 * 收藏／去過的共用狀態。
 *
 * 探索頁、聊天推薦卡片、護照頁、盲盒都會切換同一份狀態，
 * 放在模組層級的小 store，任何一處按了，其他地方立刻跟著變，
 * 也不用每張推薦卡片各打一次 API。
 */

let states = {};          // { [cafeId]: { fav, visited } }
let loaded = false;
let loading = null;
const listeners = new Set();

const emit = () => listeners.forEach((fn) => fn());
const subscribe = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
const getSnapshot = () => states;

function setState(cafeId, patch) {
  states = { ...states, [cafeId]: { fav: false, visited: false, ...states[cafeId], ...patch } };
  emit();
}

/** 換帳號時清掉上一個人的狀態 */
export function resetShopStates() {
  states = {};
  loaded = false;
  loading = null;
  emit();
}

async function loadOnce() {
  if (loaded) return;
  if (!loading) {
    loading = apiClient('/api/user/shop_states', { suppressToast: true })
      .then((data) => { states = { ...(data || {}), ...states }; loaded = true; emit(); })
      .catch(() => { loading = null; });
  }
  await loading;
}

/** 取得共用狀態；enabled=false（訪客）時不打 API */
export function useShopStates(enabled = true) {
  useEffect(() => { if (enabled) loadOnce(); }, [enabled]);
  return useSyncExternalStore(subscribe, getSnapshot);
}

/** 探索頁原本自己存一份列表，進頁時把列表裡的狀態同步進來 */
export function seedShopStates(list) {
  const next = { ...states };
  list.forEach((s) => { next[s.id] = { fav: !!s.is_fav, visited: !!s.is_visited }; });
  states = next;
  loaded = true;
  emit();
}

/**
 * 切換收藏／去過。
 * source：explore / chat / blindbox / passport —— 記進後端流水帳，分析推薦成效用。
 * 回傳後端結果；新解鎖的徽章與盲盒完成會自動跳提示。
 */
export async function toggleShopState(cafeId, type, source) {
  const result = await apiClient('/api/user/shop_state', {
    method: 'POST',
    body: JSON.stringify({ cafe_id: cafeId, type, source }),
  });
  if (!result?.success) return result;

  setState(cafeId, { fav: result.fav, visited: result.visited });

  if (result.blindbox_completed) {
    toast.success('這週的咖啡盲盒完成了！記得在護照頁幫它打個分數', '盲盒完成');
  }
  (result.new_badges || []).forEach((b) => {
    toast.success(`${b.name}：${b.desc}`, '解鎖新徽章');
  });
  window.dispatchEvent(new CustomEvent('passport:changed', { detail: { cafeId, type, result } }));
  return result;
}
