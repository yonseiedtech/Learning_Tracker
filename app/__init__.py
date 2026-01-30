import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
bcrypt = Bcrypt()
socketio = SocketIO()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)
    
    allowed_origins = []
    replit_domains = os.environ.get('REPLIT_DOMAINS', '')
    if replit_domains:
        for domain in replit_domains.split(','):
            allowed_origins.append(f'https://{domain.strip()}')
    
    if not allowed_origins:
        allowed_origins = []
        app.logger.warning('REPLIT_DOMAINS not set - WebSocket CORS restricted to same origin only')
    
    socketio.init_app(app, cors_allowed_origins=allowed_origins if allowed_origins else None, async_mode='eventlet')
    
    from app.routes import auth, courses, checkpoints, progress, analytics, main, forum, subjects, attendance, community
    app.register_blueprint(auth.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(checkpoints.bp)
    app.register_blueprint(progress.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(forum.bp)
    app.register_blueprint(subjects.bp)
    app.register_blueprint(attendance.bp)
    app.register_blueprint(community.bp)
    
    from app import events
    
    with app.app_context():
        db.create_all()
    
    return app
