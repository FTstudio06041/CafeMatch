/**
 * 集中式日誌管理工具
 * - 在開發環境中顯示日誌
 * - 未來可透過設定環境變數在正式環境隱藏日誌，或串接遠端監控系統 (如 Sentry)
 */

const IS_PROD = import.meta.env.MODE === 'production';

export const logger = {
  info: (...args) => {
    if (!IS_PROD) {
      console.log('[INFO]', ...args);
    }
  },
  warn: (...args) => {
    if (!IS_PROD) {
      console.warn('[WARN]', ...args);
    }
  },
  error: (...args) => {
    if (!IS_PROD) {
      console.error('[ERROR]', ...args);
    }
    // TODO: 未來可加入送出錯誤到後端或 Sentry 的邏輯
  }
};
