import logging
from database import db
from models import User, UserShopState, ChatSession, ChatFeedback, UserQuizResult, CommunityPost, PostLike, PostComment, CommunityNote, CommunityLike, CommunityComment

def delete_user_data(user_id):
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
    
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting user data for {user_id}: {e}")
