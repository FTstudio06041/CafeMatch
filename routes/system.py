from flask import Blueprint, jsonify, request, session, current_app
from database import db
from models import User, SystemAnnouncement, BugReport
from utils import admin_required, log_action

system_bp = Blueprint('system', __name__)

@system_bp.route('/')
def index():
    return 'Backend (XAMPP MySQL) is running!'

@system_bp.route('/api/announcements/latest', methods=['GET'])
def get_latest_announcement():
    try:
        latest_ann = SystemAnnouncement.query.order_by(SystemAnnouncement.id.desc()).first()
        if not latest_ann:
            return jsonify({'success': True, 'show_popup': False, 'announcement': None})

        user_email = session.get('user_email')
        if not user_email:
            return jsonify({'success': True, 'show_popup': False, 'announcement': None})

        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({'success': True, 'show_popup': False, 'announcement': None})

        show_popup = latest_ann.id > user.last_read_announcement_id

        return jsonify({
            'success': True,
            'show_popup': show_popup,
            'announcement': {
                'id': latest_ann.id,
                'content': latest_ann.content,
                'created_at': latest_ann.created_at.strftime('%Y-%m-%d %H:%M') if latest_ann.created_at else ''
            }
        })
    except Exception as e:
        current_app.logger.error(f'取得最新公告錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/announcements/read', methods=['POST'])
def mark_announcement_as_read():
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({'success': False, 'message': '未登入'}), 401

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'success': False, 'message': '使用者不存在'}), 404

    try:
        latest_ann = SystemAnnouncement.query.order_by(SystemAnnouncement.id.desc()).first()
        if latest_ann:
            user.last_read_announcement_id = latest_ann.id
            db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'更新公告已讀記錄錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/admin/announcements', methods=['GET'])
@admin_required
def admin_get_announcements():
    try:
        anns = SystemAnnouncement.query.order_by(SystemAnnouncement.id.desc()).all()
        result = []
        for a in anns:
            result.append({
                'id': a.id,
                'content': a.content,
                'created_at': a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else ''
            })
        return jsonify({'success': True, 'announcements': result})
    except Exception as e:
        current_app.logger.error(f'管理員載入公告錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/admin/announcements', methods=['POST'])
@admin_required
def admin_create_announcement():
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'message': '公告內容不能為空'}), 400

    try:
        new_ann = SystemAnnouncement(content=content)
        db.session.add(new_ann)
        db.session.commit()

        user_email = session.get('user_email')
        log_action(user_email, '發布系統公告', f'發布了新公告：{content[:30]}...')

        return jsonify({'success': True, 'id': new_ann.id})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'發布公告錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/admin/announcements/<int:ann_id>', methods=['DELETE'])
@admin_required
def admin_delete_announcement(ann_id):
    try:
        ann = SystemAnnouncement.query.get(ann_id)
        if not ann:
            return jsonify({'success': False, 'message': '公告不存在'}), 404

        db.session.delete(ann)
        db.session.commit()

        user_email = session.get('user_email')
        log_action(user_email, '刪除系統公告', f'刪除了公告 ID：{ann_id}')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'刪除公告錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/bug_reports', methods=['POST'])
def create_bug_report():
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    report_type = data.get('report_type', 'bug').strip()

    if not content:
        return jsonify({'success': False, 'message': '回報內容不能為空'}), 400
    if report_type not in ['bug', 'suggest']:
        return jsonify({'success': False, 'message': '無效的回報類型'}), 400

    try:
        user_email = session.get('user_email')
        user_id = None
        if user_email:
            user = User.query.filter_by(email=user_email).first()
            if user:
                user_id = user.id

        new_report = BugReport(
            user_id=user_id,
            report_type=report_type,
            content=content
        )
        db.session.add(new_report)
        db.session.commit()

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'提交 Bug 回報錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/admin/bug_reports', methods=['GET'])
@admin_required
def admin_get_bug_reports():
    try:
        reports = BugReport.query.order_by(BugReport.id.desc()).all()
        result = []
        for r in reports:
            author = User.query.get(r.user_id) if r.user_id else None
            result.append({
                'id': r.id,
                'report_type': r.report_type,
                'content': r.content,
                'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                'user_name': author.name if author else '訪客/未登入',
                'user_email': author.email if author else ''
            })
        return jsonify({'success': True, 'reports': result})
    except Exception as e:
        current_app.logger.error(f'管理員載入 Bug 回報錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500


@system_bp.route('/api/admin/bug_reports/<int:report_id>', methods=['DELETE'])
@admin_required
def admin_delete_bug_report(report_id):
    try:
        report = BugReport.query.get(report_id)
        if not report:
            return jsonify({'success': False, 'message': '回報不存在'}), 404

        db.session.delete(report)
        db.session.commit()

        user_email = session.get('user_email')
        log_action(user_email, '刪除 Bug 回報', f'刪除了回報 ID：{report_id}')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'刪除 Bug 回報錯誤：{e}')
        return jsonify({'success': False, "message": "系統發生錯誤，請稍後再試"}), 500
