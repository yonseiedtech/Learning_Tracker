from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app import db, socketio
from app.models import Progress, Checkpoint, Enrollment
from datetime import datetime

bp = Blueprint('progress', __name__, url_prefix='/progress')

@bp.route('/<int:checkpoint_id>/start', methods=['POST'])
@login_required
def start(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if not progress:
        progress = Progress(
            user_id=current_user.id,
            checkpoint_id=checkpoint_id,
            mode=mode,
            started_at=datetime.utcnow(),
            accumulated_seconds=0,
            is_paused=False
        )
        db.session.add(progress)
    elif not progress.started_at:
        progress.started_at = datetime.utcnow()
        if progress.completed_at:
            progress.completed_at = None
            progress.accumulated_seconds = 0
            progress.duration_seconds = None
        progress.is_paused = False
    elif progress.is_paused:
        pass
    elif progress.completed_at:
        progress.started_at = datetime.utcnow()
        progress.completed_at = None
        progress.accumulated_seconds = 0
        progress.duration_seconds = None
        progress.is_paused = False
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'checkpoint_id': checkpoint_id,
        'started_at': progress.started_at.isoformat()
    })

@bp.route('/<int:checkpoint_id>/complete', methods=['POST'])
@login_required
def complete(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if not progress:
        progress = Progress(
            user_id=current_user.id,
            checkpoint_id=checkpoint_id,
            mode=mode,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            accumulated_seconds=0,
            duration_seconds=0
        )
        db.session.add(progress)
    else:
        if not progress.is_paused and progress.started_at:
            current_session = (datetime.utcnow() - progress.started_at).total_seconds()
            progress.accumulated_seconds = (progress.accumulated_seconds or 0) + int(current_session)
        
        progress.completed_at = datetime.utcnow()
        progress.duration_seconds = progress.accumulated_seconds if progress.accumulated_seconds else 0
        progress.is_paused = False
        progress.paused_at = None
        progress.started_at = None
    
    db.session.commit()
    
    if mode == 'live':
        socketio.emit('progress_update', {
            'user_id': current_user.id,
            'username': current_user.username,
            'checkpoint_id': checkpoint_id,
            'status': 'completed'
        }, room=f'course_{course.id}')
    
    return jsonify({
        'success': True,
        'checkpoint_id': checkpoint_id,
        'completed_at': progress.completed_at.isoformat(),
        'duration_seconds': progress.duration_seconds
    })

@bp.route('/<int:checkpoint_id>/uncomplete', methods=['POST'])
@login_required
def uncomplete(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if progress and progress.completed_at:
        progress.completed_at = None
        progress.duration_seconds = None
        db.session.commit()
        
        if mode == 'live':
            socketio.emit('progress_update', {
                'user_id': current_user.id,
                'username': current_user.username,
                'checkpoint_id': checkpoint_id,
                'status': 'uncompleted'
            }, room=f'course_{course.id}')
        
        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'uncompleted'
        })
    
    return jsonify({'success': False, 'error': 'Progress not found or not completed'}), 400

@bp.route('/<int:checkpoint_id>/pause', methods=['POST'])
@login_required
def pause(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if progress and progress.started_at and not progress.is_paused and not progress.completed_at:
        current_session = (datetime.utcnow() - progress.started_at).total_seconds()
        progress.accumulated_seconds = (progress.accumulated_seconds or 0) + int(current_session)
        progress.paused_at = datetime.utcnow()
        progress.is_paused = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'paused',
            'elapsed_seconds': progress.accumulated_seconds
        })
    
    return jsonify({'success': False, 'error': 'Cannot pause'}), 400

@bp.route('/<int:checkpoint_id>/resume', methods=['POST'])
@login_required
def resume(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if progress and progress.is_paused and not progress.completed_at:
        progress.started_at = datetime.utcnow()
        progress.paused_at = None
        progress.is_paused = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'resumed',
            'elapsed_seconds': progress.accumulated_seconds or 0
        })
    
    return jsonify({'success': False, 'error': 'Cannot resume'}), 400

@bp.route('/<int:checkpoint_id>/stop', methods=['POST'])
@login_required
def stop(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if progress and progress.started_at and not progress.completed_at:
        if not progress.is_paused:
            current_session = (datetime.utcnow() - progress.started_at).total_seconds()
            progress.accumulated_seconds = (progress.accumulated_seconds or 0) + int(current_session)
        
        progress.duration_seconds = progress.accumulated_seconds
        progress.started_at = None
        progress.paused_at = None
        progress.is_paused = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'stopped',
            'duration_seconds': progress.duration_seconds
        })
    
    return jsonify({'success': False, 'error': 'Cannot stop'}), 400

@bp.route('/student/<int:user_id>')
@login_required
def student_progress(user_id):
    if current_user.id != user_id and not current_user.is_instructor():
        return jsonify({'error': 'Access denied'}), 403
    
    progress_records = Progress.query.filter_by(user_id=user_id).all()
    return jsonify([{
        'checkpoint_id': p.checkpoint_id,
        'mode': p.mode,
        'started_at': p.started_at.isoformat() if p.started_at else None,
        'completed_at': p.completed_at.isoformat() if p.completed_at else None,
        'duration_seconds': p.duration_seconds
    } for p in progress_records])

@bp.route('/<int:checkpoint_id>/reset', methods=['POST'])
@login_required
def reset(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    
    if not current_user.is_enrolled(course) and course.instructor_id != current_user.id:
        return jsonify({'error': 'Not enrolled in this course'}), 403
    
    data = request.get_json() or {}
    mode = data.get('mode', 'self_paced')
    
    progress = Progress.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        mode=mode
    ).first()
    
    if progress:
        progress.started_at = None
        progress.completed_at = None
        progress.paused_at = None
        progress.accumulated_seconds = 0
        progress.duration_seconds = None
        progress.is_paused = False
        db.session.commit()
        
        return jsonify({
            'success': True,
            'checkpoint_id': checkpoint_id,
            'status': 'reset'
        })
    
    return jsonify({'success': True, 'checkpoint_id': checkpoint_id, 'status': 'no_progress'})

@bp.route('/course/<int:course_id>')
@login_required
def course_progress(course_id):
    from app.models import Course, Checkpoint
    
    course = Course.query.get_or_404(course_id)
    
    if course.instructor_id != current_user.id and not current_user.is_enrolled(course):
        return jsonify({'error': 'Access denied'}), 403
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).order_by(Checkpoint.order).all()
    students = course.get_enrolled_students()
    
    data = request.args
    mode = data.get('mode', 'all')
    
    result = []
    for student in students:
        student_progress = {}
        for cp in checkpoints:
            if mode == 'all':
                live_progress = Progress.query.filter_by(user_id=student.id, checkpoint_id=cp.id, mode='live').first()
                self_progress = Progress.query.filter_by(user_id=student.id, checkpoint_id=cp.id, mode='self_paced').first()
                student_progress[cp.id] = {
                    'live': {
                        'started': live_progress.started_at is not None if live_progress else False,
                        'completed': live_progress.completed_at is not None if live_progress else False,
                        'duration_seconds': live_progress.duration_seconds if live_progress else None
                    },
                    'self_paced': {
                        'started': self_progress.started_at is not None if self_progress else False,
                        'completed': self_progress.completed_at is not None if self_progress else False,
                        'duration_seconds': self_progress.duration_seconds if self_progress else None,
                        'is_paused': self_progress.is_paused if self_progress else False,
                        'elapsed_seconds': self_progress.get_elapsed_seconds() if self_progress else 0
                    }
                }
            else:
                progress = Progress.query.filter_by(user_id=student.id, checkpoint_id=cp.id, mode=mode).first()
                student_progress[cp.id] = {
                    'started': progress.started_at is not None if progress else False,
                    'completed': progress.completed_at is not None if progress else False,
                    'duration_seconds': progress.duration_seconds if progress else None
                }
        result.append({
            'user_id': student.id,
            'username': student.username,
            'email': student.email,
            'progress': student_progress
        })
    
    return jsonify(result)
