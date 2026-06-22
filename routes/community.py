from flask import Blueprint, jsonify, request, session, current_app
from datetime import datetime
from database import db
from models import User, CommunityNote, CommunityLike, CommunityComment, CommunityPost, PostLike, PostComment, Cafes

community_bp = Blueprint('community', __name__)

@community_bp.route('/api/community/notes', methods=['GET'])
def community_get_notes():
    try:
        from datetime import timedelta
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        notes = CommunityNote.query.filter(CommunityNote.created_at >= twenty_four_hours_ago).order_by(CommunityNote.created_at.desc()).all()

        current_user = None
        user_email = session.get('user_email')
        if user_email:
            current_user = User.query.filter_by(email=user_email).first()

        result = []
        
        if not notes:
            return jsonify({'success': True, 'notes': result})

        from sqlalchemy import func
        user_ids = {n.user_id for n in notes}
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        note_ids = [n.id for n in notes]

        like_counts_q = db.session.query(CommunityLike.note_id, func.count(CommunityLike.id)).filter(CommunityLike.note_id.in_(note_ids)).group_by(CommunityLike.note_id).all()
        like_counts = {nid: cnt for nid, cnt in like_counts_q}

        comment_counts_q = db.session.query(CommunityComment.note_id, func.count(CommunityComment.id)).filter(CommunityComment.note_id.in_(note_ids)).group_by(CommunityComment.note_id).all()
        comment_counts = {nid: cnt for nid, cnt in comment_counts_q}

        user_liked_set = set()
        if current_user:
            user_likes = CommunityLike.query.filter(CommunityLike.note_id.in_(note_ids), CommunityLike.user_id == current_user.id).all()
            user_liked_set = {like.note_id for like in user_likes}

        for note in notes:
            author = users.get(note.user_id)
            result.append({
                'id': note.id,
                'content': note.content,
                'color_index': note.color_index,
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M') if note.created_at else '',
                'user_name': author.name if author else '匿名',
                'user_picture': author.picture if author else '',
                'user_email': author.email if author else '',
                'like_count': like_counts.get(note.id, 0),
                'comment_count': comment_counts.get(note.id, 0),
                'is_liked': note.id in user_liked_set
            })

        return jsonify({'success': True, 'notes': result})

    except Exception as e:
        current_app.logger.error(f'取得便利貼錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/notes', methods=['POST'])
def community_create_note():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        data = request.json
        content = data.get('content', '').strip()
        color_index = data.get('color_index', 0)

        if not content:
            return jsonify({'success': False, 'message': '內容不可為空'}), 400
        if len(content) > 100:
            return jsonify({'success': False, 'message': '內容不可超過 100 字'}), 400

        existing_note = CommunityNote.query.filter_by(user_id=user.id).first()
        if existing_note:
            existing_note.content = content
            existing_note.color_index = color_index
            existing_note.created_at = datetime.utcnow()
            note = existing_note
        else:
            note = CommunityNote(
                user_id=user.id,
                content=content,
                color_index=color_index
            )
            db.session.add(note)
        
        db.session.commit()

        return jsonify({
            'success': True,
            'note': {
                'id': note.id,
                'content': note.content,
                'color_index': note.color_index,
                'created_at': note.created_at.strftime('%Y-%m-%d %H:%M') if note.created_at else '',
                'user_name': user.name,
                'user_picture': user.picture or '',
                'like_count': 0,
                'comment_count': 0,
                'is_liked': False
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'新增便利貼錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/notes/<int:note_id>', methods=['DELETE'])
def community_delete_note(note_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404
        if note.user_id != user.id:
            return jsonify({'success': False, 'message': '只能刪除自己的便利貼'}), 403

        CommunityLike.query.filter_by(note_id=note_id).delete()
        CommunityComment.query.filter_by(note_id=note_id).delete()
        db.session.delete(note)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'刪除便利貼錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/notes/<int:note_id>/like', methods=['POST'])
def community_toggle_like(note_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404

        existing_like = CommunityLike.query.filter_by(
            user_id=user.id, note_id=note_id
        ).first()

        if existing_like:
            db.session.delete(existing_like)
            is_liked = False
        else:
            new_like = CommunityLike(user_id=user.id, note_id=note_id)
            db.session.add(new_like)
            is_liked = True

        db.session.commit()
        like_count = CommunityLike.query.filter_by(note_id=note_id).count()

        return jsonify({
            'success': True,
            'is_liked': is_liked,
            'like_count': like_count
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'愛心操作錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/notes/<int:note_id>/comments', methods=['GET'])
def community_get_comments(note_id):
    try:
        comments = CommunityComment.query.filter_by(note_id=note_id).order_by(CommunityComment.created_at.desc()).all()
        
        # 批次查詢使用者
        user_ids = list(set([c.user_id for c in comments]))
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        
        result = []
        for c in comments:
            author = users.get(c.user_id)
            result.append({
                'id': c.id,
                'content': c.content,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'author': {
                    'name': author.name if author else '未知',
                    'email': author.email if author else '',
                    'avatar': author.avatar if author else None
                }
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/notes/<int:note_id>/comments', methods=['POST'])
def community_create_comment(note_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        note = CommunityNote.query.get(note_id)
        if not note:
            return jsonify({'success': False, 'message': '便利貼不存在'}), 404

        data = request.json
        content = data.get('content', '').strip()

        if not content:
            return jsonify({'success': False, 'message': '留言內容不可為空'}), 400
        if len(content) > 200:
            return jsonify({'success': False, 'message': '留言不可超過 200 字'}), 400

        comment = CommunityComment(
            user_id=user.id,
            note_id=note_id,
            content=content
        )
        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'user_name': user.name,
                'user_picture': user.picture or '',
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M') if comment.created_at else ''
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'新增留言錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/posts', methods=['GET'])
def community_get_posts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        current_user_id = None
        user_email = session.get('user_email')
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                current_user_id = user.id

        pagination = CommunityPost.query.order_by(CommunityPost.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)

        result = []
        posts = pagination.items
        
        if not posts:
            return jsonify({
                'success': True,
                'posts': result,
                'total': pagination.total,
                'pages': pagination.pages,
                'current_page': pagination.page
            })
            
        from sqlalchemy import func
        user_ids = {p.user_id for p in posts}
        cafe_ids = {p.cafe_id for p in posts if p.cafe_id}
        post_ids = [p.id for p in posts]
        orig_post_ids = {p.original_post_id for p in posts if p.original_post_id}

        orig_posts = {p.id: p for p in CommunityPost.query.filter(CommunityPost.id.in_(orig_post_ids)).all()} if orig_post_ids else {}
        all_user_ids = user_ids.union({p.user_id for p in orig_posts.values()})
        
        users = {u.id: u for u in User.query.filter(User.id.in_(all_user_ids)).all()} if all_user_ids else {}
        cafes = {c.id: c for c in Cafes.query.filter(Cafes.id.in_(cafe_ids)).all()} if cafe_ids else {}

        like_counts_q = db.session.query(PostLike.post_id, func.count(PostLike.id)).filter(PostLike.post_id.in_(post_ids)).group_by(PostLike.post_id).all()
        like_counts = {pid: cnt for pid, cnt in like_counts_q}

        comment_counts_q = db.session.query(PostComment.post_id, func.count(PostComment.id)).filter(PostComment.post_id.in_(post_ids)).group_by(PostComment.post_id).all()
        comment_counts = {pid: cnt for pid, cnt in comment_counts_q}

        repost_counts_q = db.session.query(CommunityPost.original_post_id, func.count(CommunityPost.id)).filter(CommunityPost.original_post_id.in_(post_ids)).group_by(CommunityPost.original_post_id).all()
        repost_counts = {pid: cnt for pid, cnt in repost_counts_q}

        user_liked_set = set()
        if current_user_id:
            user_likes = PostLike.query.filter(PostLike.post_id.in_(post_ids), PostLike.user_id == current_user_id).all()
            user_liked_set = {like.post_id for like in user_likes}

        for post in posts:
            author = users.get(post.user_id)
            cafe = cafes.get(post.cafe_id)

            original_post_data = None
            if post.original_post_id and post.original_post_id in orig_posts:
                orig = orig_posts[post.original_post_id]
                orig_author = users.get(orig.user_id)
                original_post_data = {
                    'id': orig.id,
                    'content': orig.content,
                    'image': orig.image or '',
                    'user_name': orig_author.name if orig_author else '匿名',
                    'user_picture': orig_author.picture if orig_author else '',
                    'created_at': orig.created_at.strftime('%Y-%m-%d %H:%M') if orig.created_at else ''
                }

            result.append({
                'id': post.id,
                'content': post.content,
                'image': post.image or '',
                'cafe_id': post.cafe_id,
                'cafe_name': cafe.name if cafe else '',
                'user_name': author.name if author else '匿名',
                'user_picture': author.picture if author else '',
                'user_email': author.email if author else '',
                'created_at': post.created_at.strftime('%Y-%m-%d %H:%M') if post.created_at else '',
                'like_count': like_counts.get(post.id, 0),
                'comment_count': comment_counts.get(post.id, 0),
                'repost_count': repost_counts.get(post.id, 0),
                'is_liked': post.id in user_liked_set,
                'original_post': original_post_data
            })

        return jsonify({
            'success': True,
            'posts': result,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': pagination.page
        })

    except Exception as e:
        current_app.logger.error(f'取得貼文錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500

@community_bp.route('/api/community/posts/<int:post_id>', methods=['GET'])
def community_get_single_post(post_id):
    try:
        post = CommunityPost.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'message': '找不到貼文'}), 404

        current_user_id = None
        user_email = session.get('user_email')
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                current_user_id = user.id

        author = User.query.get(post.user_id)
        cafe_name = None
        if post.cafe_id:
            cafe = Cafes.query.get(post.cafe_id)
            cafe_name = cafe.name if cafe else None

        like_count = PostLike.query.filter_by(post_id=post.id).count()
        comment_count = PostComment.query.filter_by(post_id=post.id).count()
        repost_count = CommunityPost.query.filter_by(original_post_id=post.id).count()
        is_liked = False
        if current_user_id:
            is_liked = PostLike.query.filter_by(post_id=post.id, user_id=current_user_id).first() is not None

        original_post_data = None
        if post.original_post_id:
            orig = CommunityPost.query.get(post.original_post_id)
            if orig:
                orig_author = User.query.get(orig.user_id)
                original_post_data = {
                    'id': orig.id,
                    'content': orig.content,
                    'image': orig.image or '',
                    'user_name': orig_author.name if orig_author else '匿名',
                    'user_picture': orig_author.picture if orig_author else '',
                    'created_at': orig.created_at.strftime('%Y-%m-%d %H:%M') if orig.created_at else ''
                }

        post_data = {
            'id': post.id,
            'content': post.content,
            'image': post.image or '',
            'cafe_id': post.cafe_id,
            'cafe_name': cafe_name or '',
            'user_name': author.name if author else '匿名',
            'user_picture': author.picture if author else '',
            'user_email': author.email if author else '',
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M') if post.created_at else '',
            'like_count': like_count,
            'comment_count': comment_count,
            'repost_count': repost_count,
            'is_liked': is_liked,
            'original_post': original_post_data
        }

        return jsonify({'success': True, 'post': post_data})
    except Exception as e:
        current_app.logger.error(f'取得單一貼文錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500

@community_bp.route('/api/community/posts/<int:post_id>/like', methods=['POST'])
def community_like_post(post_id):
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'success': False, 'message': '未登入'}), 401
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({'success': False, 'message': '用戶不存在'}), 401

        post = CommunityPost.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'message': '貼文不存在'}), 404

        existing_like = PostLike.query.filter_by(post_id=post_id, user_id=user.id).first()
        if existing_like:
            db.session.delete(existing_like)
            action = 'unliked'
        else:
            new_like = PostLike(user_id=user.id, post_id=post_id)
            db.session.add(new_like)
            action = 'liked'
        
        db.session.commit()
        like_count = PostLike.query.filter_by(post_id=post_id).count()
        return jsonify({'success': True, 'action': action, 'like_count': like_count})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'貼文按讚錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500

@community_bp.route('/api/community/posts/<int:post_id>/comments', methods=['GET'])
def community_get_post_comments(post_id):
    try:
        comments = PostComment.query.filter_by(post_id=post_id).order_by(PostComment.created_at.desc()).all()
        
        # 批次查詢使用者
        user_ids = list(set([c.user_id for c in comments]))
        users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}
        
        result = []
        for c in comments:
            author = users.get(c.user_id)
            result.append({
                'id': c.id,
                'content': c.content,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'author': {
                    'name': author.name if author else '未知',
                    'email': author.email if author else '',
                    'avatar': author.avatar if author else None
                }
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': "系統發生錯誤，請稍後再試"}), 500

@community_bp.route('/api/community/posts/<int:post_id>/comments', methods=['POST'])
def community_create_post_comment(post_id):
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'success': False, 'message': '未登入'}), 401
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({'success': False, 'message': '用戶不存在'}), 401

        data = request.get_json()
        content = data.get('content', '').strip()
        if not content:
            return jsonify({'success': False, 'message': '留言內容不可為空'}), 400

        post = CommunityPost.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'message': '貼文不存在'}), 404

        new_comment = PostComment(user_id=user.id, post_id=post_id, content=content)
        db.session.add(new_comment)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '留言成功'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'新增貼文留言錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500

@community_bp.route('/api/community/posts/<int:post_id>/repost', methods=['POST'])
def community_repost(post_id):
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'success': False, 'message': '未登入'}), 401
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({'success': False, 'message': '用戶不存在'}), 401

        data = request.get_json()
        content = data.get('content', '').strip()

        original_post = CommunityPost.query.get(post_id)
        if not original_post:
            return jsonify({'success': False, 'message': '原始貼文不存在'}), 404

        target_original_id = original_post.original_post_id if original_post.original_post_id else original_post.id

        new_repost = CommunityPost(
            user_id=user.id,
            content=content,
            original_post_id=target_original_id
        )
        db.session.add(new_repost)
        db.session.commit()
        return jsonify({'success': True, 'message': '轉發成功'})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'轉發貼文錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/posts', methods=['POST'])
def community_create_post():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        data = request.json
        content = data.get('content', '').strip()
        image = data.get('image')
        cafe_id = data.get('cafe_id') 

        if not content:
            return jsonify({'success': False, 'message': '貼文內容不可為空'}), 400

        post = CommunityPost(
            user_id=user.id,
            content=content,
            image=image,
            cafe_id=cafe_id
        )
        db.session.add(post)
        db.session.commit()

        cafe_name = ''
        if cafe_id:
            cafe = Cafes.query.get(cafe_id)
            cafe_name = cafe.name if cafe else ''

        return jsonify({
            'success': True,
            'post': {
                'id': post.id,
                'content': post.content,
                'image': post.image or '',
                'cafe_id': post.cafe_id,
                'cafe_name': cafe_name,
                'user_name': user.name,
                'user_picture': user.picture or '',
                'created_at': post.created_at.strftime('%Y-%m-%d %H:%M') if post.created_at else ''
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'新增貼文錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@community_bp.route('/api/community/posts/<int:post_id>', methods=['DELETE'])
def community_delete_post(post_id):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        post = CommunityPost.query.get(post_id)
        if not post:
            return jsonify({'success': False, 'message': '貼文不存在'}), 404
        if post.user_id != user.id and not getattr(user, 'is_admin', False):
            return jsonify({'success': False, 'message': '只能刪除自己的貼文'}), 403

        PostLike.query.filter_by(post_id=post.id).delete()
        PostComment.query.filter_by(post_id=post.id).delete()
        CommunityPost.query.filter_by(original_post_id=post.id).update({CommunityPost.original_post_id: None})

        db.session.delete(post)
        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'刪除貼文錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500
