"""
Firestore Data Access Object (DAO) layer.

Replaces all SQLAlchemy queries with Firestore operations.
Route files should call functions from this module instead of
querying the database directly.
"""

import string
import random
from datetime import datetime, timezone

from google.cloud.firestore_v1 import FieldFilter
from google.cloud.firestore_v1.base_query import FieldFilter as _FF

from app.firebase_init import get_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doc_to_dict(doc_snapshot):
    """Convert a Firestore DocumentSnapshot to a dict with 'id' field."""
    if not doc_snapshot.exists:
        return None
    d = doc_snapshot.to_dict()
    d['id'] = doc_snapshot.id
    return d


def _query_to_list(query_ref):
    """Run a query and return a list of dicts."""
    return [_doc_to_dict(doc) for doc in query_ref.stream()]


def _now():
    return datetime.now(timezone.utc)


# ========================================================================
# Users  (collection: users)
# ========================================================================

def get_user(uid):
    """Get a user document by UID. Returns dict or None."""
    doc = get_db().collection('users').document(uid).get()
    return _doc_to_dict(doc)


def get_user_by_email(email):
    """Get a user by email address. Returns dict or None."""
    docs = (
        get_db().collection('users')
        .where(filter=FieldFilter('email', '==', email))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def get_user_by_username(username):
    """Get a user by username. Returns dict or None."""
    docs = (
        get_db().collection('users')
        .where(filter=FieldFilter('username', '==', username))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_user(uid, data):
    """Create a user document with the given UID as the document ID."""
    data.setdefault('created_at', _now())
    get_db().collection('users').document(uid).set(data)


def update_user(uid, data):
    """Update fields on an existing user document."""
    data.setdefault('updated_at', _now())
    get_db().collection('users').document(uid).update(data)


def get_users_by_ids(uids):
    """Fetch multiple users by their UIDs. Returns list of dicts."""
    if not uids:
        return []
    results = []
    # Firestore 'in' filter supports max 30 items per query
    for i in range(0, len(uids), 30):
        batch = uids[i:i + 30]
        docs = (
            get_db().collection('users')
            .where(filter=FieldFilter('__name__', 'in',
                    [get_db().collection('users').document(uid) for uid in batch]))
            .stream()
        )
        for doc in docs:
            results.append(_doc_to_dict(doc))
    # Fallback: if the __name__ approach is unavailable, fetch individually
    if not results and uids:
        for uid in uids:
            d = get_user(uid)
            if d:
                results.append(d)
    return results


# ========================================================================
# Organizations  (collection: organizations)
# ========================================================================

def get_organization(org_id):
    """Get an organization by ID. Returns dict or None."""
    doc = get_db().collection('organizations').document(org_id).get()
    return _doc_to_dict(doc)


def create_organization(data):
    """Create a new organization. Returns the generated doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('organizations').add(data)
    return doc_ref.id


# ========================================================================
# Subjects  (collection: subjects)
# ========================================================================

def get_subject(subject_id):
    """Get a subject by ID. Returns dict or None."""
    doc = get_db().collection('subjects').document(subject_id).get()
    return _doc_to_dict(doc)


def get_subject_by_invite_code(code):
    """Look up a subject by its invite code. Returns dict or None."""
    docs = (
        get_db().collection('subjects')
        .where(filter=FieldFilter('invite_code', '==', code))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_subject(data):
    """Create a new subject. Returns the generated doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('subjects').add(data)
    return doc_ref.id


def update_subject(subject_id, data):
    """Update fields on an existing subject."""
    data.setdefault('updated_at', _now())
    get_db().collection('subjects').document(subject_id).update(data)


def get_subjects_by_instructor(instructor_id):
    """Get all subjects created by a given instructor."""
    return _query_to_list(
        get_db().collection('subjects')
        .where(filter=FieldFilter('instructor_id', '==', instructor_id))
        .order_by('created_at')
    )


def get_visible_subjects():
    """Get all subjects that are visible (visibility == True or 'public')."""
    return _query_to_list(
        get_db().collection('subjects')
        .where(filter=FieldFilter('visibility', '==', True))
        .order_by('created_at')
    )


def generate_invite_code(collection='subjects'):
    """Generate a unique 8-character alphanumeric invite code for the given collection."""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=8))
        existing = (
            get_db().collection(collection)
            .where(filter=FieldFilter('invite_code', '==', code))
            .limit(1)
            .stream()
        )
        if not any(True for _ in existing):
            return code


# ========================================================================
# Courses / Sessions  (collection: courses)
# ========================================================================

def get_course(course_id):
    """Get a course by ID. Returns dict or None."""
    doc = get_db().collection('courses').document(course_id).get()
    return _doc_to_dict(doc)


def get_course_by_invite_code(code):
    """Look up a course by its invite code. Returns dict or None."""
    docs = (
        get_db().collection('courses')
        .where(filter=FieldFilter('invite_code', '==', code))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_course(data):
    """Create a new course. Returns the generated doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('courses').add(data)
    return doc_ref.id


def update_course(course_id, data):
    """Update fields on an existing course."""
    data.setdefault('updated_at', _now())
    get_db().collection('courses').document(course_id).update(data)


def get_courses_by_subject(subject_id):
    """Get all courses belonging to a subject."""
    return _query_to_list(
        get_db().collection('courses')
        .where(filter=FieldFilter('subject_id', '==', subject_id))
        .order_by('order')
    )


def get_courses_by_instructor(instructor_id, standalone_only=False):
    """Get courses created by an instructor. Optionally only standalone courses."""
    q = (
        get_db().collection('courses')
        .where(filter=FieldFilter('instructor_id', '==', instructor_id))
    )
    if standalone_only:
        q = q.where(filter=FieldFilter('subject_id', '==', None))
    return _query_to_list(q.order_by('created_at'))


# ========================================================================
# Enrollments  (collection: enrollments)
# ========================================================================

def _enrollment_id(course_id, user_id):
    return f"{course_id}_{user_id}"


def get_enrollment(course_id, user_id):
    """Get an enrollment by composite key. Returns dict or None."""
    doc = get_db().collection('enrollments').document(_enrollment_id(course_id, user_id)).get()
    return _doc_to_dict(doc)


def create_enrollment(data):
    """Create an enrollment. Uses composite ID course_id + user_id. Returns doc ID."""
    course_id = data['course_id']
    user_id = data['user_id']
    doc_id = _enrollment_id(course_id, user_id)
    data.setdefault('created_at', _now())
    get_db().collection('enrollments').document(doc_id).set(data)
    return doc_id


def delete_enrollment(course_id, user_id):
    """Delete an enrollment."""
    get_db().collection('enrollments').document(_enrollment_id(course_id, user_id)).delete()


def get_enrollments_by_course(course_id):
    """Get all enrollments for a course."""
    return _query_to_list(
        get_db().collection('enrollments')
        .where(filter=FieldFilter('course_id', '==', course_id))
    )


def get_enrollments_by_user(user_id):
    """Get all enrollments for a user."""
    return _query_to_list(
        get_db().collection('enrollments')
        .where(filter=FieldFilter('user_id', '==', user_id))
    )


def is_enrolled(user_id, course_id):
    """Check whether a user is enrolled in a course."""
    doc = get_db().collection('enrollments').document(_enrollment_id(course_id, user_id)).get()
    return doc.exists


def update_enrollment_status(course_id, user_id, status):
    """Update the status field of an enrollment."""
    get_db().collection('enrollments').document(
        _enrollment_id(course_id, user_id)
    ).update({'status': status, 'updated_at': _now()})


# ========================================================================
# Subject Enrollments  (collection: subject_enrollments)
# ========================================================================

def _subject_enrollment_id(subject_id, user_id):
    return f"{subject_id}_{user_id}"


def get_subject_enrollment(subject_id, user_id):
    """Get a subject enrollment by composite key."""
    doc = get_db().collection('subject_enrollments').document(
        _subject_enrollment_id(subject_id, user_id)
    ).get()
    return _doc_to_dict(doc)


def create_subject_enrollment(data):
    """Create a subject enrollment. Returns doc ID."""
    subject_id = data['subject_id']
    user_id = data['user_id']
    doc_id = _subject_enrollment_id(subject_id, user_id)
    data.setdefault('created_at', _now())
    get_db().collection('subject_enrollments').document(doc_id).set(data)
    return doc_id


def delete_subject_enrollment(subject_id, user_id):
    """Delete a subject enrollment."""
    get_db().collection('subject_enrollments').document(
        _subject_enrollment_id(subject_id, user_id)
    ).delete()


def get_subject_enrollments_by_user(user_id, status=None):
    """Get subject enrollments for a user, optionally filtered by status."""
    q = (
        get_db().collection('subject_enrollments')
        .where(filter=FieldFilter('user_id', '==', user_id))
    )
    if status is not None:
        q = q.where(filter=FieldFilter('status', '==', status))
    return _query_to_list(q)


def get_subject_enrollments_by_subject(subject_id, status=None):
    """Get subject enrollments for a subject, optionally filtered by status."""
    q = (
        get_db().collection('subject_enrollments')
        .where(filter=FieldFilter('subject_id', '==', subject_id))
    )
    if status is not None:
        q = q.where(filter=FieldFilter('status', '==', status))
    return _query_to_list(q)


def update_subject_enrollment(subject_id, user_id, data):
    """Update a subject enrollment."""
    data.setdefault('updated_at', _now())
    get_db().collection('subject_enrollments').document(
        _subject_enrollment_id(subject_id, user_id)
    ).update(data)


# ========================================================================
# Subject Members  (collection: subject_members)
# ========================================================================

def get_subject_member(subject_id, user_id):
    """Get a subject member by subject and user. Returns dict or None."""
    docs = (
        get_db().collection('subject_members')
        .where(filter=FieldFilter('subject_id', '==', subject_id))
        .where(filter=FieldFilter('user_id', '==', user_id))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_subject_member(data):
    """Create a subject member record. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('subject_members').add(data)
    return doc_ref.id


def delete_subject_member(member_id):
    """Delete a subject member by doc ID."""
    get_db().collection('subject_members').document(member_id).delete()


def get_subject_members(subject_id):
    """Get all members of a subject."""
    return _query_to_list(
        get_db().collection('subject_members')
        .where(filter=FieldFilter('subject_id', '==', subject_id))
    )


def update_subject_member(member_id, data):
    """Update a subject member record."""
    data.setdefault('updated_at', _now())
    get_db().collection('subject_members').document(member_id).update(data)


# ========================================================================
# Checkpoints  (collection: checkpoints)
# ========================================================================

def get_checkpoint(checkpoint_id):
    """Get a checkpoint by ID. Returns dict or None."""
    doc = get_db().collection('checkpoints').document(checkpoint_id).get()
    return _doc_to_dict(doc)


def create_checkpoint(data):
    """Create a new checkpoint. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('checkpoints').add(data)
    return doc_ref.id


def update_checkpoint(checkpoint_id, data):
    """Update a checkpoint."""
    data.setdefault('updated_at', _now())
    get_db().collection('checkpoints').document(checkpoint_id).update(data)


def get_checkpoints_by_course(course_id, include_deleted=False):
    """Get all checkpoints for a course, ordered by 'order'."""
    q = (
        get_db().collection('checkpoints')
        .where(filter=FieldFilter('course_id', '==', course_id))
    )
    if not include_deleted:
        q = q.where(filter=FieldFilter('is_deleted', '==', False))
    return _query_to_list(q.order_by('order'))


def get_max_order(course_id):
    """Get the maximum order value among checkpoints in a course."""
    docs = (
        get_db().collection('checkpoints')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('order', direction='DESCENDING')
        .limit(1)
        .stream()
    )
    for doc in docs:
        d = doc.to_dict()
        return d.get('order', 0)
    return 0


# ========================================================================
# Progress  (collection: progress)
# ========================================================================

def get_progress(user_id, checkpoint_id, mode):
    """Get a progress record by user, checkpoint, and mode."""
    docs = (
        get_db().collection('progress')
        .where(filter=FieldFilter('user_id', '==', user_id))
        .where(filter=FieldFilter('checkpoint_id', '==', checkpoint_id))
        .where(filter=FieldFilter('mode', '==', mode))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_progress(data):
    """Create a progress record. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('progress').add(data)
    return doc_ref.id


def update_progress(progress_id, data):
    """Update a progress record."""
    data.setdefault('updated_at', _now())
    get_db().collection('progress').document(progress_id).update(data)


def get_progress_by_user(user_id):
    """Get all progress records for a user."""
    return _query_to_list(
        get_db().collection('progress')
        .where(filter=FieldFilter('user_id', '==', user_id))
    )


def get_progress_by_checkpoint(checkpoint_id, mode=None):
    """Get all progress records for a checkpoint, optionally filtered by mode."""
    q = (
        get_db().collection('progress')
        .where(filter=FieldFilter('checkpoint_id', '==', checkpoint_id))
    )
    if mode is not None:
        q = q.where(filter=FieldFilter('mode', '==', mode))
    return _query_to_list(q)


def count_completed_progress(checkpoint_ids, mode=None):
    """Count completed progress per checkpoint. Returns dict[checkpoint_id, count]."""
    if not checkpoint_ids:
        return {}
    counts = {cid: 0 for cid in checkpoint_ids}
    # Firestore 'in' supports max 30 items
    for i in range(0, len(checkpoint_ids), 30):
        batch = checkpoint_ids[i:i + 30]
        q = (
            get_db().collection('progress')
            .where(filter=FieldFilter('checkpoint_id', 'in', batch))
            .where(filter=FieldFilter('completed', '==', True))
        )
        if mode is not None:
            q = q.where(filter=FieldFilter('mode', '==', mode))
        for doc in q.stream():
            d = doc.to_dict()
            cid = d.get('checkpoint_id')
            if cid in counts:
                counts[cid] += 1
    return counts


# ========================================================================
# Active Sessions  (collection: active_sessions)
# ========================================================================

def get_active_session(session_id):
    """Get an active session by ID. Returns dict or None."""
    doc = get_db().collection('active_sessions').document(session_id).get()
    return _doc_to_dict(doc)


def get_active_session_for_course(course_id):
    """Get the currently active session for a course (ended_at is None)."""
    docs = (
        get_db().collection('active_sessions')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .where(filter=FieldFilter('ended_at', '==', None))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_active_session(data):
    """Create a new active session. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('active_sessions').add(data)
    return doc_ref.id


def update_active_session(session_id, data):
    """Update an active session."""
    get_db().collection('active_sessions').document(session_id).update(data)


def get_sessions_by_course(course_id):
    """Get all sessions for a course, ordered by created_at descending."""
    return _query_to_list(
        get_db().collection('active_sessions')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('created_at', direction='DESCENDING')
    )


# ========================================================================
# Chat Messages  (collection: chat_messages)
# ========================================================================

def create_chat_message(data):
    """Create a chat message. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('chat_messages').add(data)
    return doc_ref.id


def get_chat_messages(course_id, limit=50):
    """Get recent chat messages for a course, ordered by created_at."""
    return _query_to_list(
        get_db().collection('chat_messages')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('created_at', direction='DESCENDING')
        .limit(limit)
    )


def get_chat_message(message_id):
    """Get a single chat message by ID."""
    doc = get_db().collection('chat_messages').document(message_id).get()
    return _doc_to_dict(doc)


def update_chat_message(message_id, data):
    """Update a chat message."""
    data.setdefault('updated_at', _now())
    get_db().collection('chat_messages').document(message_id).update(data)


def delete_chat_message(message_id):
    """Delete a chat message."""
    get_db().collection('chat_messages').document(message_id).delete()


# ========================================================================
# Forum Posts  (collection: forum_posts)
# ========================================================================

def get_forum_post(post_id):
    """Get a forum post by ID. Returns dict or None."""
    doc = get_db().collection('forum_posts').document(post_id).get()
    return _doc_to_dict(doc)


def create_forum_post(data):
    """Create a forum post. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('forum_posts').add(data)
    return doc_ref.id


def delete_forum_post(post_id):
    """Delete a forum post and its comments."""
    # Delete associated comments first
    comments = (
        get_db().collection('forum_comments')
        .where(filter=FieldFilter('post_id', '==', post_id))
        .stream()
    )
    batch = get_db().batch()
    for comment in comments:
        batch.delete(comment.reference)
    batch.delete(get_db().collection('forum_posts').document(post_id))
    batch.commit()


def get_forum_posts_by_course(course_id):
    """Get all forum posts for a course, newest first."""
    return _query_to_list(
        get_db().collection('forum_posts')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('created_at', direction='DESCENDING')
    )


# ========================================================================
# Forum Comments  (collection: forum_comments)
# ========================================================================

def get_forum_comments(post_id):
    """Get all comments for a forum post, oldest first."""
    return _query_to_list(
        get_db().collection('forum_comments')
        .where(filter=FieldFilter('post_id', '==', post_id))
        .order_by('created_at')
    )


def create_forum_comment(data):
    """Create a forum comment. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('forum_comments').add(data)
    return doc_ref.id


def delete_forum_comment(comment_id):
    """Delete a forum comment."""
    get_db().collection('forum_comments').document(comment_id).delete()


# ========================================================================
# Live Session Posts  (collection: live_session_posts)
# ========================================================================

def create_live_session_post(data):
    """Create a live session post. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('live_session_posts').add(data)
    return doc_ref.id


def get_live_session_posts(session_id):
    """Get all posts for a live session, ordered by created_at."""
    return _query_to_list(
        get_db().collection('live_session_posts')
        .where(filter=FieldFilter('session_id', '==', session_id))
        .order_by('created_at')
    )


# ========================================================================
# Attendance  (collection: attendance)
# ========================================================================

def _attendance_id(course_id, user_id, session_id):
    return f"{course_id}_{user_id}_{session_id}"


def get_attendance(course_id, user_id, session_id):
    """Get an attendance record. Returns dict or None."""
    doc = get_db().collection('attendance').document(
        _attendance_id(course_id, user_id, session_id)
    ).get()
    return _doc_to_dict(doc)


def create_or_update_attendance(data):
    """Create or update an attendance record. Returns doc ID."""
    course_id = data['course_id']
    user_id = data['user_id']
    session_id = data['session_id']
    doc_id = _attendance_id(course_id, user_id, session_id)
    data.setdefault('created_at', _now())
    data['updated_at'] = _now()
    get_db().collection('attendance').document(doc_id).set(data, merge=True)
    return doc_id


def get_attendance_by_course_session(course_id, session_id):
    """Get all attendance records for a course session."""
    return _query_to_list(
        get_db().collection('attendance')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .where(filter=FieldFilter('session_id', '==', session_id))
    )


# ========================================================================
# Notifications  (collection: notifications)
# ========================================================================

def create_notification(data):
    """Create a notification. Returns doc ID."""
    data.setdefault('created_at', _now())
    data.setdefault('is_read', False)
    _, doc_ref = get_db().collection('notifications').add(data)
    return doc_ref.id


def get_notifications(user_id, limit=50):
    """Get notifications for a user, newest first."""
    return _query_to_list(
        get_db().collection('notifications')
        .where(filter=FieldFilter('user_id', '==', user_id))
        .order_by('created_at', direction='DESCENDING')
        .limit(limit)
    )


def mark_notification_read(notification_id):
    """Mark a single notification as read."""
    get_db().collection('notifications').document(notification_id).update({
        'is_read': True,
        'read_at': _now(),
    })


def mark_all_read(user_id):
    """Mark all notifications for a user as read."""
    docs = (
        get_db().collection('notifications')
        .where(filter=FieldFilter('user_id', '==', user_id))
        .where(filter=FieldFilter('is_read', '==', False))
        .stream()
    )
    batch = get_db().batch()
    now = _now()
    count = 0
    for doc in docs:
        batch.update(doc.reference, {'is_read': True, 'read_at': now})
        count += 1
        # Firestore batches are limited to 500 writes
        if count % 500 == 0:
            batch.commit()
            batch = get_db().batch()
    if count % 500 != 0:
        batch.commit()


def count_unread(user_id):
    """Count unread notifications for a user."""
    docs = (
        get_db().collection('notifications')
        .where(filter=FieldFilter('user_id', '==', user_id))
        .where(filter=FieldFilter('is_read', '==', False))
        .stream()
    )
    return sum(1 for _ in docs)


# ========================================================================
# Video Watch Logs  (collection: video_watch_logs)
# ========================================================================

def _watch_log_id(course_id, user_id):
    return f"{course_id}_{user_id}"


def get_watch_log(course_id, user_id):
    """Get a video watch log by composite ID. Returns dict or None."""
    doc = get_db().collection('video_watch_logs').document(
        _watch_log_id(course_id, user_id)
    ).get()
    return _doc_to_dict(doc)


def create_or_update_watch_log(course_id, user_id, data):
    """Create or update a video watch log. Returns doc ID."""
    doc_id = _watch_log_id(course_id, user_id)
    data['course_id'] = course_id
    data['user_id'] = user_id
    data['updated_at'] = _now()
    data.setdefault('created_at', _now())
    get_db().collection('video_watch_logs').document(doc_id).set(data, merge=True)
    return doc_id


# ========================================================================
# Session Completions  (collection: session_completions)
# ========================================================================

def _session_completion_id(course_id, user_id):
    return f"{course_id}_{user_id}"


def get_session_completion(course_id, user_id):
    """Get a session completion record. Returns dict or None."""
    doc = get_db().collection('session_completions').document(
        _session_completion_id(course_id, user_id)
    ).get()
    return _doc_to_dict(doc)


def create_session_completion(data):
    """Create a session completion record. Returns doc ID."""
    course_id = data['course_id']
    user_id = data['user_id']
    doc_id = _session_completion_id(course_id, user_id)
    data.setdefault('created_at', _now())
    get_db().collection('session_completions').document(doc_id).set(data)
    return doc_id


def delete_session_completion(course_id, user_id):
    """Delete a session completion record."""
    get_db().collection('session_completions').document(
        _session_completion_id(course_id, user_id)
    ).delete()


# ========================================================================
# Page Time Logs  (collection: page_time_logs)
# ========================================================================

def _page_time_log_id(course_id, user_id):
    return f"{course_id}_{user_id}"


def get_page_time_log(course_id, user_id):
    """Get a page time log. Returns dict or None."""
    doc = get_db().collection('page_time_logs').document(
        _page_time_log_id(course_id, user_id)
    ).get()
    return _doc_to_dict(doc)


def create_or_update_page_time_log(course_id, user_id, data):
    """Create or update a page time log. Returns doc ID."""
    doc_id = _page_time_log_id(course_id, user_id)
    data['course_id'] = course_id
    data['user_id'] = user_id
    data['updated_at'] = _now()
    data.setdefault('created_at', _now())
    get_db().collection('page_time_logs').document(doc_id).set(data, merge=True)
    return doc_id


# ========================================================================
# Quiz Questions  (collection: quiz_questions)
# ========================================================================

def get_quiz_questions(course_id):
    """Get all quiz questions for a course, ordered by 'order'."""
    return _query_to_list(
        get_db().collection('quiz_questions')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('order')
    )


def create_quiz_question(data):
    """Create a quiz question. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('quiz_questions').add(data)
    return doc_ref.id


# ========================================================================
# Quiz Attempts  (collection: quiz_attempts)
# ========================================================================

def get_quiz_attempt(course_id, user_id, completed=None):
    """Get a quiz attempt for a user in a course. Optionally filter by completed status."""
    q = (
        get_db().collection('quiz_attempts')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .where(filter=FieldFilter('user_id', '==', user_id))
    )
    if completed is not None:
        q = q.where(filter=FieldFilter('completed', '==', completed))
    q = q.order_by('created_at', direction='DESCENDING').limit(1)
    for doc in q.stream():
        return _doc_to_dict(doc)
    return None


def create_quiz_attempt(data):
    """Create a quiz attempt. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('quiz_attempts').add(data)
    return doc_ref.id


def update_quiz_attempt(attempt_id, data):
    """Update a quiz attempt."""
    data.setdefault('updated_at', _now())
    get_db().collection('quiz_attempts').document(attempt_id).update(data)


def get_quiz_attempts_by_course(course_id):
    """Get all quiz attempts for a course."""
    return _query_to_list(
        get_db().collection('quiz_attempts')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('created_at', direction='DESCENDING')
    )


# ========================================================================
# Assignment Submissions  (collection: assignment_submissions)
# ========================================================================

def _submission_id(course_id, user_id):
    return f"{course_id}_{user_id}"


def get_submission(course_id, user_id):
    """Get an assignment submission. Returns dict or None."""
    doc = get_db().collection('assignment_submissions').document(
        _submission_id(course_id, user_id)
    ).get()
    return _doc_to_dict(doc)


def create_or_update_submission(course_id, user_id, data):
    """Create or update an assignment submission. Returns doc ID."""
    doc_id = _submission_id(course_id, user_id)
    data['course_id'] = course_id
    data['user_id'] = user_id
    data['updated_at'] = _now()
    data.setdefault('created_at', _now())
    get_db().collection('assignment_submissions').document(doc_id).set(data, merge=True)
    return doc_id


def get_submissions_by_course(course_id):
    """Get all submissions for a course."""
    return _query_to_list(
        get_db().collection('assignment_submissions')
        .where(filter=FieldFilter('course_id', '==', course_id))
    )


# ========================================================================
# Slide Decks  (collection: slide_decks)
# ========================================================================

def get_slide_deck(deck_id):
    """Get a slide deck by ID. Returns dict or None."""
    doc = get_db().collection('slide_decks').document(deck_id).get()
    return _doc_to_dict(doc)


def create_slide_deck(data):
    """Create a slide deck. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('slide_decks').add(data)
    return doc_ref.id


def update_slide_deck(deck_id, data):
    """Update a slide deck."""
    data.setdefault('updated_at', _now())
    get_db().collection('slide_decks').document(deck_id).update(data)


def delete_slide_deck(deck_id):
    """Delete a slide deck."""
    get_db().collection('slide_decks').document(deck_id).delete()


def get_slide_decks_by_course(course_id):
    """Get all slide decks for a course."""
    return _query_to_list(
        get_db().collection('slide_decks')
        .where(filter=FieldFilter('course_id', '==', course_id))
        .order_by('created_at')
    )


# ========================================================================
# Slide Reactions  (collection: slide_reactions)
# ========================================================================

def _slide_reaction_id(deck_id, user_id, slide_index):
    return f"{deck_id}_{user_id}_{slide_index}"


def get_slide_reaction(deck_id, user_id, slide_index):
    """Get a slide reaction. Returns dict or None."""
    doc = get_db().collection('slide_reactions').document(
        _slide_reaction_id(deck_id, user_id, slide_index)
    ).get()
    return _doc_to_dict(doc)


def set_slide_reaction(deck_id, user_id, slide_index, reaction):
    """Set (create/update) a slide reaction."""
    doc_id = _slide_reaction_id(deck_id, user_id, slide_index)
    get_db().collection('slide_reactions').document(doc_id).set({
        'deck_id': deck_id,
        'user_id': user_id,
        'slide_index': slide_index,
        'reaction': reaction,
        'updated_at': _now(),
    }, merge=True)


def delete_slide_reaction(deck_id, user_id, slide_index):
    """Delete a slide reaction."""
    get_db().collection('slide_reactions').document(
        _slide_reaction_id(deck_id, user_id, slide_index)
    ).delete()


def get_reactions_by_deck(deck_id):
    """Get all reactions for a slide deck."""
    return _query_to_list(
        get_db().collection('slide_reactions')
        .where(filter=FieldFilter('deck_id', '==', deck_id))
    )


def count_reactions(deck_id, slide_index):
    """Count reactions for a specific slide. Returns dict with understood/question/hard counts."""
    counts = {'understood': 0, 'question': 0, 'hard': 0}
    docs = (
        get_db().collection('slide_reactions')
        .where(filter=FieldFilter('deck_id', '==', deck_id))
        .where(filter=FieldFilter('slide_index', '==', slide_index))
        .stream()
    )
    for doc in docs:
        reaction = doc.to_dict().get('reaction')
        if reaction in counts:
            counts[reaction] += 1
    return counts


# ========================================================================
# Slide Bookmarks  (collection: slide_bookmarks)
# ========================================================================

def _slide_bookmark_id(deck_id, slide_index):
    return f"{deck_id}_{slide_index}"


def get_slide_bookmark(deck_id, slide_index):
    """Get a slide bookmark. Returns dict or None."""
    doc = get_db().collection('slide_bookmarks').document(
        _slide_bookmark_id(deck_id, slide_index)
    ).get()
    return _doc_to_dict(doc)


def create_or_update_bookmark(deck_id, slide_index, data):
    """Create or update a slide bookmark."""
    doc_id = _slide_bookmark_id(deck_id, slide_index)
    data['deck_id'] = deck_id
    data['slide_index'] = slide_index
    data['updated_at'] = _now()
    data.setdefault('created_at', _now())
    get_db().collection('slide_bookmarks').document(doc_id).set(data, merge=True)


def delete_bookmark(deck_id, slide_index):
    """Delete a slide bookmark."""
    get_db().collection('slide_bookmarks').document(
        _slide_bookmark_id(deck_id, slide_index)
    ).delete()


def get_bookmarks_by_deck(deck_id):
    """Get all bookmarks for a slide deck."""
    return _query_to_list(
        get_db().collection('slide_bookmarks')
        .where(filter=FieldFilter('deck_id', '==', deck_id))
    )


# ========================================================================
# Understanding Status  (collection: understanding_status)
# ========================================================================

def _understanding_id(user_id, checkpoint_id, session_id):
    return f"{user_id}_{checkpoint_id}_{session_id}"


def get_understanding(user_id, checkpoint_id, session_id):
    """Get an understanding status record. Returns dict or None."""
    doc = get_db().collection('understanding_status').document(
        _understanding_id(user_id, checkpoint_id, session_id)
    ).get()
    return _doc_to_dict(doc)


def set_understanding(data):
    """Set (create/update) an understanding status. Returns doc ID."""
    user_id = data['user_id']
    checkpoint_id = data['checkpoint_id']
    session_id = data['session_id']
    doc_id = _understanding_id(user_id, checkpoint_id, session_id)
    data['updated_at'] = _now()
    data.setdefault('created_at', _now())
    get_db().collection('understanding_status').document(doc_id).set(data, merge=True)
    return doc_id


def count_understanding(checkpoint_id, session_id):
    """Count understanding statuses for a checkpoint in a session.
    Returns dict with 'understood' and 'confused' counts."""
    counts = {'understood': 0, 'confused': 0}
    docs = (
        get_db().collection('understanding_status')
        .where(filter=FieldFilter('checkpoint_id', '==', checkpoint_id))
        .where(filter=FieldFilter('session_id', '==', session_id))
        .stream()
    )
    for doc in docs:
        status = doc.to_dict().get('status')
        if status in counts:
            counts[status] += 1
    return counts


# ========================================================================
# Learning Reviews  (collection: learning_reviews)
# ========================================================================

def get_learning_review(review_id):
    """Get a learning review by ID. Returns dict or None."""
    doc = get_db().collection('learning_reviews').document(review_id).get()
    return _doc_to_dict(doc)


def create_learning_review(data):
    """Create a learning review. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('learning_reviews').add(data)
    return doc_ref.id


def update_learning_review(review_id, data):
    """Update a learning review."""
    data.setdefault('updated_at', _now())
    get_db().collection('learning_reviews').document(review_id).update(data)


def delete_learning_review(review_id):
    """Delete a learning review and its comments."""
    comments = (
        get_db().collection('review_comments')
        .where(filter=FieldFilter('review_id', '==', review_id))
        .stream()
    )
    batch = get_db().batch()
    for comment in comments:
        batch.delete(comment.reference)
    batch.delete(get_db().collection('learning_reviews').document(review_id))
    batch.commit()


def get_learning_reviews(course_id=None, user_id=None, limit=20, start_after=None):
    """Get learning reviews with optional filters and pagination."""
    q = get_db().collection('learning_reviews')
    if course_id:
        q = q.where(filter=FieldFilter('course_id', '==', course_id))
    if user_id:
        q = q.where(filter=FieldFilter('user_id', '==', user_id))
    q = q.order_by('created_at', direction='DESCENDING')
    if start_after:
        doc = get_db().collection('learning_reviews').document(start_after).get()
        if doc.exists:
            q = q.start_after(doc)
    q = q.limit(limit)
    return _query_to_list(q)


# ========================================================================
# Review Comments  (collection: review_comments)
# ========================================================================

def get_review_comment(comment_id):
    """Get a review comment by ID."""
    doc = get_db().collection('review_comments').document(comment_id).get()
    return _doc_to_dict(doc)


def create_review_comment(data):
    """Create a review comment. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('review_comments').add(data)
    return doc_ref.id


def delete_review_comment(comment_id):
    """Delete a review comment."""
    get_db().collection('review_comments').document(comment_id).delete()


def get_review_comments(review_id):
    """Get all comments for a learning review."""
    return _query_to_list(
        get_db().collection('review_comments')
        .where(filter=FieldFilter('review_id', '==', review_id))
        .order_by('created_at')
    )


# ========================================================================
# QnA Posts  (collection: qna_posts)
# ========================================================================

def get_qna_post(post_id):
    """Get a QnA post by ID. Returns dict or None."""
    doc = get_db().collection('qna_posts').document(post_id).get()
    return _doc_to_dict(doc)


def create_qna_post(data):
    """Create a QnA post. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('qna_posts').add(data)
    return doc_ref.id


def update_qna_post(post_id, data):
    """Update a QnA post."""
    data.setdefault('updated_at', _now())
    get_db().collection('qna_posts').document(post_id).update(data)


def delete_qna_post(post_id):
    """Delete a QnA post and its answers."""
    answers = (
        get_db().collection('qna_answers')
        .where(filter=FieldFilter('post_id', '==', post_id))
        .stream()
    )
    batch = get_db().batch()
    for answer in answers:
        batch.delete(answer.reference)
    batch.delete(get_db().collection('qna_posts').document(post_id))
    batch.commit()


def get_qna_posts(course_id=None, user_id=None, limit=20, start_after=None):
    """Get QnA posts with optional filters and pagination."""
    q = get_db().collection('qna_posts')
    if course_id:
        q = q.where(filter=FieldFilter('course_id', '==', course_id))
    if user_id:
        q = q.where(filter=FieldFilter('user_id', '==', user_id))
    q = q.order_by('created_at', direction='DESCENDING')
    if start_after:
        doc = get_db().collection('qna_posts').document(start_after).get()
        if doc.exists:
            q = q.start_after(doc)
    q = q.limit(limit)
    return _query_to_list(q)


# ========================================================================
# QnA Answers  (collection: qna_answers)
# ========================================================================

def get_qna_answer(answer_id):
    """Get a QnA answer by ID."""
    doc = get_db().collection('qna_answers').document(answer_id).get()
    return _doc_to_dict(doc)


def create_qna_answer(data):
    """Create a QnA answer. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('qna_answers').add(data)
    return doc_ref.id


def update_qna_answer(answer_id, data):
    """Update a QnA answer."""
    data.setdefault('updated_at', _now())
    get_db().collection('qna_answers').document(answer_id).update(data)


def delete_qna_answer(answer_id):
    """Delete a QnA answer."""
    get_db().collection('qna_answers').document(answer_id).delete()


def get_qna_answers(post_id):
    """Get all answers for a QnA post."""
    return _query_to_list(
        get_db().collection('qna_answers')
        .where(filter=FieldFilter('post_id', '==', post_id))
        .order_by('created_at')
    )


# ========================================================================
# Study Groups  (collection: study_groups)
# ========================================================================

def get_study_group(group_id):
    """Get a study group by ID. Returns dict or None."""
    doc = get_db().collection('study_groups').document(group_id).get()
    return _doc_to_dict(doc)


def create_study_group(data):
    """Create a study group. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('study_groups').add(data)
    return doc_ref.id


def update_study_group(group_id, data):
    """Update a study group."""
    data.setdefault('updated_at', _now())
    get_db().collection('study_groups').document(group_id).update(data)


def delete_study_group(group_id):
    """Delete a study group and its members."""
    members = (
        get_db().collection('study_group_members')
        .where(filter=FieldFilter('group_id', '==', group_id))
        .stream()
    )
    batch = get_db().batch()
    for member in members:
        batch.delete(member.reference)
    batch.delete(get_db().collection('study_groups').document(group_id))
    batch.commit()


def get_study_groups(course_id=None, limit=20, start_after=None):
    """Get study groups with optional filters and pagination."""
    q = get_db().collection('study_groups')
    if course_id:
        q = q.where(filter=FieldFilter('course_id', '==', course_id))
    q = q.order_by('created_at', direction='DESCENDING')
    if start_after:
        doc = get_db().collection('study_groups').document(start_after).get()
        if doc.exists:
            q = q.start_after(doc)
    q = q.limit(limit)
    return _query_to_list(q)


# ========================================================================
# Study Group Members  (collection: study_group_members)
# ========================================================================

def get_study_group_member(group_id, user_id):
    """Get a study group member. Returns dict or None."""
    docs = (
        get_db().collection('study_group_members')
        .where(filter=FieldFilter('group_id', '==', group_id))
        .where(filter=FieldFilter('user_id', '==', user_id))
        .limit(1)
        .stream()
    )
    for doc in docs:
        return _doc_to_dict(doc)
    return None


def create_study_group_member(data):
    """Create a study group member. Returns doc ID."""
    data.setdefault('joined_at', _now())
    _, doc_ref = get_db().collection('study_group_members').add(data)
    return doc_ref.id


def delete_study_group_member(member_id):
    """Delete a study group member by doc ID."""
    get_db().collection('study_group_members').document(member_id).delete()


def get_study_group_members(group_id):
    """Get all members of a study group."""
    return _query_to_list(
        get_db().collection('study_group_members')
        .where(filter=FieldFilter('group_id', '==', group_id))
    )


def get_user_study_groups(user_id):
    """Get all study group memberships for a user."""
    return _query_to_list(
        get_db().collection('study_group_members')
        .where(filter=FieldFilter('user_id', '==', user_id))
    )


# ========================================================================
# Guide Posts  (collection: guide_posts)
# ========================================================================

def get_guide_post(post_id):
    """Get a guide post by ID. Returns dict or None."""
    doc = get_db().collection('guide_posts').document(post_id).get()
    return _doc_to_dict(doc)


def create_guide_post(data):
    """Create a guide post. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('guide_posts').add(data)
    return doc_ref.id


def update_guide_post(post_id, data):
    """Update a guide post."""
    data.setdefault('updated_at', _now())
    get_db().collection('guide_posts').document(post_id).update(data)


def delete_guide_post(post_id):
    """Delete a guide post and its comments and attachments."""
    batch = get_db().batch()
    # Delete comments
    for doc in get_db().collection('guide_comments').where(
        filter=FieldFilter('post_id', '==', post_id)
    ).stream():
        batch.delete(doc.reference)
    # Delete attachments
    for doc in get_db().collection('guide_attachments').where(
        filter=FieldFilter('post_id', '==', post_id)
    ).stream():
        batch.delete(doc.reference)
    batch.delete(get_db().collection('guide_posts').document(post_id))
    batch.commit()


def get_guide_posts(course_id=None, category=None, limit=20, start_after=None):
    """Get guide posts with optional filters and pagination."""
    q = get_db().collection('guide_posts')
    if course_id:
        q = q.where(filter=FieldFilter('course_id', '==', course_id))
    if category:
        q = q.where(filter=FieldFilter('category', '==', category))
    q = q.order_by('created_at', direction='DESCENDING')
    if start_after:
        doc = get_db().collection('guide_posts').document(start_after).get()
        if doc.exists:
            q = q.start_after(doc)
    q = q.limit(limit)
    return _query_to_list(q)


# ========================================================================
# Guide Comments  (collection: guide_comments)
# ========================================================================

def get_guide_comment(comment_id):
    """Get a guide comment by ID."""
    doc = get_db().collection('guide_comments').document(comment_id).get()
    return _doc_to_dict(doc)


def create_guide_comment(data):
    """Create a guide comment. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('guide_comments').add(data)
    return doc_ref.id


def update_guide_comment(comment_id, data):
    """Update a guide comment."""
    data.setdefault('updated_at', _now())
    get_db().collection('guide_comments').document(comment_id).update(data)


def delete_guide_comment(comment_id):
    """Delete a guide comment."""
    get_db().collection('guide_comments').document(comment_id).delete()


def get_guide_comments(post_id):
    """Get all comments for a guide post."""
    return _query_to_list(
        get_db().collection('guide_comments')
        .where(filter=FieldFilter('post_id', '==', post_id))
        .order_by('created_at')
    )


# ========================================================================
# Guide Attachments  (collection: guide_attachments)
# ========================================================================

def get_guide_attachment(attachment_id):
    """Get a guide attachment by ID."""
    doc = get_db().collection('guide_attachments').document(attachment_id).get()
    return _doc_to_dict(doc)


def create_guide_attachment(data):
    """Create a guide attachment. Returns doc ID."""
    data.setdefault('created_at', _now())
    _, doc_ref = get_db().collection('guide_attachments').add(data)
    return doc_ref.id


def delete_guide_attachment(attachment_id):
    """Delete a guide attachment."""
    get_db().collection('guide_attachments').document(attachment_id).delete()


def get_guide_attachments(post_id):
    """Get all attachments for a guide post."""
    return _query_to_list(
        get_db().collection('guide_attachments')
        .where(filter=FieldFilter('post_id', '==', post_id))
    )
