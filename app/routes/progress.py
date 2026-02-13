from flask import Blueprint, jsonify, request
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app import socketio
from datetime import datetime

bp = Blueprint('progress', __name__, url_prefix='/progress')

@bp.route('/<checkpoint_id>/start', methods=['POST'])
@auth_required
def start(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if not progress:
        doc_id = dao.create_progress({
            'user_id': user.uid,
            'checkpoint_id': checkpoint_id,
            'mode': mode,
            'started_at': datetime.utcnow(),
            'accumulated_seconds': 0,
            'is_paused': False,
            'completed_at': None,
            'paused_at': None,
            'duration_seconds': None
        })
        started_at = datetime.utcnow()
    elif not progress.get('started_at'):
        update_data = {
            'started_at': datetime.utcnow(),
            'is_paused': False
        }
        if progress.get('completed_at'):
            update_data['completed_at'] = None
            update_data['accumulated_seconds'] = 0
            update_data['duration_seconds'] = None
        dao.update_progress(progress['id'], update_data)
        started_at = datetime.utcnow()
    elif progress.get('is_paused'):
        started_at = progress['started_at']
    elif progress.get('completed_at'):
        dao.update_progress(progress['id'], {
            'started_at': datetime.utcnow(),
            'completed_at': None,
            'accumulated_seconds': 0,
            'duration_seconds': None,
            'is_paused': False
        })
        started_at = datetime.utcnow()
    else:
        started_at = progress['started_at']

    return jsonify({
        'success': True,
        'checkpoint_id': checkpoint_id,
        'started_at': started_at.isoformat() if hasattr(started_at, 'isoformat') else str(started_at)
    })

@bp.route('/<checkpoint_id>/complete', methods=['POST'])
@auth_required
def complete(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)
    now = datetime.utcnow()

    if not progress:
        doc_id = dao.create_progress({
            'user_id': user.uid,
            'checkpoint_id': checkpoint_id,
            'mode': mode,
            'started_at': now,
            'completed_at': now,
            'accumulated_seconds': 0,
            'duration_seconds': 0,
            'is_paused': False,
            'paused_at': None
        })
        completed_at = now
        duration_seconds = 0
    else:
        accumulated = progress.get('accumulated_seconds') or 0
        if not progress.get('is_paused') and progress.get('started_at'):
            current_session = (now - progress['started_at']).total_seconds()
            accumulated = accumulated + int(current_session)

        dao.update_progress(progress['id'], {
            'completed_at': now,
            'duration_seconds': accumulated if accumulated else 0,
            'accumulated_seconds': accumulated,
            'is_paused': False,
            'paused_at': None,
            'started_at': None
        })
        completed_at = now
        duration_seconds = accumulated if accumulated else 0

    if mode == 'live':
        socketio.emit('progress_update', {
            'user_id': user.uid,
            'username': user.display_name if hasattr(user, 'display_name') else '',
            'checkpoint_id': checkpoint_id,
            'status': 'completed'
        }, room=f'course_{course["id"]}')

    return jsonify({
        'success': True,
        'checkpoint_id': checkpoint_id,
        'completed_at': completed_at.isoformat(),
        'duration_seconds': duration_seconds
    })

@bp.route('/<checkpoint_id>/uncomplete', methods=['POST'])
@auth_required
def uncomplete(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if progress and progress.get('completed_at'):
        dao.update_progress(progress['id'], {
            'completed_at': None,
            'duration_seconds': None
        })

        if mode == 'live':
            socketio.emit('progress_update', {
                'user_id': user.uid,
                'username': user.display_name if hasattr(user, 'display_name') else '',
                'checkpoint_id': checkpoint_id,
                'status': 'uncompleted'
            }, room=f'course_{course["id"]}')

        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'uncompleted'
        })

    return jsonify({'success': False, 'error': 'Progress not found or not completed'}), 400

@bp.route('/<checkpoint_id>/pause', methods=['POST'])
@auth_required
def pause(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if progress and progress.get('started_at') and not progress.get('is_paused') and not progress.get('completed_at'):
        current_session = (datetime.utcnow() - progress['started_at']).total_seconds()
        accumulated = (progress.get('accumulated_seconds') or 0) + int(current_session)
        dao.update_progress(progress['id'], {
            'accumulated_seconds': accumulated,
            'paused_at': datetime.utcnow(),
            'is_paused': True
        })

        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'paused',
            'elapsed_seconds': accumulated
        })

    return jsonify({'success': False, 'error': 'Cannot pause'}), 400

@bp.route('/<checkpoint_id>/resume', methods=['POST'])
@auth_required
def resume(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if progress and progress.get('is_paused') and not progress.get('completed_at'):
        dao.update_progress(progress['id'], {
            'started_at': datetime.utcnow(),
            'paused_at': None,
            'is_paused': False
        })

        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'resumed',
            'elapsed_seconds': progress.get('accumulated_seconds') or 0
        })

    return jsonify({'success': False, 'error': 'Cannot resume'}), 400

@bp.route('/<checkpoint_id>/stop', methods=['POST'])
@auth_required
def stop(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if progress and progress.get('started_at') and not progress.get('completed_at'):
        accumulated = progress.get('accumulated_seconds') or 0
        if not progress.get('is_paused'):
            current_session = (datetime.utcnow() - progress['started_at']).total_seconds()
            accumulated = accumulated + int(current_session)

        dao.update_progress(progress['id'], {
            'accumulated_seconds': accumulated,
            'duration_seconds': accumulated,
            'started_at': None,
            'paused_at': None,
            'is_paused': False
        })

        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'stopped',
            'duration_seconds': accumulated
        })

    return jsonify({'success': False, 'error': 'Cannot stop'}), 400

@bp.route('/student/<user_id>')
@auth_required
def student_progress(user_id):
    user = get_current_user()
    if user.uid != user_id and not user.custom_claims.get('instructor', False):
        return jsonify({'error': 'Access denied'}), 403

    progress_records = dao.get_progress_by_user(user_id)
    return jsonify([{
        'checkpoint_id': p['checkpoint_id'],
        'mode': p.get('mode'),
        'started_at': p['started_at'].isoformat() if p.get('started_at') else None,
        'completed_at': p['completed_at'].isoformat() if p.get('completed_at') else None,
        'duration_seconds': p.get('duration_seconds')
    } for p in progress_records])

@bp.route('/<checkpoint_id>/reset', methods=['POST'])
@auth_required
def reset(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return jsonify({'error': 'Checkpoint not found'}), 404
    course = dao.get_course(checkpoint['course_id'])

    if not dao.is_enrolled(user.uid, course['id']) and course.get('instructor_id') != user.uid:
        return jsonify({'error': 'Not enrolled in this course'}), 403

    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if progress:
        dao.update_progress(progress['id'], {
            'started_at': None,
            'completed_at': None,
            'paused_at': None,
            'accumulated_seconds': 0,
            'duration_seconds': None,
            'is_paused': False
        })

        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'reset'
        })

    return jsonify({'success': True, 'checkpoint_id': checkpoint_id, 'status': 'no_progress'})

@bp.route('/course/<course_id>')
@auth_required
def course_progress(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('instructor_id') != user.uid and not dao.is_enrolled(user.uid, course['id']):
        return jsonify({'error': 'Access denied'}), 403

    checkpoints = dao.get_checkpoints_by_course(course_id)
    enrollments = dao.get_enrollments_by_course(course_id)
    students = []
    for enrollment in enrollments:
        student = dao.get_user(enrollment['user_id'])
        if student:
            students.append(student)

    query_data = request.args
    mode = query_data.get('mode', 'all')

    result = []
    for student in students:
        student_prog = {}
        for cp in checkpoints:
            if mode == 'all':
                live_progress = dao.get_progress(student['uid'], cp['id'], 'live')
                self_progress = dao.get_progress(student['uid'], cp['id'], 'self_paced')
                student_prog[cp['id']] = {
                    'live': {
                        'started': live_progress.get('started_at') is not None if live_progress else False,
                        'completed': live_progress.get('completed_at') is not None if live_progress else False,
                        'duration_seconds': live_progress.get('duration_seconds') if live_progress else None
                    },
                    'self_paced': {
                        'started': self_progress.get('started_at') is not None if self_progress else False,
                        'completed': self_progress.get('completed_at') is not None if self_progress else False,
                        'duration_seconds': self_progress.get('duration_seconds') if self_progress else None,
                        'is_paused': self_progress.get('is_paused') if self_progress else False,
                        'elapsed_seconds': self_progress.get('accumulated_seconds', 0) if self_progress else 0
                    }
                }
            else:
                p = dao.get_progress(student['uid'], cp['id'], mode)
                student_prog[cp['id']] = {
                    'started': p.get('started_at') is not None if p else False,
                    'completed': p.get('completed_at') is not None if p else False,
                    'duration_seconds': p.get('duration_seconds') if p else None
                }
        result.append({
            'user_id': student['uid'],
            'username': student.get('username', ''),
            'email': student.get('email', ''),
            'progress': student_prog
        })

    return jsonify(result)
