from flask import Blueprint, jsonify, request, session, current_app
from database import db
from models import User, Cafes, AdminLog, UserShopState, cafe_tags, OperatingHours, AiQueryLog, ChatSession, ChatFeedback
from utils.auth import admin_required
from services.admin_service import AdminService
from services.google_maps_service import get_cafe_image_url, has_google_maps_key
from services import conversation_guide
from services.ollama_admin_service import get_default_model, list_models, delete_model
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'email': u.email,
        'name': u.name,
        'picture': u.picture[:80] + '...' if u.picture and len(u.picture) > 80 else u.picture,
        'is_admin': u.is_admin
    } for u in users])

@admin_bp.route('/api/admin/users/<int:user_id>/admin', methods=['PUT'])
@admin_required
def admin_toggle_admin(user_id):
    target = User.query.get_or_404(user_id)
    current_email = session.get('user_email')
    if target.email == current_email:
        return jsonify({'error': '不能變更自己的管理員權限'}), 400
    target.is_admin = not target.is_admin
    db.session.commit()
    AdminService.log_action(current_email, '切換管理員權限', f'將 {target.email} 設為 {"管理員" if target.is_admin else "一般用戶"}')
    return jsonify({'success': True, 'is_admin': target.is_admin})

@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    target = User.query.get_or_404(user_id)
    current_email = session.get('user_email')
    if target.email == current_email:
        return jsonify({'error': '不能刪除自己'}), 400
    email = target.email
    
    from services.user_service import delete_user_data
    delete_user_data(target.id)
    db.session.commit()
    AdminService.log_action(current_email, '刪除用戶', f'已刪除 {email}')
    return jsonify({'success': True})

@admin_bp.route('/api/admin/cafes', methods=['GET'])
@admin_required
def admin_get_cafes():
    cafes = Cafes.query.all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'address': c.address or '',
        'phone': c.phone or '',
        'website': c.website or '',
        'cost': c.cost or '',
        'image': c.image or '',
        'image_url': get_cafe_image_url(c),
        'image_source': 'manual' if c.image else ('google' if has_google_maps_key() else ''),
        'image_attribution': c.google_photo_attribution or '',
        'tags': ', '.join([t.tag_name for t in c.tags])
    } for c in cafes])

@admin_bp.route('/api/admin/cafes/<int:cafe_id>', methods=['PUT'])
@admin_required
def admin_update_cafe(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)
    data = request.json
    should_refresh_google_place = False
    if 'name' in data and data['name'] != cafe.name:
        cafe.name = data['name']
        should_refresh_google_place = True
    if 'address' in data and data['address'] != cafe.address:
        cafe.address = data['address']
        should_refresh_google_place = True
    if 'phone' in data: cafe.phone = data['phone']
    if 'website' in data: cafe.website = data['website']
    if 'cost' in data: cafe.cost = data['cost']
    if 'image' in data: cafe.image = data['image']
    if should_refresh_google_place:
        cafe.google_place_id = None
        cafe.google_photo_attribution = None
    db.session.commit()
    current_email = session.get('user_email')
    AdminService.log_action(current_email, '更新店家', f'更新 {cafe.name} (ID: {cafe_id})')
    return jsonify({'success': True})

@admin_bp.route('/api/admin/cafes/<int:cafe_id>', methods=['DELETE'])
@admin_required
def admin_delete_cafe(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)
    name = cafe.name
    db.session.execute(cafe_tags.delete().where(cafe_tags.c.cafe_id == cafe_id))
    OperatingHours.query.filter_by(cafe_id=cafe_id).delete()
    UserShopState.query.filter_by(cafe_id=cafe_id).delete()
    db.session.delete(cafe)
    db.session.commit()
    current_email = session.get('user_email')
    AdminService.log_action(current_email, '刪除店家', f'已刪除 {name} (ID: {cafe_id})')
    return jsonify({'success': True})

@admin_bp.route('/api/admin/logs', methods=['GET'])
@admin_required
def admin_get_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        'logs': [{
            'id': l.id,
            'user_email': l.user_email,
            'action': l.action,
            'detail': l.detail or '',
            'created_at': l.created_at.strftime('%Y-%m-%d %H:%M:%S') if l.created_at else ''
        } for l in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'current_page': logs.page
    })

@admin_bp.route('/api/admin/overview', methods=['GET'])
@admin_required
def admin_get_overview():
    try:
        data = AdminService.get_overview_data()
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Overview API Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "系統發生錯誤，請稍後再試"}), 500


def get_current_model():
    from services.settings_service import get_selected_model
    return get_selected_model() or get_default_model()

@admin_bp.route('/api/admin/model', methods=['GET'])
@admin_required
def admin_get_model():
    current_model = get_current_model()
    ollama_status, installed_models = list_models()
    if installed_models:
        installed_models.sort(key=lambda x: x.get('name', ''))
        
    return jsonify({
        'current_model': current_model,
        'ollama_status': ollama_status,
        'installed_models': installed_models,
        'default_model': get_default_model()
    })

@admin_bp.route('/api/admin/model/switch', methods=['POST'])
@admin_required
def admin_switch_model():
    data = request.json
    new_model = data.get('model')
    if not new_model:
        return jsonify({'error': '請指定模型名稱'}), 400
    
    from services.settings_service import set_selected_model
    set_selected_model(new_model)
    current_email = session.get('user_email')
    AdminService.log_action(current_email, '切換模型', f'切換至 {new_model}')
    return jsonify({'success': True, 'current_model': new_model})

@admin_bp.route('/api/admin/model/delete', methods=['POST'])
@admin_required
def admin_delete_model():
    data = request.json
    model_name = data.get('model')
    if not model_name:
        return jsonify({'error': '請指定模型名稱'}), 400
    
    current_model = get_current_model()
    if model_name == current_model:
        return jsonify({'error': '不能刪除目前正在使用的模型'}), 400

    success, error = delete_model(model_name)
    if success:
        current_email = session.get('user_email')
        AdminService.log_action(current_email, '刪除模型', f'刪除模型 {model_name}')
        return jsonify({'success': True})
    else:
        return jsonify({'error': error}), 500

@admin_bp.route('/api/admin/guide-strategy', methods=['GET'])
@admin_required
def admin_get_guide_strategy():
    strategy = conversation_guide.get_strategy()
    return jsonify(strategy)

@admin_bp.route('/api/admin/guide-strategy', methods=['PUT'])
@admin_required
def admin_update_guide_strategy():
    data = request.json
    updated = conversation_guide.update_strategy(data)
    current_email = session.get('user_email')
    AdminService.log_action(current_email, '更新對話引導策略', f'更新為 {updated}')
    return jsonify({'success': True, 'strategy': updated})

@admin_bp.route('/api/admin/feedbacks', methods=['GET'])
@admin_required
def admin_get_feedbacks():
    try:
        feedbacks = ChatFeedback.query.order_by(ChatFeedback.created_at.desc()).all()
        user_ids = {f.user_id for f in feedbacks if f.user_id}
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}
        result = []
        for f in feedbacks:
            user_info = "訪客"
            if f.user_id:
                u = users.get(f.user_id)
                user_info = u.name if u else "未知使用者"
            result.append({
                "id": f.id,
                "user": user_info,
                "user_message": f.user_message,
                "ai_response": f.ai_response,
                "feedback_type": f.feedback_type,
                "created_at": f.created_at.strftime('%Y-%m-%d %H:%M')
            })
        return jsonify({"success": True, "feedbacks": result})
    except Exception as e:
        return jsonify({"success": False, "error": "系統發生錯誤，請稍後再試"}), 500
