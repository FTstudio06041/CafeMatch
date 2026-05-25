/**
 * 時間格式化工具
 * 將 UTC 格式的時間字串轉換為如 "剛剛"、"X 分鐘前" 或 "YYYY/MM/DD" 的人性化字串
 * @param {string} timeStr - 傳入的時間字串
 * @returns {string} 格式化後的時間
 */
export const formatTime = (timeStr) => {
  if (!timeStr) return '';
  let utcStr = timeStr.replace(' ', 'T');
  if (utcStr.length === 16) utcStr += ':00';
  if (!utcStr.endsWith('Z')) utcStr += 'Z';
  const d = new Date(utcStr);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  
  if (diff < 60) return '剛剛';
  if (diff < 3600) return `${Math.floor(diff / 60)} 分鐘前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小時前`;
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`;
  
  return d.toLocaleDateString('zh-TW');
};
