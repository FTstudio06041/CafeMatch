from flask import Blueprint, jsonify, request, current_app
from models import User
from services.note_service import NoteService
from services.post_service import PostService
from utils.auth import login_required, get_current_user
from utils.response import error_response, success_response

community_bp = Blueprint('community', __name__)

@community_bp.route('/api/community/notes', methods=['GET'])
def community_get_notes():
    try:
        current_user = get_current_user()
        result = NoteService.get_notes(current_user)
        return success_response({'notes': result})
    except Exception as e:
        current_app.logger.error(f'取得便利貼錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/notes', methods=['POST'])
@login_required
def community_create_note(user):
    try:
        data = request.json
        content = data.get('content', '').strip()
        color_index = data.get('color_index', 0)

        if not content:
            return error_response("內容不可為空", 400)
        if len(content) > 100:
            return error_response("內容不可超過 100 字", 400)

        note_data = NoteService.create_or_update_note(user, content, color_index)
        return success_response({'note': note_data})
    except Exception as e:
        current_app.logger.error(f'新增便利貼錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/notes/<int:note_id>', methods=['DELETE'])
@login_required
def community_delete_note(user, note_id):
    try:
        success, msg = NoteService.delete_note(user, note_id)
        if not success:
            return error_response(msg, 403 if '只能' in msg else 404)
        return success_response()
    except Exception as e:
        current_app.logger.error(f'刪除便利貼錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/notes/<int:note_id>/like', methods=['POST'])
@login_required
def community_toggle_like(user, note_id):
    try:
        success, is_liked_or_msg, like_count = NoteService.toggle_like_note(user, note_id)
        if not success:
            return error_response(is_liked_or_msg, 404)

        return success_response({
            'is_liked': is_liked_or_msg,
            'like_count': like_count
        })
    except Exception as e:
        current_app.logger.error(f'愛心操作錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/notes/<int:note_id>/comments', methods=['GET'])
def community_get_comments(note_id):
    try:
        result = NoteService.get_note_comments(note_id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f'取得留言錯誤: {e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/notes/<int:note_id>/comments', methods=['POST'])
@login_required
def community_create_comment(user, note_id):
    try:
        data = request.json
        content = data.get('content', '').strip()

        if not content:
            return error_response("留言內容不可為空", 400)
        if len(content) > 200:
            return error_response("留言不可超過 200 字", 400)

        success, msg, comment_data = NoteService.create_note_comment(user, note_id, content)
        if not success:
            return error_response(msg, 404)

        return success_response({'comment': comment_data})
    except Exception as e:
        current_app.logger.error(f'新增留言錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts', methods=['GET'])
def community_get_posts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        current_user = get_current_user()
        current_user_id = current_user.id if current_user else None

        result, total, pages, current_page = PostService.get_posts(page, per_page, current_user_id)
        
        return success_response({
            'posts': result,
            'total': total,
            'pages': pages,
            'current_page': current_page
        })

    except Exception as e:
        current_app.logger.error(f'取得貼文錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts/<int:post_id>', methods=['GET'])
def community_get_single_post(post_id):
    try:
        current_user = get_current_user()
        current_user_id = current_user.id if current_user else None

        post_data = PostService.get_single_post(post_id, current_user_id)
        if not post_data:
            return error_response("找不到貼文", 404)

        return success_response({'post': post_data})
    except Exception as e:
        current_app.logger.error(f'取得單一貼文錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts/<int:post_id>/like', methods=['POST'])
@login_required
def community_like_post(user, post_id):
    try:
        success, action, like_count = PostService.toggle_like_post(user, post_id)
        if not success:
            return error_response(action, 404)
        
        return success_response({'action': action, 'like_count': like_count})
    except Exception as e:
        current_app.logger.error(f'貼文按讚錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts/<int:post_id>/comments', methods=['GET'])
def community_get_post_comments(post_id):
    try:
        result = PostService.get_post_comments(post_id)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f'取得貼文留言錯誤: {e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts/<int:post_id>/comments', methods=['POST'])
@login_required
def community_create_post_comment(user, post_id):
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        if not content:
            return error_response("留言內容不可為空", 400)

        success, msg = PostService.create_post_comment(user, post_id, content)
        if not success:
            return error_response(msg, 404)
        
        return success_response({'message': '留言成功'})
    except Exception as e:
        current_app.logger.error(f'新增貼文留言錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts/<int:post_id>/repost', methods=['POST'])
@login_required
def community_repost(user, post_id):
    try:
        data = request.get_json()
        content = data.get('content', '').strip()

        success, msg = PostService.create_repost(user, post_id, content)
        if not success:
            return error_response(msg, 404)
        
        return success_response({'message': '轉發成功'})
    except Exception as e:
        current_app.logger.error(f'轉發貼文錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts', methods=['POST'])
@login_required
def community_create_post(user):
    try:
        data = request.json
        content = data.get('content', '').strip()
        image = data.get('image')
        cafe_id = data.get('cafe_id') 

        if not content:
            return error_response("貼文內容不可為空", 400)

        post_data = PostService.create_post(user, content, image, cafe_id)
        return success_response({'post': post_data})

    except Exception as e:
        current_app.logger.error(f'新增貼文錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@community_bp.route('/api/community/posts/<int:post_id>', methods=['DELETE'])
@login_required
def community_delete_post(user, post_id):
    try:
        success, msg = PostService.delete_post(user, post_id)
        if not success:
            return error_response(msg, 403 if '只能' in msg else 404)
        return success_response()
    except Exception as e:
        current_app.logger.error(f'刪除貼文錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)
