import { apiClient, API_BASE_URL } from '../utils/apiClient';

export const chatService = {
  fetchSessions: async () => {
    return await apiClient('/api/chat/sessions');
  },
  fetchSessionDetail: async (sessionId) => {
    return await apiClient(`/api/chat/sessions/${sessionId}`);
  },
  deleteSession: async (sessionId) => {
    return await apiClient(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
  },
  submitFeedback: async (feedbackData) => {
    return await apiClient('/api/chat/feedback', {
      method: 'POST',
      body: JSON.stringify(feedbackData)
    });
  },
  streamChat: async (payload, signal) => {
    // API_BASE_URL is inside apiClient, but we can export it or just use fetch here
    // Let's import API_BASE_URL from apiClient
    return await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:5000'}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
      signal
    });
  }
};
