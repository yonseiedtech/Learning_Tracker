from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, Checkpoint, Progress
from app.forms import CourseForm, EnrollForm

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
        flash('Only instructors can create courses.', 'danger')
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
        flash('Course created successfully!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/create.html', form=form)

@bp.route('/<int:course_id>')
@login_required
def view(course_id):
    course = Course.query.get_or_404(course_id)
    
    if current_user.is_instructor():
        if course.instructor_id != current_user.id:
            flash('You do not have access to this course.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = course.get_enrolled_students()
        checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
        return render_template('courses/view_instructor.html', course=course, students=students, checkpoints=checkpoints)
    else:
        if not current_user.is_enrolled(course):
            flash('You are not enrolled in this course.', 'danger')
            return redirect(url_for('main.dashboard'))
        checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
        progress_records = {p.checkpoint_id: p for p in Progress.query.filter_by(user_id=current_user.id).all()}
        return render_template('courses/view_student.html', course=course, checkpoints=checkpoints, progress=progress_records)

@bp.route('/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('You do not have permission to edit this course.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CourseForm(obj=course)
    if form.validate_on_submit():
        course.title = form.title.data
        course.description = form.description.data
        db.session.commit()
        flash('Course updated successfully!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/edit.html', form=form, course=course)

@bp.route('/<int:course_id>/delete', methods=['POST'])
@login_required
def delete(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('You do not have permission to delete this course.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    db.session.delete(course)
    db.session.commit()
    flash('Course deleted successfully!', 'success')
    return redirect(url_for('main.dashboard'))

@bp.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll():
    if current_user.is_instructor():
        flash('Instructors cannot enroll in courses.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    form = EnrollForm()
    if form.validate_on_submit():
        course = Course.query.filter_by(invite_code=form.invite_code.data.upper()).first()
        if not course:
            flash('Invalid invite code.', 'danger')
            return render_template('courses/enroll.html', form=form)
        
        if current_user.is_enrolled(course):
            flash('You are already enrolled in this course.', 'warning')
            return redirect(url_for('courses.view', course_id=course.id))
        
        enrollment = Enrollment(course_id=course.id, user_id=current_user.id)
        db.session.add(enrollment)
        db.session.commit()
        flash(f'Successfully enrolled in {course.title}!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('courses/enroll.html', form=form)

@bp.route('/<int:course_id>/live')
@login_required
def live_mode(course_id):
    course = Course.query.get_or_404(course_id)
    checkpoints = Checkpoint.query.filter_by(course_id=course.id, deleted_at=None).order_by(Checkpoint.order).all()
    
    if current_user.is_instructor():
        if course.instructor_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('main.dashboard'))
        students = course.get_enrolled_students()
        return render_template('courses/live_instructor.html', course=course, checkpoints=checkpoints, students=students)
    else:
        if not current_user.is_enrolled(course):
            flash('You are not enrolled in this course.', 'danger')
            return redirect(url_for('main.dashboard'))
        progress_records = {p.checkpoint_id: p for p in Progress.query.filter_by(user_id=current_user.id, mode='live').all()}
        return render_template('courses/live_student.html', course=course, checkpoints=checkpoints, progress=progress_records)

@bp.route('/<int:course_id>/regenerate-code', methods=['POST'])
@login_required
def regenerate_code(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    
    course.invite_code = Course.generate_invite_code()
    db.session.commit()
    return jsonify({'invite_code': course.invite_code})
