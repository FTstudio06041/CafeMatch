import json
import re
from flask import current_app, session
from database import db
from models import User, Cafes, Tags, AiQueryLog
from services import ai_service, conversation_guide, preference_service
from services.intent_classifier import classify_intent
from services.cafe_retriever import retrieve_cafe_data, format_cafe_context, serialize_cafe
from services.ollama_admin_service import check_health, get_default_model
from services.settings_service import get_selected_model
from config.ai_constants import CHAT_EXIT_KEYWORDS

class ChatPipelineService:
    @staticmethod
    def generate_pipeline(data, is_debug_requested):
        try:
            user_message = data.get('message', '')
            history = data.get('history', [])
            is_quiz_result = data.get('is_quiz_result', False)
            force_recommend = data.get('force_recommend', False)

            if not user_message:
                yield json.dumps({"error": "未提供訊息", "done": True}, ensure_ascii=False) + "\n"
                return

            if not check_health():
                yield json.dumps({"error": "Ollama 連線失敗，請確認是否已啟動 Ollama。", "done": True}, ensure_ascii=False) + "\n"
                return

            yield json.dumps({"status": "analyzing_intent"}, ensure_ascii=False) + "\n"
            is_cafe_related, matched_keywords = classify_intent(user_message)
            if not is_cafe_related and len(history) > 0:
                lower_msg = user_message.lower()
                if not any(kw in lower_msg for kw in CHAT_EXIT_KEYWORDS):
                    is_cafe_related = True

            extracted_data = None
            guide_instruction = None

            if is_cafe_related:
                if is_quiz_result:
                    # 心理測驗結果進場：先讓 AI 根據測驗結果確認這次的實際需求，
                    # 不直接推薦；後續輪次的偏好照常回流狀態機決定何時推薦
                    yield json.dumps({"status": "processing_quiz_result"}, ensure_ascii=False) + "\n"
                    from config.prompts import QUIZ_RESULT_CONFIRMATION_INSTRUCTION
                    guide_instruction = QUIZ_RESULT_CONFIRMATION_INSTRUCTION
                else:
                    yield json.dumps({"status": "extracting_preferences"}, ensure_ascii=False) + "\n"
                    model_name = get_selected_model() or get_default_model()
                    extracted_data = preference_service.extract_preferences(history, user_message, model_name)

                    temp_history = history.copy()
                    temp_history.append({"role": "user", "content": user_message})

                    # 累積偏好：先前輪次確認過的偏好（隨對話儲存、由前端帶回）
                    # 與本輪萃取結果合併 — 長對話不再因 6 則歷史視窗而「失憶」
                    base_prefs = ChatPipelineService._clean_pref_dict(
                        (data.get('pref_state') or {}).get('preferences')
                        if isinstance(data.get('pref_state'), dict) else None
                    )
                    fresh_prefs = (extracted_data or {}).get("preferences") or {}
                    merged_prefs = ChatPipelineService._merge_preferences(base_prefs, fresh_prefs)

                    # 「都可以／沒特別需求」這類明確回答也計入維度：
                    # 使用者明說沒偏好，等同回答了該維度，百分比要照實反映
                    merged_prefs = conversation_guide.apply_no_preference_answers(
                        temp_history, merged_prefs
                    )
                    extracted_data = {"preferences": merged_prefs}

                    all_keywords = []
                    for vals in merged_prefs.values():
                        all_keywords.extend(v for v in vals if v != '不限')
                    matched_keywords = list(set(matched_keywords + all_keywords))

                    # 回報累積偏好與維度數：前端即時更新百分比、並隨對話儲存
                    collected_dims = sum(1 for v in merged_prefs.values() if v)
                    yield json.dumps({"progress_dims": collected_dims}, ensure_ascii=False) + "\n"
                    yield json.dumps(
                        {"pref_state": {"preferences": merged_prefs}}, ensure_ascii=False
                    ) + "\n"

                    if force_recommend:
                        # 使用者按下「直接推薦」：跳過確認需求，直接以現有資訊推薦
                        guide_instruction = None
                    else:
                        # 確認需求 → 結果丟給狀態機（狀態機只負責確認節奏，永不出卡片）
                        guide_instruction = conversation_guide.analyze_and_guide(temp_history, extracted_data)

            # 推薦（出卡片）只發生在使用者按下「直接推薦咖啡廳」按鈕的那一輪
            cafe_context = ""
            cafes = []
            recommend_engine = None
            if is_cafe_related and force_recommend:
                yield json.dumps({"status": "retrieving_cafes"}, ensure_ascii=False) + "\n"
                # 「換一批」：排除這個對話已經推薦過的店家
                exclude_ids = set()
                for cid in (data.get('exclude_cafe_ids') or []):
                    try:
                        exclude_ids.add(int(cid))
                    except (TypeError, ValueError):
                        continue

                # GNN 推薦接口：測驗基礎分數 × 對話確認結果 → 調整五維 → GNN 打分
                cafes = ChatPipelineService._recommend_with_gnn(
                    data, history, user_message, extracted_data, exclude_ids
                )
                if cafes:
                    recommend_engine = "gnn"
                if not cafes:
                    cafes = retrieve_cafe_data(matched_keywords, Cafes, Tags)
                    if exclude_ids:
                        remaining = [c for c in cafes if c.id not in exclude_ids]
                        # 全被排除時寧可重複推薦，也不要空手而回
                        cafes = remaining or cafes
                    if cafes:
                        recommend_engine = "keyword"
                if recommend_engine:
                    # 讓前端／測試可以驗證這批推薦來自哪個引擎
                    yield json.dumps({"recommend_engine": recommend_engine}, ensure_ascii=False) + "\n"
                cafe_context = format_cafe_context(cafes)
                if cafes:
                    yield json.dumps({"cafes": [serialize_cafe(c) for c in cafes]}, ensure_ascii=False) + "\n"
            elif not is_cafe_related:
                yield json.dumps({"status": "general_chat"}, ensure_ascii=False) + "\n"

            # 有卡片時：店名交給卡片呈現，不把知識庫店名餵給 LLM，並改用「卡片模式」格式（不准講店名）
            has_cards = bool(cafes)
            extracted_prefs = extracted_data.get("preferences") if extracted_data else None
            model_name = get_selected_model() or get_default_model()
            prompt_text = ai_service.build_prompt(
                user_message=user_message,
                history=history,
                is_cafe_related=is_cafe_related,
                cafe_context=("" if has_cards else cafe_context),
                guide_instruction=guide_instruction,
                extracted_preferences=extracted_prefs,
                cards_mode=has_cards
            )

            user_id = None
            is_admin = False
            user_email = session.get('user_email')
            if user_email:
                current_user = User.query.filter_by(email=user_email).first()
                if current_user:
                    user_id = current_user.id
                    is_admin = getattr(current_user, 'is_admin', False)

            show_debug = is_debug_requested and is_admin

            # 快速選項保底：選項是狀態機決定的，不依賴模型是否聽話。
            # 若指令有指定 [QUICK_OPTIONS] 而模型漏了，在 done 前補上。
            expected_options_line = None
            if guide_instruction:
                m = re.search(r'\[QUICK_OPTIONS\][^\n]+', guide_instruction)
                if m:
                    expected_options_line = m.group(0).strip()

            generated_text = ""
            yield json.dumps({"status": "generating_response"}, ensure_ascii=False) + "\n"
            for chunk in ai_service.stream_generate(
                model_name=model_name,
                prompt_text=prompt_text,
                is_cafe_related=is_cafe_related,
                cafe_context=cafe_context,
                db=db,
                AiQueryLog=AiQueryLog,
                user_id=user_id,
                show_debug=show_debug
            ):
                if expected_options_line:
                    try:
                        parsed = json.loads(chunk)
                        if parsed.get("response"):
                            generated_text += parsed["response"]
                        if parsed.get("done") and "[QUICK_OPTIONS]" not in generated_text:
                            yield json.dumps(
                                {"response": "\n\n" + expected_options_line},
                                ensure_ascii=False
                            ) + "\n"
                    except (ValueError, TypeError):
                        pass
                yield chunk

        except Exception as e:
            current_app.logger.exception(f"Chat API Error: {e}")
            yield json.dumps({"error": "系統暫時無法處理，請稍後再試", "done": True}, ensure_ascii=False) + "\n"

    # 偏好維度白名單（與 guide_dimensions.json / 萃取格式對齊）
    _ALLOWED_PREF_DIMS = ('purpose', 'vibe', 'taste', 'budget', 'special')

    @staticmethod
    def _clean_pref_dict(prefs):
        """驗證前端帶回的累積偏好：只收已知維度、字串值、每維度最多 6 個。"""
        clean = {}
        if not isinstance(prefs, dict):
            return clean
        for dim in ChatPipelineService._ALLOWED_PREF_DIMS:
            vals = prefs.get(dim)
            if not isinstance(vals, list):
                continue
            kept = [v.strip() for v in vals if isinstance(v, str) and v.strip()][:6]
            if kept:
                clean[dim] = kept
        return clean

    @staticmethod
    def _merge_preferences(base, fresh):
        """
        合併累積偏好與本輪萃取結果（去重、保序、每維度上限 6）。
        若某維度原本是「不限」而本輪出現真實偏好，以真實偏好取代。
        """
        merged = {}
        for dim in ChatPipelineService._ALLOWED_PREF_DIMS:
            vals = []
            for v in (base.get(dim) or []) + (fresh.get(dim) or []):
                if isinstance(v, str) and v and v not in vals:
                    vals.append(v)
            real = [v for v in vals if v != '不限']
            vals = real if real else vals
            if vals:
                merged[dim] = vals[:6]
        return merged

    @staticmethod
    def _recommend_with_gnn(data, history, user_message, extracted_data, exclude_ids=None):
        """
        GNN 推薦接口：
          心理測驗五維分數（payload 或 DB 最新紀錄）
          × 使用者對測驗準不準的回饋
          × 對話確認到的偏好
          → preference_adjuster 調整五維向量 → gnn_recommender 打分。

        任一環節失敗回傳 []，由呼叫端回退關鍵字檢索。
        """
        from services import gnn_recommender
        from services.preference_adjuster import build_gnn_input

        try:
            quiz_scores = data.get('quiz_scores')
            if not (isinstance(quiz_scores, dict) and quiz_scores):
                quiz_scores = ChatPipelineService._latest_quiz_scores_from_db()

            temp_history = history.copy()
            temp_history.append({"role": "user", "content": user_message})
            preferences = (extracted_data or {}).get("preferences")

            adjusted, hard_filters, accuracy = build_gnn_input(
                quiz_scores, temp_history, preferences
            )
            # 已表達的偏好關鍵字：與店家標籤混合排序，補足 GNN 對當輪需求的反應度
            pref_keywords = []
            for vals in (preferences or {}).values():
                pref_keywords.extend(v for v in vals if isinstance(v, str) and v != '不限')

            ranked = gnn_recommender.recommend_by_scores(
                adjusted, hard_filters, exclude_ids=exclude_ids,
                pref_keywords=pref_keywords
            )
            if not ranked:
                return []

            ids = [c['cafe_id'] for c in ranked]
            rows = {c.id: c for c in Cafes.query.filter(Cafes.id.in_(ids)).all()}
            cafes = [rows[i] for i in ids if i in rows]

            adjusted_str = {k: round(v, 1) for k, v in adjusted.items()}
            current_app.logger.info(
                f"[GNN] 推薦 {len(cafes)} 家（回饋={accuracy}、調整後五維={adjusted_str}、"
                f"硬過濾={hard_filters}、混合關鍵字={pref_keywords}）"
            )
            return cafes
        except gnn_recommender.GnnUnavailable as e:
            current_app.logger.warning(f"[GNN] 不可用，回退關鍵字檢索：{e}")
            return []
        except Exception as e:
            current_app.logger.exception(f"[GNN] 推薦失敗，回退關鍵字檢索：{e}")
            return []

    @staticmethod
    def _latest_quiz_scores_from_db():
        """登入使用者：從資料庫取最新一次心理測驗的五維分數。"""
        user_email = session.get('user_email')
        if not user_email:
            return None
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return None
        from models import UserQuizResult
        record = UserQuizResult.query.filter_by(user_id=user.id)\
            .order_by(UserQuizResult.created_at.desc()).first()
        if not record:
            return None
        return {
            'work': record.score_work,
            'env': record.score_env,
            'social': record.score_social,
            'taste': record.score_taste,
            'cp': record.score_cp,
        }
