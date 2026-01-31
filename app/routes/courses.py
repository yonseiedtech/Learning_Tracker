from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, Checkpoint, Progress, ActiveSession, ChatMessage, LiveSessionPost, SubjectMember
from app.forms import CourseForm, EnrollForm
from datetime import datetime

bp = Blueprint('courses', __name__, url_prefix='/courses')

def has_course_access(course, user, roles=['instructor', 'assistant']):
    if course.instructor_id == user.id:
        return True
    if course.subject_id:
        member = SubjectMember.query.filter_by(subject_id=course.subject_id, user_id=user.id).first()
        if member and member.role in roles:
            return True
    return False

@bp.route('/')
@login_required
def list_courses():
    is_instructor = current_user.is_instructor()
    
    if is_instructor:
        my_courses = Course.query.filter_by(instructor_id=current_user.id).filter(
            Course.deleted_at.is_(None),
            Course.subject_id.is_(None)
        ).order_by(Course.created_at.desc()).all()
        enrolled_courses = []
        public_courses = []
    else:
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
        enrolled_course_ids = [e.course_id for e in enrollments]
        enrolled_courses = [e.course for e in enrollments 
                          if not e.course.deleted_at 
                          and not e.course.subject_id]
        
        public_courses = Course.query.filter(
            Course.deleted_at.is_(None),
            Course.subject_id.is_(None),
            Course.visibility == 'public',
            ~Course.id.in_(enrolled_course_ids) if enrolled_course_ids else True
        ).order_by(Course.created_at.desc()).all()
        my_courses = []
    
    return render_template('courses/list.html', 
                          my_courses=my_courses,
                          enrolled_courses=enrolled_courses,
                          public_courses=public_courses,
                          is_instructor=is_instructor)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_instructor():
        flash('강사만 세미나를 생성할 수 있습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CourseForm()
    if form.validate_on_submit():
        course = Course(
            title=form.title.data,
            description=form.description.data,
            instructor_id=current_user.id,
            invite_code=Course.generate_invite_code()
        )
        db.session.add(course)
        db.session.commit()
        flash('세미나가 생성되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/create.html', form=form)

@bp.route('/<int:course_id>')
@login_required
def view(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.deleted_at:
        if not has_course_access(course, current_user):
            flash('해당 세션을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
    
    if course.session_type in ['video', 'video_external']:
        return redirect(url_for('sessions.video_session', course_id=course_id))
    elif course.session_type == 'material':
        return redirect(url_for('sessions.material_session', course_id=course_id))
    elif course.session_type == 'assignment':
        return redirect(url_for('sessions.assignment_session', course_id=course_id))
    elif course.session_type == 'quiz':
        return redirect(url_for('sessions.quiz_session', course_id=course_id))
    
    if current_user.is_instructor():
        if not has_course_access(course, current_user):
            flash('이 세미나에 접근 권한이 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = course.get_enrolled_students()
        checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
        return render_template('courses/view_instructor.html', course=course, students=students, checkpoints=checkpoints)
    else:
        if not current_user.is_enrolled(course):
            flash('이 세미나에 등록되어 있지 않습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        if not course.is_accessible_by(current_user):
            if course.visibility == 'private':
                flash('이 세션은 현재 비공개 상태입니다.', 'warning')
            elif course.visibility == 'date_based':
                if course.start_date and datetime.utcnow() < course.start_date:
                    flash(f'이 세션은 {course.start_date.strftime("%Y-%m-%d %H:%M")}에 공개됩니다.', 'info')
                elif course.end_date and datetime.utcnow() > course.end_date:
                    flash('이 세션의 공개 기간이 종료되었습니다.', 'warning')
            elif course.visibility == 'prerequisite':
                prereq = Course.query.get(course.prerequisite_course_id)
                if prereq:
                    flash(f'이 세션에 접근하려면 먼저 "{prereq.title}" 세션을 완료해야 합니다.', 'info')
            return redirect(url_for('main.dashboard'))
        
        checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
        
        live_progress = {p.checkpoint_id: p for p in Progress.query.filter_by(
            user_id=current_user.id, mode='live'
        ).all()}
        self_progress = {p.checkpoint_id: p for p in Progress.query.filter_by(
            user_id=current_user.id, mode='self_paced'
        ).all()}
        
        active_session = ActiveSession.query.filter_by(
            course_id=course.id, ended_at=None
        ).first()
        
        return render_template('courses/view_student.html', 
                             course=course, 
                             checkpoints=checkpoints, 
                             live_progress=live_progress,
                             self_progress=self_progress,
                             active_session=active_session)

@bp.route('/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        flash('이 세미나를 수정할 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CourseForm(obj=course)
    if form.validate_on_submit():
        course.title = form.title.data
        course.description = form.description.data
        db.session.commit()
        flash('세미나가 수정되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/edit.html', form=form, course=course)

@bp.route('/<int:course_id>/delete', methods=['POST'])
@login_required
def delete(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        flash('이 세미나를 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    course.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('세미나가 삭제되었습니다!', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll():
    if current_user.is_instructor():
        flash('강사는 수강 신청을 할 수 없습니다.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    form = EnrollForm()
    if form.validate_on_submit():
        course = Course.query.filter_by(invite_code=form.invite_code.data.upper()).first()
        if not course:
            flash('유효하지 않은 초대 코드입니다.', 'danger')
            return render_template('courses/enroll.html', form=form)
        
        if course.deleted_at or course.visibility == 'private':
            flash('해당 세션에 등록할 수 없습니다.', 'danger')
            return render_template('courses/enroll.html', form=form)
        
        if current_user.is_enrolled(course):
            flash('이미 이 세미나에 등록되어 있습니다.', 'warning')
            return redirect(url_for('courses.view', course_id=course.id))
        
        enrollment = Enrollment(course_id=course.id, user_id=current_user.id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'{course.title} 세미나에 등록되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/enroll.html', form=form)

@bp.route('/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    if current_user.is_instructor():
        flash('강사는 수강 신청을 할 수 없습니다.', 'warning')
        return redirect(url_for('courses.list_courses'))
    
    course = Course.query.get_or_404(course_id)
    
    if course.deleted_at or course.visibility == 'private':
        flash('해당 세션에 등록할 수 없습니다.', 'danger')
        return redirect(url_for('courses.list_courses'))
    
    if current_user.is_enrolled(course):
        flash('이미 이 세션에 등록되어 있습니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course.id))
    
    enrollment = Enrollment(course_id=course.id, user_id=current_user.id)
    db.session.add(enrollment)
    db.session.commit()
    flash(f'{course.title} 세션에 등록되었습니다!', 'success')
    return redirect(url_for('courses.view', course_id=course.id))

@bp.route('/<int:course_id>/start-session', methods=['GET', 'POST'])
@login_required
def start_session(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        flash('강사만 세션을 시작할 수 있습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course_id))
    
    existing_session = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
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
        
        session = ActiveSession(
            course_id=course.id,
            mode='live',
            session_type=session_type,
            scheduled_at=scheduled_at,
            started_at=datetime.utcnow() if session_type == 'immediate' else None
        )
        db.session.add(session)
        db.session.commit()
        
        if session_type == 'immediate':
            flash('라이브 세션이 시작되었습니다.', 'success')
            return redirect(url_for('courses.live_mode', course_id=course_id))
        else:
            flash(f'세션이 {scheduled_at.strftime("%Y-%m-%d %H:%M")}에 예약되었습니다.', 'success')
            return redirect(url_for('courses.view', course_id=course_id))
    
    return render_template('courses/start_session.html', course=course, form=form)

@bp.route('/<int:course_id>/live')
@login_required
def live_mode(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.deleted_at:
        if not has_course_access(course, current_user):
            flash('해당 세션을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
    
    checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
    
    session = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
    if not session:
        if has_course_access(course, current_user):
            return redirect(url_for('courses.start_session', course_id=course_id))
        else:
            flash('현재 진행 중인 세션이 없습니다.', 'warning')
            return redirect(url_for('courses.view', course_id=course_id))
    
    if session.session_type == 'scheduled' and session.scheduled_at:
        if datetime.utcnow() < session.scheduled_at:
            if not current_user.is_instructor():
                flash(f'세션이 {session.scheduled_at.strftime("%Y-%m-%d %H:%M")}에 시작될 예정입니다.', 'info')
                return redirect(url_for('courses.view', course_id=course_id))
        elif not session.started_at:
            session.started_at = datetime.utcnow()
            db.session.commit()
    
    recent_messages = ChatMessage.query.filter_by(course_id=course.id).order_by(ChatMessage.created_at.desc()).limit(50).all()
    recent_messages = list(reversed(recent_messages))
    
    if current_user.is_instructor():
        if not has_course_access(course, current_user):
            flash('접근 권한이 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = course.get_enrolled_students()
        return render_template('courses/live_instructor.html', course=course, checkpoints=checkpoints, students=students, session=session, messages=recent_messages)
    else:
        if not current_user.is_enrolled(course):
            flash('이 세미나에 등록되어 있지 않습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        
        if not course.is_accessible_by(current_user):
            flash('이 세션에 접근할 수 없습니다.', 'warning')
            return redirect(url_for('main.dashboard'))
        
        from app.models import Attendance
        attendance_checked = Attendance.query.filter_by(
            course_id=course_id,
            user_id=current_user.id,
            session_id=session.id
        ).first() is not None if session else False
        
        progress_records = {p.checkpoint_id: p for p in Progress.query.filter_by(user_id=current_user.id, mode='live').all()}
        enrollments = Enrollment.query.filter_by(course_id=course_id).all()
        return render_template('courses/live_student.html', course=course, checkpoints=checkpoints, progress=progress_records, session=session, messages=recent_messages, enrollments=enrollments, attendance_checked=attendance_checked)

@bp.route('/<int:course_id>/regenerate-code', methods=['POST'])
@login_required
def regenerate_code(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        return jsonify({'error': '권한이 없습니다'}), 403
    
    course.invite_code = Course.generate_invite_code()
    db.session.commit()
    return jsonify({'invite_code': course.invite_code})

@bp.route('/<int:course_id>/settings', methods=['GET', 'POST'])
@login_required
def settings(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        flash('설정 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        setting_type = request.form.get('setting_type', 'basic')
        
        if setting_type == 'basic':
            course.title = request.form.get('title', course.title)
            course.description = request.form.get('description', course.description)
            
            order_num = request.form.get('order_number')
            course.order_number = int(order_num) if order_num else None
            
            start_date_str = request.form.get('start_date')
            if start_date_str:
                course.start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M')
            else:
                course.start_date = None
            
            end_date_str = request.form.get('end_date')
            if end_date_str:
                course.end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
            else:
                course.end_date = None
            
            attendance_start_str = request.form.get('attendance_start')
            if attendance_start_str:
                course.attendance_start = datetime.strptime(attendance_start_str, '%Y-%m-%dT%H:%M')
            else:
                course.attendance_start = None
            
            attendance_end_str = request.form.get('attendance_end')
            if attendance_end_str:
                course.attendance_end = datetime.strptime(attendance_end_str, '%Y-%m-%dT%H:%M')
            else:
                course.attendance_end = None
            
            course.late_allowed = 'late_allowed' in request.form
            late_end_str = request.form.get('late_end')
            if late_end_str and course.late_allowed:
                course.late_end = datetime.strptime(late_end_str, '%Y-%m-%dT%H:%M')
            else:
                course.late_end = None
            
            db.session.commit()
            flash('기본 설정이 저장되었습니다.', 'success')
        
        elif setting_type == 'visibility':
            visibility = request.form.get('visibility', 'public')
            course.visibility = visibility
            
            prerequisite_id = request.form.get('prerequisite_course_id')
            if prerequisite_id and prerequisite_id != '0':
                course.prerequisite_course_id = int(prerequisite_id)
            else:
                course.prerequisite_course_id = None
            
            db.session.commit()
            flash('공개 설정이 저장되었습니다.', 'success')
        
        return redirect(url_for('courses.settings', course_id=course_id))
    
    other_courses = Course.query.filter(
        Course.instructor_id == current_user.id,
        Course.id != course_id,
        Course.deleted_at.is_(None)
    ).all()
    
    return render_template('courses/settings.html', course=course, other_courses=other_courses)

@bp.route('/<int:course_id>/self-study-progress')
@login_required
def self_study_progress(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    students = course.get_enrolled_students()
    checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
    
    progress_data = {}
    for student in students:
        progress_data[student.id] = {}
        for cp in checkpoints:
            p = Progress.query.filter_by(
                user_id=student.id,
                checkpoint_id=cp.id,
                mode='self_paced'
            ).first()
            progress_data[student.id][cp.id] = p
    
    return render_template('courses/self_study_progress.html', 
                         course=course, 
                         students=students, 
                         checkpoints=checkpoints,
                         progress_data=progress_data)

@bp.route('/<int:course_id>/session-post', methods=['POST'])
@login_required
def create_session_post(course_id):
    course = Course.query.get_or_404(course_id)
    session = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
    
    if not session:
        flash('현재 진행 중인 세션이 없습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course_id))
    
    if not has_course_access(course, current_user):
        flash('강사만 공지를 작성할 수 있습니다.', 'danger')
        return redirect(url_for('courses.live_mode', course_id=course_id))
    
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    pinned = request.form.get('pinned') == 'on'
    
    if not title or not content:
        flash('제목과 내용을 입력하세요.', 'danger')
        return redirect(url_for('courses.live_mode', course_id=course_id))
    
    post = LiveSessionPost(
        session_id=session.id,
        user_id=current_user.id,
        title=title,
        content=content,
        pinned=pinned
    )
    db.session.add(post)
    db.session.commit()
    
    flash('공지가 등록되었습니다.', 'success')
    return redirect(url_for('courses.live_mode', course_id=course_id))


@bp.route('/<int:course_id>/live/set-status', methods=['POST'])
@login_required
def set_live_status(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    
    session = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
    if not session:
        return jsonify({'success': False, 'message': '진행 중인 세션이 없습니다.'}), 404
    
    status = request.json.get('status', 'preparing')
    if status not in ['preparing', 'live', 'ended']:
        return jsonify({'success': False, 'message': '유효하지 않은 상태입니다.'}), 400
    
    session.live_status = status
    if status == 'ended':
        session.ended_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'success': True,
        'status': status,
        'status_display': session.get_live_status_display()
    })
