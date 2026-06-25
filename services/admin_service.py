from database import db
from models import AdminLog, User, Cafes, AiQueryLog, ChatSession
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta
import logging
from config.settings import ANALYSIS_KEYWORDS

class AdminService:
    @staticmethod
    def log_action(email, action, detail=''):
        try:
            log = AdminLog(user_email=email, action=action, detail=detail)
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logging.error(f'Log error: {e}')
            db.session.rollback()

    @staticmethod
    def get_kpi_data():
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        total_users = User.query.count()
        total_cafes = Cafes.query.count()

        today_queries = AiQueryLog.query.filter(
            AiQueryLog.created_at >= today_start
        ).count()

        today_tokens_result = db.session.query(
            func.coalesce(func.sum(AiQueryLog.prompt_tokens + AiQueryLog.completion_tokens), 0)
        ).filter(AiQueryLog.created_at >= today_start).scalar()
        today_tokens = int(today_tokens_result)

        avg_time_result = db.session.query(
            func.avg(AiQueryLog.total_time_ms)
        ).filter(
            AiQueryLog.created_at >= today_start,
            AiQueryLog.total_time_ms > 0
        ).scalar()
        avg_response_sec = round(float(avg_time_result) / 1000, 1) if avg_time_result else 0
        
        return {
            'total_users': total_users,
            'total_cafes': total_cafes,
            'today_queries': today_queries,
            'today_tokens': today_tokens,
            'avg_response_sec': avg_response_sec
        }

    @staticmethod
    def get_chart_data():
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=6)
        
        chart_rows = db.session.query(
            cast(AiQueryLog.created_at, Date).label('date'),
            func.count(AiQueryLog.id).label('query_count'),
            func.coalesce(func.sum(AiQueryLog.prompt_tokens), 0).label('prompt_tokens'),
            func.coalesce(func.sum(AiQueryLog.completion_tokens), 0).label('completion_tokens')
        ).filter(
            AiQueryLog.created_at >= seven_days_ago
        ).group_by(
            cast(AiQueryLog.created_at, Date)
        ).order_by(
            cast(AiQueryLog.created_at, Date)
        ).all()

        chart_data = []
        for i in range(7):
            target_date = (seven_days_ago + timedelta(days=i)).date()
            found = False
            for row in chart_rows:
                if row.date == target_date:
                    chart_data.append({
                        'date': target_date.strftime('%m/%d'),
                        'queries': row.query_count,
                        'prompt_tokens': int(row.prompt_tokens),
                        'completion_tokens': int(row.completion_tokens),
                        'total_tokens': int(row.prompt_tokens) + int(row.completion_tokens)
                    })
                    found = True
                    break
            if not found:
                chart_data.append({
                    'date': target_date.strftime('%m/%d'),
                    'queries': 0,
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                })
        return chart_data

    @staticmethod
    def get_keyword_analysis():
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=6)
        
        keyword_counts = {kw: 0 for kw in ANALYSIS_KEYWORDS}
        recent_sessions = ChatSession.query.filter(
            ChatSession.updated_at >= seven_days_ago
        ).all()

        for s in recent_sessions:
            if s.messages:
                for msg in s.messages:
                    if msg.get('sender') == 'user' or msg.get('role') == 'user':
                        text = (msg.get('text', '') + msg.get('content', '')).lower()
                        for kw in ANALYSIS_KEYWORDS:
                            if kw in text:
                                keyword_counts[kw] += 1

        top_keywords = sorted(
            [{'keyword': k, 'count': v} for k, v in keyword_counts.items() if v > 0],
            key=lambda x: x['count'],
            reverse=True
        )[:10]
        return top_keywords

    @staticmethod
    def get_top_users():
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = today_start - timedelta(days=6)
        
        top_users_rows = db.session.query(
            AiQueryLog.user_id,
            func.count(AiQueryLog.id).label('query_count'),
            func.coalesce(func.sum(AiQueryLog.prompt_tokens + AiQueryLog.completion_tokens), 0).label('total_tokens')
        ).filter(
            AiQueryLog.user_id.isnot(None),
            AiQueryLog.created_at >= seven_days_ago
        ).group_by(
            AiQueryLog.user_id
        ).order_by(
            func.count(AiQueryLog.id).desc()
        ).limit(5).all()

        top_users = []
        for row in top_users_rows:
            user = User.query.get(row.user_id)
            if user:
                top_users.append({
                    'name': user.name,
                    'email': user.email,
                    'query_count': row.query_count,
                    'total_tokens': int(row.total_tokens)
                })
        return top_users

    @staticmethod
    def get_overview_data():
        return {
            'kpi': AdminService.get_kpi_data(),
            'chart_data': AdminService.get_chart_data(),
            'top_keywords': AdminService.get_keyword_analysis(),
            'top_users': AdminService.get_top_users()
        }
