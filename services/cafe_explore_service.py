from models import Cafes, UserShopState
from services.google_maps_service import get_cafe_image_url, has_google_maps_key

def get_cafes_data(current_user):
    all_cafes = Cafes.query.all()
    results = []
    
    user_states = {} 
    if current_user:
        states = UserShopState.query.filter_by(user_id=current_user.id).all()
        for s in states:
            user_states[s.cafe_id] = {'fav': s.is_fav, 'visited': s.is_visited}

    # Define color palette (moved from route)
    palette = [
        "#8D6E63", "#A1887F", "#BCAAA4", "#D7CCC8", 
        "#795548", "#6D4C41", "#5D4037", "#4E342E", 
        "#78909C", "#607D8B", "#546E7A"             
    ]

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
    
    return results
