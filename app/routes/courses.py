from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app.services.storage import get_slide_image_url
from datetime import datetime

bp = Blueprint('courses', __name__, url_prefix='/courses')


def has_course_access(course, user, roles=['instructor', 'assistant']):
    if course['instructor_id'] == user.uid:
        return True
    if course.get('subject_id'):
        member = dao.get_subject_member(course['subject_id'], user.uid)
        if member and member.get('role') in roles:
            return True
    return False


def _is_course_accessible(course, user):
    """Check whether a course is accessible by a given user (inline replacement
    for the old Course.is_accessible_by ORM method)."""
    if course['instructor_id'] == user.uid:
        return True
    if not dao.is_enrolled(user.uid, course['id']):
        return False
    visibility = course.get('visibility', 'public')
    if visibility == 'public':
        return True
    if visibility == 'private':
        return False
    if visibility == 'date_based':
        now = datetime.utcnow()
        start_date = course.get('start_date')
        end_date = course.get('end_date')
        if start_date and now < start_date:
            return False
        if end_date and now > end_date:
            return False
        return True
    if visibility == 'prerequisite':
        prereq_id = course.get('prerequisite_course_id')
        if not prereq_id:
            return True
        prereq_checkpoints = dao.get_checkpoints_by_course(prereq_id)
        if not prereq_checkpoints:
            return False
        completed = 0
        for cp in prereq_checkpoints:
            p = dao.get_progress(user.uid, cp['id'], 'self_paced')
            if p and p.get('completed_at'):
                completed += 1
        return completed >= len(prereq_checkpoints)
    return True


def _get_enrolled_students(course_id):
    """Get enrolled student user objects for a course."""
    enrollments = dao.get_enrollments_by_course(course_id)
    students = []
    for e in enrollments:
        u = dao.get_user(e['user_id'])
        if u:
            students.append(u)
    return students


def _get_slide_urls(deck):
    """Generate signed slide image URLs for a deck dict."""
    slide_count = deck.get('slide_count', 0)
    if slide_count == 0:
        return []
    return [get_slide_image_url(deck['id'], i) for i in range(slide_count)]


def _get_live_status_display(session):
    """Return Korean display string for a session's live_status."""
    status_map = {
        'preparing': '라이브 준비중',
        'live': '라이브 중',
        'ended': '라이브 종료'
    }
    return status_map.get(session.get('live_status', ''), '대기중')


@bp.route('/')
@auth_required
def list_courses():
    user = get_current_user()
    is_instructor = user.is_instructor()

    if is_instructor:
        all_courses = dao.get_courses_by_instructor(user.uid, standalone_only=True)
        my_courses = [c for c in all_courses if not c.get('deleted_at')]
        enrolled_courses = []
        public_courses = []
    else:
        enrollments = dao.get_enrollments_by_user(user.uid)
        enrolled_course_ids = set()
        enrolled_courses = []
        for e in enrollments:
            c = dao.get_course(e['course_id'])
            if c and not c.get('deleted_at') and not c.get('subject_id'):
                enrolled_courses.append(c)
            if c:
                enrolled_course_ids.add(c['id'])

        # For public courses, we need to get instructor's courses that are public
        # and not already enrolled. There's no dedicated DAO, so we filter manually.
        # We can't enumerate all courses without a collection scan; instead we rely
        # on the template only showing what's available. For now, this mirrors the
        # original behavior as closely as possible with available DAO functions.
        public_courses = []
        my_courses = []

    return render_template('courses/list.html',
                           my_courses=my_courses,
                           enrolled_courses=enrolled_courses,
                           public_courses=public_courses,
                           is_instructor=is_instructor)


@bp.route('/create', methods=['GET', 'POST'])
@auth_required
def create():
    user = get_current_user()
    if not user.is_instructor():
        flash('강사만 세미나를 생성할 수 있습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    from app.forms import CourseForm
    form = CourseForm()
    if form.validate_on_submit():
        course_id = dao.create_course({
            'title': form.title.data,
            'description': form.description.data,
            'instructor_id': user.uid,
            'invite_code': dao.generate_invite_code('courses'),
            'visibility': 'public',
        })
        flash('세미나가 생성되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course_id))

    return render_template('courses/create.html', form=form)


@bp.route('/<course_id>')
@auth_required
def view(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course.get('deleted_at'):
        if not has_course_access(course, user):
            flash('해당 세션을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))

    if course.get('session_type') in ['video', 'video_external']:
        return redirect(url_for('sessions.video_session', course_id=course_id))
    elif course.get('session_type') == 'material':
        return redirect(url_for('sessions.material_session', course_id=course_id))
    elif course.get('session_type') == 'assignment':
        return redirect(url_for('sessions.assignment_session', course_id=course_id))
    elif course.get('session_type') == 'quiz':
        return redirect(url_for('sessions.quiz_session', course_id=course_id))

    if user.is_instructor():
        if not has_course_access(course, user):
            flash('이 세미나에 접근 권한이 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = _get_enrolled_students(course_id)
        checkpoints = dao.get_checkpoints_by_course(course_id)
        return render_template('courses/view_instructor.html',
                               course=course, students=students, checkpoints=checkpoints)
    else:
        if not dao.is_enrolled(user.uid, course_id):
            flash('이 세미나에 등록되어 있지 않습니다.', 'danger')
            return redirect(url_for('main.dashboard'))

        if not _is_course_accessible(course, user):
            visibility = course.get('visibility', 'public')
            if visibility == 'private':
                flash('이 세션은 현재 비공개 상태입니다.', 'warning')
            elif visibility == 'date_based':
                start_date = course.get('start_date')
                end_date = course.get('end_date')
                if start_date and datetime.utcnow() < start_date:
                    flash(f'이 세션은 {start_date.strftime("%Y-%m-%d %H:%M")}에 공개됩니다.', 'info')
                elif end_date and datetime.utcnow() > end_date:
                    flash('이 세션의 공개 기간이 종료되었습니다.', 'warning')
            elif visibility == 'prerequisite':
                prereq_id = course.get('prerequisite_course_id')
                if prereq_id:
                    prereq = dao.get_course(prereq_id)
                    if prereq:
                        flash(f'이 세션에 접근하려면 먼저 "{prereq["title"]}" 세션을 완료해야 합니다.', 'info')
            return redirect(url_for('main.dashboard'))

        checkpoints = dao.get_checkpoints_by_course(course_id)

        progress_records = dao.get_progress_by_user(user.uid)
        live_progress = {p['checkpoint_id']: p for p in progress_records if p.get('mode') == 'live'}
        self_progress = {p['checkpoint_id']: p for p in progress_records if p.get('mode') == 'self_paced'}

        active_session = dao.get_active_session_for_course(course_id)

        return render_template('courses/view_student.html',
                               course=course,
                               checkpoints=checkpoints,
                               live_progress=live_progress,
                               self_progress=self_progress,
                               active_session=active_session)


@bp.route('/<course_id>/edit', methods=['GET', 'POST'])
@auth_required
def edit(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('이 세미나를 수정할 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    from app.forms import CourseForm
    form = CourseForm(data=course)
    if form.validate_on_submit():
        dao.update_course(course_id, {
            'title': form.title.data,
            'description': form.description.data,
        })
        flash('세미나가 수정되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course_id))

    return render_template('courses/edit.html', form=form, course=course)


@bp.route('/<course_id>/delete', methods=['POST'])
@auth_required
def delete(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('이 세미나를 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    dao.update_course(course_id, {'deleted_at': datetime.utcnow()})
    flash('세미나가 삭제되었습니다!', 'success')
    return redirect(url_for('main.dashboard'))


@bp.route('/enroll', methods=['GET', 'POST'])
@auth_required
def enroll():
    user = get_current_user()
    if user.is_instructor():
        flash('강사는 수강 신청을 할 수 없습니다.', 'warning')
        return redirect(url_for('main.dashboard'))

    from app.forms import EnrollForm
    form = EnrollForm()
    if form.validate_on_submit():
        course = dao.get_course_by_invite_code(form.invite_code.data.upper())
        if not course:
            flash('유효하지 않은 초대 코드입니다.', 'danger')
            return render_template('courses/enroll.html', form=form)

        if course.get('deleted_at') or course.get('visibility') == 'private':
            flash('해당 세션에 등록할 수 없습니다.', 'danger')
            return render_template('courses/enroll.html', form=form)

        if dao.is_enrolled(user.uid, course['id']):
            flash('이미 이 세미나에 등록되어 있습니다.', 'warning')
            return redirect(url_for('courses.view', course_id=course['id']))

        dao.create_enrollment({
            'course_id': course['id'],
            'user_id': user.uid,
            'status': 'approved',
        })
        flash(f'{course["title"]} 세미나에 등록되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course['id']))

    return render_template('courses/enroll.html', form=form)


@bp.route('/<course_id>/enroll', methods=['POST'])
@auth_required
def enroll_course(course_id):
    user = get_current_user()
    if user.is_instructor():
        flash('강사는 수강 신청을 할 수 없습니다.', 'warning')
        return redirect(url_for('courses.list_courses'))

    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course.get('deleted_at') or course.get('visibility') == 'private':
        flash('해당 세션에 등록할 수 없습니다.', 'danger')
        return redirect(url_for('courses.list_courses'))

    if dao.is_enrolled(user.uid, course_id):
        flash('이미 이 세션에 등록되어 있습니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))

    dao.create_enrollment({
        'course_id': course_id,
        'user_id': user.uid,
        'status': 'approved',
    })
    flash(f'{course["title"]} 세션에 등록되었습니다!', 'success')
    return redirect(url_for('courses.view', course_id=course_id))


@bp.route('/<course_id>/start-session', methods=['GET', 'POST'])
@auth_required
def start_session(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('강사만 세션을 시작할 수 있습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course_id))

    existing_session = dao.get_active_session_for_course(course_id)
    if existing_session:
        flash('이미 진행 중인 세션이 있습니다.', 'warning')
        return redirect(url_for('courses.live_mode', course_id=course_id))

    from app.forms import SessionScheduleForm
    form = SessionScheduleForm()

    if request.method == 'POST':
        session_type = request.form.get('session_type', 'immediate')
        scheduled_at = None

        if session_type == 'scheduled':
            scheduled_str = request.form.get('scheduled_at')
            if not scheduled_str:
                flash('예약 시간을 입력하세요.', 'danger')
                return render_template('courses/start_session.html', course=course, form=form)
            try:
                scheduled_at = datetime.strptime(scheduled_str, '%Y-%m-%dT%H:%M')
                if scheduled_at <= datetime.utcnow():
                    flash('예약 시간은 현재 시간 이후여야 합니다.', 'danger')
                    return render_template('courses/start_session.html', course=course, form=form)
            except ValueError:
                flash('올바른 날짜/시간 형식을 입력하세요.', 'danger')
                return render_template('courses/start_session.html', course=course, form=form)

        session_id = dao.create_active_session({
            'course_id': course_id,
            'mode': 'live',
            'session_type': session_type,
            'scheduled_at': scheduled_at,
            'started_at': datetime.utcnow() if session_type == 'immediate' else None,
            'ended_at': None,
            'live_status': 'preparing',
        })

        if session_type == 'immediate':
            flash('라이브 세션이 시작되었습니다.', 'success')
            return redirect(url_for('courses.live_mode', course_id=course_id))
        else:
            flash(f'세션이 {scheduled_at.strftime("%Y-%m-%d %H:%M")}에 예약되었습니다.', 'success')
            return redirect(url_for('courses.view', course_id=course_id))

    return render_template('courses/start_session.html', course=course, form=form)


@bp.route('/<course_id>/live')
@auth_required
def live_mode(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)

    if course.get('deleted_at'):
        if not has_course_access(course, user):
            flash('해당 세션을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))

    checkpoints = dao.get_checkpoints_by_course(course_id)

    session = dao.get_active_session_for_course(course_id)
    if not session:
        if has_course_access(course, user):
            return redirect(url_for('courses.start_session', course_id=course_id))
        else:
            flash('현재 진행 중인 세션이 없습니다.', 'warning')
            return redirect(url_for('courses.view', course_id=course_id))

    if session.get('session_type') == 'scheduled' and session.get('scheduled_at'):
        if datetime.utcnow() < session['scheduled_at']:
            if not user.is_instructor():
                flash(f'세션이 {session["scheduled_at"].strftime("%Y-%m-%d %H:%M")}에 시작될 예정입니다.', 'info')
                return redirect(url_for('courses.view', course_id=course_id))
        elif not session.get('started_at'):
            dao.update_active_session(session['id'], {'started_at': datetime.utcnow()})

    recent_messages = dao.get_chat_messages(course_id, limit=50)
    # get_chat_messages returns descending order; reverse for chronological display
    recent_messages = list(reversed(recent_messages))

    if user.is_instructor():
        if not has_course_access(course, user):
            flash('접근 권한이 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = _get_enrolled_students(course_id)
        all_decks = dao.get_slide_decks_by_course(course_id)
        slide_decks = [d for d in all_decks if d.get('conversion_status') == 'completed']
        active_deck = slide_decks[-1] if slide_decks else None
        active_slides = _get_slide_urls(active_deck) if active_deck else []
        active_bookmarks = {}
        if active_deck:
            bookmarks = dao.get_bookmarks_by_deck(active_deck['id'])
            for b in bookmarks:
                active_bookmarks[b.get('slide_index')] = b
        return render_template('courses/live_instructor.html',
                               course=course, checkpoints=checkpoints,
                               students=students, session=session,
                               messages=recent_messages, slide_decks=slide_decks,
                               active_deck=active_deck, active_slides=active_slides,
                               active_bookmarks=active_bookmarks)
    else:
        if not dao.is_enrolled(user.uid, course_id):
            flash('이 세미나에 등록되어 있지 않습니다.', 'danger')
            return redirect(url_for('main.dashboard'))

        if not _is_course_accessible(course, user):
            flash('이 세션에 접근할 수 없습니다.', 'warning')
            return redirect(url_for('main.dashboard'))

        attendance_checked = False
        if session:
            attendance = dao.get_attendance(course_id, user.uid, session['id'])
            attendance_checked = attendance is not None

        progress_records = dao.get_progress_by_user(user.uid)
        progress_dict = {p['checkpoint_id']: p for p in progress_records if p.get('mode') == 'live'}
        enrollments = dao.get_enrollments_by_course(course_id)

        all_decks = dao.get_slide_decks_by_course(course_id)
        completed_decks = [d for d in all_decks if d.get('conversion_status') == 'completed']
        active_deck = completed_decks[-1] if completed_decks else None
        active_slides = _get_slide_urls(active_deck) if active_deck else []
        my_reactions = {}
        if active_deck:
            reactions = dao.get_reactions_by_deck(active_deck['id'])
            for r in reactions:
                if r.get('user_id') == user.uid:
                    my_reactions[r.get('slide_index')] = r.get('reaction')
        return render_template('courses/live_student.html',
                               course=course, checkpoints=checkpoints,
                               progress=progress_dict, session=session,
                               messages=recent_messages, enrollments=enrollments,
                               attendance_checked=attendance_checked,
                               active_deck=active_deck, active_slides=active_slides,
                               my_reactions=my_reactions)


@bp.route('/<course_id>/regenerate-code', methods=['POST'])
@auth_required
def regenerate_code(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다'}), 403

    new_code = dao.generate_invite_code('courses')
    dao.update_course(course_id, {'invite_code': new_code})
    return jsonify({'invite_code': new_code})


@bp.route('/<course_id>/settings', methods=['GET', 'POST'])
@auth_required
def settings(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('설정 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        setting_type = request.form.get('setting_type', 'basic')

        if setting_type == 'basic':
            update_data = {
                'title': request.form.get('title', course.get('title', '')),
                'description': request.form.get('description', course.get('description', '')),
            }

            order_num = request.form.get('order_number')
            update_data['order_number'] = int(order_num) if order_num else None

            start_date_str = request.form.get('start_date')
            if start_date_str:
                update_data['start_date'] = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
            else:
                update_data['start_date'] = None

            end_date_str = request.form.get('end_date')
            if end_date_str:
                update_data['end_date'] = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
            else:
                update_data['end_date'] = None

            attendance_start_str = request.form.get('attendance_start')
            if attendance_start_str:
                update_data['attendance_start'] = datetime.strptime(attendance_start_str, '%Y-%m-%dT%H:%M')
            else:
                update_data['attendance_start'] = None

            attendance_end_str = request.form.get('attendance_end')
            if attendance_end_str:
                update_data['attendance_end'] = datetime.strptime(attendance_end_str, '%Y-%m-%dT%H:%M')
            else:
                update_data['attendance_end'] = None

            update_data['late_allowed'] = 'late_allowed' in request.form
            late_end_str = request.form.get('late_end')
            if late_end_str and update_data['late_allowed']:
                update_data['late_end'] = datetime.strptime(late_end_str, '%Y-%m-%dT%H:%M')
            else:
                update_data['late_end'] = None

            dao.update_course(course_id, update_data)
            flash('기본 설정이 저장되었습니다.', 'success')

        elif setting_type == 'visibility':
            update_data = {
                'visibility': request.form.get('visibility', 'public'),
            }

            prerequisite_id = request.form.get('prerequisite_course_id')
            if prerequisite_id and prerequisite_id != '0':
                update_data['prerequisite_course_id'] = prerequisite_id
            else:
                update_data['prerequisite_course_id'] = None

            dao.update_course(course_id, update_data)
            flash('공개 설정이 저장되었습니다.', 'success')

        return redirect(url_for('courses.settings', course_id=course_id))

    all_instructor_courses = dao.get_courses_by_instructor(user.uid)
    other_courses = [c for c in all_instructor_courses
                     if c['id'] != course_id and not c.get('deleted_at')]

    return render_template('courses/settings.html', course=course, other_courses=other_courses)


@bp.route('/<course_id>/self-study-progress')
@auth_required
def self_study_progress(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    students = _get_enrolled_students(course_id)
    checkpoints = dao.get_checkpoints_by_course(course_id)

    progress_data = {}
    for student in students:
        student_id = student['id']
        progress_data[student_id] = {}
        for cp in checkpoints:
            p = dao.get_progress(student_id, cp['id'], 'self_paced')
            progress_data[student_id][cp['id']] = p

    return render_template('courses/self_study_progress.html',
                           course=course,
                           students=students,
                           checkpoints=checkpoints,
                           progress_data=progress_data)


@bp.route('/<course_id>/session-post', methods=['POST'])
@auth_required
def create_session_post(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    session = dao.get_active_session_for_course(course_id)

    if not session:
        flash('현재 진행 중인 세션이 없습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course_id))

    if not has_course_access(course, user):
        flash('강사만 공지를 작성할 수 있습니다.', 'danger')
        return redirect(url_for('courses.live_mode', course_id=course_id))

    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    pinned = request.form.get('pinned') == 'on'

    if not title or not content:
        flash('제목과 내용을 입력하세요.', 'danger')
        return redirect(url_for('courses.live_mode', course_id=course_id))

    dao.create_live_session_post({
        'session_id': session['id'],
        'user_id': user.uid,
        'title': title,
        'content': content,
        'pinned': pinned,
    })

    flash('공지가 등록되었습니다.', 'success')
    return redirect(url_for('courses.live_mode', course_id=course_id))


@bp.route('/<course_id>/live/set-status', methods=['POST'])
@auth_required
def set_live_status(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    session = dao.get_active_session_for_course(course_id)
    if not session:
        return jsonify({'success': False, 'message': '진행 중인 세션이 없습니다.'}), 404

    status = request.json.get('status', 'preparing')
    if status not in ['preparing', 'live', 'ended']:
        return jsonify({'success': False, 'message': '유효하지 않은 상태입니다.'}), 400

    update_data = {'live_status': status}
    if status == 'ended':
        update_data['ended_at'] = datetime.utcnow()
    dao.update_active_session(session['id'], update_data)

    return jsonify({
        'success': True,
        'status': status,
        'status_display': _get_live_status_display({**session, 'live_status': status})
    })


@bp.route('/<course_id>/members')
@auth_required
def members(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course_id))

    enrollments = dao.get_enrollments_by_course(course_id)

    enrollment_data = {
        'approved': [],
        'pending': [],
        'rejected': []
    }

    for enrollment in enrollments:
        u = dao.get_user(enrollment['user_id'])
        if u:
            item = {'user': u, 'enrollment': enrollment}
            status = enrollment.get('status', 'approved')
            if status in enrollment_data:
                enrollment_data[status].append(item)
            else:
                enrollment_data['approved'].append(item)

    return render_template('courses/members.html', course=course, enrollment_data=enrollment_data)


@bp.route('/<course_id>/members/add', methods=['POST'])
@auth_required
def add_course_member(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('courses.members', course_id=course_id))

    email = request.form.get('email', '').strip()
    target_user = dao.get_user_by_email(email)

    if not target_user:
        flash('해당 이메일로 등록된 사용자가 없습니다.', 'danger')
        return redirect(url_for('courses.members', course_id=course_id))

    existing = dao.get_enrollment(course_id, target_user['id'])
    if existing:
        flash('이미 등록된 사용자입니다.', 'warning')
        return redirect(url_for('courses.members', course_id=course_id))

    dao.create_enrollment({
        'course_id': course_id,
        'user_id': target_user['id'],
        'status': 'approved',
    })

    flash(f'{target_user.get("display_name", target_user.get("nickname", target_user.get("username", "")))}님이 등록되었습니다.', 'success')
    return redirect(url_for('courses.members', course_id=course_id))


@bp.route('/<course_id>/members/change-status/<user_id>', methods=['POST'])
@auth_required
def change_course_enrollment_status(course_id, user_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('courses.members', course_id=course_id))

    enrollment = dao.get_enrollment(course_id, user_id)
    if not enrollment:
        flash('등록 정보를 찾을 수 없습니다.', 'warning')
        return redirect(url_for('courses.members', course_id=course_id))

    new_status = request.form.get('status')
    target_user = dao.get_user(user_id)

    if new_status and new_status in ['approved', 'pending', 'rejected']:
        dao.update_enrollment_status(course_id, user_id, new_status)
        display_name = target_user.get('display_name', target_user.get('nickname', target_user.get('username', ''))) if target_user else ''
        flash(f'{display_name}의 상태가 변경되었습니다.', 'success')

    return redirect(url_for('courses.members', course_id=course_id))


@bp.route('/<course_id>/members/remove/<user_id>', methods=['POST'])
@auth_required
def remove_course_member(course_id, user_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('courses.members', course_id=course_id))

    enrollment = dao.get_enrollment(course_id, user_id)
    if not enrollment:
        flash('등록 정보를 찾을 수 없습니다.', 'warning')
        return redirect(url_for('courses.members', course_id=course_id))

    target_user = dao.get_user(user_id)
    dao.delete_enrollment(course_id, user_id)

    display_name = target_user.get('display_name', target_user.get('nickname', target_user.get('username', ''))) if target_user else ''
    flash(f'{display_name}님이 제외되었습니다.', 'info')
    return redirect(url_for('courses.members', course_id=course_id))


@bp.route('/<course_id>/members/approve/<user_id>', methods=['POST'])
@auth_required
def approve_course_enrollment(course_id, user_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('courses.members', course_id=course_id))

    enrollment = dao.get_enrollment(course_id, user_id)
    if not enrollment or enrollment.get('status') != 'pending':
        flash('대기 중인 등록 요청이 없습니다.', 'warning')
        return redirect(url_for('courses.members', course_id=course_id))

    dao.update_enrollment_status(course_id, user_id, 'approved')

    target_user = dao.get_user(user_id)
    display_name = target_user.get('display_name', target_user.get('nickname', target_user.get('username', ''))) if target_user else ''
    flash(f'{display_name}의 등록 신청을 승인했습니다.', 'success')
    return redirect(url_for('courses.members', course_id=course_id))


@bp.route('/<course_id>/members/reject/<user_id>', methods=['POST'])
@auth_required
def reject_course_enrollment(course_id, user_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('courses.members', course_id=course_id))

    enrollment = dao.get_enrollment(course_id, user_id)
    if not enrollment or enrollment.get('status') != 'pending':
        flash('대기 중인 등록 요청이 없습니다.', 'warning')
        return redirect(url_for('courses.members', course_id=course_id))

    dao.update_enrollment_status(course_id, user_id, 'rejected')

    target_user = dao.get_user(user_id)
    display_name = target_user.get('display_name', target_user.get('nickname', target_user.get('username', ''))) if target_user else ''
    flash(f'{display_name}의 등록 신청을 거절했습니다.', 'info')
    return redirect(url_for('courses.members', course_id=course_id))
