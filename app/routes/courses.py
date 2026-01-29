from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, Checkpoint, Progress, ActiveSession, ChatMessage, LiveSessionPost
from app.forms import CourseForm, EnrollForm
from datetime import datetime

bp = Blueprint('courses', __name__, url_prefix='/courses')

@bp.route('/')
@login_required
def list_courses():
    if current_user.is_instructor():
        courses = Course.query.filter_by(instructor_id=current_user.id).all()
    else:
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
        courses = [e.course for e in enrollments]
    return render_template('courses/list.html', courses=courses)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_instructor():
        flash('강사만 강좌를 생성할 수 있습니다.', 'danger')
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
        flash('강좌가 생성되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/create.html', form=form)

@bp.route('/<int:course_id>')
@login_required
def view(course_id):
    course = Course.query.get_or_404(course_id)
    
    if current_user.is_instructor():
        if course.instructor_id != current_user.id:
            flash('이 강좌에 접근 권한이 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = course.get_enrolled_students()
        checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
        return render_template('courses/view_instructor.html', course=course, students=students, checkpoints=checkpoints)
    else:
        if not current_user.is_enrolled(course):
            flash('이 강좌에 등록되어 있지 않습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
        progress_records = {p.checkpoint_id: p for p in Progress.query.filter_by(user_id=current_user.id).all()}
        return render_template('courses/view_student.html', course=course, checkpoints=checkpoints, progress=progress_records)

@bp.route('/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('이 강좌를 수정할 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CourseForm(obj=course)
    if form.validate_on_submit():
        course.title = form.title.data
        course.description = form.description.data
        db.session.commit()
        flash('강좌가 수정되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/edit.html', form=form, course=course)

@bp.route('/<int:course_id>/delete', methods=['POST'])
@login_required
def delete(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('이 강좌를 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    db.session.delete(course)
    db.session.commit()
    flash('강좌가 삭제되었습니다!', 'success')
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
        
        if current_user.is_enrolled(course):
            flash('이미 이 강좌에 등록되어 있습니다.', 'warning')
            return redirect(url_for('courses.view', course_id=course.id))
        
        enrollment = Enrollment(course_id=course.id, user_id=current_user.id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'{course.title} 강좌에 등록되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/enroll.html', form=form)

@bp.route('/<int:course_id>/start-session', methods=['GET', 'POST'])
@login_required
def start_session(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
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
    checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
    
    session = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
    if not session:
        if current_user.is_instructor() and course.instructor_id == current_user.id:
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
        if course.instructor_id != current_user.id:
            flash('접근 권한이 없습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = course.get_enrolled_students()
        return render_template('courses/live_instructor.html', course=course, checkpoints=checkpoints, students=students, session=session, messages=recent_messages)
    else:
        if not current_user.is_enrolled(course):
            flash('이 강좌에 등록되어 있지 않습니다.', 'danger')
            return redirect(url_for('main.dashboard'))
        progress_records = {p.checkpoint_id: p for p in Progress.query.filter_by(user_id=current_user.id, mode='live').all()}
        enrollments = Enrollment.query.filter_by(course_id=course_id).all()
        return render_template('courses/live_student.html', course=course, checkpoints=checkpoints, progress=progress_records, session=session, messages=recent_messages, enrollments=enrollments)

@bp.route('/<int:course_id>/regenerate-code', methods=['POST'])
@login_required
def regenerate_code(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': '권한이 없습니다'}), 403
    
    course.invite_code = Course.generate_invite_code()
    db.session.commit()
    return jsonify({'invite_code': course.invite_code})

@bp.route('/<int:course_id>/session-post', methods=['POST'])
@login_required
def create_session_post(course_id):
    course = Course.query.get_or_404(course_id)
    session = ActiveSession.query.filter_by(course_id=course.id, ended_at=None).first()
    
    if not session:
        flash('현재 진행 중인 세션이 없습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course_id))
    
    if not current_user.is_instructor() or course.instructor_id != current_user.id:
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
