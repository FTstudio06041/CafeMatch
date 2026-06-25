from sqlalchemy import func
import logging
from database import db
from models import User, CommunityPost, PostLike, PostComment, Cafes

class PostService:
    @staticmethod
    def get_posts(page, per_page, current_user_id):
        pagination = CommunityPost.query.order_by(CommunityPost.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)

        result = []
        posts = pagination.items
        if not posts:
            return result, pagination.total, pagination.pages, pagination.page

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
        return result, pagination.total, pagination.pages, pagination.page

    @staticmethod
    def get_single_post(post_id, current_user_id):
        post = CommunityPost.query.get(post_id)
        if not post:
            return None

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

        return {
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

    @staticmethod
    def toggle_like_post(user, post_id):
        post = CommunityPost.query.get(post_id)
        if not post:
            return False, '貼文不存在', None
        
        existing_like = PostLike.query.filter_by(post_id=post_id, user_id=user.id).first()
        if existing_like:
            db.session.delete(existing_like)
            action = 'unliked'
        else:
            new_like = PostLike(user_id=user.id, post_id=post_id)
            db.session.add(new_like)
            action = 'liked'
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error toggling post like: {e}")
            return False, '系統錯誤', None
        like_count = PostLike.query.filter_by(post_id=post_id).count()
        return True, action, like_count

    @staticmethod
    def get_post_comments(post_id):
        comments = PostComment.query.filter_by(post_id=post_id).order_by(PostComment.created_at.desc()).all()
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
                    'avatar': author.picture if author else None
                }
            })
        return result

    @staticmethod
    def create_post_comment(user, post_id, content):
        post = CommunityPost.query.get(post_id)
        if not post:
            return False, '貼文不存在'
            
        new_comment = PostComment(user_id=user.id, post_id=post_id, content=content)
        db.session.add(new_comment)
        try:
            db.session.commit()
            return True, ''
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating post comment: {e}")
            return False, '系統錯誤'

    @staticmethod
    def create_repost(user, post_id, content):
        original_post = CommunityPost.query.get(post_id)
        if not original_post:
            return False, '原始貼文不存在'

        target_original_id = original_post.original_post_id if original_post.original_post_id else original_post.id
        new_repost = CommunityPost(
            user_id=user.id,
            content=content,
            original_post_id=target_original_id
        )
        db.session.add(new_repost)
        try:
            db.session.commit()
            return True, ''
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating repost: {e}")
            return False, '系統錯誤'

    @staticmethod
    def create_post(user, content, image, cafe_id):
        post = CommunityPost(
            user_id=user.id,
            content=content,
            image=image,
            cafe_id=cafe_id
        )
        db.session.add(post)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating post: {e}")
            return None

        cafe_name = ''
        if cafe_id:
            cafe = Cafes.query.get(cafe_id)
            cafe_name = cafe.name if cafe else ''
            
        return {
            'id': post.id,
            'content': post.content,
            'image': post.image or '',
            'cafe_id': post.cafe_id,
            'cafe_name': cafe_name,
            'user_name': user.name,
            'user_picture': user.picture or '',
            'created_at': post.created_at.strftime('%Y-%m-%d %H:%M') if post.created_at else ''
        }

    @staticmethod
    def delete_post(user, post_id):
        post = CommunityPost.query.get(post_id)
        if not post:
            return False, '貼文不存在'
        if post.user_id != user.id and not getattr(user, 'is_admin', False):
            return False, '只能刪除自己的貼文'

        PostLike.query.filter_by(post_id=post.id).delete()
        PostComment.query.filter_by(post_id=post.id).delete()
        CommunityPost.query.filter_by(original_post_id=post.id).update({CommunityPost.original_post_id: None})

        try:
            db.session.delete(post)
            db.session.commit()
            return True, ''
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting post: {e}")
            return False, '系統錯誤'
