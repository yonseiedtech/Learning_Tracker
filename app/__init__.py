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
    socketio.init_app(app, cors_allowed_origins="*", async_mode='eventlet')
    
    from app.routes import auth, courses, checkpoints, progress, analytics, main
    app.register_blueprint(auth.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(checkpoints.bp)
    app.register_blueprint(progress.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(main.bp)
    
    from app import events
    
    with app.app_context():
        db.create_all()
    
    return app
