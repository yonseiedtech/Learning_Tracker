from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from datetime import datetime

bp = Blueprint('attendance', __name__, url_prefix='/attendance')


def get_enrolled_students(course_id):
    """Get enrolled student user dicts for a course."""
    enrollments = dao.get_enrollments_by_course(course_id)
    students = []
    for enrollment in enrollments:
        user = dao.get_user(enrollment['user_id'])
        if user:
            students.append(user)
    return students


@bp.route('/course/<course_id>')
@auth_required
def course_attendance(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course['instructor_id'] != user.id and not dao.is_enrolled(user.id, course_id):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    sessions = dao.get_sessions_by_course(course_id)
    students = get_enrolled_students(course_id)

    attendance_data = {}
    for session in sessions:
        session_id = session['id']
        attendance_data[session_id] = {}
        for student in students:
            student_id = student['id']
            att = dao.get_attendance(course_id, student_id, session_id)
            attendance_data[session_id][student_id] = att

    is_instructor = course['instructor_id'] == user.id

    return render_template('attendance/course.html',
                           course=course,
                           sessions=sessions,
                           students=students,
                           attendance_data=attendance_data,
                           is_instructor=is_instructor)


@bp.route('/mark', methods=['POST'])
@auth_required
def mark_attendance():
    user = get_current_user()
    data = request.get_json()
    course_id = data.get('course_id')
    session_id = data.get('session_id')
    user_id = data.get('user_id')
    status = data.get('status', 'present')
    notes = data.get('notes', '')

    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course['instructor_id'] != user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403

    result = dao.create_or_update_attendance({
        'course_id': course_id,
        'user_id': user_id,
        'session_id': session_id,
        'status': status,
        'notes': notes,
        'checked_at': datetime.utcnow(),
        'checked_by_id': user.id,
    })

    return jsonify({
        'success': True,
        'attendance_id': result['id'] if isinstance(result, dict) else result,
        'status': status
    })


@bp.route('/self-check', methods=['POST'])
@auth_required
def self_check():
    user = get_current_user()
    data = request.get_json()
    course_id = data.get('course_id')
    session_id = data.get('session_id')

    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if not dao.is_enrolled(user.id, course_id):
        return jsonify({'error': '등록되지 않은 세미나입니다.'}), 403

    session = dao.get_active_session(session_id)
    if not session or session.get('ended_at'):
        return jsonify({'error': '진행 중인 세션이 없습니다.'}), 400

    existing = dao.get_attendance(course_id, user.id, session_id)
    if existing:
        return jsonify({'success': True, 'message': '이미 출석 체크되었습니다.', 'attendance_id': existing['id']})

    result = dao.create_or_update_attendance({
        'course_id': course_id,
        'user_id': user.id,
        'session_id': session_id,
        'status': 'present',
    })

    return jsonify({
        'success': True,
        'message': '출석이 확인되었습니다.',
        'attendance_id': result['id'] if isinstance(result, dict) else result
    })


@bp.route('/bulk-mark', methods=['POST'])
@auth_required
def bulk_mark():
    user = get_current_user()
    data = request.get_json()
    course_id = data.get('course_id')
    session_id = data.get('session_id')
    attendances = data.get('attendances', [])

    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course['instructor_id'] != user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403

    for att_data in attendances:
        att_user_id = att_data.get('user_id')
        status = att_data.get('status', 'present')

        dao.create_or_update_attendance({
            'course_id': course_id,
            'user_id': att_user_id,
            'session_id': session_id,
            'status': status,
            'checked_at': datetime.utcnow(),
            'checked_by_id': user.id,
        })

    return jsonify({'success': True, 'count': len(attendances)})


@bp.route('/student/<user_id>/course/<course_id>')
@auth_required
def student_attendance(user_id, course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course['instructor_id'] != user.id and user.id != user_id:
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    student = dao.get_user(user_id)
    if not student:
        abort(404)

    sessions = dao.get_sessions_by_course(course_id)

    attendance_records = []
    for session in sessions:
        att = dao.get_attendance(course_id, user_id, session['id'])
        started_at = session.get('started_at')
        attendance_records.append({
            'session_id': session['id'],
            'session_started_at': started_at.isoformat() if started_at else None,
            'status': att['status'] if att else 'absent',
            'checked_at': att['checked_at'].isoformat() if att and att.get('checked_at') else None
        })

    total_sessions = len(sessions)
    present_count = sum(1 for r in attendance_records if r['status'] == 'present')
    late_count = sum(1 for r in attendance_records if r['status'] == 'late')
    absent_count = sum(1 for r in attendance_records if r['status'] == 'absent')

    return jsonify({
        'student': {
            'id': student['id'],
            'username': student.get('username', ''),
            'email': student.get('email', '')
        },
        'total_sessions': total_sessions,
        'present': present_count,
        'late': late_count,
        'absent': absent_count,
        'attendance_rate': round(present_count / total_sessions * 100, 1) if total_sessions > 0 else 0,
        'records': attendance_records
    })
