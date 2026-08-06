import json
import re
from flask import current_app, session
from database import db
from models import User, Cafes, Tags, AiQueryLog
from services import ai_service, conversation_guide, preference_service, debug_logger
from services.preference_adjuster import build_gnn_input
from services.intent_classifier import classify_intent, is_off_topic
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

            # 使用者直接說「不要問了，推薦給我」→ 等同按下推薦按鈕，
            # 不該再擋一輪追問（那正是鬼打牆的感受來源）
            if not force_recommend and not is_quiz_result and \
                    conversation_guide.wants_recommendation(user_message):
                force_recommend = True

            if not user_message:
                yield json.dumps({"error": "未提供訊息", "done": True}, ensure_ascii=False) + "\n"
                return

            if not check_health():
                yield json.dumps({"error": "Ollama 連線失敗，請確認是否已啟動 Ollama。", "done": True}, ensure_ascii=False) + "\n"
                return

            yield json.dumps({"status": "analyzing_intent"}, ensure_ascii=False) + "\n"
            is_cafe_related, matched_keywords = classify_intent(user_message)

            # 明確與咖啡廳無關的請求（寫詩、寫程式、問天氣…）→ 直接婉拒並說明用途。
            # 不做偏好萃取、不進狀態機，也不能真的照做。
            off_topic, off_topic_hit = is_off_topic(user_message)
            if off_topic:
                from config.prompts import OFF_TOPIC_INSTRUCTION
                debug_logger.log_off_topic(user_message, off_topic_hit)
                yield from ChatPipelineService._respond_only(
                    OFF_TOPIC_INSTRUCTION, user_message, history,
                    is_debug_requested=is_debug_requested,
                )
                return

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
                    debug_logger.log_quiz_result(data.get('quiz_scores'), user_message)
                else:
                    yield json.dumps({"status": "extracting_preferences"}, ensure_ascii=False) + "\n"
                    model_name = get_selected_model() or get_default_model()
                    extracted_raw = preference_service.extract_preferences(history, user_message, model_name)
                    extracted_data = extracted_raw

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

                    # 每一輪都重算五維向量：使用者的回答會即時改變推薦的權重，
                    # 不必等到按下推薦按鈕才知道自己的回答造成什麼影響
                    quiz_scores = ChatPipelineService._resolve_quiz_scores(data)
                    has_quiz = bool(quiz_scores and any(quiz_scores.values()))
                    live_scores, live_filters, live_accuracy = build_gnn_input(
                        quiz_scores, temp_history, merged_prefs
                    )

                    # 進度條的基準值與目標值一律由後端決定（前端不再自己猜）：
                    #   有測驗分數 → 從 50% 起跳，目標依信任度 3~5 維
                    #   沒有測驗   → 從 0% 起跳，目標 5 維（全靠對話認識使用者）
                    collected_dims = sum(1 for v in merged_prefs.values() if v)
                    progress_target = conversation_guide.get_target_dimensions(
                        temp_history, has_quiz=has_quiz
                    )
                    progress_base = conversation_guide.QUIZ_PROGRESS_BASE if has_quiz else 0
                    # 資料太少就推薦等於亂猜，前端據此決定推薦按鈕能不能按
                    ready = conversation_guide.is_ready_to_recommend(
                        temp_history, collected_dims, has_quiz=has_quiz
                    )
                    yield json.dumps({
                        "progress_dims": collected_dims,
                        "progress_target": progress_target,
                        "progress_base": progress_base,
                        "recommend_ready": ready,
                        "recommend_needs": conversation_guide.dimensions_needed_to_recommend(
                            temp_history, has_quiz=has_quiz
                        ),
                    }, ensure_ascii=False) + "\n"

                    yield json.dumps({
                        "pref_state": {"preferences": merged_prefs},
                        "dimension_scores": {k: round(v, 1) for k, v in live_scores.items()},
                    }, ensure_ascii=False) + "\n"

                    # 資料還不夠就要求推薦 → 擋下來，改成再確認一題。
                    # （實測沒有任何偏好時，模型對不同需求給出的推薦幾乎一樣，
                    #   等於亂猜；寧可多問一題也不要給沒根據的結果。）
                    blocked = force_recommend and not ready
                    if blocked:
                        force_recommend = False
                        debug_logger.log_blocked_recommend(
                            collected_dims,
                            conversation_guide.dimensions_needed_to_recommend(
                                temp_history, has_quiz=has_quiz),
                        )

                    if force_recommend:
                        # 使用者按下「直接推薦」：跳過確認需求，直接以現有資訊推薦
                        guide_instruction = None
                    else:
                        # 確認需求 → 結果丟給狀態機（狀態機只負責確認節奏，永不出卡片）
                        guide_instruction = conversation_guide.analyze_and_guide(
                            temp_history, extracted_data, has_quiz=has_quiz
                        )

                    # 終端除錯輸出：這一輪知道了什麼、決定做什麼
                    decision, focus = ChatPipelineService._describe_decision(
                        guide_instruction, force_recommend
                    )
                    # 上一輪的五維（只用先前累積的偏好算），用來顯示這輪的增減
                    prev_scores, _, _ = build_gnn_input(quiz_scores, history, base_prefs)
                    debug_logger.log_round(
                        turn=sum(1 for m in temp_history if m.get('role') == 'user'),
                        user_message=user_message,
                        fresh_prefs=fresh_prefs,
                        merged_prefs=merged_prefs,
                        dims=collected_dims,
                        decision=decision,
                        focus_dim=focus,
                        fast_path=bool((extracted_raw or {}).get('fast_path')),
                        scores=live_scores,
                        prev_scores=prev_scores,
                        asked=conversation_guide.get_asked_dimensions(temp_history),
                    )

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
            elif is_cafe_related and not force_recommend:
                # 新增：聊天過程中的輕量 RAG，只給文字參考，不出卡片
                yield json.dumps({"status": "retrieving_context"}, ensure_ascii=False) + "\n"
                context_cafes = retrieve_cafe_data(matched_keywords, Cafes, Tags)
                if context_cafes:
                    cafe_context = format_cafe_context(context_cafes)
                    # cafes 仍保持 []，不觸發卡片顯示

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
                    # GNN 失敗時走這條，除錯輸出要標明是回退路徑
                    debug_logger.log_recommendation(
                        accuracy='-', base_scores=None, adjusted_scores=None,
                        hard_filters=None, keywords=matched_keywords,
                        engine='keyword', cafes=cafes, excluded=len(exclude_ids),
                    )
                if recommend_engine:
                    # 讓前端／測試可以驗證這批推薦來自哪個引擎
                    yield json.dumps({"recommend_engine": recommend_engine}, ensure_ascii=False) + "\n"
                cafe_context = format_cafe_context(cafes)
                if cafes:
                    yield json.dumps({"cafes": [serialize_cafe(c) for c in cafes]}, ensure_ascii=False) + "\n"
            elif not is_cafe_related:
                yield json.dumps({"status": "general_chat"}, ensure_ascii=False) + "\n"

            # 推薦後追問（「第一家在哪裡？」「有停車位嗎？」）：
            # 把先前推薦過的店家資料餵回去，AI 才答得出來，
            # 而不是每次都叫使用者自己去點卡片。
            from config.prompts.guide_instructions import (
                ALREADY_RECOMMENDED_INSTRUCTION as _POST_REC,
                ALREADY_RECOMMENDED_NO_DATA_INSTRUCTION as _POST_REC_NO_DATA,
            )
            if guide_instruction == _POST_REC and not cafes:
                shown = ChatPipelineService._load_shown_cafes(data)
                if shown:
                    cafe_context = "【已推薦店家】\n" + format_cafe_context(shown)
                else:
                    # 拿不到資料就換一版指令，明確禁止模型編造店名與地址
                    guide_instruction = _POST_REC_NO_DATA

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
                try:
                    parsed = json.loads(chunk)
                except (ValueError, TypeError):
                    yield chunk
                    continue

                if parsed.get("response"):
                    generated_text += parsed["response"]

                if parsed.get("done"):
                    # 模型偶爾整段空白（例如使用者只回「嗯」），
                    # 空訊息在畫面上會變成「生成中斷或無回應」，這裡補一句話兜底
                    if not generated_text.strip():
                        yield json.dumps(
                            {"response": ChatPipelineService._fallback_reply(guide_instruction)},
                            ensure_ascii=False
                        ) + "\n"
                    elif expected_options_line and "[QUICK_OPTIONS]" not in generated_text:
                        yield json.dumps(
                            {"response": "\n\n" + expected_options_line},
                            ensure_ascii=False
                        ) + "\n"
                yield chunk

        except Exception as e:
            current_app.logger.exception(f"Chat API Error: {e}")
            yield json.dumps({"error": "系統暫時無法處理，請稍後再試", "done": True}, ensure_ascii=False) + "\n"

    # 偏好維度白名單（與 guide_dimensions.json / 萃取格式對齊）
    _ALLOWED_PREF_DIMS = ('purpose', 'vibe', 'taste', 'budget', 'special')

    @staticmethod
    def _respond_only(instruction, user_message, history, is_debug_requested=False):
        """
        只依指令生成一段回覆就結束：不萃取偏好、不進狀態機、不檢索店家。
        用於離題婉拒這類「回一句就好」的情境。
        """
        model_name = get_selected_model() or get_default_model()
        prompt_text = ai_service.build_prompt(
            user_message=user_message,
            history=history,
            is_cafe_related=False,
            cafe_context="",
            guide_instruction=instruction,
            extracted_preferences=None,
            cards_mode=False,
        )

        user_id, is_admin = None, False
        user_email = session.get('user_email')
        if user_email:
            current_user = User.query.filter_by(email=user_email).first()
            if current_user:
                user_id = current_user.id
                is_admin = getattr(current_user, 'is_admin', False)

        generated = ""
        yield json.dumps({"status": "generating_response"}, ensure_ascii=False) + "\n"
        for chunk in ai_service.stream_generate(
            model_name=model_name,
            prompt_text=prompt_text,
            is_cafe_related=False,
            cafe_context="",
            db=db,
            AiQueryLog=AiQueryLog,
            user_id=user_id,
            show_debug=is_debug_requested and is_admin,
        ):
            try:
                parsed = json.loads(chunk)
                if parsed.get("response"):
                    generated += parsed["response"]
                if parsed.get("done") and not generated.strip():
                    yield json.dumps({
                        "response": "抱歉，我是花蓮咖啡廳推薦系統，只能幫你找店。"
                                    "想找什麼樣的咖啡廳呢？"
                    }, ensure_ascii=False) + "\n"
            except (ValueError, TypeError):
                pass
            yield chunk

    @staticmethod
    def _fallback_reply(guide_instruction):
        """模型回空白時的兜底句子（依當下狀態給合理回應）。"""
        kind, _ = conversation_guide.classify_instruction(guide_instruction)
        return {
            '邀請後閒聊': '好的，隨時可以按下方的「直接推薦咖啡廳」按鈕。',
            '邀請按鈕': '需求我大致掌握了，可以按下方的「直接推薦咖啡廳」按鈕。',
            '推薦後': '店家細節可以點卡片查看；想換一批就再按一次推薦按鈕。',
            '回答提問': '這我不太確定，你可以按下方的「直接推薦咖啡廳」按鈕看看實際店家。',
        }.get(kind, '好的，還有什麼想補充的嗎？')

    @staticmethod
    def _load_shown_cafes(data):
        """取出這個對話已經推薦過的店家（供推薦後追問時回答細節用）。"""
        ids = []
        for cid in (data.get('exclude_cafe_ids') or []):
            try:
                ids.append(int(cid))
            except (TypeError, ValueError):
                continue
        if not ids:
            return []
        rows = {c.id: c for c in Cafes.query.filter(Cafes.id.in_(ids)).all()}
        return [rows[i] for i in ids if i in rows]

    @staticmethod
    def _resolve_quiz_scores(data):
        """取得心理測驗五維分數：優先用前端帶的，否則查資料庫最新一筆。"""
        scores = data.get('quiz_scores')
        if isinstance(scores, dict) and scores:
            return scores
        return ChatPipelineService._latest_quiz_scores_from_db()

    _DECISION_TEXT = {
        '確認': '確認需求',
        '邀請按鈕': '資訊足夠 → 邀請使用者按推薦按鈕',
        '推薦後': '推薦後問答（用已推薦店家資料回答）',
        '測驗確認': '詢問測驗結果是否準確',
        '回答提問': '使用者在提問 → 先回答，不追問',
        '邀請後閒聊': '已邀請過按鈕 → 自然回應，不重複邀請',
        '直接推薦': '直接推薦',
    }

    @staticmethod
    def _describe_decision(guide_instruction, force_recommend):
        """把狀態機的決定翻成人看得懂的字串（供終端除錯輸出）。"""
        if force_recommend:
            return '略過確認（使用者按下推薦按鈕）', None
        kind, focus = conversation_guide.classify_instruction(guide_instruction)
        return ChatPipelineService._DECISION_TEXT.get(kind, '其他引導'), focus

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
            quiz_scores = ChatPipelineService._resolve_quiz_scores(data)

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

            debug_logger.log_recommendation(
                accuracy=accuracy,
                base_scores=quiz_scores,
                adjusted_scores=adjusted,
                hard_filters=hard_filters,
                keywords=pref_keywords,
                engine='gnn',
                cafes=cafes,
                excluded=len(exclude_ids or []),
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
