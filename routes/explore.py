import requests
import random
from flask import Blueprint, jsonify, request, session, redirect, current_app, url_for
from database import db
from models import Cafes, User, UserShopState

explore_bp = Blueprint('explore', __name__)

from utils import has_google_maps_key, get_cafe_image_url, get_google_photo_uri

@explore_bp.route('/api/cafes', methods=['GET'])
def get_cafes():
    try:
        all_cafes = Cafes.query.all()
        results = []
        
        user_email = session.get('user_email')
        user_states = {} 
        
        current_user = None
        if user_email:
            current_user = User.query.filter_by(email=user_email).first()
        
        if current_user:
            states = UserShopState.query.filter_by(user_id=current_user.id).all()
            for s in states:
                user_states[s.cafe_id] = {'fav': s.is_fav, 'visited': s.is_visited}

        for cafe in all_cafes:
            tag_list = [f"#{t.tag_name}" for t in cafe.tags]
            tag_str = " ".join(tag_list) if tag_list else "#無標籤"

            hours_str = "營業時間請洽店家"
            if cafe.hours:
                for h in cafe.hours:
                    if h.is_closed == 0 and h.open_time and h.close_time:
                        try:
                            o_time = h.open_time.strftime('%H:%M')
                            c_time = h.close_time.strftime('%H:%M')
                            hours_str = f"{o_time} - {c_time}"
                        except:
                            pass
                        break
            
            my_state = user_states.get(cafe.id, {'fav': False, 'visited': False})

            map_link = ""
            if cafe.url:
                map_link = f"http://maps.app.goo.gl/{cafe.url}"
            
            palette = [
                "#8D6E63", "#A1887F", "#BCAAA4", "#D7CCC8", 
                "#795548", "#6D4C41", "#5D4037", "#4E342E", 
                "#78909C", "#607D8B", "#546E7A"             
            ]
            
            color_idx = cafe.id % len(palette)
            
            results.append({
                "id": cafe.id,
                "name": cafe.name,
                "tags": tag_str,
                "rating": None,
                "hours": hours_str,
                "phone": cafe.phone or "無電話",
                "address": cafe.address or "地址未知",
                "desc": cafe.website or "尚無介紹",
                "color": palette[color_idx], 
                "image": cafe.image or "",
                "image_url": get_cafe_image_url(cafe),
                "image_source": "manual" if cafe.image else ("google" if has_google_maps_key() else ""),
                "image_attribution": cafe.google_photo_attribution or "",
                "map_url": map_link, 
                "is_fav": my_state['fav'],          
                "is_visited": my_state['visited']   
            })
        
        return jsonify(results)

    except Exception as e:
        current_app.logger.error("Database Error:", e)
        return jsonify({"error": "系統發生錯誤，請稍後再試"}), 500

@explore_bp.route('/api/cafes/<int:cafe_id>/photo', methods=['GET'])
def get_cafe_photo(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)

    if not has_google_maps_key():
        return jsonify({'error': 'Google Maps API key is not configured'}), 503

    try:
        max_width = request.args.get('width', 900, type=int)
        photo_uri = get_google_photo_uri(cafe, max_width=max_width)
        if not photo_uri:
            return jsonify({'error': 'No Google photo found for this cafe'}), 404
        return redirect(photo_uri, code=302)
    except requests.RequestException as e:
        current_app.logger.error(f'Google Places photo error for cafe {cafe_id}: {e}')
        db.session.rollback()
        return jsonify({'error': 'Failed to fetch Google photo'}), 502
    except Exception as e:
        current_app.logger.error(f'Cafe photo error for cafe {cafe_id}: {e}')
        db.session.rollback()
        return jsonify({"error": "系統發生錯誤，請稍後再試"}), 500
