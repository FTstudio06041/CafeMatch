from database import db

class Cafes(db.Model):
    __tablename__ = 'cafes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    num = db.Column(db.Integer)
    url = db.Column(db.String(255))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    website = db.Column(db.String(255))
    cost = db.Column(db.String(50))
    image = db.Column(db.Text)
    google_place_id = db.Column(db.String(255))
    google_photo_attribution = db.Column(db.Text)
    
    tags = db.relationship('Tags', secondary='cafe_tags', backref='cafes')
    hours = db.relationship('OperatingHours', backref='cafe')

class Tags(db.Model):
    __tablename__ = 'tags'
    tag_id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(50), nullable=False)

cafe_tags = db.Table('cafe_tags',
    db.Column('cafe_id', db.Integer, db.ForeignKey('cafes.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.tag_id'), primary_key=True)
)

class OperatingHours(db.Model):
    __tablename__ = 'operatinghours'
    id = db.Column(db.Integer, primary_key=True)
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafes.id'), nullable=False)
    day_of_week = db.Column(db.Integer)
    open_time = db.Column(db.Time)
    close_time = db.Column(db.Time)
    is_closed = db.Column(db.Integer)
