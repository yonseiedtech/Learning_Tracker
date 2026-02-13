from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app.services.slide_converter import convert_file_to_images, ALLOWED_EXTENSIONS
from app.services.storage import get_slide_image_url, upload_slide_image, delete_slide_deck_images
from datetime import datetime
import traceback
import tempfile
import os

bp = Blueprint('slides', __name__, url_prefix='/slides')


def has_course_access(course, user):
    if course['instructor_id'] == user['uid']:
        return True
    if course.get('subject_id'):
        member = dao.get_subject_member(course['subject_id'], user['uid'])
        if member and member['role'] in ['instructor', 'assistant']:
            return True
    return False


@bp.route('/<deck_id>/<path:filename>')
@auth_required
def serve_slide_image(deck_id, filename):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    if not course:
        abort(404)
    user = get_current_user()
    enrolled = dao.is_enrolled(user['uid'], course['id'])
    is_instructor = has_course_access(course, user)
    if not enrolled and not is_instructor:
        abort(403)
    # Extract slide index from filename (e.g., "3.png" -> 3)
    try:
        slide_index = int(os.path.splitext(filename)[0])
    except (ValueError, IndexError):
        abort(404)
    signed_url = get_slide_image_url(deck_id, slide_index)
    if not signed_url:
        abort(404)
    return redirect(signed_url)


@bp.route('/upload/<course_id>', methods=['POST'])
@auth_required
def upload_pptx(course_id):
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    user = get_current_user()
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    file = request.files.get('pptx_file') or request.files.get('slide_file')
    if not file or not file.filename:
        return jsonify({'error': '파일을 선택해주세요.'}), 400

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': '.pptx, .ppt 또는 .pdf 파일만 업로드 가능합니다.'}), 400

    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        return jsonify({'error': f'파일 크기가 50MB를 초과합니다. ({file_size // (1024*1024)}MB)'}), 400

    active_session = dao.get_active_session_for_course(course_id)

    estimated_duration = request.form.get('estimated_duration_minutes', type=int)

    deck_data = {
        'course_id': course_id,
        'session_id': active_session['id'] if active_session else None,
        'file_name': file.filename,
        'conversion_status': 'converting',
        'estimated_duration_minutes': estimated_duration if estimated_duration and estimated_duration > 0 else None,
        'slide_count': 0,
        'current_slide_index': 0,
        'created_at': datetime.utcnow().isoformat()
    }
    deck_id = dao.create_slide_deck(deck_data)

    try:
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        slide_count, deck_dir = convert_file_to_images(tmp_path, deck_id)

        # Upload each slide image to Firebase Storage
        for i in range(slide_count):
            img_path = os.path.join(deck_dir, f'{i}.png')
            if os.path.exists(img_path):
                with open(img_path, 'rb') as img_file:
                    image_data = img_file.read()
                upload_slide_image(deck_id, i, image_data)

        dao.update_slide_deck(deck_id, {
            'slide_count': slide_count,
            'conversion_status': 'completed'
        })

        os.unlink(tmp_path)

        slide_urls = [get_slide_image_url(deck_id, i) for i in range(slide_count)]

        return jsonify({
            'success': True,
            'deck_id': deck_id,
            'slide_count': slide_count,
            'slides': slide_urls,
            'message': f'{slide_count}개의 슬라이드가 변환되었습니다.'
        })

    except Exception as e:
        dao.update_slide_deck(deck_id, {
            'conversion_status': 'failed',
            'conversion_error': str(e)
        })
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'error': f'변환 실패: {str(e)}'}), 500


@bp.route('/delete/<deck_id>', methods=['POST'])
@auth_required
def delete_deck(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    delete_slide_deck_images(deck_id, deck['slide_count'])
    dao.delete_slide_deck(deck_id)

    return jsonify({'success': True, 'message': '슬라이드 덱이 삭제되었습니다.'})


@bp.route('/presenter/<deck_id>')
@auth_required
def presenter_view(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        flash('강사만 프레젠터 뷰를 사용할 수 있습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course['id']))

    slides = [get_slide_image_url(deck_id, i) for i in range(deck['slide_count'])]
    bookmarks_list = dao.get_bookmarks_by_deck(deck_id)
    bookmarks = {b['slide_index']: b for b in bookmarks_list}

    return render_template('sessions/slide_presenter.html',
                         deck=deck,
                         course=course,
                         slides=slides,
                         bookmarks=bookmarks)


@bp.route('/viewer/<deck_id>')
@auth_required
def viewer_view(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()

    enrolled = dao.is_enrolled(user['uid'], course['id'])
    is_instructor = has_course_access(course, user)

    if not enrolled and not is_instructor:
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if is_instructor:
        return redirect(url_for('slides.presenter_view', deck_id=deck_id))

    slides = [get_slide_image_url(deck_id, i) for i in range(deck['slide_count'])]

    my_reactions = {}
    reactions = dao.get_reactions_by_deck(deck_id)
    for r in reactions:
        if r['user_id'] == user['uid']:
            my_reactions[r['slide_index']] = r['reaction']

    return render_template('sessions/slide_viewer.html',
                         deck=deck,
                         course=course,
                         slides=slides,
                         my_reactions=my_reactions)


@bp.route('/review/<deck_id>')
@auth_required
def review_view(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        flash('강사만 리뷰 페이지에 접근할 수 있습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course['id']))

    slides = [get_slide_image_url(deck_id, i) for i in range(deck['slide_count'])]
    bookmarks_list = dao.get_bookmarks_by_deck(deck_id)
    bookmarks = {b['slide_index']: b for b in bookmarks_list}

    aggregates = {}
    for i in range(deck['slide_count']):
        counts = dao.count_reactions(deck_id, i)
        understood = counts.get('understood', 0) if isinstance(counts, dict) else 0
        question = counts.get('question', 0) if isinstance(counts, dict) else 0
        hard = counts.get('hard', 0) if isinstance(counts, dict) else 0
        total_reacted = understood + question + hard
        aggregates[i] = {
            'understood': understood,
            'question': question,
            'hard': hard,
            'total_reacted': total_reacted
        }

    return render_template('sessions/slide_review.html',
                         deck=deck,
                         course=course,
                         slides=slides,
                         bookmarks=bookmarks,
                         aggregates=aggregates)


@bp.route('/review/<deck_id>/save-memo', methods=['POST'])
@auth_required
def save_bookmark_memo(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    slide_index = data.get('slide_index')
    memo = data.get('memo', '')
    supplement_url = data.get('supplement_url', '')

    bookmark = dao.get_slide_bookmark(deck_id, slide_index)
    if not bookmark:
        dao.create_or_update_bookmark(deck_id, slide_index, {
            'deck_id': deck_id,
            'slide_index': slide_index,
            'is_manual': True,
            'memo': memo,
            'supplement_url': supplement_url
        })
    else:
        dao.create_or_update_bookmark(deck_id, slide_index, {
            'memo': memo,
            'supplement_url': supplement_url
        })

    return jsonify({'success': True})


@bp.route('/review/<deck_id>/toggle-bookmark', methods=['POST'])
@auth_required
def toggle_manual_bookmark(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    slide_index = data.get('slide_index')

    bookmark = dao.get_slide_bookmark(deck_id, slide_index)
    if bookmark:
        if bookmark.get('is_auto') and not bookmark.get('is_manual'):
            dao.create_or_update_bookmark(deck_id, slide_index, {'is_manual': True})
        elif bookmark.get('is_manual') and not bookmark.get('is_auto'):
            dao.delete_bookmark(deck_id, slide_index)
        else:
            dao.create_or_update_bookmark(deck_id, slide_index, {'is_manual': not bookmark.get('is_manual', False)})
    else:
        dao.create_or_update_bookmark(deck_id, slide_index, {
            'deck_id': deck_id,
            'slide_index': slide_index,
            'is_manual': True
        })

    return jsonify({'success': True})


@bp.route('/deck/<course_id>')
@auth_required
def get_course_decks(course_id):
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    decks = dao.get_slide_decks_by_course(course_id)
    return jsonify({
        'decks': [{
            'id': d['id'],
            'file_name': d['file_name'],
            'slide_count': d.get('slide_count', 0),
            'conversion_status': d.get('conversion_status', ''),
            'current_slide_index': d.get('current_slide_index', 0),
            'created_at': d['created_at'] if isinstance(d['created_at'], str) else d['created_at'].strftime('%Y-%m-%d %H:%M')
        } for d in decks]
    })


@bp.route('/<deck_id>/ai-generate-checkpoints', methods=['POST'])
@auth_required
def ai_generate_from_deck(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    if deck['conversion_status'] != 'completed' or deck.get('slide_count', 0) == 0:
        return jsonify({'error': '슬라이드 변환이 완료되지 않았습니다.'}), 400

    try:
        from app.services.ai_checkpoint import CheckpointGenerator

        # Download slide images to temp directory for AI analysis
        image_paths = []
        tmp_dir = tempfile.mkdtemp()
        for i in range(deck['slide_count']):
            url = get_slide_image_url(deck_id, i)
            if url:
                image_paths.append(url)

        if not image_paths:
            return jsonify({'error': '슬라이드 이미지 파일이 없습니다.'}), 404

        MAX_SLIDES_FOR_AI = 50
        if len(image_paths) > MAX_SLIDES_FOR_AI:
            step = len(image_paths) / MAX_SLIDES_FOR_AI
            sampled = [image_paths[int(i * step)] for i in range(MAX_SLIDES_FOR_AI)]
            image_paths = sampled

        checkpoints = CheckpointGenerator.generate_checkpoints_from_slide_images(image_paths)

        return jsonify({
            'success': True,
            'checkpoints': checkpoints,
            'deck_name': deck['file_name'],
            'slide_count': deck['slide_count']
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'AI 분석 중 오류가 발생했습니다: {str(e)}'}), 500


@bp.route('/<deck_id>/ai-save-checkpoints', methods=['POST'])
@auth_required
def ai_save_checkpoints(deck_id):
    deck = dao.get_slide_deck(deck_id)
    if not deck:
        abort(404)
    course = dao.get_course(deck['course_id'])
    user = get_current_user()
    if not has_course_access(course, user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    checkpoints_data = data.get('checkpoints', [])

    if not checkpoints_data:
        return jsonify({'error': '체크포인트가 없습니다.'}), 400

    max_order = dao.get_max_order(course['id']) or 0

    created_count = 0
    for cp_data in checkpoints_data:
        max_order += 1
        dao.create_checkpoint({
            'course_id': course['id'],
            'title': cp_data.get('title', ''),
            'description': cp_data.get('description', ''),
            'estimated_minutes': cp_data.get('estimated_minutes', 5),
            'order': max_order
        })
        created_count += 1

    return jsonify({
        'success': True,
        'created_count': created_count,
        'redirect_url': url_for('courses.view', course_id=course['id'])
    })
