from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app.models import Course, Enrollment, Progress, Checkpoint, ActiveSession, Subject, SubjectEnrollment, Notification
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func

bp = Blueprint('main', __name__)

@bp.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@bp.route('/')
def index():
    if request.args.get('health') == '1':
        return 'OK', 200
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_instructor():
        courses = Course.query.filter_by(instructor_id=current_user.id).filter(
            Course.deleted_at.is_(None),
            Course.subject_id.is_(None)
        ).all()
        subjects = Subject.query.filter_by(instructor_id=current_user.id).filter(Subject.deleted_at.is_(None)).all()
        
        total_students = db.session.query(func.count(func.distinct(Enrollment.user_id))).join(Course).filter(
            Course.instructor_id == current_user.id
        ).scalar() or 0
        
        total_checkpoints = Checkpoint.query.join(Course).filter(
            Course.instructor_id == current_user.id,
            Checkpoint.deleted_at == None
        ).count()
        
        active_sessions = ActiveSession.query.join(Course).filter(
            Course.instructor_id == current_user.id,
            Course.deleted_at.is_(None),
            ActiveSession.ended_at == None
        ).all()
        
        upcoming_sessions = ActiveSession.query.join(Course).filter(
            Course.instructor_id == current_user.id,
            Course.deleted_at.is_(None),
            ActiveSession.session_type == 'scheduled',
            ActiveSession.scheduled_at > datetime.utcnow(),
            ActiveSession.ended_at == None
        ).order_by(ActiveSession.scheduled_at).limit(5).all()
        
        recent_progress = Progress.query.join(Checkpoint).join(Course).filter(
            Course.instructor_id == current_user.id,
            Progress.completed_at != None
        ).order_by(Progress.completed_at.desc()).limit(10).all()
        
        return render_template('dashboard/instructor.html', 
            courses=courses,
            subjects=subjects,
            total_students=total_students,
            total_checkpoints=total_checkpoints,
            active_sessions=active_sessions,
            upcoming_sessions=upcoming_sessions,
            recent_progress=recent_progress
        )
    else:
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
        courses = [e.course for e in enrollments if not e.course.deleted_at and e.course.visibility != 'private' and e.course.subject_id is None]
        
        subject_enrollments = SubjectEnrollment.query.filter_by(
            user_id=current_user.id,
            status='approved'
        ).all()
        subjects = [se.subject for se in subject_enrollments if se.subject and not se.subject.deleted_at]
        
        pending_subject_enrollments = SubjectEnrollment.query.filter_by(
            user_id=current_user.id,
            status='pending'
        ).all()
        
        total_completed = Progress.query.filter_by(user_id=current_user.id).filter(Progress.completed_at != None).count()
        
        total_checkpoints = 0
        for course in courses:
            total_checkpoints += course.checkpoints.filter_by(deleted_at=None).count()
        
        completion_rate = round((total_completed / total_checkpoints * 100) if total_checkpoints > 0 else 0)
        
        total_minutes = db.session.query(func.sum(Progress.duration_seconds)).filter(
            Progress.user_id == current_user.id,
            Progress.duration_seconds != None
        ).scalar() or 0
        total_hours = round(total_minutes / 3600, 1)
        
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        daily_progress = db.session.query(
            func.date(Progress.completed_at),
            func.count(Progress.id)
        ).filter(
            Progress.user_id == current_user.id,
            Progress.completed_at >= seven_days_ago
        ).group_by(func.date(Progress.completed_at)).all()
        
        streak_days = calculate_streak(current_user.id)
        
        active_sessions_for_student = []
        for course in courses:
            active = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
            if active:
                active_sessions_for_student.append({'course': course, 'session': active})
        
        upcoming_for_student = ActiveSession.query.join(Course).join(Enrollment).filter(
            Enrollment.user_id == current_user.id,
            Course.deleted_at.is_(None),
            Course.visibility != 'private',
            ActiveSession.session_type == 'scheduled',
            ActiveSession.scheduled_at > datetime.utcnow(),
            ActiveSession.ended_at == None
        ).order_by(ActiveSession.scheduled_at).limit(5).all()
        
        all_subjects = Subject.query.filter(
            Subject.deleted_at.is_(None),
            Subject.is_visible == True
        ).all()
        available_subjects = [s for s in all_subjects if s.id not in [se.subject_id for se in subject_enrollments + pending_subject_enrollments]]
        
        return render_template('dashboard/student.html', 
            courses=courses,
            subjects=subjects,
            pending_enrollments=pending_subject_enrollments,
            available_subjects=available_subjects,
            total_completed=total_completed,
            total_checkpoints=total_checkpoints,
            completion_rate=completion_rate,
            total_hours=total_hours,
            streak_days=streak_days,
            daily_progress=daily_progress,
            active_sessions=active_sessions_for_student,
            upcoming_sessions=upcoming_for_student
        )


def calculate_streak(user_id):
    today = datetime.utcnow().date()
    streak = 0
    current_date = today
    
    while True:
        has_progress = Progress.query.filter(
            Progress.user_id == user_id,
            func.date(Progress.completed_at) == current_date
        ).first()
        
        if has_progress:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break
        
        if streak > 365:
            break
    
    return streak

@bp.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return render_template('notifications.html', notifications=user_notifications)


@bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/notifications/unread-count')
@login_required
def unread_notification_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})
