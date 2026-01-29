from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app.models import Course, Enrollment, Progress, Checkpoint, ActiveSession, Subject
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
        courses = Course.query.filter_by(instructor_id=current_user.id).all()
        subjects = Subject.query.filter_by(instructor_id=current_user.id).all()
        
        total_students = db.session.query(func.count(func.distinct(Enrollment.user_id))).join(Course).filter(
            Course.instructor_id == current_user.id
        ).scalar() or 0
        
        total_checkpoints = Checkpoint.query.join(Course).filter(
            Course.instructor_id == current_user.id,
            Checkpoint.deleted_at == None
        ).count()
        
        active_sessions = ActiveSession.query.join(Course).filter(
            Course.instructor_id == current_user.id,
            ActiveSession.ended_at == None
        ).all()
        
        upcoming_sessions = ActiveSession.query.join(Course).filter(
            Course.instructor_id == current_user.id,
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
        courses = [e.course for e in enrollments]
        
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
            ActiveSession.session_type == 'scheduled',
            ActiveSession.scheduled_at > datetime.utcnow(),
            ActiveSession.ended_at == None
        ).order_by(ActiveSession.scheduled_at).limit(5).all()
        
        return render_template('dashboard/student.html', 
            courses=courses,
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
