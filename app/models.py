from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager, bcrypt
import secrets
import string

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    courses_taught = db.relationship('Course', backref='instructor', lazy='dynamic')
    enrollments = db.relationship('Enrollment', backref='user', lazy='dynamic')
    progress_records = db.relationship('Progress', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def is_instructor(self):
        return self.role == 'instructor'
    
    def is_enrolled(self, course):
        return Enrollment.query.filter_by(user_id=self.id, course_id=course.id).first() is not None

class Subject(db.Model):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    instructor = db.relationship('User', backref='subjects_taught')
    courses = db.relationship('Course', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    
    @staticmethod
    def generate_invite_code():
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(8))
            if not Subject.query.filter_by(invite_code=code).first():
                return code
    
    def get_enrolled_students(self):
        return User.query.join(Enrollment).join(Course).filter(
            Course.subject_id == self.id,
            User.role == 'student'
        ).distinct().all()

class Course(db.Model):
    __tablename__ = 'courses'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    week_number = db.Column(db.Integer, nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    enrollments = db.relationship('Enrollment', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    checkpoints = db.relationship('Checkpoint', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    active_sessions = db.relationship('ActiveSession', backref='course', lazy='dynamic', cascade='all, delete-orphan')
    
    @staticmethod
    def generate_invite_code():
        chars = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(secrets.choice(chars) for _ in range(8))
            if not Course.query.filter_by(invite_code=code).first():
                return code
    
    def get_enrolled_students(self):
        return User.query.join(Enrollment).filter(
            Enrollment.course_id == self.id,
            User.role == 'student'
        ).all()

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('course_id', 'user_id', name='unique_enrollment'),)

class Checkpoint(db.Model):
    __tablename__ = 'checkpoints'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    order = db.Column(db.Integer, nullable=False, default=0)
    estimated_minutes = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    progress_records = db.relationship('Progress', backref='checkpoint', lazy='dynamic', cascade='all, delete-orphan')
    
    def is_deleted(self):
        return self.deleted_at is not None

class Progress(db.Model):
    __tablename__ = 'progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    checkpoint_id = db.Column(db.Integer, db.ForeignKey('checkpoints.id'), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default='self_paced')
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Integer)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'checkpoint_id', 'mode', name='unique_progress'),)
    
    def calculate_duration(self):
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())

class ActiveSession(db.Model):
    __tablename__ = 'active_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default='live')
    session_type = db.Column(db.String(20), nullable=False, default='immediate')
    scheduled_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    current_checkpoint_id = db.Column(db.Integer, db.ForeignKey('checkpoints.id'), nullable=True)
    
    def is_scheduled(self):
        return self.session_type == 'scheduled'
    
    def can_start(self):
        if self.session_type == 'immediate':
            return True
        if self.scheduled_at:
            return datetime.utcnow() >= self.scheduled_at
        return False

class UnderstandingStatus(db.Model):
    __tablename__ = 'understanding_status'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    checkpoint_id = db.Column(db.Integer, db.ForeignKey('checkpoints.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('active_sessions.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='understanding_records')
    checkpoint = db.relationship('Checkpoint', backref='understanding_records')

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='chat_messages')
    course = db.relationship('Course', backref='chat_messages')

class ForumPost(db.Model):
    __tablename__ = 'forum_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='forum_posts')
    course = db.relationship('Course', backref='forum_posts')
    comments = db.relationship('ForumComment', backref='post', lazy='dynamic', cascade='all, delete-orphan')

class ForumComment(db.Model):
    __tablename__ = 'forum_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='forum_comments')

class LiveSessionPost(db.Model):
    __tablename__ = 'live_session_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('active_sessions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='live_session_posts')
    session = db.relationship('ActiveSession', backref='posts')
    comments = db.relationship('LiveSessionComment', backref='post', lazy='dynamic', cascade='all, delete-orphan')

class LiveSessionComment(db.Model):
    __tablename__ = 'live_session_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('live_session_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='live_session_comments')
