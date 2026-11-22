// 咖啡人格插畫：檔名 = 人格類型 key（work / env / social / taste / cp /
// work_env / taste_cp / balanced），由 scripts/sync_cafe_photos.py 同步產生
const personalityImages = import.meta.glob('../assets/personality/*.{jpg,jpeg,png,webp}', {
  eager: true,
  import: 'default',
});

export const getPersonalityImage = (typeKey) => {
  if (!typeKey) return null;
  for (const ext of ['jpg', 'jpeg', 'png', 'webp']) {
    const img = personalityImages[`../assets/personality/${typeKey}.${ext}`];
    if (img) return img;
  }
  return null;
};

// 測驗頁把最近一次的結果放在 sessionStorage（切頁再回來不會重置）
export const QUIZ_RESULT_CACHE_KEY = 'quizResultCache';

export function readCachedQuizResult() {
  try {
    return JSON.parse(sessionStorage.getItem(QUIZ_RESULT_CACHE_KEY) || 'null');
  } catch {
    return null;
  }
}
