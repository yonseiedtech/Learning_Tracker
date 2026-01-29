from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Course, Checkpoint
from app.forms import CheckpointForm
from datetime import datetime
import traceback

bp = Blueprint('checkpoints', __name__, url_prefix='/checkpoints')

@bp.route('/course/<int:course_id>/create', methods=['GET', 'POST'])
@login_required
def create(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('권한이 없습니다.', 'danger')
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
        flash('체크포인트가 추가되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course_id))
    
    return render_template('checkpoints/create.html', form=form, course=course)

@bp.route('/<int:checkpoint_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    if course.instructor_id != current_user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = CheckpointForm(obj=checkpoint)
    if form.validate_on_submit():
        checkpoint.title = form.title.data
        checkpoint.description = form.description.data
        checkpoint.estimated_minutes = form.estimated_minutes.data
        db.session.commit()
        flash('체크포인트가 수정되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course.id))
    
    return render_template('checkpoints/edit.html', form=form, checkpoint=checkpoint, course=course)

@bp.route('/<int:checkpoint_id>/delete', methods=['POST'])
@login_required
def delete(checkpoint_id):
    checkpoint = Checkpoint.query.get_or_404(checkpoint_id)
    course = checkpoint.course
    if course.instructor_id != current_user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    checkpoint.deleted_at = datetime.utcnow()
    db.session.commit()
    flash('체크포인트가 삭제되었습니다!', 'success')
    return redirect(url_for('courses.view', course_id=course.id))


@bp.route('/course/<int:course_id>/bulk-delete', methods=['POST'])
@login_required
def bulk_delete(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    data = request.get_json()
    checkpoint_ids = data.get('checkpoint_ids', [])
    delete_all = data.get('delete_all', False)
    
    if delete_all:
        checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).all()
    else:
        checkpoints = Checkpoint.query.filter(
            Checkpoint.id.in_(checkpoint_ids),
            Checkpoint.course_id == course_id,
            Checkpoint.deleted_at == None
        ).all()
    
    deleted_count = 0
    for cp in checkpoints:
        cp.deleted_at = datetime.utcnow()
        deleted_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'deleted_count': deleted_count
    })

@bp.route('/reorder', methods=['POST'])
@login_required
def reorder():
    data = request.get_json()
    if not data or 'checkpoints' not in data:
        return jsonify({'error': '잘못된 데이터입니다'}), 400
    
    for item in data['checkpoints']:
        checkpoint = Checkpoint.query.get(item['id'])
        if checkpoint and checkpoint.course.instructor_id == current_user.id:
            checkpoint.order = item['order']
    
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/course/<int:course_id>/ai-generate', methods=['GET', 'POST'])
@login_required
def ai_generate(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        return redirect(url_for('checkpoints.ai_generate', course_id=course_id))
    
    return render_template('checkpoints/ai_generate.html', course=course)


@bp.route('/course/<int:course_id>/ai-generate/upload', methods=['POST'])
@login_required
def ai_generate_upload(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    try:
        from app.services.ai_checkpoint import CheckpointGenerator
        
        source_type = request.form.get('source_type', 'ppt')
        file = request.files.get('file')
        text_content = request.form.get('text_content', '')
        
        checkpoints = []
        transcript = None
        
        if source_type == 'text' and text_content:
            checkpoints = CheckpointGenerator.generate_from_text(text_content)
        elif file:
            file_data = file.read()
            filename = file.filename or 'unknown'
            
            if source_type == 'ppt':
                checkpoints = CheckpointGenerator.generate_checkpoints_from_ppt(file_data, filename)
            elif source_type == 'video':
                mime_type = file.content_type or 'video/mp4'
                checkpoints, transcript = CheckpointGenerator.generate_checkpoints_from_media(file_data, mime_type)
            elif source_type == 'audio':
                mime_type = file.content_type or 'audio/mpeg'
                checkpoints, transcript = CheckpointGenerator.generate_checkpoints_from_media(file_data, mime_type)
        
        return jsonify({
            'success': True,
            'checkpoints': checkpoints,
            'transcript': transcript
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@bp.route('/course/<int:course_id>/ai-generate/save', methods=['POST'])
@login_required
def ai_generate_save(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403
    
    data = request.get_json()
    checkpoints_data = data.get('checkpoints', [])
    
    if not checkpoints_data:
        return jsonify({'error': '체크포인트가 없습니다.'}), 400
    
    max_order = db.session.query(db.func.max(Checkpoint.order)).filter_by(course_id=course_id).scalar() or 0
    
    created_count = 0
    for cp_data in checkpoints_data:
        max_order += 1
        checkpoint = Checkpoint(
            course_id=course_id,
            title=cp_data.get('title', ''),
            description=cp_data.get('description', ''),
            estimated_minutes=cp_data.get('estimated_minutes', 5),
            order=max_order
        )
        db.session.add(checkpoint)
        created_count += 1
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'created_count': created_count,
        'redirect_url': url_for('courses.view', course_id=course_id)
    })
