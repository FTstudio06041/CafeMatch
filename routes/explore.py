import requests
from flask import Blueprint, jsonify, request, redirect, current_app
from database import db
from models import Cafes
from utils.auth import get_current_user
from utils.response import error_response
from services.cafe_explore_service import get_cafes_data
from services.google_maps_service import has_google_maps_key, get_google_photo_uri

explore_bp = Blueprint('explore', __name__)

@explore_bp.route('/api/cafes', methods=['GET'])
def get_cafes():
    try:
        current_user = get_current_user()
        results = get_cafes_data(current_user)
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Database Error: {e}")
        return error_response("系統發生錯誤，請稍後再試", 500)


@explore_bp.route('/api/cafes/<int:cafe_id>/photo', methods=['GET'])
def get_cafe_photo(cafe_id):
    cafe = Cafes.query.get_or_404(cafe_id)

    if not has_google_maps_key():
        return jsonify({'error': 'Google Maps API key is not configured'}), 503

    try:
        max_width = request.args.get('width', 900, type=int)
        photo_uri = get_google_photo_uri(cafe, max_width=max_width)
        if not photo_uri:
            return jsonify({'error': 'No Google photo found for this cafe'}), 404
        return redirect(photo_uri, code=302)
    except requests.RequestException as e:
        current_app.logger.error(f'Google Places photo error for cafe {cafe_id}: {e}')
        db.session.rollback()
        return jsonify({'error': 'Failed to fetch Google photo'}), 502
    except Exception as e:
        current_app.logger.error(f'Cafe photo error for cafe {cafe_id}: {e}')
        db.session.rollback()
        return error_response("系統發生錯誤，請稍後再試", 500)
