# services/cafe_retriever.py
import logging
from sqlalchemy import or_
from config.ai_constants import CAFE_TAG_MATCH_LIMIT, CAFE_NAME_MATCH_LIMIT, CAFE_TAGS_DISPLAY_LIMIT

DAY_NAMES = ['', '一', '二', '三', '四', '五', '六', '日']

def retrieve_cafe_context(matched_keywords, Cafes, Tags):
    """
    根據命中的關鍵字從資料庫檢索相關咖啡廳資料，
    並組裝成可注入 Prompt 的上下文文字。

    參數:
        matched_keywords: 使用者訊息中命中的關鍵字列表
        Cafes: SQLAlchemy Cafes 模型類別
        Tags: SQLAlchemy Tags 模型類別

    回傳:
        cafe_context: str — 格式化後的咖啡廳資料上下文
    """
    try:
        # 建立篩選條件
        tag_filters = []
        name_filters = []
        for kw in matched_keywords:
            tag_filters.append(Tags.tag_name.contains(kw))
            name_filters.append(Cafes.name.contains(kw))
            name_filters.append(Cafes.address.contains(kw))

        # 先找標籤匹配的咖啡廳
        tagged_cafes = Cafes.query.join(Cafes.tags).filter(
            or_(*tag_filters)
        ).distinct().limit(CAFE_TAG_MATCH_LIMIT).all() if tag_filters else []

        # 再找名稱/地址匹配的
        name_cafes = Cafes.query.filter(
            or_(*name_filters)
        ).limit(CAFE_NAME_MATCH_LIMIT).all() if name_filters else []

        # 合併去重（最多取 5 家）
        seen_ids = set()
        relevant_cafes = []
        for cafe in tagged_cafes + name_cafes:
            if cafe.id not in seen_ids and len(relevant_cafes) < 5:
                seen_ids.add(cafe.id)
                relevant_cafes.append(cafe)

        # 如果關鍵字匹配不到，就拿最熱門的 5 家
        if not relevant_cafes:
            relevant_cafes = Cafes.query.order_by(Cafes.num.desc()).limit(CAFE_TAG_MATCH_LIMIT).all()

        # 組裝上下文
        cafe_lines = []
        for cafe in relevant_cafes:
            tags_str = ', '.join([t.tag_name for t in cafe.tags[:CAFE_TAGS_DISPLAY_LIMIT]])

            # 營業時間簡要
            hours_parts = []
            for h in sorted(cafe.hours, key=lambda x: x.day_of_week or 0):
                if h.is_closed:
                    hours_parts.append(f"週{DAY_NAMES[h.day_of_week]}:公休")
                elif h.open_time and h.close_time:
                    hours_parts.append(
                        f"週{DAY_NAMES[h.day_of_week]}:"
                        f"{h.open_time.strftime('%H:%M')}-{h.close_time.strftime('%H:%M')}"
                    )
            hours_str = '、'.join(hours_parts) if hours_parts else '未提供'

            cafe_lines.append(
                f"- {cafe.name} | 地址：{cafe.address or '未提供'} | 消費：{cafe.cost or '未提供'} | "
                f"標籤：{tags_str or '無'} | 營業：{hours_str}"
            )

        if cafe_lines:
            return "\n".join(cafe_lines)
        return ""

    except Exception as e:
        logging.error(f"RAG 查詢失敗: {e}")
        return ""
