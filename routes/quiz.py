from flask import Blueprint, jsonify, request, session, current_app
from database import db
from models import User, QuizQuestion, QuizResultType, UserQuizResult
from services.quiz_service import process_quiz_submission
from utils.auth import login_required
from utils.response import error_response, success_response

quiz_bp = Blueprint('quiz', __name__)

@quiz_bp.route('/api/quiz/questions', methods=['GET'])
def quiz_get_questions():
    questions = QuizQuestion.query.order_by(QuizQuestion.order).all()
    result = []
    for q in questions:
        options_list = []
        for opt in q.options:
            options_list.append({
                'id': opt.id,
                'code': opt.code,
                'text': opt.text,
                'subtext': opt.subtext
            })
        result.append({
            'id': q.id,
            'order': q.order,
            'scenario_tag': q.scenario_tag,
            'question_text': q.question_text,
            'is_multiple': q.is_multiple,
            'options': options_list
        })
    return jsonify({'questions': result})


@quiz_bp.route('/api/quiz/submit', methods=['POST'])
def quiz_submit():
    user_email = session.get('user_email')
    user = User.query.filter_by(email=user_email).first() if user_email else None

    try:
        data = request.json
        answer_ids = data.get('answers', [])
        filter_ids = data.get('filters', [])

        response_data = process_quiz_submission(user, answer_ids, filter_ids)
        return jsonify(response_data)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'測驗提交錯誤：{e}')
        return error_response("系統發生錯誤，請稍後再試", 500)


@quiz_bp.route('/api/quiz/history', methods=['GET'])
@login_required
def quiz_history(user):
    records = UserQuizResult.query.filter_by(user_id=user.id)\
        .order_by(UserQuizResult.created_at.desc()).all()

    history = []
    for r in records:
        rt = QuizResultType.query.filter_by(type_key=r.result_type_key).first()
        history.append({
            'id': r.id,
            'type_key': r.result_type_key,
            'title': rt.title if rt else '',
            'scores': {
                'work': r.score_work,
                'env': r.score_env,
                'social': r.score_social,
                'taste': r.score_taste,
                'cp': r.score_cp
            },
            'filters': r.filter_tags or '',
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
        })

    return jsonify({'history': history})


@quiz_bp.route('/api/quiz/latest', methods=['GET'])
@login_required
def quiz_latest(user):
    record = UserQuizResult.query.filter_by(user_id=user.id)\
        .order_by(UserQuizResult.created_at.desc()).first()

    if not record:
        return jsonify({'result': None})

    result_type = QuizResultType.query.filter_by(type_key=record.result_type_key).first()

    scores = {
        'work': record.score_work,
        'env': record.score_env,
        'social': record.score_social,
        'taste': record.score_taste,
        'cp': record.score_cp
    }

    filter_tags = record.filter_tags.split(',') if record.filter_tags else []

    result_data = None
    if result_type:
        result_data = {
            'type_key': result_type.type_key,
            'title': result_type.title,
            'inner_voice': result_type.inner_voice,
            'profile': result_type.profile,
            'cafe_match': result_type.cafe_match
        }

    return jsonify({
        'result': result_data,
        'scores': scores,
        'filters': filter_tags,
        'record_id': record.id
    })
