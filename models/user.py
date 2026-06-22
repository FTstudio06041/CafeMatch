from database import db
from datetime import datetime
import uuid

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    picture = db.Column(db.Text)
    is_admin = db.Column(db.Boolean, default=False)
    last_read_announcement_id = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<User {self.email}>'

class UserShopState(db.Model):
    __tablename__ = 'user_shop_state'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafes.id'), nullable=False)
    is_fav = db.Column(db.Boolean, default=False)
    is_visited = db.Column(db.Boolean, default=False)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'cafe_id', name='uix_user_cafe_state'),
    )
