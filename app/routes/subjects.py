from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Subject, Course, Enrollment, SubjectEnrollment
from app.forms import SubjectForm
from datetime import datetime

bp = Blueprint('subjects', __name__, url_prefix='/subjects')

@bp.route('/')
@login_required
def list_subjects():
    if current_user.is_instructor():
        enrolled_subjects = Subject.query.filter_by(instructor_id=current_user.id).filter(Subject.deleted_at.is_(None)).order_by(Subject.created_at.desc()).all()
        all_subjects = []
    else:
        enrolled_subject_ids = db.session.query(SubjectEnrollment.subject_id).filter(
            SubjectEnrollment.user_id == current_user.id
        ).all()
        enrolled_ids = [s[0] for s in enrolled_subject_ids]
        enrolled_subjects = Subject.query.filter(Subject.id.in_(enrolled_ids), Subject.deleted_at.is_(None), Subject.is_visible == True).all() if enrolled_ids else []
        all_subjects = Subject.query.filter(
            ~Subject.id.in_(enrolled_ids) if enrolled_ids else True,
            Subject.deleted_at.is_(None),
            Subject.is_visible == True
        ).order_by(Subject.created_at.desc()).all()
    
    return render_template('subjects/list.html', 
                          enrolled_subjects=enrolled_subjects, 
                          all_subjects=all_subjects,
                          is_instructor=current_user.is_instructor())

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_instructor():
        flash('강사만 과목을 생성할 수 있습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            title=form.title.data,
            description=form.description.data,
            instructor_id=current_user.id,
            invite_code=Subject.generate_invite_code()
        )
        db.session.add(subject)
        db.session.commit()
        flash('과목이 생성되었습니다.', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    return render_template('subjects/create.html', form=form)

@bp.route('/<int:subject_id>')
@login_required
def view(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    if subject.deleted_at:
        if not (current_user.is_instructor() and subject.instructor_id == current_user.id):
            flash('해당 과목을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('subjects.list_subjects'))
    
    if not subject.is_visible:
        if not (current_user.is_instructor() and subject.instructor_id == current_user.id):
            flash('해당 과목은 비공개 상태입니다.', 'warning')
            return redirect(url_for('subjects.list_subjects'))
    
    courses = subject.courses.filter(Course.deleted_at.is_(None)).order_by(Course.week_number.asc().nullslast(), Course.created_at.asc()).all()
    
    is_enrolled = False
    if not current_user.is_instructor():
        subject_enrollment = SubjectEnrollment.query.filter_by(
            subject_id=subject_id, 
            user_id=current_user.id
        ).first()
        is_enrolled = subject_enrollment is not None
    
    return render_template('subjects/view.html', subject=subject, courses=courses, is_enrolled=is_enrolled)

@bp.route('/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject.title = form.title.data
        subject.description = form.description.data
        db.session.commit()
        flash('과목이 수정되었습니다.', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    return render_template('subjects/edit.html', form=form, subject=subject)

@bp.route('/<int:subject_id>/add-course', methods=['GET', 'POST'])
@login_required
def add_course(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    from app.forms import CourseForm
    
    class WeekCourseForm(CourseForm):
        pass
    
    form = WeekCourseForm()
    
    if form.validate_on_submit():
        next_week = subject.courses.count() + 1
        course = Course(
            title=form.title.data,
            description=form.description.data,
            instructor_id=current_user.id,
            subject_id=subject.id,
            week_number=next_week,
            invite_code=Course.generate_invite_code()
        )
        db.session.add(course)
        db.session.commit()
        flash(f'{next_week}주차 세션이 추가되었습니다.', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    
    return render_template('subjects/add_course.html', form=form, subject=subject)

@bp.route('/<int:subject_id>/regenerate-code', methods=['POST'])
@login_required
def regenerate_code(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.instructor_id != current_user.id:
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    
    subject.invite_code = Subject.generate_invite_code()
    db.session.commit()
    return jsonify({'success': True, 'invite_code': subject.invite_code})

@bp.route('/<int:subject_id>/enroll', methods=['POST'])
@login_required
def enroll_subject(subject_id):
    if current_user.is_instructor():
        flash('강사는 과목 등록을 할 수 없습니다.', 'warning')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject = Subject.query.get_or_404(subject_id)
    
    if subject.deleted_at or not subject.is_visible:
        flash('해당 과목에 등록할 수 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    existing_enrollment = SubjectEnrollment.query.filter_by(
        subject_id=subject_id,
        user_id=current_user.id
    ).first()
    
    if existing_enrollment:
        flash('이미 해당 과목에 등록되어 있습니다.', 'info')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject_enrollment = SubjectEnrollment(
        subject_id=subject_id,
        user_id=current_user.id
    )
    db.session.add(subject_enrollment)
    
    courses = subject.courses.filter(Course.deleted_at.is_(None), Course.visibility != 'private').all()
    enrolled_count = 0
    for course in courses:
        if not current_user.is_enrolled(course):
            enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
            db.session.add(enrollment)
            enrolled_count += 1
    
    db.session.commit()
    flash(f'{subject.title} 과목에 등록되었습니다. ({enrolled_count}개 세션 자동 등록)', 'success')
    return redirect(url_for('subjects.view', subject_id=subject_id))


@bp.route('/<int:subject_id>/unenroll', methods=['POST'])
@login_required
def unenroll_subject(subject_id):
    if current_user.is_instructor():
        flash('강사는 과목 등록 취소를 할 수 없습니다.', 'warning')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject = Subject.query.get_or_404(subject_id)
    
    subject_enrollment = SubjectEnrollment.query.filter_by(
        subject_id=subject_id,
        user_id=current_user.id
    ).first()
    
    if not subject_enrollment:
        flash('해당 과목에 등록되어 있지 않습니다.', 'warning')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    db.session.delete(subject_enrollment)
    
    courses = subject.courses.all()
    for course in courses:
        enrollment = Enrollment.query.filter_by(
            course_id=course.id,
            user_id=current_user.id
        ).first()
        if enrollment:
            db.session.delete(enrollment)
    
    db.session.commit()
    flash(f'{subject.title} 과목 등록이 취소되었습니다.', 'success')
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/enroll-by-code', methods=['POST'])
@login_required
def enroll_by_code():
    if current_user.is_instructor():
        flash('강사는 과목 등록을 할 수 없습니다.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    invite_code = request.form.get('invite_code', '').strip().upper()
    if not invite_code:
        flash('초대 코드를 입력하세요.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    subject = Subject.query.filter_by(invite_code=invite_code).first()
    if subject and not subject.deleted_at and subject.is_visible:
        existing_enrollment = SubjectEnrollment.query.filter_by(
            subject_id=subject.id,
            user_id=current_user.id
        ).first()
        
        if existing_enrollment:
            flash('이미 해당 과목에 등록되어 있습니다.', 'info')
            return redirect(url_for('subjects.view', subject_id=subject.id))
        
        subject_enrollment = SubjectEnrollment(
            subject_id=subject.id,
            user_id=current_user.id
        )
        db.session.add(subject_enrollment)
        
        courses = subject.courses.filter(Course.deleted_at.is_(None), Course.visibility != 'private').all()
        enrolled_count = 0
        for course in courses:
            if not current_user.is_enrolled(course):
                enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
                db.session.add(enrollment)
                enrolled_count += 1
        
        db.session.commit()
        flash(f'{subject.title} 과목에 등록되었습니다. ({enrolled_count}개 세션 자동 등록)', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    
    flash('유효하지 않은 초대 코드입니다.', 'danger')
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    subject.deleted_at = datetime.now()
    db.session.commit()
    flash(f'{subject.title} 과목이 삭제되었습니다.', 'success')
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/<int:subject_id>/toggle-visibility', methods=['POST'])
@login_required
def toggle_subject_visibility(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject.is_visible = not subject.is_visible
    db.session.commit()
    status = '공개' if subject.is_visible else '비공개'
    flash(f'{subject.title} 과목이 {status}로 변경되었습니다.', 'success')
    return redirect(url_for('subjects.view', subject_id=subject_id))


@bp.route('/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    subject_id = course.subject_id
    course.deleted_at = datetime.now()
    db.session.commit()
    flash(f'{course.title} 세션이 삭제되었습니다.', 'success')
    
    if subject_id:
        return redirect(url_for('subjects.view', subject_id=subject_id))
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/course/<int:course_id>/toggle-visibility', methods=['POST'])
@login_required
def toggle_course_visibility(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    if course.visibility == 'private':
        course.visibility = 'public'
        status = '공개'
    else:
        course.visibility = 'private'
        status = '비공개'
    db.session.commit()
    flash(f'{course.title} 세션이 {status}로 변경되었습니다.', 'success')
    
    if course.subject_id:
        return redirect(url_for('subjects.view', subject_id=course.subject_id))
    return redirect(url_for('courses.view', course_id=course_id))
