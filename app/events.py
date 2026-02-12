from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio, db
from app.models import Progress, Course, Checkpoint, Enrollment, ActiveSession, ChatMessage, UnderstandingStatus, SlideDeck, SlideReaction, SlideBookmark
from datetime import datetime

screen_share_state = {}

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

@socketio.on('disconnect')
def handle_disconnect():
    if not current_user.is_authenticated:
        return
    deck_ids_to_remove = []
    for deck_id, state in screen_share_state.items():
        if state.get('user_id') == current_user.id:
            deck_ids_to_remove.append(deck_id)
    for deck_id in deck_ids_to_remove:
        screen_share_state.pop(deck_id, None)
        room = f'slide_deck_{deck_id}'
        emit('screen_share_stopped', {'deck_id': deck_id}, room=room)

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

@socketio.on('edit_chat_message')
def handle_edit_chat_message(data):
    if not current_user.is_authenticated:
        return
    
    course_id = data.get('course_id')
    message_id = data.get('message_id')
    new_message = data.get('new_message', '').strip()
    
    if not message_id or not new_message:
        return
    
    chat_msg = ChatMessage.query.get(message_id)
    if not chat_msg:
        return
    
    if chat_msg.course_id != course_id:
        emit('error', {'message': 'Invalid course'})
        return
    
    course = Course.query.get(chat_msg.course_id)
    if not course or not user_has_course_access(current_user, course):
        return
    
    if chat_msg.user_id != current_user.id and not (current_user.is_instructor() and course.instructor_id == current_user.id):
        emit('error', {'message': 'Permission denied'})
        return
    
    chat_msg.message = new_message
    db.session.commit()
    
    room = f'course_{chat_msg.course_id}'
    emit('chat_message_edited', {
        'message_id': message_id,
        'new_message': new_message
    }, room=room)

@socketio.on('delete_chat_message')
def handle_delete_chat_message(data):
    if not current_user.is_authenticated:
        return
    
    course_id = data.get('course_id')
    message_id = data.get('message_id')
    
    if not message_id:
        return
    
    chat_msg = ChatMessage.query.get(message_id)
    if not chat_msg:
        return
    
    if chat_msg.course_id != course_id:
        emit('error', {'message': 'Invalid course'})
        return
    
    course = Course.query.get(chat_msg.course_id)
    if not course or not user_has_course_access(current_user, course):
        return
    
    if chat_msg.user_id != current_user.id and not (current_user.is_instructor() and course.instructor_id == current_user.id):
        emit('error', {'message': 'Permission denied'})
        return
    
    db.session.delete(chat_msg)
    db.session.commit()
    
    room = f'course_{chat_msg.course_id}'
    emit('chat_message_deleted', {
        'message_id': message_id
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

@socketio.on('checkpoint_timer_action')
def handle_checkpoint_timer_action(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return
    
    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    action = data.get('action')
    elapsed_seconds = data.get('elapsed_seconds', 0)
    
    course = Course.query.get(course_id)
    if not course or course.instructor_id != current_user.id:
        return
    
    room = f'course_{course_id}'
    emit('timer_sync', {
        'checkpoint_id': checkpoint_id,
        'elapsed_seconds': elapsed_seconds,
        'action': action,
        'is_running': action in ['start', 'resume']
    }, room=room)

@socketio.on('instructor_checkpoint_complete')
def handle_instructor_checkpoint_complete(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return
    
    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    completed = data.get('completed', False)
    elapsed_seconds = data.get('elapsed_seconds', 0)
    
    course = Course.query.get(course_id)
    if not course or course.instructor_id != current_user.id:
        return
    
    room = f'course_{course_id}'
    emit('instructor_checkpoint_status', {
        'checkpoint_id': checkpoint_id,
        'completed': completed,
        'elapsed_seconds': elapsed_seconds
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


@socketio.on('join_slide_session')
def handle_join_slide_session(data):
    if not current_user.is_authenticated:
        return
    
    deck_id = data.get('deck_id')
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return
    
    course = Course.query.get(deck.course_id)
    if not course or not user_has_course_access(current_user, course):
        return
    
    room = f'slide_deck_{deck_id}'
    join_room(room)
    
    share_active = screen_share_state.get(deck_id, {}).get('active', False)
    
    emit('slide_session_state', {
        'current_slide_index': deck.current_slide_index,
        'slide_count': deck.slide_count,
        'screen_share_active': share_active
    })


@socketio.on('leave_slide_session')
def handle_leave_slide_session(data):
    if not current_user.is_authenticated:
        return
    deck_id = data.get('deck_id')
    room = f'slide_deck_{deck_id}'
    leave_room(room)


@socketio.on('change_slide')
def handle_change_slide(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return
    
    deck_id = data.get('deck_id')
    slide_index = data.get('slide_index')
    
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return
    
    course = Course.query.get(deck.course_id)
    if not course or course.instructor_id != current_user.id:
        return
    
    if slide_index < 0 or slide_index >= deck.slide_count:
        return
    
    deck.current_slide_index = slide_index
    db.session.commit()
    
    room = f'slide_deck_{deck_id}'
    emit('slide_changed', {
        'slide_index': slide_index
    }, room=room)


def get_slide_aggregate(deck_id, slide_index):
    understood = SlideReaction.query.filter_by(deck_id=deck_id, slide_index=slide_index, reaction='understood').count()
    question = SlideReaction.query.filter_by(deck_id=deck_id, slide_index=slide_index, reaction='question').count()
    hard = SlideReaction.query.filter_by(deck_id=deck_id, slide_index=slide_index, reaction='hard').count()
    return {
        'understood': understood,
        'question': question,
        'hard': hard,
        'total_reacted': understood + question + hard
    }


def check_and_update_flag(deck, slide_index, counts):
    problem_count = counts['question'] + counts['hard']
    total = counts['total_reacted']
    
    flagged = False
    reason = ''
    
    if problem_count >= deck.flag_threshold_count:
        flagged = True
        reason = f'어려움+질문 {problem_count}명 (기준: {deck.flag_threshold_count}명)'
    elif total > 0 and (problem_count / total) >= deck.flag_threshold_rate:
        flagged = True
        reason = f'어려움+질문 비율 {int(problem_count/total*100)}% (기준: {int(deck.flag_threshold_rate*100)}%)'
    
    if flagged:
        bookmark = SlideBookmark.query.filter_by(deck_id=deck.id, slide_index=slide_index).first()
        if not bookmark:
            bookmark = SlideBookmark(deck_id=deck.id, slide_index=slide_index, is_auto=True, reason=reason)
            db.session.add(bookmark)
        else:
            bookmark.is_auto = True
            bookmark.reason = reason
        db.session.commit()
    else:
        bookmark = SlideBookmark.query.filter_by(deck_id=deck.id, slide_index=slide_index).first()
        if bookmark and bookmark.is_auto and not bookmark.is_manual:
            db.session.delete(bookmark)
            db.session.commit()
        elif bookmark and bookmark.is_auto:
            bookmark.is_auto = False
            bookmark.reason = None
            db.session.commit()
    
    return flagged, reason


@socketio.on('set_slide_reaction')
def handle_set_slide_reaction(data):
    if not current_user.is_authenticated or current_user.is_instructor():
        return
    
    deck_id = data.get('deck_id')
    slide_index = data.get('slide_index')
    reaction = data.get('reaction', 'none')
    
    if reaction not in ['understood', 'question', 'hard', 'none']:
        return
    
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return
    
    course = Course.query.get(deck.course_id)
    if not course or not user_has_course_access(current_user, course):
        return
    
    existing = SlideReaction.query.filter_by(
        deck_id=deck_id,
        user_id=current_user.id,
        slide_index=slide_index
    ).first()
    
    if reaction == 'none':
        if existing:
            db.session.delete(existing)
            db.session.commit()
    else:
        if existing:
            existing.reaction = reaction
            existing.updated_at = datetime.utcnow()
        else:
            new_reaction = SlideReaction(
                deck_id=deck_id,
                user_id=current_user.id,
                slide_index=slide_index,
                reaction=reaction
            )
            db.session.add(new_reaction)
        db.session.commit()
    
    counts = get_slide_aggregate(deck_id, slide_index)
    flagged, reason = check_and_update_flag(deck, slide_index, counts)
    
    room = f'slide_deck_{deck_id}'
    emit('slide_aggregate_updated', {
        'slide_index': slide_index,
        'counts': counts,
        'flagged': flagged,
        'reason': reason
    }, room=room)


@socketio.on('request_slide_aggregates')
def handle_request_slide_aggregates(data):
    if not current_user.is_authenticated:
        return
    
    deck_id = data.get('deck_id')
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return
    
    all_aggregates = {}
    flagged_slides = []
    
    for i in range(deck.slide_count):
        counts = get_slide_aggregate(deck_id, i)
        all_aggregates[i] = counts
        
        bookmark = SlideBookmark.query.filter_by(deck_id=deck_id, slide_index=i).first()
        if bookmark:
            flagged_slides.append({
                'slide_index': i,
                'is_auto': bookmark.is_auto,
                'is_manual': bookmark.is_manual,
                'reason': bookmark.reason
            })
    
    emit('all_slide_aggregates', {
        'aggregates': all_aggregates,
        'flagged_slides': flagged_slides
    })


@socketio.on('toggle_slide_bookmark')
def handle_toggle_slide_bookmark(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return
    
    deck_id = data.get('deck_id')
    slide_index = data.get('slide_index')
    
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return
    
    course = Course.query.get(deck.course_id)
    if not course or course.instructor_id != current_user.id:
        return
    
    bookmark = SlideBookmark.query.filter_by(deck_id=deck_id, slide_index=slide_index).first()
    is_bookmarked = False
    
    if bookmark:
        if bookmark.is_auto and not bookmark.is_manual:
            bookmark.is_manual = True
            is_bookmarked = True
        elif bookmark.is_manual and not bookmark.is_auto:
            db.session.delete(bookmark)
            is_bookmarked = False
        else:
            bookmark.is_manual = not bookmark.is_manual
            is_bookmarked = bookmark.is_manual or bookmark.is_auto
    else:
        bookmark = SlideBookmark(deck_id=deck_id, slide_index=slide_index, is_manual=True)
        db.session.add(bookmark)
        is_bookmarked = True
    
    db.session.commit()
    
    room = f'slide_deck_{deck_id}'
    emit('bookmark_updated', {
        'slide_index': slide_index,
        'is_bookmarked': is_bookmarked
    }, room=room)


@socketio.on('start_screen_share')
def handle_start_screen_share(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return

    deck_id = data.get('deck_id')
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return

    course = Course.query.get(deck.course_id)
    if not course or course.instructor_id != current_user.id:
        return

    screen_share_state[deck_id] = {'active': True, 'user_id': current_user.id}

    room = f'slide_deck_{deck_id}'
    emit('screen_share_started', {
        'deck_id': deck_id,
        'instructor_name': current_user.nickname or current_user.username
    }, room=room)


@socketio.on('stop_screen_share')
def handle_stop_screen_share(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return

    deck_id = data.get('deck_id')
    deck = SlideDeck.query.get(deck_id)
    if not deck:
        return

    course = Course.query.get(deck.course_id)
    if not course or course.instructor_id != current_user.id:
        return

    screen_share_state.pop(deck_id, None)

    room = f'slide_deck_{deck_id}'
    emit('screen_share_stopped', {
        'deck_id': deck_id
    }, room=room)


@socketio.on('screen_share_frame')
def handle_screen_share_frame(data):
    if not current_user.is_authenticated or not current_user.is_instructor():
        return

    deck_id = data.get('deck_id')
    frame_data = data.get('frame')

    if not deck_id or not frame_data:
        return

    state = screen_share_state.get(deck_id)
    if not state or state.get('user_id') != current_user.id:
        return

    room = f'slide_deck_{deck_id}'
    emit('screen_share_frame', {
        'frame': frame_data
    }, room=room, include_self=False)
