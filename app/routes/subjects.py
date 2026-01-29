from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Subject, Course, Enrollment
from app.forms import SubjectForm
from datetime import datetime

bp = Blueprint('subjects', __name__, url_prefix='/subjects')

@bp.route('/')
@login_required
def list_subjects():
    if current_user.is_instructor():
        subjects = Subject.query.filter_by(instructor_id=current_user.id).order_by(Subject.created_at.desc()).all()
    else:
        enrolled_subject_ids = db.session.query(Course.subject_id).join(Enrollment).filter(
            Enrollment.user_id == current_user.id,
            Course.subject_id.isnot(None)
        ).distinct().all()
        subject_ids = [s[0] for s in enrolled_subject_ids if s[0]]
        subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all() if subject_ids else []
    return render_template('subjects/list.html', subjects=subjects)

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
        for course in courses:
            if current_user.is_enrolled(course):
                is_enrolled = True
                break
    
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

@bp.route('/enroll', methods=['POST'])
@login_required
def enroll():
    invite_code = request.form.get('invite_code', '').strip().upper()
    if not invite_code:
        flash('초대 코드를 입력하세요.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    subject = Subject.query.filter_by(invite_code=invite_code).first()
    if subject:
        courses = subject.courses.all()
        if not courses:
            flash('해당 과목에 등록된 세션이 없습니다.', 'warning')
            return redirect(url_for('main.dashboard'))
        
        enrolled_count = 0
        for course in courses:
            if not current_user.is_enrolled(course):
                enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
                db.session.add(enrollment)
                enrolled_count += 1
        
        if enrolled_count > 0:
            db.session.commit()
            flash(f'{subject.title} 과목의 {enrolled_count}개 세션에 등록되었습니다.', 'success')
        else:
            flash('이미 해당 과목에 등록되어 있습니다.', 'info')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    
    flash('유효하지 않은 초대 코드입니다.', 'danger')
    return redirect(url_for('main.dashboard'))
