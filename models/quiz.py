from database import db
from datetime import datetime
from config.settings import get_utc_now

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    id = db.Column(db.Integer, primary_key=True)
    order = db.Column(db.Integer, nullable=False)
    scenario_tag = db.Column(db.String(100))
    question_text = db.Column(db.Text, nullable=False)
    is_multiple = db.Column(db.Boolean, default=False)
    options = db.relationship('QuizOption', backref='question', order_by='QuizOption.code')

class QuizOption(db.Model):
    __tablename__ = 'quiz_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.id'), nullable=False)
    code = db.Column(db.String(5), nullable=False)
    text = db.Column(db.Text, nullable=False)
    subtext = db.Column(db.Text)
    score_work = db.Column(db.Integer, default=0)
    score_env = db.Column(db.Integer, default=0)
    score_social = db.Column(db.Integer, default=0)
    score_taste = db.Column(db.Integer, default=0)
    score_cp = db.Column(db.Integer, default=0)
    filter_tag = db.Column(db.String(50))

class QuizResultType(db.Model):
    __tablename__ = 'quiz_result_types'
    id = db.Column(db.Integer, primary_key=True)
    type_key = db.Column(db.String(50), unique=True, nullable=False)
    condition = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    inner_voice = db.Column(db.Text)
    profile = db.Column(db.Text)
    cafe_match = db.Column(db.Text)

class UserQuizResult(db.Model):
    __tablename__ = 'user_quiz_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    result_type_key = db.Column(db.String(50), db.ForeignKey('quiz_result_types.type_key'), nullable=False)
    result_type = db.relationship('QuizResultType', backref='user_results')
    score_work = db.Column(db.Integer, default=0)
    score_env = db.Column(db.Integer, default=0)
    score_social = db.Column(db.Integer, default=0)
    score_taste = db.Column(db.Integer, default=0)
    score_cp = db.Column(db.Integer, default=0)
    filter_tags = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=get_utc_now)
