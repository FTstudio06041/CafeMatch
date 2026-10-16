/**
 * 頁面切換動畫（瀏覽器內建的 View Transitions API）。
 *
 * 不支援的瀏覽器、或使用者開了「減少動態效果」，就直接切換，不做動畫。
 *
 * 為什麼換頁不能用常見的 flushSync 寫法：React Router 7 的 <BrowserRouter> 把換頁的
 * state 更新包在 startTransition 裡，flushSync 逼不出同步提交，動畫拍到的「新畫面」
 * 會是舊的。改成讓更新回呼回傳 promise，等 AppShell 在換頁真正提交後（layout effect，
 * 畫面還沒畫出來之前）呼叫 notifyRouteCommitted() 才放行。
 */

// 換頁卡住時的保險：最多凍結畫面這麼久就放行，不能讓頁面一直定格
const ROUTE_COMMIT_TIMEOUT = 1200;

let pendingRouteCommit = null;

export function canAnimateTransitions() {
  return typeof document !== 'undefined'
    && typeof document.startViewTransition === 'function'
    && !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * 執行一段帶動畫的畫面更新。
 *   kind    'forward' | 'back'（換頁滑動方向）、'focus'（首頁 ↔ 店家畫面）
 *   update  實際改變畫面的函式；可回傳 promise（等它完成才拍新畫面）
 */
export function runViewTransition(kind, update) {
  if (!canAnimateTransitions()) {
    update();
    return;
  }
  const root = document.documentElement;
  root.dataset.vt = kind;
  const transition = document.startViewTransition(update);
  transition.finished.finally(() => {
    if (root.dataset.vt === kind) delete root.dataset.vt;
  });
}

/** 帶滑動動畫的換頁。direction：'forward'（往右邊的頁面）或 'back' */
export function navigateWithTransition(navigate, to, direction = 'forward', options) {
  // 已經在目標頁：網址不會變，也就等不到換頁通知，直接導過去
  if (new URL(to, window.location.origin).pathname === window.location.pathname) {
    navigate(to, options);
    return;
  }
  runViewTransition(direction, () => new Promise((resolve) => {
    pendingRouteCommit = resolve;
    navigate(to, options);
    setTimeout(resolve, ROUTE_COMMIT_TIMEOUT);
  }));
}

/** AppShell 在每次換頁提交後呼叫：放行正在等待的換頁動畫 */
export function notifyRouteCommitted() {
  if (pendingRouteCommit) {
    pendingRouteCommit();
    pendingRouteCommit = null;
  }
}
