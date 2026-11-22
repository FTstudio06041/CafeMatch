export const CHAT_UI_TEXTS = {
  inputPlaceholder: '輸入訊息...',
  typingPlaceholder: 'AI 正在思考中...',
  disclaimer: 'AI 生成內容可能含有錯誤，請斟酌採納生成內容。',
  enableDebug: '開啟 Debug 模式',
  disableDebug: '關閉 Debug 模式',
  retryBtn: '重新傳送',
  likeBtn: '讚',
  dislikeBtn: '倒讚',
  debugConsole: 'Debug Console',
  debugModel: 'Model:',
  debugIntent: 'Intent (意圖分類):',
  debugSpeed: 'Generation Speed:',
  debugTotalDuration: 'Total Duration:',
  debugRag: 'RAG 注入資料:',
  debugPrompt: '完整 Prompt:'
};

export const SIDEBAR_UI_TEXTS = {
  confirmDelete: '確定要刪除此對話嗎？',
  reportSuccess: '回報提交成功！感謝您的支持與反饋 ❤️',
  reportFail: '提交失敗，請稍後再試！',
  networkError: '網路連線錯誤，請稍後再試！',
  unnamedChat: '未命名對話',
  defaultUserName: '使用者名稱',
  newChat: '新增對話',
  chatHistory: '對話紀錄',
  noHistory: '尚無對話紀錄',
  guestNoHistory: '登入後可保存對話紀錄',
  appTitle: 'CafeMatch',
  reportBug: '回報問題 / 建議',
  bugReportTitle: '提出反饋',
  bugReportDesc: '您遇到了什麼問題？或是對我們有什麼建議呢？',
  typeBug: '🐛 程式錯誤 (Bug)',
  typeFeature: '💡 功能建議',
  typeOther: '💬 其他想法',
  submit: '送出',
  cancel: '取消',
  placeholder: '請詳述您的問題或建議...'
};

export const CHAT_WINDOW_UI_TEXTS = {
  welcomeMessage: '你好！我是咖啡廳推薦助手，想找什麼樣的店呢？',
  networkError: '連線發生錯誤，請稍後再試。',
  chatButton: '💬 聊聊',
  chatHeader: '咖啡助手',
  typing: '思考中...',
  inputPlaceholder: '輸入訊息...',
  send: '送出'
};

export const LANDING_UI_TEXTS = {
  loginError: 'Google 登入失敗，請重新登入。',
};

// 護照頁：滑卡探店與想去清單
export const SWIPE_UI_TEXTS = {
  title: '滑卡探店',
  subtitle: '右滑有興趣，加進想去清單；左滑跳過。左滑的店不會出現在盲盒裡。',
  want: '想去',
  pass: '沒興趣',
  undo: '復原',
  moreInfo: '看店家資訊',
  remaining: (n) => `還有 ${n} 家`,
  loading: '洗牌中…',
  doneTitle: '都看完了',
  doneBody: '收錄的店你都看過一輪了。',
  resetPassed: (n) => `重新看看略過的 ${n} 家`,
  resetDone: (n) => `${n} 家店回到牌堆了`,
  keyboardHint: '鍵盤也可以：← 跳過、→ 想去',
  wantListTitle: '想去清單',
  wantListEmpty: '還沒有想去的店。滑卡往右滑，就會加進來。',
  removeWant: '從想去清單移除',
  visitedBadge: '去過了',
};
