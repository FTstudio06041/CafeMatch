import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { queueQuizConsultation, resumeQuizConsultation } from '../src/utils/quizHandoff.js';

const result = {
  result: { title: 'Work', inner_voice: 'Focus', profile: 'Quiet', cafe_match: 'Desk' },
  scores: { work: 10, env: 8, social: 2, taste: 4, cp: 6 },
};

function memoryStorage() {
  const entries = new Map();
  return {
    getItem: key => entries.get(key) ?? null,
    setItem: (key, value) => entries.set(key, String(value)),
    removeItem: key => entries.delete(key),
  };
}

beforeEach(() => {
  globalThis.localStorage = memoryStorage();
  globalThis.sessionStorage = memoryStorage();
});

test('guest result waits through login and resumes once for an authenticated user', () => {
  queueQuizConsultation(result, true);
  assert.equal(localStorage.getItem('targetQuizContext'), null);
  assert.equal(resumeQuizConsultation(null), false);
  assert.equal(resumeQuizConsultation({ isGuest: true, is_logged_in: true }), false);
  assert.ok(sessionStorage.getItem('pendingQuizConsultation'));
  localStorage.setItem('forceQuiz', 'true');
  assert.equal(resumeQuizConsultation({ is_logged_in: true }), true);
  assert.deepEqual(JSON.parse(localStorage.getItem('targetQuizContext')), {
    ...result.result, scores: result.scores,
  });
  assert.equal(localStorage.getItem('forceQuiz'), null);
  assert.equal(resumeQuizConsultation({ is_logged_in: true }), false);
});

test('malformed pending results cannot bypass first-time onboarding', () => {
  for (const value of ['broken', 'null', '{}', '{"scores":{"work":10}}']) {
    sessionStorage.setItem('pendingQuizConsultation', value);
    localStorage.setItem('forceQuiz', 'true');
    assert.equal(resumeQuizConsultation({ is_logged_in: true }), false);
    assert.equal(localStorage.getItem('forceQuiz'), 'true');
    assert.equal(localStorage.getItem('targetQuizContext'), null);
  }
});

test('a newer consultation replaces a pending result', () => {
  queueQuizConsultation(result, true);
  queueQuizConsultation({ ...result, scores: { ...result.scores, work: 12 } });
  assert.equal(sessionStorage.getItem('pendingQuizConsultation'), null);
  assert.equal(JSON.parse(localStorage.getItem('targetQuizContext')).scores.work, 12);
});
