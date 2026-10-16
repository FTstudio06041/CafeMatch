import { useSyncExternalStore } from 'react';

/**
 * 訂閱 CSS media query，例如 useMediaQuery('(min-width: 769px)')
 *
 * 除了 matchMedia 的 change 事件也聽 resize：視窗從隱藏（寬度 0）直接恢復時，
 * 有些環境不會送 change，版面就會卡在錯的模式。
 */
export function useMediaQuery(query) {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', onChange);
      window.addEventListener('resize', onChange);
      return () => {
        mql.removeEventListener('change', onChange);
        window.removeEventListener('resize', onChange);
      };
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}
