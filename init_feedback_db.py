from app import app, db, ChatFeedback

with app.app_context():
    # 只建立新加入的表，不會影響既有表
    db.create_all()
    print("ChatFeedback 表格建立完成！")
