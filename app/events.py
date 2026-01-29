from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from app.models import Progress, Course, Checkpoint, Enrollment, ActiveSession, ChatMessage, UnderstandingStatus
from datetime import datetime

def user_has_course_access(user, course):
    if not course:
        return False
    if user.is_instructor() and course.instructor_id == user.id:
        return True
    return Enrollment.query.filter_by(user_id=user.id, course_id=course.id).first() is not None

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
    
    if not course_id:
        return
    
    course = Course.query.get(course_id)
    if not course or not user_has_course_access(current_user, course):
        emit('error', {'message': 'Access denied to this course'})
        return
    
    room = f'course_{course_id}'
    join_room(room)
    emit('student_joined', {
        'user_id': current_user.id,
        'username': current_user.username
    }, room=room)
    
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
        emit('error', {'message': 'Authentication required'})
        return
    
    course_id = data.get('course_id')
    if not course_id:
        emit('error', {'message': 'Course ID required'})
        return
    
    course = Course.query.get(course_id)
    if not course or not user_has_course_access(current_user, course):
        emit('error', {'message': 'Access denied to this course'})
        return
    
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
    if not user_has_course_access(current_user, course):
        emit('error', {'message': 'Access denied to this course'})
        return
    
    if current_user.is_instructor():
        emit('error', {'message': 'Instructors cannot mark checkpoints complete'})
        return
    
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
    if not course or not user_has_course_access(current_user, course):
        emit('error', {'message': 'Access denied to this course'})
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

@socketio.on('send_chat_message')
def handle_send_chat_message(data):
    if not current_user.is_authenticated:
        return
    
    course_id = data.get('course_id')
    message_text = data.get('message', '').strip()
    
    if not course_id or not message_text:
        return
    
    course = Course.query.get(course_id)
    if not course or not user_has_course_access(current_user, course):
        emit('error', {'message': 'Access denied to this course'})
        return
    
    chat_msg = ChatMessage(
        course_id=course_id,
        user_id=current_user.id,
        message=message_text
    )
    db.session.add(chat_msg)
    db.session.commit()
    
    room = f'course_{course_id}'
    emit('new_chat_message', {
        'id': chat_msg.id,
        'user_id': current_user.id,
        'username': current_user.username,
        'role': current_user.role,
        'message': message_text,
        'created_at': chat_msg.created_at.strftime('%H:%M')
    }, room=room)

@socketio.on('set_current_checkpoint')
def handle_set_current_checkpoint(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return
    
    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    
    course = Course.query.get(course_id)
    if not course or course.instructor_id != current_user.id:
        emit('error', {'message': 'Access denied'})
        return
    
    session = ActiveSession.query.filter_by(course_id=course_id, ended_at=None).first()
    if session:
        session.current_checkpoint_id = checkpoint_id
        db.session.commit()
    
    room = f'course_{course_id}'
    emit('current_checkpoint_changed', {
        'checkpoint_id': checkpoint_id
    }, room=room)

@socketio.on('submit_understanding')
def handle_submit_understanding(data):
    if not current_user.is_authenticated or current_user.is_instructor():
        return
    
    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    status = data.get('status')
    
    if status not in ['understood', 'confused']:
        return
    
    course = Course.query.get(course_id)
    if not course or not user_has_course_access(current_user, course):
        emit('error', {'message': 'Access denied'})
        return
    
    session = ActiveSession.query.filter_by(course_id=course_id, ended_at=None).first()
    if not session:
        return
    
    existing = UnderstandingStatus.query.filter_by(
        user_id=current_user.id,
        checkpoint_id=checkpoint_id,
        session_id=session.id
    ).first()
    
    if existing:
        existing.status = status
        existing.created_at = datetime.utcnow()
    else:
        understanding = UnderstandingStatus(
            user_id=current_user.id,
            checkpoint_id=checkpoint_id,
            session_id=session.id,
            status=status
        )
        db.session.add(understanding)
    
    db.session.commit()
    
    understood_count = UnderstandingStatus.query.filter_by(
        checkpoint_id=checkpoint_id,
        session_id=session.id,
        status='understood'
    ).count()
    
    confused_count = UnderstandingStatus.query.filter_by(
        checkpoint_id=checkpoint_id,
        session_id=session.id,
        status='confused'
    ).count()
    
    room = f'course_{course_id}'
    emit('understanding_updated', {
        'checkpoint_id': checkpoint_id,
        'understood': understood_count,
        'confused': confused_count
    }, room=room)
