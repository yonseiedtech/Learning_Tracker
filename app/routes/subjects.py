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
        enrolled_subjects = Subject.query.filter_by(instructor_id=current_user.id).order_by(Subject.created_at.desc()).all()
        all_subjects = []
    else:
        enrolled_subject_ids = db.session.query(SubjectEnrollment.subject_id).filter(
            SubjectEnrollment.user_id == current_user.id
        ).all()
        enrolled_ids = [s[0] for s in enrolled_subject_ids]
        enrolled_subjects = Subject.query.filter(Subject.id.in_(enrolled_ids)).all() if enrolled_ids else []
        all_subjects = Subject.query.filter(~Subject.id.in_(enrolled_ids) if enrolled_ids else True).order_by(Subject.created_at.desc()).all()
    
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
    courses = subject.courses.order_by(Course.week_number.asc().nullslast(), Course.created_at.asc()).all()
    
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
    
    courses = subject.courses.all()
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
    if subject:
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
        
        courses = subject.courses.all()
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
