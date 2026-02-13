from flask import Blueprint, render_template, jsonify, Response
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
import csv
import io

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/instructor/<course_id>')
@auth_required
def instructor_dashboard(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404
    if course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Access denied'}), 403

    checkpoints = dao.get_checkpoints_by_course(course_id)
    enrollments = dao.get_enrollments_by_course(course_id)
    students = []
    for enrollment in enrollments:
        student = dao.get_user(enrollment['user_id'])
        if student:
            students.append(student)
    total_students = len(students)

    enrolled_user_ids = {s['uid'] for s in students}

    stats = []
    for cp in checkpoints:
        completed_count = 0
        durations = []
        for student in students:
            p = dao.get_progress(student['uid'], cp['id'], None)
            if p and p.get('completed_at'):
                completed_count += 1
            if p and p.get('duration_seconds') is not None:
                durations.append(p['duration_seconds'])

        avg_duration = sum(durations) / len(durations) if durations else 0
        completion_rate = (completed_count / total_students * 100) if total_students > 0 else 0

        stats.append({
            'checkpoint_id': cp['id'],
            'title': cp.get('title', ''),
            'completed_count': completed_count,
            'total_students': total_students,
            'completion_rate': round(completion_rate, 1),
            'avg_duration_seconds': round(avg_duration) if avg_duration else 0,
            'estimated_minutes': cp.get('estimated_minutes') or 0
        })

    student_data = []
    checkpoint_ids = {cp['id'] for cp in checkpoints}
    for student in students:
        completed = 0
        for cp in checkpoints:
            p = dao.get_progress(student['uid'], cp['id'], None)
            if p and p.get('completed_at'):
                completed += 1

        student_data.append({
            'id': student['uid'],
            'username': student.get('username', ''),
            'completed_checkpoints': completed,
            'total_checkpoints': len(checkpoints),
            'progress_percent': round(completed / len(checkpoints) * 100, 1) if checkpoints else 0
        })

    avg_progress = sum(s['progress_percent'] for s in student_data) / len(student_data) if student_data else 0
    lagging_students = [s for s in student_data if s['progress_percent'] < avg_progress * 0.7]

    return render_template('analytics/instructor.html',
                         course=course,
                         stats=stats,
                         students=student_data,
                         lagging_students=lagging_students,
                         avg_progress=round(avg_progress, 1))

@bp.route('/student/<course_id>')
@auth_required
def student_dashboard(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404
    if not dao.is_enrolled(user.uid, course['id']):
        return jsonify({'error': 'Not enrolled'}), 403

    checkpoints = dao.get_checkpoints_by_course(course_id)

    my_progress = []
    total_time = 0
    completed_count = 0

    for cp in checkpoints:
        progress = dao.get_progress(user.uid, cp['id'], None)

        duration = progress.get('duration_seconds', 0) if progress and progress.get('duration_seconds') else 0
        total_time += duration

        if progress and progress.get('completed_at'):
            completed_count += 1

        my_progress.append({
            'checkpoint_id': cp['id'],
            'title': cp.get('title', ''),
            'order': cp.get('order', 0),
            'estimated_minutes': cp.get('estimated_minutes') or 0,
            'started': progress.get('started_at') is not None if progress else False,
            'completed': progress.get('completed_at') is not None if progress else False,
            'started_at': progress['started_at'].isoformat() if progress and progress.get('started_at') else None,
            'completed_at': progress['completed_at'].isoformat() if progress and progress.get('completed_at') else None,
            'duration_seconds': duration,
            'duration_minutes': round(duration / 60, 1) if duration else 0
        })

    sorted_by_duration = sorted([p for p in my_progress if p['duration_seconds'] > 0],
                                key=lambda x: x['duration_seconds'],
                                reverse=True)
    slowest_checkpoints = sorted_by_duration[:3]

    progress_percent = round(completed_count / len(checkpoints) * 100, 1) if checkpoints else 0

    # Compute course average duration across all enrolled students
    enrollments = dao.get_enrollments_by_course(course_id)
    all_durations = []
    for enrollment in enrollments:
        for cp in checkpoints:
            p = dao.get_progress(enrollment['user_id'], cp['id'], None)
            if p and p.get('duration_seconds') is not None:
                all_durations.append(p['duration_seconds'])
    course_avg = sum(all_durations) / len(all_durations) if all_durations else 0

    return render_template('analytics/student.html',
                         course=course,
                         progress=my_progress,
                         progress_percent=progress_percent,
                         completed_count=completed_count,
                         total_checkpoints=len(checkpoints),
                         total_time_minutes=round(total_time / 60, 1),
                         slowest_checkpoints=slowest_checkpoints,
                         course_avg_seconds=round(course_avg))

@bp.route('/export/<course_id>')
@auth_required
def export_csv(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404
    if course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Access denied'}), 403

    checkpoints = dao.get_checkpoints_by_course(course_id)
    enrollments = dao.get_enrollments_by_course(course_id)
    students = []
    for enrollment in enrollments:
        student = dao.get_user(enrollment['user_id'])
        if student:
            students.append(student)

    output = io.StringIO()
    writer = csv.writer(output)

    header = ['Student', 'Email']
    for cp in checkpoints:
        title = cp.get('title', '')
        header.extend([f'{title} - Started', f'{title} - Completed', f'{title} - Duration (min)'])
    writer.writerow(header)

    for student in students:
        row = [student.get('username', ''), student.get('email', '')]
        for cp in checkpoints:
            progress = dao.get_progress(student['uid'], cp['id'], None)
            if progress:
                started_at = progress.get('started_at')
                completed_at = progress.get('completed_at')
                duration = progress.get('duration_seconds')
                row.append(started_at.strftime('%Y-%m-%d %H:%M') if started_at else '')
                row.append(completed_at.strftime('%Y-%m-%d %H:%M') if completed_at else '')
                row.append(round(duration / 60, 1) if duration else '')
            else:
                row.extend(['', '', ''])
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=course_{course_id}_progress.csv'}
    )

@bp.route('/api/instructor/<course_id>')
@auth_required
def instructor_api(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404
    if course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Access denied'}), 403

    checkpoints = dao.get_checkpoints_by_course(course_id)
    enrollments = dao.get_enrollments_by_course(course_id)
    students = []
    for enrollment in enrollments:
        student = dao.get_user(enrollment['user_id'])
        if student:
            students.append(student)
    total_students = len(students)

    checkpoint_stats = []
    for cp in checkpoints:
        completed_count = 0
        for student in students:
            p = dao.get_progress(student['uid'], cp['id'], None)
            if p and p.get('completed_at'):
                completed_count += 1

        checkpoint_stats.append({
            'id': cp['id'],
            'title': cp.get('title', ''),
            'completed': completed_count,
            'total': total_students,
            'rate': round(completed_count / total_students * 100, 1) if total_students > 0 else 0
        })

    student_progress = []
    for student in students:
        progress_list = []
        for cp in checkpoints:
            p = dao.get_progress(student['uid'], cp['id'], None)
            progress_list.append({
                'checkpoint_id': cp['id'],
                'completed': p.get('completed_at') is not None if p else False
            })
        student_progress.append({
            'id': student['uid'],
            'username': student.get('username', ''),
            'checkpoints': progress_list
        })

    return jsonify({
        'checkpoint_stats': checkpoint_stats,
        'student_progress': student_progress
    })
