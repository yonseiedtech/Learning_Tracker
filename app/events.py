from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from app.models import Progress, Course, Checkpoint
from datetime import datetime

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        emit('connected', {'user_id': current_user.id, 'username': current_user.username})

@socketio.on('join_course')
def handle_join_course(data):
    if not current_user.is_authenticated:
        return
    
    course_id = data.get('course_id')
    mode = data.get('mode', 'live')
    
    if course_id:
        room = f'course_{course_id}'
        join_room(room)
        emit('student_joined', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room)
        
        course = Course.query.get(course_id)
        if course:
            checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).all()
            students = course.get_enrolled_students()
            
            stats = {}
            for cp in checkpoints:
                completed = Progress.query.filter(
                    Progress.checkpoint_id == cp.id,
                    Progress.completed_at.isnot(None),
                    Progress.mode == mode
                ).count()
                stats[cp.id] = {
                    'completed': completed,
                    'total': len(students)
                }
            
            emit('session_stats', {'completion_rates': stats})

@socketio.on('leave_course')
def handle_leave_course(data):
    if not current_user.is_authenticated:
        return
    
    course_id = data.get('course_id')
    if course_id:
        room = f'course_{course_id}'
        leave_room(room)
        emit('student_left', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room)

@socketio.on('checkpoint_completed')
def handle_checkpoint_completed(data):
    if not current_user.is_authenticated:
        return
    
    checkpoint_id = data.get('checkpoint_id')
    mode = data.get('mode', 'live')
    
    checkpoint = Checkpoint.query.get(checkpoint_id)
    if not checkpoint:
        return
    
    course = checkpoint.course
    room = f'course_{course.id}'
    
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
    
    emit('progress_update', {
        'user_id': current_user.id,
        'username': current_user.username,
        'checkpoint_id': checkpoint_id,
        'status': 'completed'
    }, room=room)
    
    checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).all()
    students = course.get_enrolled_students()
    
    stats = {}
    for cp in checkpoints:
        completed = Progress.query.filter(
            Progress.checkpoint_id == cp.id,
            Progress.completed_at.isnot(None),
            Progress.mode == mode
        ).count()
        stats[cp.id] = {
            'completed': completed,
            'total': len(students)
        }
    
    emit('session_stats', {'completion_rates': stats}, room=room)

@socketio.on('request_stats')
def handle_request_stats(data):
    if not current_user.is_authenticated:
        return
    
    course_id = data.get('course_id')
    mode = data.get('mode', 'live')
    
    course = Course.query.get(course_id)
    if not course:
        return
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).all()
    students = course.get_enrolled_students()
    
    stats = {}
    for cp in checkpoints:
        completed = Progress.query.filter(
            Progress.checkpoint_id == cp.id,
            Progress.completed_at.isnot(None),
            Progress.mode == mode
        ).count()
        stats[cp.id] = {
            'completed': completed,
            'total': len(students)
        }
    
    emit('session_stats', {'completion_rates': stats})
