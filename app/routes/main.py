from flask import Blueprint, render_template, redirect, url_for, jsonify, request, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app.firebase_init import get_db
from datetime import datetime, timedelta, timezone
from collections import defaultdict

bp = Blueprint('main', __name__)

@bp.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@bp.route('/')
def index():
    if request.args.get('health') == '1':
        return 'OK', 200
    user = get_current_user()
    if user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/dashboard')
@auth_required
def dashboard():
    user = get_current_user()

    if user.is_instructor():
        # --- Instructor dashboard ---

        # Standalone courses (no subject_id, not deleted)
        all_instructor_courses = dao.get_courses_by_instructor(user.id)
        courses = [
            c for c in all_instructor_courses
            if not c.get('deleted_at') and not c.get('subject_id')
        ]

        # Subjects owned by instructor (not deleted)
        all_subjects = dao.get_subjects_by_instructor(user.id)
        subjects = [s for s in all_subjects if not s.get('deleted_at')]

        # Total unique students across standalone courses and subjects
        student_ids = set()

        # Students from standalone course enrollments
        for course in courses:
            enrollments = dao.get_enrollments_by_course(course['id'])
            for e in enrollments:
                student_ids.add(e['user_id'])

        # Students from subject enrollments (approved only)
        for subject in subjects:
            sub_enrollments = dao.get_subject_enrollments_by_subject(subject['id'], status='approved')
            for se in sub_enrollments:
                student_ids.add(se['user_id'])

        total_students = len(student_ids)

        # Total checkpoints across all instructor courses (standalone + subject courses)
        total_checkpoints = 0
        all_course_ids = []
        # Include standalone courses
        for course in courses:
            cps = dao.get_checkpoints_by_course(course['id'])
            total_checkpoints += len(cps)
            all_course_ids.append(course['id'])
        # Include subject courses
        for subject in subjects:
            subject_courses = dao.get_courses_by_subject(subject['id'])
            for sc in subject_courses:
                if not sc.get('deleted_at'):
                    cps = dao.get_checkpoints_by_course(sc['id'])
                    total_checkpoints += len(cps)
                    all_course_ids.append(sc['id'])

        # Active sessions for instructor's courses
        active_sessions = []
        for cid in all_course_ids:
            session = dao.get_active_session_for_course(cid)
            if session:
                session['course'] = dao.get_course(cid)
                active_sessions.append(session)

        # Upcoming scheduled sessions
        now = datetime.now(timezone.utc)
        upcoming_sessions = []
        for cid in all_course_ids:
            sessions = dao.get_sessions_by_course(cid)
            for s in sessions:
                if (s.get('session_type') == 'scheduled'
                        and s.get('scheduled_at')
                        and s['scheduled_at'] > now
                        and not s.get('ended_at')):
                    s['course'] = dao.get_course(cid)
                    upcoming_sessions.append(s)
        # Sort by scheduled_at and take first 5
        upcoming_sessions.sort(key=lambda s: s['scheduled_at'])
        upcoming_sessions = upcoming_sessions[:5]

        # Recent progress across all instructor courses
        recent_progress = []
        for cid in all_course_ids:
            checkpoints = dao.get_checkpoints_by_course(cid)
            cp_map = {cp['id']: cp for cp in checkpoints}
            for cp in checkpoints:
                progress_records = dao.get_progress_by_checkpoint(cp['id'])
                for p in progress_records:
                    if p.get('completed_at'):
                        p['checkpoint'] = cp_map.get(p.get('checkpoint_id'))
                        p['course'] = dao.get_course(cid)
                        p['user'] = dao.get_user(p['user_id'])
                        recent_progress.append(p)
        # Sort by completed_at descending and take first 10
        recent_progress.sort(key=lambda p: p.get('completed_at', datetime.min), reverse=True)
        recent_progress = recent_progress[:10]

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
        # --- Student dashboard ---

        # Enrolled standalone courses
        enrollments = dao.get_enrollments_by_user(user.id)
        courses = []
        for e in enrollments:
            course = dao.get_course(e['course_id'])
            if course and not course.get('deleted_at') and course.get('visibility') != 'private' and not course.get('subject_id'):
                courses.append(course)

        # Approved subject enrollments
        subject_enrollments = dao.get_subject_enrollments_by_user(user.id, status='approved')
        subjects = []
        for se in subject_enrollments:
            subject = dao.get_subject(se['subject_id'])
            if subject and not subject.get('deleted_at'):
                subjects.append(subject)

        # Pending subject enrollments
        pending_subject_enrollments = dao.get_subject_enrollments_by_user(user.id, status='pending')

        # Progress stats
        all_progress = dao.get_progress_by_user(user.id)
        total_completed = sum(1 for p in all_progress if p.get('completed_at'))

        # Count checkpoints from standalone courses
        total_checkpoints = 0
        for course in courses:
            cps = dao.get_checkpoints_by_course(course['id'])
            total_checkpoints += len(cps)

        # Also count checkpoints from enrolled subject sessions
        for subject in subjects:
            subject_courses = dao.get_courses_by_subject(subject['id'])
            for sc in subject_courses:
                if not sc.get('deleted_at'):
                    cps = dao.get_checkpoints_by_course(sc['id'])
                    total_checkpoints += len(cps)

        completion_rate = round((total_completed / total_checkpoints * 100) if total_checkpoints > 0 else 0)

        # Total hours from duration_seconds
        total_seconds = sum(p.get('duration_seconds', 0) or 0 for p in all_progress)
        total_hours = round(total_seconds / 3600, 1)

        # Daily progress for last 7 days
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        daily_counts = defaultdict(int)
        for p in all_progress:
            completed_at = p.get('completed_at')
            if completed_at and completed_at >= seven_days_ago:
                day = completed_at.date() if hasattr(completed_at, 'date') else completed_at
                daily_counts[day] += 1
        daily_progress = sorted(daily_counts.items())

        streak_days = calculate_streak(user.id, all_progress)

        # Active sessions for student's enrolled courses
        active_sessions_for_student = []
        for course in courses:
            active = dao.get_active_session_for_course(course['id'])
            if active:
                active_sessions_for_student.append({'course': course, 'session': active})

        # Active sessions for subject courses
        for subject in subjects:
            subject_courses = dao.get_courses_by_subject(subject['id'])
            for sc in subject_courses:
                if not sc.get('deleted_at'):
                    active = dao.get_active_session_for_course(sc['id'])
                    if active:
                        active_sessions_for_student.append({'course': sc, 'session': active})

        # Upcoming scheduled sessions for student
        now = datetime.now(timezone.utc)
        upcoming_for_student = []
        for course in courses:
            sessions = dao.get_sessions_by_course(course['id'])
            for s in sessions:
                if (s.get('session_type') == 'scheduled'
                        and s.get('scheduled_at')
                        and s['scheduled_at'] > now
                        and not s.get('ended_at')):
                    s['course'] = course
                    upcoming_for_student.append(s)
        upcoming_for_student.sort(key=lambda s: s['scheduled_at'])
        upcoming_for_student = upcoming_for_student[:5]

        # Available subjects (visible, not already enrolled or pending)
        enrolled_subject_ids = {se['subject_id'] for se in subject_enrollments}
        pending_subject_ids = {se['subject_id'] for se in pending_subject_enrollments}
        excluded_ids = enrolled_subject_ids | pending_subject_ids
        all_visible_subjects = dao.get_visible_subjects()
        available_subjects = [s for s in all_visible_subjects if s['id'] not in excluded_ids]

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


def calculate_streak(user_id, all_progress=None):
    if all_progress is None:
        all_progress = dao.get_progress_by_user(user_id)

    # Build a set of dates that have completed progress
    completed_dates = set()
    for p in all_progress:
        completed_at = p.get('completed_at')
        if completed_at:
            day = completed_at.date() if hasattr(completed_at, 'date') else completed_at
            completed_dates.add(day)

    today = datetime.now(timezone.utc).date()
    streak = 0
    current_date = today

    while current_date in completed_dates:
        streak += 1
        current_date -= timedelta(days=1)
        if streak > 365:
            break

    return streak

@bp.route('/notifications')
@auth_required
def notifications():
    user = get_current_user()
    user_notifications = dao.get_notifications(user.id, limit=50)
    return render_template('notifications.html', notifications=user_notifications)


@bp.route('/notifications/<notification_id>/read', methods=['POST'])
@auth_required
def mark_notification_read(notification_id):
    user = get_current_user()
    # Verify ownership by fetching the notification document
    doc = get_db().collection('notifications').document(notification_id).get()
    if not doc.exists:
        abort(404)
    notif = doc.to_dict()
    if notif.get('user_id') != user.id:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    dao.mark_notification_read(notification_id)
    return jsonify({'success': True})


@bp.route('/notifications/mark-all-read', methods=['POST'])
@auth_required
def mark_all_notifications_read():
    user = get_current_user()
    dao.mark_all_read(user.id)
    return jsonify({'success': True})


@bp.route('/notifications/unread-count')
@auth_required
def unread_notification_count():
    user = get_current_user()
    count = dao.count_unread(user.id)
    return jsonify({'count': count})
