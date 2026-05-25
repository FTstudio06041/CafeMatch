/**
 * 貼文 ID 混淆器 (極簡手動版 Hashids)
 * 用於將貼文的數值 ID 轉換為無規律的大寫小寫英文加數字亂碼，並支援雙向還原
 */

const SALT_PRIME = 48271; // 混淆用大質數
const OFFSET = 538421;    // 混淆偏移量

// 隨機混淆過的 Base62 字符集，讓編碼結果沒有任何規律性與連續性
const BASE62_CHARS = "vYw1aK6WdD2JbcC3eEf4gGhH5iIjJkKlLmMnNoOpPqQrRsStTuUvVxXzZ9870";

/**
 * 將數值 ID 編碼為短字串
 * @param {number|string} id 
 * @returns {string}
 */
export function encodeId(id) {
  let num = typeof id === 'number' ? id : parseInt(id, 10);
  if (isNaN(num) || num <= 0) return '';
  
  // 混淆原始數字
  let target = num * SALT_PRIME + OFFSET;
  let result = '';
  
  while (target > 0) {
    result = BASE62_CHARS[target % 62] + result;
    target = Math.floor(target / 62);
  }
  
  return result;
}

/**
 * 將混淆字串還原為數值 ID
 * @param {string} code 
 * @returns {number|null}
 */
export function decodeId(code) {
  if (!code || typeof code !== 'string') return null;
  
  let num = 0;
  for (let i = 0; i < code.length; i++) {
    const charIndex = BASE62_CHARS.indexOf(code[i]);
    if (charIndex === -1) return null; // 包含非 Base62 字元，解碼失敗
    num = num * 62 + charIndex;
  }
  
  // 還原並驗證
  const original = (num - OFFSET) / SALT_PRIME;
  
  // 確保是正整數且除得盡
  if (original > 0 && original % 1 === 0) {
    return original;
  }
  
  return null;
}
