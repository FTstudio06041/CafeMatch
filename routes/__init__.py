from .auth import auth_bp
from .explore import explore_bp
from .chat import chat_bp
from .quiz import quiz_bp
from .community import community_bp
from .admin import admin_bp
from .system import system_bp

def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(explore_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(quiz_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(system_bp)
