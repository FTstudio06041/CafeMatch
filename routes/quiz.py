from flask import Blueprint, jsonify, request, session, current_app
from database import db
from models import User, QuizQuestion, QuizOption, QuizResultType, UserQuizResult

quiz_bp = Blueprint('quiz', __name__)

def determine_result_type(scores):
    work = scores['work']
    env = scores['env']
    social = scores['social']
    taste = scores['taste']
    cp = scores['cp']
    all_scores = [work, env, social, taste, cp]
    max_score = max(all_scores)
    avg = sum(all_scores) / 5

    if max(all_scores) - min(all_scores) <= 2:
        return 'balanced'

    if abs(work - env) <= 2 and work >= avg + 2 and env >= avg + 2:
        others = [social, taste, cp]
        if all(work > o + 3 for o in others) and all(env > o + 3 for o in others):
            return 'work_env'

    if abs(taste - cp) <= 2 and taste >= avg + 2 and cp >= avg + 2:
        others = [work, env, social]
        if all(taste > o + 3 for o in others) and all(cp > o + 3 for o in others):
            return 'taste_cp'

    dimension_keys = ['work', 'env', 'social', 'taste', 'cp']
    max_idx = all_scores.index(max_score)
    return dimension_keys[max_idx]

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

        scores = {'work': 0, 'env': 0, 'social': 0, 'taste': 0, 'cp': 0}

        if answer_ids:
            answer_options = QuizOption.query.filter(QuizOption.id.in_(answer_ids)).all()
            for opt in answer_options:
                scores['work'] += opt.score_work
                scores['env'] += opt.score_env
                scores['social'] += opt.score_social
                scores['taste'] += opt.score_taste
                scores['cp'] += opt.score_cp

        filter_tags = []
        if filter_ids:
            filter_options = QuizOption.query.filter(QuizOption.id.in_(filter_ids)).all()
            for opt in filter_options:
                if opt.filter_tag:
                    filter_tags.append(opt.filter_tag)

        result_type_key = determine_result_type(scores)

        result_type = QuizResultType.query.filter_by(type_key=result_type_key).first()

        record_id = None
        if user:
            record = UserQuizResult(
                user_id=user.id,
                result_type_key=result_type_key,
                score_work=scores['work'],
                score_env=scores['env'],
                score_social=scores['social'],
                score_taste=scores['taste'],
                score_cp=scores['cp'],
                filter_tags=','.join(filter_tags) if filter_tags else ''
            )
            db.session.add(record)
            db.session.commit()
            record_id = record.id

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
            'record_id': record_id
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'測驗提交錯誤：{e}')
        return jsonify({'error': f'提交失敗：{str(e)}'}), 500


@quiz_bp.route('/api/quiz/history', methods=['GET'])
def quiz_history():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': '請先登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'error': '使用者不存在'}), 404

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
def quiz_latest():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'error': '請先登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'error': '使用者不存在'}), 404

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
