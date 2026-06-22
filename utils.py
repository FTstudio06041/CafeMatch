from database import db
from models import AdminLog

def log_action(email, action, detail=''):
    try:
        log = AdminLog(user_email=email, action=action, detail=detail)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f'Log error: {e}')
        db.session.rollback()

def admin_required(f):
    from functools import wraps
    from flask import session, jsonify
    from models import User
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "未登入"}), 401
        user = User.query.filter_by(email=user_email).first()
        if not user or not user.is_admin:
            return jsonify({"error": "權限不足"}), 403
        return f(*args, **kwargs)
    return decorated_function

import requests
from flask import current_app, url_for

GOOGLE_PLACES_TEXT_SEARCH_URL = 'https://places.googleapis.com/v1/places:searchText'

def has_google_maps_key():
    return bool(current_app.config.get('GOOGLE_MAPS_API_KEY'))

def get_cafe_image_url(cafe):
    if cafe.image:
        return cafe.image
    if not has_google_maps_key():
        return ''
    return url_for('explore.get_cafe_photo', cafe_id=cafe.id, _external=True)

def build_google_place_query(cafe):
    parts = [cafe.name]
    if cafe.address:
        parts.append(cafe.address)
    else:
        parts.append('花蓮 咖啡廳')
    return ' '.join(part for part in parts if part)

def ensure_google_place_id(cafe):
    if cafe.google_place_id:
        return cafe.google_place_id

    api_key = current_app.config.get('GOOGLE_MAPS_API_KEY')
    if not api_key:
        return None

    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress',
    }
    payload = {
        'textQuery': build_google_place_query(cafe),
        'languageCode': 'zh-TW',
        'regionCode': 'TW',
    }

    response = requests.post(GOOGLE_PLACES_TEXT_SEARCH_URL, headers=headers, json=payload, timeout=10)
    response.raise_for_status()
    places = response.json().get('places', [])
    if not places:
        return None

    cafe.google_place_id = places[0].get('id')
    db.session.commit()
    return cafe.google_place_id

def get_google_photo_uri(cafe, max_width=900):
    api_key = current_app.config.get('GOOGLE_MAPS_API_KEY')
    place_id = ensure_google_place_id(cafe)
    if not api_key or not place_id:
        return None

    details_url = f'https://places.googleapis.com/v1/places/{place_id}'
    details_headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': api_key,
        'X-Goog-FieldMask': 'photos',
    }
    details_response = requests.get(
        details_url,
        headers=details_headers,
        params={'languageCode': 'zh-TW'},
        timeout=10
    )
    details_response.raise_for_status()
    photos = details_response.json().get('photos', [])
    if not photos:
        return None

    photo = photos[0]
    attributions = photo.get('authorAttributions') or []
    attribution_text = ', '.join(
        item.get('displayName', '').strip()
        for item in attributions
        if item.get('displayName')
    )
    if attribution_text != (cafe.google_photo_attribution or ''):
        cafe.google_photo_attribution = attribution_text
        db.session.commit()

    photo_name = photo.get('name')
    if not photo_name:
        return None

    media_response = requests.get(
        f'https://places.googleapis.com/v1/{photo_name}/media',
        params={
            'maxWidthPx': max(1, min(int(max_width), 4800)),
            'skipHttpRedirect': 'true',
            'key': api_key,
        },
        timeout=10
    )
    media_response.raise_for_status()
    return media_response.json().get('photoUri')




def delete_user_data(user_id, db):
    from models import User, UserShopState, ChatSession, ChatFeedback, UserQuizResult, CommunityPost, PostLike, PostComment, CommunityNote, CommunityLike, CommunityComment
    
    # 刪除與此使用者相關的所有按讚和留言
    PostLike.query.filter_by(user_id=user_id).delete()
    PostComment.query.filter_by(user_id=user_id).delete()
    CommunityLike.query.filter_by(user_id=user_id).delete()
    CommunityComment.query.filter_by(user_id=user_id).delete()
    
    # 刪除便利貼 (必須先清空「所有」其他使用者對這些便利貼的按讚和留言)
    user_notes = CommunityNote.query.filter_by(user_id=user_id).all()
    for note in user_notes:
        CommunityLike.query.filter_by(note_id=note.id).delete()
        CommunityComment.query.filter_by(note_id=note.id).delete()
        db.session.delete(note)
        
    # 刪除貼文 (必須先清空讚和留言，並斷開 repost 關聯)
    posts = CommunityPost.query.filter_by(user_id=user_id).all()
    for post in posts:
        PostLike.query.filter_by(post_id=post.id).delete()
        PostComment.query.filter_by(post_id=post.id).delete()
        CommunityPost.query.filter_by(original_post_id=post.id).update({CommunityPost.original_post_id: None})
        db.session.delete(post)
        
    # 刪除聊天紀錄與測驗
    ChatSession.query.filter_by(user_id=user_id).delete()
    ChatFeedback.query.filter_by(user_id=user_id).delete()
    UserQuizResult.query.filter_by(user_id=user_id).delete()

    # 刪除收藏
    UserShopState.query.filter_by(user_id=user_id).delete()
    
    # 刪除使用者
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
