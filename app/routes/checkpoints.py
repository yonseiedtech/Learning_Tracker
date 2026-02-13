from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app.forms import CheckpointForm
from datetime import datetime
import traceback

bp = Blueprint('checkpoints', __name__, url_prefix='/checkpoints')


@bp.route('/course/<course_id>/create', methods=['GET', 'POST'])
@auth_required
def create(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    form = CheckpointForm()
    if form.validate_on_submit():
        max_order = dao.get_max_order(course_id) or 0
        dao.create_checkpoint({
            'course_id': course_id,
            'title': form.title.data,
            'description': form.description.data,
            'estimated_minutes': form.estimated_minutes.data,
            'order': max_order + 1,
            'created_at': datetime.utcnow(),
        })
        flash('체크포인트가 추가되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course_id))

    return render_template('checkpoints/create.html', form=form, course=course)


@bp.route('/<checkpoint_id>/edit', methods=['GET', 'POST'])
@auth_required
def edit(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        abort(404)

    course = dao.get_course(checkpoint['course_id'])
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    form = CheckpointForm(data=checkpoint)
    if form.validate_on_submit():
        dao.update_checkpoint(checkpoint_id, {
            'title': form.title.data,
            'description': form.description.data,
            'estimated_minutes': form.estimated_minutes.data,
        })
        flash('체크포인트가 수정되었습니다!', 'success')
        return redirect(url_for('courses.view', course_id=course['id']))

    return render_template('checkpoints/edit.html', form=form, checkpoint=checkpoint, course=course)


@bp.route('/<checkpoint_id>/delete', methods=['POST'])
@auth_required
def delete(checkpoint_id):
    user = get_current_user()
    checkpoint = dao.get_checkpoint(checkpoint_id)
    if not checkpoint:
        abort(404)

    course = dao.get_course(checkpoint['course_id'])
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        dao.update_checkpoint(checkpoint_id, {'deleted_at': datetime.utcnow()})
        flash('체크포인트가 삭제되었습니다!', 'success')
    except Exception:
        flash('체크포인트 삭제 중 오류가 발생했습니다.', 'danger')
    return redirect(url_for('courses.view', course_id=course['id']))


@bp.route('/course/<course_id>/bulk-delete', methods=['POST'])
@auth_required
def bulk_delete(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    checkpoint_ids = data.get('checkpoint_ids', [])
    delete_all = data.get('delete_all', False)

    checkpoints = dao.get_checkpoints_by_course(course_id)

    deleted_count = 0
    for cp in checkpoints:
        if cp.get('deleted_at'):
            continue
        if delete_all or cp['id'] in checkpoint_ids:
            dao.update_checkpoint(cp['id'], {'deleted_at': datetime.utcnow()})
            deleted_count += 1

    return jsonify({
        'success': True,
        'deleted_count': deleted_count
    })


@bp.route('/reorder', methods=['POST'])
@auth_required
def reorder():
    user = get_current_user()
    data = request.get_json()
    if not data or 'checkpoints' not in data:
        return jsonify({'error': '잘못된 데이터입니다'}), 400

    for item in data['checkpoints']:
        checkpoint = dao.get_checkpoint(item['id'])
        if not checkpoint:
            continue
        course = dao.get_course(checkpoint['course_id'])
        if course and course['instructor_id'] == user.id:
            dao.update_checkpoint(item['id'], {'order': item['order']})

    return jsonify({'success': True})


@bp.route('/course/<course_id>/ai-generate', methods=['GET', 'POST'])
@auth_required
def ai_generate(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        return redirect(url_for('checkpoints.ai_generate', course_id=course_id))

    return render_template('checkpoints/ai_generate.html', course=course)


@bp.route('/course/<course_id>/ai-generate/upload', methods=['POST'])
@auth_required
def ai_generate_upload(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
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


@bp.route('/course/<course_id>/ai-generate/save', methods=['POST'])
@auth_required
def ai_generate_save(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if course['instructor_id'] != user.id:
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    checkpoints_data = data.get('checkpoints', [])

    if not checkpoints_data:
        return jsonify({'error': '체크포인트가 없습니다.'}), 400

    max_order = dao.get_max_order(course_id) or 0

    created_count = 0
    for cp_data in checkpoints_data:
        max_order += 1
        dao.create_checkpoint({
            'course_id': course_id,
            'title': cp_data.get('title', ''),
            'description': cp_data.get('description', ''),
            'estimated_minutes': cp_data.get('estimated_minutes', 5),
            'order': max_order,
            'created_at': datetime.utcnow(),
        })
        created_count += 1

    return jsonify({
        'success': True,
        'created_count': created_count,
        'redirect_url': url_for('courses.view', course_id=course_id)
    })
