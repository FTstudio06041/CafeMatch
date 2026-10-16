import { apiClient } from '../utils/apiClient';

const SCORE_DIMS = ['work', 'env', 'social', 'taste', 'cp'];

const post = (endpoint, body) => apiClient(endpoint, {
  method: 'POST',
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const cafeService = {
  fetchCafes: () => apiClient('/api/cafes', { suppressToast: true }),

  /**
   * 首頁「你可能會喜歡」。登入者由後端讀最近一次測驗；
   * 未登入但在這台裝置做過測驗的人，把五維分數帶在 query string。
   */
  fetchRecommended: (guestScores) => {
    const params = new URLSearchParams();
    if (guestScores && SCORE_DIMS.every((d) => Number.isFinite(Number(guestScores[d])))) {
      SCORE_DIMS.forEach((d) => params.set(d, String(guestScores[d])));
    }
    const qs = params.toString();
    return apiClient(`/api/cafes/recommended${qs ? `?${qs}` : ''}`, { suppressToast: true });
  },

  toggleShopState: (cafeId, type) => post('/api/user/shop_state', { cafe_id: cafeId, type }),

  // 評論（評論即社群）
  fetchReviews: (cafeId, page = 1) => apiClient(`/api/cafes/${cafeId}/reviews?page=${page}`, { suppressToast: true }),
  saveReview: (cafeId, rating, content) => post(`/api/cafes/${cafeId}/reviews`, { rating, content }),
  deleteReview: (reviewId) => apiClient(`/api/reviews/${reviewId}`, { method: 'DELETE' }),
  toggleReviewLike: (reviewId) => post(`/api/reviews/${reviewId}/like`),
  fetchComments: (reviewId) => apiClient(`/api/reviews/${reviewId}/comments`, { suppressToast: true }),
  addComment: (reviewId, content) => post(`/api/reviews/${reviewId}/comments`, { content }),
  deleteComment: (reviewId, commentId) => apiClient(`/api/reviews/${reviewId}/comments/${commentId}`, { method: 'DELETE' }),

  // 24 小時現況回報
  fetchReports: (cafeId) => apiClient(`/api/cafes/${cafeId}/reports`, { suppressToast: true }),
  saveReport: (cafeId, content) => post(`/api/cafes/${cafeId}/reports`, { content }),
  deleteReport: (reportId) => apiClient(`/api/reports/${reportId}`, { method: 'DELETE' }),
  toggleReportConfirm: (reportId) => post(`/api/reports/${reportId}/confirm`),
};
