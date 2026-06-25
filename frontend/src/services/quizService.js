import { apiClient } from '../utils/apiClient';

export const quizService = {
  fetchQuestions: async () => {
    return await apiClient('/api/quiz/questions');
  },
  submitQuiz: async (payload) => {
    return await apiClient('/api/quiz/submit', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }
};
