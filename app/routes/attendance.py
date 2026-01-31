from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import Attendance, Course, ActiveSession, User, Enrollment
from datetime import datetime

bp = Blueprint('attendance', __name__, url_prefix='/attendance')

@bp.route('/course/<int:course_id>')
@login_required
def course_attendance(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.instructor_id != current_user.id and not current_user.is_enrolled(course):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    sessions = ActiveSession.query.filter_by(course_id=course_id).order_by(ActiveSession.started_at.desc()).all()
    students = course.get_enrolled_students()
    
    attendance_data = {}
    for session in sessions:
        attendance_data[session.id] = {}
        for student in students:
            att = Attendance.query.filter_by(
                course_id=course_id,
                user_id=student.id,
                session_id=session.id
            ).first()
            attendance_data[session.id][student.id] = att
    
    is_instructor = course.instructor_id == current_user.id
    
    return render_template('attendance/course.html', 
                         course=course, 
                         sessions=sessions, 
                         students=students,
                         attendance_data=attendance_data,
                         is_instructor=is_instructor)

@bp.route('/mark', methods=['POST'])
@login_required
def mark_attendance():
    data = request.get_json()
    course_id = data.get('course_id')
    session_id = data.get('session_id')
    user_id = data.get('user_id')
    status = data.get('status', 'present')
    notes = data.get('notes', '')
    
    course = Course.query.get_or_404(course_id)
    
    if course.instructor_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    attendance = Attendance.query.filter_by(
        course_id=course_id,
        user_id=user_id,
        session_id=session_id
    ).first()
    
    if attendance:
        attendance.status = status
        attendance.notes = notes
        attendance.checked_at = datetime.utcnow()
        attendance.checked_by_id = current_user.id
    else:
        attendance = Attendance(
            course_id=course_id,
            user_id=user_id,
            session_id=session_id,
            status=status,
            notes=notes,
            checked_by_id=current_user.id
        )
        db.session.add(attendance)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'attendance_id': attendance.id,
        'status': status
    })

@bp.route('/self-check', methods=['POST'])
@login_required
def self_check():
    data = request.get_json()
    course_id = data.get('course_id')
    session_id = data.get('session_id')
    
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_enrolled(course):
        return jsonify({'error': '등록되지 않은 세미나입니다.'}), 403
    
    session = ActiveSession.query.filter_by(id=session_id, ended_at=None).first()
    if not session:
        return jsonify({'error': '진행 중인 세션이 없습니다.'}), 400
    
    existing = Attendance.query.filter_by(
        course_id=course_id,
        user_id=current_user.id,
        session_id=session_id
    ).first()
    
    if existing:
        return jsonify({'success': True, 'message': '이미 출석 체크되었습니다.', 'attendance_id': existing.id})
    
    attendance = Attendance(
        course_id=course_id,
        user_id=current_user.id,
        session_id=session_id,
        status='present'
    )
    db.session.add(attendance)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '출석이 확인되었습니다.',
        'attendance_id': attendance.id
    })

@bp.route('/bulk-mark', methods=['POST'])
@login_required
def bulk_mark():
    data = request.get_json()
    course_id = data.get('course_id')
    session_id = data.get('session_id')
    attendances = data.get('attendances', [])
    
    course = Course.query.get_or_404(course_id)
    
    if course.instructor_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    for att_data in attendances:
        user_id = att_data.get('user_id')
        status = att_data.get('status', 'present')
        
        attendance = Attendance.query.filter_by(
            course_id=course_id,
            user_id=user_id,
            session_id=session_id
        ).first()
        
        if attendance:
            attendance.status = status
            attendance.checked_at = datetime.utcnow()
            attendance.checked_by_id = current_user.id
        else:
            attendance = Attendance(
                course_id=course_id,
                user_id=user_id,
                session_id=session_id,
                status=status,
                checked_by_id=current_user.id
            )
            db.session.add(attendance)
    
    db.session.commit()
    
    return jsonify({'success': True, 'count': len(attendances)})

@bp.route('/student/<int:user_id>/course/<int:course_id>')
@login_required
def student_attendance(user_id, course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.instructor_id != current_user.id and current_user.id != user_id:
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    student = User.query.get_or_404(user_id)
    sessions = ActiveSession.query.filter_by(course_id=course_id).order_by(ActiveSession.started_at.desc()).all()
    
    attendance_records = []
    for session in sessions:
        att = Attendance.query.filter_by(
            course_id=course_id,
            user_id=user_id,
            session_id=session.id
        ).first()
        attendance_records.append({
            'session_id': session.id,
            'session_started_at': session.started_at.isoformat() if session.started_at else None,
            'status': att.status if att else 'absent',
            'checked_at': att.checked_at.isoformat() if att and att.checked_at else None
        })
    
    total_sessions = len(sessions)
    present_count = sum(1 for r in attendance_records if r['status'] == 'present')
    late_count = sum(1 for r in attendance_records if r['status'] == 'late')
    absent_count = sum(1 for r in attendance_records if r['status'] == 'absent')
    
    return jsonify({
        'student': {'id': student.id, 'username': student.username, 'email': student.email},
        'total_sessions': total_sessions,
        'present': present_count,
        'late': late_count,
        'absent': absent_count,
        'attendance_rate': round(present_count / total_sessions * 100, 1) if total_sessions > 0 else 0,
        'records': attendance_records
    })
