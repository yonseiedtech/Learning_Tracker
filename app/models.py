from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager, bcrypt
import secrets
import string

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Organization(db.Model):
    __tablename__ = 'organizations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    logo = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    members = db.relationship('User', backref='org', lazy='dynamic')
    subjects = db.relationship('Subject', backref='org', lazy='dynamic')

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Profile fields
    profile_image = db.Column(db.Text, nullable=True)
    nickname = db.Column(db.String(80), nullable=True)
    full_name = db.Column(db.String(120), nullable=True)
    profile_url = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Basic info
    phone = db.Column(db.String(20), nullable=True)
    
    # Additional info
    organization_name = db.Column(db.String(200), nullable=True)
    position = db.Column(db.String(100), nullable=True)
    job_title = db.Column(db.String(100), nullable=True)
    
    # Instructor verification
    instructor_verified = db.Column(db.Boolean, default=False)
    verification_requested_at = db.Column(db.DateTime, nullable=True)
    
    courses_taught = db.relationship('Course', backref='instructor', lazy='dynamic')
    enrollments = db.relationship('Enrollment', backref='user', lazy='dynamic')
    progress_records = db.relationship('Progress', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def is_student(self):
        return self.role == 'student'
    
    def is_instructor(self):
        return self.role in ['instructor', 'org_admin', 'system_admin']
    
    def is_org_admin(self):
        return self.role == 'org_admin'
    
    def is_system_admin(self):
        return self.role == 'system_admin'
    
    def can_access_subject(self, subject):
        if self.is_system_admin():
            return True
        if self.is_org_admin() and subject.organization_id == self.organization_id:
            return True
        if subject.instructor_id == self.id:
            return True
        return False
    
    def is_enrolled(self, course):
        return Enrollment.query.filter_by(user_id=self.id, course_id=course.id).first() is not None

class Subject(db.Model):
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    is_visible = db.Column(db.Boolean, default=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    instructor = db.relationship('User', backref='subjects_taught')
    courses = db.relationship('Course', backref='subject', lazy='dynamic', cascade='all, delete-orphan')
    enrollments = db.relationship('SubjectEnrollment', backref='enrolled_subject', lazy='dynamic')
    members = db.relationship('SubjectMember', backref='member_subject', lazy='dynamic')
    
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
    session_number = db.Column(db.Integer, nullable=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    session_type = db.Column(db.String(30), default='live_session')
    
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    attendance_start = db.Column(db.DateTime, nullable=True)
    attendance_end = db.Column(db.DateTime, nullable=True)
    late_allowed = db.Column(db.Boolean, default=False)
    late_end = db.Column(db.DateTime, nullable=True)
    visibility = db.Column(db.String(20), default='public')
    prerequisite_course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    
    video_url = db.Column(db.Text, nullable=True)
    video_file_path = db.Column(db.Text, nullable=True)
    video_file_name = db.Column(db.String(255), nullable=True)
    
    material_file_path = db.Column(db.Text, nullable=True)
    material_file_name = db.Column(db.String(255), nullable=True)
    material_file_type = db.Column(db.String(50), nullable=True)
    
    assignment_description = db.Column(db.Text, nullable=True)
    assignment_due_date = db.Column(db.DateTime, nullable=True)
    
    quiz_time_limit = db.Column(db.Integer, nullable=True)
    quiz_pass_score = db.Column(db.Integer, nullable=True)
    
    preparation_status = db.Column(db.String(30), default='not_ready')
    
    prerequisite = db.relationship('Course', remote_side=[id], backref='dependent_courses')
    
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
    
    def is_accessible_by(self, user):
        if self.instructor_id == user.id:
            return True
        if not user.is_enrolled(self):
            return False
        if self.visibility == 'public':
            return True
        if self.visibility == 'private':
            return False
        if self.visibility == 'date_based':
            now = datetime.utcnow()
            if self.start_date and now < self.start_date:
                return False
            if self.end_date and now > self.end_date:
                return False
            return True
        if self.visibility == 'prerequisite':
            if not self.prerequisite_course_id:
                return True
            prereq_completed = Progress.query.join(Checkpoint).filter(
                Progress.user_id == user.id,
                Progress.completed_at.isnot(None),
                Checkpoint.course_id == self.prerequisite_course_id
            ).count()
            total_checkpoints = Checkpoint.query.filter_by(
                course_id=self.prerequisite_course_id,
                deleted_at=None
            ).count()
            return prereq_completed >= total_checkpoints and total_checkpoints > 0
        return True

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
    paused_at = db.Column(db.DateTime, nullable=True)
    accumulated_seconds = db.Column(db.Integer, default=0)
    is_paused = db.Column(db.Boolean, default=False)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'checkpoint_id', 'mode', name='unique_progress'),)
    
    def calculate_duration(self):
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())
    
    def get_elapsed_seconds(self):
        accumulated = self.accumulated_seconds or 0
        
        if self.completed_at:
            return self.duration_seconds or accumulated
        
        if not self.started_at:
            return accumulated
        
        if self.is_paused:
            return accumulated
        
        current_session = (datetime.utcnow() - self.started_at).total_seconds()
        return int(accumulated + current_session)

class ActiveSession(db.Model):
    __tablename__ = 'active_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default='live')
    session_type = db.Column(db.String(20), nullable=False, default='immediate')
    live_status = db.Column(db.String(20), default='preparing')
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
    
    def get_live_status_display(self):
        status_map = {
            'preparing': '라이브 준비중',
            'live': '라이브 중',
            'ended': '라이브 종료'
        }
        return status_map.get(self.live_status, '대기중')

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

class Attendance(db.Model):
    __tablename__ = 'attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('active_sessions.id'), nullable=True)
    status = db.Column(db.String(20), default='present')
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    checked_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    course = db.relationship('Course', backref='attendance_records')
    user = db.relationship('User', foreign_keys=[user_id], backref='attendance_records')
    session = db.relationship('ActiveSession', backref='attendance_records')
    checked_by = db.relationship('User', foreign_keys=[checked_by_id])
    
    __table_args__ = (db.UniqueConstraint('course_id', 'user_id', 'session_id', name='unique_attendance'),)


# Community Models
class LearningReview(db.Model):
    __tablename__ = 'learning_reviews'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    likes_count = db.Column(db.Integer, default=0)
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='learning_reviews')
    course = db.relationship('Course', backref='reviews')
    subject = db.relationship('Subject', backref='reviews')
    comments = db.relationship('ReviewComment', backref='review', lazy='dynamic', cascade='all, delete-orphan')

class ReviewComment(db.Model):
    __tablename__ = 'review_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('learning_reviews.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='review_comments')

class QnAPost(db.Model):
    __tablename__ = 'qna_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_resolved = db.Column(db.Boolean, default=False)
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='qna_posts')
    course = db.relationship('Course', backref='qna_posts')
    subject = db.relationship('Subject', backref='qna_posts')
    answers = db.relationship('QnAAnswer', backref='post', lazy='dynamic', cascade='all, delete-orphan')

class QnAAnswer(db.Model):
    __tablename__ = 'qna_answers'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('qna_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_accepted = db.Column(db.Boolean, default=False)
    likes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='qna_answers')

class StudyGroup(db.Model):
    __tablename__ = 'study_groups'
    
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='general')
    max_members = db.Column(db.Integer, default=10)
    current_members = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='recruiting')
    meeting_type = db.Column(db.String(20), default='online')
    meeting_schedule = db.Column(db.String(200), nullable=True)
    tags = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    creator = db.relationship('User', backref='created_study_groups')
    members = db.relationship('StudyGroupMember', backref='group', lazy='dynamic', cascade='all, delete-orphan')

class StudyGroupMember(db.Model):
    __tablename__ = 'study_group_members'
    
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('study_groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='study_group_memberships')
    
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='unique_group_member'),)


class SubjectEnrollment(db.Model):
    __tablename__ = 'subject_enrollments'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='subject_enrollments')
    
    __table_args__ = (db.UniqueConstraint('subject_id', 'user_id', name='unique_subject_enrollment'),)


class GuidePost(db.Model):
    __tablename__ = 'guide_posts'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_pinned = db.Column(db.Boolean, default=False)
    is_answered = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    author = db.relationship('User', backref='guide_posts')
    comments = db.relationship('GuideComment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('GuideAttachment', backref='post', lazy='dynamic', cascade='all, delete-orphan')


class GuideComment(db.Model):
    __tablename__ = 'guide_comments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('guide_posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_admin_reply = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', backref='guide_comments')


class GuideAttachment(db.Model):
    __tablename__ = 'guide_attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('guide_posts.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(100))
    file_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SubjectMember(db.Model):
    __tablename__ = 'subject_members'
    
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(30), nullable=False, default='student')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('subject_memberships', lazy='dynamic'))
    
    __table_args__ = (db.UniqueConstraint('subject_id', 'user_id', name='unique_subject_member'),)
    
    @staticmethod
    def get_role_display(role):
        role_map = {
            'instructor': '강사',
            'assistant': '조교',
            'student': '학습자'
        }
        return role_map.get(role, role)

class QuizQuestion(db.Model):
    __tablename__ = 'quiz_questions'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(30), default='multiple_choice')
    options = db.Column(db.Text)
    correct_answer = db.Column(db.Text)
    points = db.Column(db.Integer, default=1)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    course = db.relationship('Course', backref=db.backref('quiz_questions', lazy='dynamic'))

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    max_score = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    answers = db.Column(db.Text)
    
    course = db.relationship('Course', backref=db.backref('quiz_attempts', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('quiz_attempts', lazy='dynamic'))

class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text)
    file_path = db.Column(db.Text, nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    score = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_at = db.Column(db.DateTime, nullable=True)
    graded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    course = db.relationship('Course', backref=db.backref('submissions', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('submissions', lazy='dynamic'))
    grader = db.relationship('User', foreign_keys=[graded_by])
