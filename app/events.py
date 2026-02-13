from flask import request
from flask_socketio import emit, join_room, leave_room
from app import socketio
from app.decorators import get_current_user
from app import firestore_dao as dao
from datetime import datetime, timezone

screen_share_state = {}


def _get_socket_user():
    """Get current user from the Flask session context in Socket.IO events."""
    user = get_current_user()
    if user and user.is_authenticated:
        return user
    return None


def _user_has_course_access(user, course):
    if not course:
        return False
    if user.role == 'instructor' and course.get('instructor_id') == user.uid:
        return True
    return dao.is_enrolled(user.uid, course['id'])


@socketio.on('connect')
def handle_connect():
    user = _get_socket_user()
    if user:
        emit('connected', {'user_id': user.uid, 'username': user.full_name})


@socketio.on('disconnect')
def handle_disconnect():
    user = _get_socket_user()
    if not user:
        return
    deck_ids_to_remove = []
    for deck_id, state in screen_share_state.items():
        if state.get('user_id') == user.uid:
            deck_ids_to_remove.append(deck_id)
    for deck_id in deck_ids_to_remove:
        screen_share_state.pop(deck_id, None)
        room = f'slide_deck_{deck_id}'
        emit('screen_share_stopped', {'deck_id': deck_id}, room=room)


@socketio.on('join_course')
def handle_join_course(data):
    user = _get_socket_user()
    if not user:
        return

    course_id = data.get('course_id')
    mode = data.get('mode', 'live')

    if not course_id:
        return

    course = dao.get_course(course_id)
    if not course or not _user_has_course_access(user, course):
        emit('error', {'message': 'Access denied to this course'})
        return

    room = f'course_{course_id}'
    join_room(room)
    emit('student_joined', {
        'user_id': user.uid,
        'username': user.full_name
    }, room=room)

    checkpoints = dao.get_checkpoints_by_course(course_id)
    enrollments = dao.get_enrollments_by_course(course_id)
    total_students = len(enrollments)

    checkpoint_ids = [cp['id'] for cp in checkpoints]
    completed_counts = dao.count_completed_progress(checkpoint_ids, mode=mode)

    stats = {}
    for cp in checkpoints:
        stats[cp['id']] = {
            'completed': completed_counts.get(cp['id'], 0),
            'total': total_students
        }

    emit('session_stats', {'completion_rates': stats})


@socketio.on('leave_course')
def handle_leave_course(data):
    user = _get_socket_user()
    if not user:
        emit('error', {'message': 'Authentication required'})
        return

    course_id = data.get('course_id')
    if not course_id:
        emit('error', {'message': 'Course ID required'})
        return

    course = dao.get_course(course_id)
    if not course or not _user_has_course_access(user, course):
        emit('error', {'message': 'Access denied to this course'})
        return

    room = f'course_{course_id}'
    leave_room(room)
    emit('student_left', {
        'user_id': user.uid,
        'username': user.full_name
    }, room=room)


@socketio.on('checkpoint_completed')
def handle_checkpoint_completed(data):
    user = _get_socket_user()
    if not user:
        return

    checkpoint_id = data.get('checkpoint_id')
    mode = data.get('mode', 'live')

    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        return

    course = dao.get_course(checkpoint['course_id'])
    if not course or not _user_has_course_access(user, course):
        emit('error', {'message': 'Access denied to this course'})
        return

    if user.role == 'instructor':
        emit('error', {'message': 'Instructors cannot mark checkpoints complete'})
        return

    room = f'course_{course["id"]}'
    now = datetime.now(timezone.utc)

    progress = dao.get_progress(user.uid, checkpoint_id, mode)

    if not progress:
        dao.create_progress({
            'user_id': user.uid,
            'checkpoint_id': checkpoint_id,
            'course_id': checkpoint['course_id'],
            'mode': mode,
            'started_at': now,
            'completed_at': now,
            'duration_seconds': 0
        })
    else:
        update_data = {'completed_at': now}
        if progress.get('started_at'):
            delta = (now - progress['started_at']).total_seconds()
            paused = progress.get('paused_duration', 0) or 0
            update_data['duration_seconds'] = int(delta - paused)
        dao.update_progress(progress['id'], update_data)

    emit('progress_update', {
        'user_id': user.uid,
        'username': user.full_name,
        'checkpoint_id': checkpoint_id,
        'status': 'completed'
    }, room=room)

    checkpoints = dao.get_checkpoints_by_course(course['id'])
    enrollments = dao.get_enrollments_by_course(course['id'])
    total_students = len(enrollments)

    checkpoint_ids = [cp['id'] for cp in checkpoints]
    completed_counts = dao.count_completed_progress(checkpoint_ids, mode=mode)

    stats = {}
    for cp in checkpoints:
        stats[cp['id']] = {
            'completed': completed_counts.get(cp['id'], 0),
            'total': total_students
        }

    emit('session_stats', {'completion_rates': stats}, room=room)


@socketio.on('request_stats')
def handle_request_stats(data):
    user = _get_socket_user()
    if not user:
        return

    course_id = data.get('course_id')
    mode = data.get('mode', 'live')

    course = dao.get_course(course_id)
    if not course or not _user_has_course_access(user, course):
        emit('error', {'message': 'Access denied to this course'})
        return

    checkpoints = dao.get_checkpoints_by_course(course_id)
    enrollments = dao.get_enrollments_by_course(course_id)
    total_students = len(enrollments)

    checkpoint_ids = [cp['id'] for cp in checkpoints]
    completed_counts = dao.count_completed_progress(checkpoint_ids, mode=mode)

    stats = {}
    for cp in checkpoints:
        stats[cp['id']] = {
            'completed': completed_counts.get(cp['id'], 0),
            'total': total_students
        }

    emit('session_stats', {'completion_rates': stats})


@socketio.on('send_chat_message')
def handle_send_chat_message(data):
    user = _get_socket_user()
    if not user:
        return

    course_id = data.get('course_id')
    message_text = data.get('message', '').strip()

    if not course_id or not message_text:
        return

    course = dao.get_course(course_id)
    if not course or not _user_has_course_access(user, course):
        emit('error', {'message': 'Access denied to this course'})
        return

    now = datetime.now(timezone.utc)
    msg_id = dao.create_chat_message({
        'course_id': course_id,
        'user_id': user.uid,
        'user_name': user.full_name,
        'message': message_text,
        'created_at': now
    })

    room = f'course_{course_id}'
    emit('new_chat_message', {
        'id': msg_id,
        'user_id': user.uid,
        'username': user.full_name,
        'role': user.role,
        'message': message_text,
        'created_at': now.strftime('%H:%M')
    }, room=room)


@socketio.on('edit_chat_message')
def handle_edit_chat_message(data):
    user = _get_socket_user()
    if not user:
        return

    course_id = data.get('course_id')
    message_id = data.get('message_id')
    new_message = data.get('new_message', '').strip()

    if not message_id or not new_message:
        return

    chat_msg = dao.get_chat_message(message_id)
    if not chat_msg:
        return

    if chat_msg.get('course_id') != course_id:
        emit('error', {'message': 'Invalid course'})
        return

    course = dao.get_course(chat_msg['course_id'])
    if not course or not _user_has_course_access(user, course):
        return

    if chat_msg['user_id'] != user.uid and not (user.role == 'instructor' and course.get('instructor_id') == user.uid):
        emit('error', {'message': 'Permission denied'})
        return

    dao.update_chat_message(message_id, {'message': new_message})

    room = f'course_{chat_msg["course_id"]}'
    emit('chat_message_edited', {
        'message_id': message_id,
        'new_message': new_message
    }, room=room)


@socketio.on('delete_chat_message')
def handle_delete_chat_message(data):
    user = _get_socket_user()
    if not user:
        return

    course_id = data.get('course_id')
    message_id = data.get('message_id')

    if not message_id:
        return

    chat_msg = dao.get_chat_message(message_id)
    if not chat_msg:
        return

    if chat_msg.get('course_id') != course_id:
        emit('error', {'message': 'Invalid course'})
        return

    course = dao.get_course(chat_msg['course_id'])
    if not course or not _user_has_course_access(user, course):
        return

    if chat_msg['user_id'] != user.uid and not (user.role == 'instructor' and course.get('instructor_id') == user.uid):
        emit('error', {'message': 'Permission denied'})
        return

    dao.delete_chat_message(message_id)

    room = f'course_{chat_msg["course_id"]}'
    emit('chat_message_deleted', {
        'message_id': message_id
    }, room=room)


@socketio.on('set_current_checkpoint')
def handle_set_current_checkpoint(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')

    course = dao.get_course(course_id)
    if not course or course.get('instructor_id') != user.uid:
        emit('error', {'message': 'Access denied'})
        return

    session = dao.get_active_session_for_course(course_id)
    if session:
        dao.update_active_session(session['id'], {'current_checkpoint_id': checkpoint_id})

    room = f'course_{course_id}'
    emit('current_checkpoint_changed', {
        'checkpoint_id': checkpoint_id
    }, room=room)


@socketio.on('checkpoint_timer_action')
def handle_checkpoint_timer_action(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    action = data.get('action')
    elapsed_seconds = data.get('elapsed_seconds', 0)

    course = dao.get_course(course_id)
    if not course or course.get('instructor_id') != user.uid:
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
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    completed = data.get('completed', False)
    elapsed_seconds = data.get('elapsed_seconds', 0)

    course = dao.get_course(course_id)
    if not course or course.get('instructor_id') != user.uid:
        return

    room = f'course_{course_id}'
    emit('instructor_checkpoint_status', {
        'checkpoint_id': checkpoint_id,
        'completed': completed,
        'elapsed_seconds': elapsed_seconds
    }, room=room)


@socketio.on('submit_understanding')
def handle_submit_understanding(data):
    user = _get_socket_user()
    if not user or user.role == 'instructor':
        return

    course_id = data.get('course_id')
    checkpoint_id = data.get('checkpoint_id')
    status = data.get('status')

    if status not in ['understood', 'confused']:
        return

    course = dao.get_course(course_id)
    if not course or not _user_has_course_access(user, course):
        emit('error', {'message': 'Access denied'})
        return

    session = dao.get_active_session_for_course(course_id)
    if not session:
        return

    dao.set_understanding({
        'user_id': user.uid,
        'checkpoint_id': checkpoint_id,
        'session_id': session['id'],
        'status': status,
        'created_at': datetime.now(timezone.utc)
    })

    counts = dao.count_understanding(checkpoint_id, session['id'])

    room = f'course_{course_id}'
    emit('understanding_updated', {
        'checkpoint_id': checkpoint_id,
        'understood': counts.get('understood', 0),
        'confused': counts.get('confused', 0)
    }, room=room)


@socketio.on('join_slide_session')
def handle_join_slide_session(data):
    user = _get_socket_user()
    if not user:
        return

    deck_id = data.get('deck_id')
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    course = dao.get_course(deck['course_id'])
    if not course or not _user_has_course_access(user, course):
        return

    room = f'slide_deck_{deck_id}'
    join_room(room)

    share_active = screen_share_state.get(deck_id, {}).get('active', False)

    emit('slide_session_state', {
        'current_slide_index': deck.get('current_slide_index', 0),
        'slide_count': deck.get('slide_count', 0),
        'screen_share_active': share_active
    })


@socketio.on('leave_slide_session')
def handle_leave_slide_session(data):
    user = _get_socket_user()
    if not user:
        return
    deck_id = data.get('deck_id')
    room = f'slide_deck_{deck_id}'
    leave_room(room)


@socketio.on('change_slide')
def handle_change_slide(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    deck_id = data.get('deck_id')
    slide_index = data.get('slide_index')

    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    course = dao.get_course(deck['course_id'])
    if not course or course.get('instructor_id') != user.uid:
        return

    if slide_index < 0 or slide_index >= deck.get('slide_count', 0):
        return

    dao.update_slide_deck(deck_id, {'current_slide_index': slide_index})

    room = f'slide_deck_{deck_id}'
    emit('slide_changed', {
        'slide_index': slide_index
    }, room=room)


def get_slide_aggregate(deck_id, slide_index):
    counts = dao.count_reactions(deck_id, slide_index)
    understood = counts.get('understood', 0)
    question = counts.get('question', 0)
    hard = counts.get('hard', 0)
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

    threshold_count = deck.get('flag_threshold_count', 3)
    threshold_rate = deck.get('flag_threshold_rate', 0.5)

    if problem_count >= threshold_count:
        flagged = True
        reason = f'어려움+질문 {problem_count}명 (기준: {threshold_count}명)'
    elif total > 0 and (problem_count / total) >= threshold_rate:
        flagged = True
        reason = f'어려움+질문 비율 {int(problem_count/total*100)}% (기준: {int(threshold_rate*100)}%)'

    if flagged:
        bookmark = dao.get_slide_bookmark(deck['id'], slide_index)
        if not bookmark:
            dao.create_or_update_bookmark(deck['id'], slide_index, {
                'is_auto': True,
                'is_manual': False,
                'reason': reason
            })
        else:
            dao.create_or_update_bookmark(deck['id'], slide_index, {
                'is_auto': True,
                'reason': reason
            })
    else:
        bookmark = dao.get_slide_bookmark(deck['id'], slide_index)
        if bookmark and bookmark.get('is_auto') and not bookmark.get('is_manual'):
            dao.delete_bookmark(deck['id'], slide_index)
        elif bookmark and bookmark.get('is_auto'):
            dao.create_or_update_bookmark(deck['id'], slide_index, {
                'is_auto': False,
                'reason': None
            })

    return flagged, reason


@socketio.on('set_slide_reaction')
def handle_set_slide_reaction(data):
    user = _get_socket_user()
    if not user or user.role == 'instructor':
        return

    deck_id = data.get('deck_id')
    slide_index = data.get('slide_index')
    reaction = data.get('reaction', 'none')

    if reaction not in ['understood', 'question', 'hard', 'none']:
        return

    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    course = dao.get_course(deck['course_id'])
    if not course or not _user_has_course_access(user, course):
        return

    if reaction == 'none':
        dao.delete_slide_reaction(deck_id, user.uid, slide_index)
    else:
        dao.set_slide_reaction(deck_id, user.uid, slide_index, reaction)

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
    user = _get_socket_user()
    if not user:
        return

    deck_id = data.get('deck_id')
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    all_aggregates = {}
    flagged_slides = []

    for i in range(deck.get('slide_count', 0)):
        counts = get_slide_aggregate(deck_id, i)
        all_aggregates[i] = counts

        bookmark = dao.get_slide_bookmark(deck_id, i)
        if bookmark:
            flagged_slides.append({
                'slide_index': i,
                'is_auto': bookmark.get('is_auto', False),
                'is_manual': bookmark.get('is_manual', False),
                'reason': bookmark.get('reason')
            })

    emit('all_slide_aggregates', {
        'aggregates': all_aggregates,
        'flagged_slides': flagged_slides
    })


@socketio.on('toggle_slide_bookmark')
def handle_toggle_slide_bookmark(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    deck_id = data.get('deck_id')
    slide_index = data.get('slide_index')

    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    course = dao.get_course(deck['course_id'])
    if not course or course.get('instructor_id') != user.uid:
        return

    bookmark = dao.get_slide_bookmark(deck_id, slide_index)
    is_bookmarked = False

    if bookmark:
        if bookmark.get('is_auto') and not bookmark.get('is_manual'):
            dao.create_or_update_bookmark(deck_id, slide_index, {'is_manual': True})
            is_bookmarked = True
        elif bookmark.get('is_manual') and not bookmark.get('is_auto'):
            dao.delete_bookmark(deck_id, slide_index)
            is_bookmarked = False
        else:
            new_manual = not bookmark.get('is_manual', False)
            dao.create_or_update_bookmark(deck_id, slide_index, {'is_manual': new_manual})
            is_bookmarked = new_manual or bookmark.get('is_auto', False)
    else:
        dao.create_or_update_bookmark(deck_id, slide_index, {'is_manual': True, 'is_auto': False})
        is_bookmarked = True

    room = f'slide_deck_{deck_id}'
    emit('bookmark_updated', {
        'slide_index': slide_index,
        'is_bookmarked': is_bookmarked
    }, room=room)


@socketio.on('start_screen_share')
def handle_start_screen_share(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    deck_id = data.get('deck_id')
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    course = dao.get_course(deck['course_id'])
    if not course or course.get('instructor_id') != user.uid:
        return

    screen_share_state[deck_id] = {'active': True, 'user_id': user.uid}

    room = f'slide_deck_{deck_id}'
    emit('screen_share_started', {
        'deck_id': deck_id,
        'instructor_name': user.nickname or user.full_name
    }, room=room)


@socketio.on('stop_screen_share')
def handle_stop_screen_share(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    deck_id = data.get('deck_id')
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        return

    course = dao.get_course(deck['course_id'])
    if not course or course.get('instructor_id') != user.uid:
        return

    screen_share_state.pop(deck_id, None)

    room = f'slide_deck_{deck_id}'
    emit('screen_share_stopped', {
        'deck_id': deck_id
    }, room=room)


@socketio.on('screen_share_frame')
def handle_screen_share_frame(data):
    user = _get_socket_user()
    if not user or user.role != 'instructor':
        return

    deck_id = data.get('deck_id')
    frame_data = data.get('frame')

    if not deck_id or not frame_data:
        return

    state = screen_share_state.get(deck_id)
    if not state or state.get('user_id') != user.uid:
        return

    room = f'slide_deck_{deck_id}'
    emit('screen_share_frame', {
        'frame': frame_data
    }, room=room, include_self=False)
