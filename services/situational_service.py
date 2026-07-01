"""
situational_service.py — Chat page 情境元件的偏好解析

職責：讀取 data/situational_seeds.json，將前端送來的情境選項答案，
     解析成推薦系統需要的結構化輸入：
       - tag_weights：加權標籤（餵給帶權重檢索器）
       - hours_window：營業時間窗（→ OperatingHours 硬過濾）
       - cost_range：價位範圍（→ cost 欄位硬過濾）
       - soft_hints：對不到 tag 的字（停車、手沖…），給 LLM 當提示
       - summary_text：自然語言摘要，作為餵給 LLM 的「使用者訊息」

設計原則：
  - 單一事實來源 = situational_seeds.json（標籤/過濾條件由設定檔決定，
    不信任前端直接送標籤，只收選項 value）
  - 純資料轉換，不依賴 Flask / SQLAlchemy / Ollama
"""

import json
import os

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'data', 'situational_seeds.json'
)

_config_cache = None
_config_mtime = 0

# 各維度標籤的預設權重（兩層題 vibe/taste 另由使用者的 0-4 分數決定）
_DEFAULT_WEIGHTS = {
    "time": 2,
    "purpose": 3,   # activity + companion
    "budget": 2,
    "special": 3,
}


# ==========================================
# 公開介面
# ==========================================

def get_questions():
    """回傳題目定義（供 /api/situational/questions 與內部解析共用）。"""
    return _load_config().get("questions", [])


def build_recommendation_input(answers: dict) -> dict:
    """
    將前端情境答案解析成結構化推薦輸入。

    參數:
        answers: dict — 例如
            {
              "time": "afternoon",
              "activity": "work",
              "companion": "big_group",
              "vibe": {"score": 3, "flavor": "greenery"},
              "taste": {"score": 1},
              "budget": {"value": "cheap"}  或  {"custom": 120},
              "special": ["outlet", "quiet"]
            }

    回傳:
        dict — tag_weights / hours_window / cost_range / soft_hints / summary_text
    """
    answers = answers or {}
    tag_weight_map = {}   # tag -> max weight
    soft_hints = []
    summary_parts = []

    def add_tags(tags, weight):
        for t in tags or []:
            if t:
                tag_weight_map[t] = max(tag_weight_map.get(t, 0), weight)

    def add_hints(opt):
        for h in (opt.get("soft_hint") or []):
            if h and h not in soft_hints:
                soft_hints.append(h)

    # --- 時間 ---
    hours_window = None
    topt = _option(_question("time"), answers.get("time"))
    if topt:
        if topt.get("hours_window"):
            hours_window = topt["hours_window"]
        add_tags(topt.get("tags"), _DEFAULT_WEIGHTS["time"])
        add_hints(topt)
        if answers.get("time") and answers.get("time") != "any":
            summary_parts.append(f"時段：{topt['label']}")

    # --- 活動 + 同行 ---
    aq = _question("activity")
    aopt = _option(aq, answers.get("activity"))
    if aopt:
        add_tags(aopt.get("tags"), _DEFAULT_WEIGHTS["purpose"])
        add_hints(aopt)
        summary_parts.append(f"主要想{aopt['label']}")
    cval = answers.get("companion")
    if aq and cval:
        copt = _followup_option(aq, "companion", cval)
        if copt:
            add_tags(copt.get("tags"), _DEFAULT_WEIGHTS["purpose"])
            add_hints(copt)
            if cval != "any":
                summary_parts.append(f"同行：{copt['label']}")

    # --- 兩層題：氛圍、餐飲 ---
    for qid, human in (("vibe", "空間氛圍"), ("taste", "餐飲")):
        q = _question(qid)
        if not q:
            continue
        ans = answers.get(qid) or {}
        score = _as_int(ans.get("score"))
        if score is None:
            continue
        trigger = q.get("flavor_trigger_min", 2)
        if score >= 1:
            add_tags(q.get("base_tags"), 1)
        flavor_val = ans.get("flavor")
        if score >= trigger and flavor_val and flavor_val != "any":
            fopt = _flavor_option(q, flavor_val)
            if fopt:
                add_tags(fopt.get("tags"), max(score, 2))
                add_hints(fopt)
                summary_parts.append(f"{human}：很在意（{score}/4），偏好「{fopt['label']}」")
                continue
        if score >= 1:
            summary_parts.append(f"{human}：在意程度 {score}/4")
        else:
            summary_parts.append(f"{human}：不特別在意")

    # --- 預算 ---
    cost_range = None
    bq = _question("budget")
    bans = answers.get("budget") or {}
    custom = bans.get("custom")
    if custom is not None:
        c = _as_int(custom)
        if c is not None:
            cost_range = {"min": 0, "max": c}
            summary_parts.append(f"預算：每人約 NT${c}")
    elif bans.get("value"):
        bopt = _option(bq, bans["value"])
        if bopt:
            cmin, cmax = bopt.get("cost_min"), bopt.get("cost_max")
            if cmin is not None or cmax is not None:
                cost_range = {"min": cmin, "max": cmax}
            add_tags(bopt.get("tags"), _DEFAULT_WEIGHTS["budget"])
            if bans["value"] != "any":
                summary_parts.append(f"預算：{bopt['label']}")

    # --- 特殊需求（多選）---
    sq = _question("special")
    svals = answers.get("special") or []
    if isinstance(svals, list):
        picked = []
        for sv in svals:
            if sv == "none":
                continue
            sopt = _option(sq, sv)
            if sopt:
                add_tags(sopt.get("tags"), _DEFAULT_WEIGHTS["special"])
                add_hints(sopt)
                picked.append(sopt["label"])
        if picked:
            summary_parts.append("特殊需求：" + "、".join(picked))

    tag_weights = [
        {"tag": t, "weight": w}
        for t, w in sorted(tag_weight_map.items(), key=lambda kv: kv[1], reverse=True)
    ]

    if summary_parts:
        summary_text = "使用者透過情境選單提供了以下偏好——" + "；".join(summary_parts) + "。"
    else:
        summary_text = "使用者沒有特別指定條件。"
    if soft_hints:
        summary_text += "另外特別提到：" + "、".join(soft_hints) + "（若資料庫中有符合的店家請優先考慮）。"
    summary_text += (
        "請根據以上情境，從知識庫中挑選最適合的花蓮咖啡廳推薦給使用者。"
        "店家的圖片與詳細資訊會另外以卡片呈現，你只需用親切、口語的方式說明為什麼這些店適合我，"
        "不必條列地址或營業時間等細節。"
    )

    return {
        "tag_weights": tag_weights,
        "hours_window": hours_window,
        "cost_range": cost_range,
        "soft_hints": soft_hints,
        "summary_text": summary_text,
    }


# ==========================================
# 內部輔助
# ==========================================

def _load_config() -> dict:
    """讀取 situational_seeds.json，帶檔案修改時間快取（避免每次都做磁碟 I/O）。"""
    global _config_cache, _config_mtime
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        mtime = 0
    if _config_cache is None or mtime != _config_mtime:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config_cache = json.load(f)
        _config_mtime = mtime
    return _config_cache


def _question(qid):
    for q in get_questions():
        if q.get("id") == qid:
            return q
    return None


def _option(question, value):
    if not question or value is None:
        return None
    for opt in question.get("options", []):
        if opt.get("value") == value:
            return opt
    return None


def _followup_option(question, followup_key, value):
    followup = (question.get("followups") or {}).get(followup_key)
    if not followup:
        return None
    for opt in followup.get("options", []):
        if opt.get("value") == value:
            return opt
    return None


def _flavor_option(question, value):
    for opt in (question.get("flavor") or {}).get("options", []):
        if opt.get("value") == value:
            return opt
    return None


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
