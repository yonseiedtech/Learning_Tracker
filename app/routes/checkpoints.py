from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Checkpoint
from app.forms import CheckpointForm
from datetime import datetime

bp = Blueprint('checkpoints', __name__, url_prefix='/checkpoints')

@bp.route('/course/<int:course_id>/create', methods=['GET', 'POST'])
@login_required
def create(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('Permission denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CheckpointForm()
    if form.validate_on_submit():
        max_order = db.session.query(db.func.max(Checkpoint.order)).filter_by(course_id=course_id).scalar() or 0
        checkpoint = Checkpoint(
            course_id=course_id,
            title=form.title.data,
            description=form.description.data,
            estimated_minutes=form.estimated_minutes.data,
            order=max_order + 1
        )
        db.session.add(checkpoint)
        db.session.commit()
        flash('Checkpoint created successfully!', 'success')
        return redirect(url_for('courses.view', course_id=course_id))
    
    return render_template('checkpoints/create.html', form=form, course=course)

@bp.route('/<int:checkpoint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    if course.instructor_id != current_user.id:
        flash('Permission denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CheckpointForm(obj=checkpoint)
    if form.validate_on_submit():
        checkpoint.title = form.title.data
        checkpoint.description = form.description.data
        checkpoint.estimated_minutes = form.estimated_minutes.data
        db.session.commit()
        flash('Checkpoint updated successfully!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('checkpoints/edit.html', form=form, checkpoint=checkpoint, course=course)

@bp.route('/<int:checkpoint_id>/delete', methods=['POST'])
@login_required
def delete(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    if course.instructor_id != current_user.id:
        flash('Permission denied.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    checkpoint.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('Checkpoint deleted successfully!', 'success')
    return redirect(url_for('courses.view', course_id=course.id))

@bp.route('/reorder', methods=['POST'])
@login_required
def reorder():
    data = request.get_json()
    if not data or 'checkpoints' not in data:
        return jsonify({'error': 'Invalid data'}), 400
    
    for item in data['checkpoints']:
        checkpoint = Checkpoint.query.get(item['id'])
        if checkpoint and checkpoint.course.instructor_id == current_user.id:
            checkpoint.order = item['order']
    
    db.session.commit()
    return jsonify({'success': True})
