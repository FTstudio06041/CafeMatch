from database import db
from models import QuizOption, QuizResultType, UserQuizResult

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

def calculate_scores(answer_ids):
    scores = {'work': 0, 'env': 0, 'social': 0, 'taste': 0, 'cp': 0}
    if answer_ids:
        answer_options = QuizOption.query.filter(QuizOption.id.in_(answer_ids)).all()
        for opt in answer_options:
            scores['work'] += opt.score_work
            scores['env'] += opt.score_env
            scores['social'] += opt.score_social
            scores['taste'] += opt.score_taste
            scores['cp'] += opt.score_cp
    return scores

def get_filter_tags(filter_ids):
    filter_tags = []
    if filter_ids:
        filter_options = QuizOption.query.filter(QuizOption.id.in_(filter_ids)).all()
        for opt in filter_options:
            if opt.filter_tag:
                filter_tags.append(opt.filter_tag)
    return filter_tags

def process_quiz_submission(user, answer_ids, filter_ids):
    scores = calculate_scores(answer_ids)
    filter_tags = get_filter_tags(filter_ids)
    
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

    return {
        'result': result_data,
        'scores': scores,
        'filters': filter_tags,
        'record_id': record_id
    }
