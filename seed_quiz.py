"""
心理測驗種子資料匯入腳本
讀取 data/quiz_seeds.json，將測驗題目、選項與結果類型寫入資料庫。
可重複執行：每次執行時會先清除舊資料再重新匯入。
"""

import json
import os
from app import app, db, QuizQuestion, QuizOption, QuizResultType


def seed_quiz():
    """匯入心理測驗種子資料"""

    # 取得種子資料檔案路徑
    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, 'data', 'quiz_seeds.json')

    # 讀取 JSON 檔案
    print(f'[讀取] 載入種子資料：{json_path}')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    with app.app_context():
        # ==========================================
        # 步驟 1：清除舊資料（注意刪除順序，先刪子表再刪父表）
        # ==========================================
        print('[清除] 正在清除舊的測驗資料...')

        # 先刪除選項（子表，有外鍵參照 quiz_questions）
        deleted_options = QuizOption.query.delete()
        print(f'  ✓ 已刪除 {deleted_options} 筆選項')

        # 再刪除題目（父表）
        deleted_questions = QuizQuestion.query.delete()
        print(f'  ✓ 已刪除 {deleted_questions} 筆題目')

        # 刪除結果類型
        deleted_types = QuizResultType.query.delete()
        print(f'  ✓ 已刪除 {deleted_types} 筆結果類型')

        db.session.commit()

        # ==========================================
        # 步驟 2：匯入題目與選項
        # ==========================================
        print('[匯入] 正在寫入題目與選項...')

        question_count = 0
        option_count = 0

        for q_data in data['questions']:
            # 建立題目
            question = QuizQuestion(
                order=q_data['order'],
                scenario_tag=q_data.get('scenario_tag', ''),
                question_text=q_data['question_text'],
                is_multiple=q_data.get('is_multiple', False)
            )
            db.session.add(question)
            db.session.flush()  # 取得自動產生的 id
            question_count += 1

            # 建立該題目的所有選項
            for opt_data in q_data['options']:
                option = QuizOption(
                    question_id=question.id,
                    code=opt_data['code'],
                    text=opt_data['text'],
                    subtext=opt_data.get('subtext'),
                    score_work=opt_data.get('score_work', 0),
                    score_env=opt_data.get('score_env', 0),
                    score_social=opt_data.get('score_social', 0),
                    score_taste=opt_data.get('score_taste', 0),
                    score_cp=opt_data.get('score_cp', 0),
                    filter_tag=opt_data.get('filter_tag')
                )
                db.session.add(option)
                option_count += 1

            print(f'  ✓ Q{q_data["order"]}【{q_data.get("scenario_tag", "")}】'
                  f'— {len(q_data["options"])} 個選項')

        # ==========================================
        # 步驟 3：匯入結果類型
        # ==========================================
        print('[匯入] 正在寫入結果類型...')

        type_count = 0
        for rt_data in data['result_types']:
            result_type = QuizResultType(
                type_key=rt_data['type_key'],
                condition=rt_data['condition'],
                title=rt_data['title'],
                inner_voice=rt_data.get('inner_voice', ''),
                profile=rt_data.get('profile', ''),
                cafe_match=rt_data.get('cafe_match', '')
            )
            db.session.add(result_type)
            type_count += 1
            print(f'  ✓ {rt_data["type_key"]}：{rt_data["title"]}')

        # 提交所有變更
        db.session.commit()

        # ==========================================
        # 步驟 4：印出統計摘要
        # ==========================================
        print()
        print('=' * 50)
        print('  心理測驗種子資料匯入完成！')
        print('=' * 50)
        print(f'  📝 題目數量：{question_count} 題')
        print(f'  🔘 選項數量：{option_count} 個')
        print(f'  🏷️  結果類型：{type_count} 種')
        print('=' * 50)


if __name__ == '__main__':
    seed_quiz()
