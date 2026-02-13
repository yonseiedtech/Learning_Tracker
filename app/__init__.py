import os
from flask import Flask, g
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from config import Config

socketio = SocketIO()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    csrf.init_app(app)

    # Initialize Firebase
    from app.firebase_init import init_firebase
    init_firebase(app.config)

    # CORS origins
    allowed_origins = []
    cors_origins = app.config.get('CORS_ALLOWED_ORIGINS', '')
    if cors_origins:
        for origin in cors_origins.split(','):
            origin = origin.strip()
            if origin:
                allowed_origins.append(origin)

    socketio.init_app(
        app,
        cors_allowed_origins=allowed_origins if allowed_origins else None,
        async_mode='eventlet'
    )

    # Register current_user context processor and before_request
    from app.decorators import load_current_user, get_current_user

    @app.before_request
    def before_request():
        load_current_user()

    @app.context_processor
    def inject_current_user():
        return {'current_user': get_current_user()}

    # Register blueprints
    from app.routes import (
        auth, courses, checkpoints, progress, analytics,
        main, forum, subjects, attendance, community, guide,
        sessions, slides
    )
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
    app.register_blueprint(guide.bp)
    app.register_blueprint(sessions.bp)
    app.register_blueprint(slides.bp)

    from app import events  # noqa: F401

    return app
