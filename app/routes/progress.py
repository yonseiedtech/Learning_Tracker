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
            started_at=datetime.utcnow()
        )
        db.session.add(progress)
    elif not progress.started_at:
        progress.started_at = datetime.utcnow()
    
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
            completed_at=datetime.utcnow()
        )
        db.session.add(progress)
    else:
        progress.completed_at = datetime.utcnow()
    
    progress.calculate_duration()
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

@bp.route('/course/<int:course_id>')
@login_required
def course_progress(course_id):
    from app.models import Course, Checkpoint
    
    course = Course.query.get_or_404(course_id)
    
    if course.instructor_id != current_user.id and not current_user.is_enrolled(course):
        return jsonify({'error': 'Access denied'}), 403
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).order_by(Checkpoint.order).all()
    students = course.get_enrolled_students()
    
    result = []
    for student in students:
        student_progress = {}
        for cp in checkpoints:
            progress = Progress.query.filter_by(user_id=student.id, checkpoint_id=cp.id).first()
            student_progress[cp.id] = {
                'started': progress.started_at is not None if progress else False,
                'completed': progress.completed_at is not None if progress else False,
                'duration_seconds': progress.duration_seconds if progress else None
            }
        result.append({
            'user_id': student.id,
            'username': student.username,
            'progress': student_progress
        })
    
    return jsonify(result)
