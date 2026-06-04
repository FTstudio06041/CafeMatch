// 透過 EventTarget 實作的 Toast 事件派發器
// 讓非 React Component (例如 apiClient) 也能呼叫 Toast

export const toastEmitter = new EventTarget();

export const toast = {
  info: (message, title) => 
    toastEmitter.dispatchEvent(new CustomEvent('add_toast', { detail: { message, type: 'info', title } })),
  
  success: (message, title) => 
    toastEmitter.dispatchEvent(new CustomEvent('add_toast', { detail: { message, type: 'success', title } })),
  
  error: (message, title) => 
    toastEmitter.dispatchEvent(new CustomEvent('add_toast', { detail: { message, type: 'error', title } })),
};
