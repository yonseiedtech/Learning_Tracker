from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, abort
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, ActiveSession, SlideDeck, SlideReaction, SlideBookmark, SubjectMember
from app.services.slide_converter import convert_pptx_to_images, delete_deck_images, SLIDES_BASE_DIR, ensure_slides_dir
from datetime import datetime
import tempfile
import os

bp = Blueprint('slides', __name__, url_prefix='/slides')


def has_course_access(course, user):
    if course.instructor_id == user.id:
        return True
    if course.subject_id:
        member = SubjectMember.query.filter_by(subject_id=course.subject_id, user_id=user.id).first()
        if member and member.role in ['instructor', 'assistant']:
            return True
    return False


@bp.route('/<int:deck_id>/<path:filename>')
@login_required
def serve_slide_image(deck_id, filename):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)
    if not course:
        abort(404)
    is_enrolled = Enrollment.query.filter_by(course_id=course.id, user_id=current_user.id).first()
    is_instructor = has_course_access(course, current_user)
    if not is_enrolled and not is_instructor:
        abort(403)
    deck_dir = os.path.join(SLIDES_BASE_DIR, str(deck_id))
    if not os.path.exists(deck_dir):
        abort(404)
    return send_from_directory(deck_dir, filename)


@bp.route('/upload/<int:course_id>', methods=['POST'])
@login_required
def upload_pptx(course_id):
    course = Course.query.get_or_404(course_id)
    if not has_course_access(course, current_user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    file = request.files.get('pptx_file')
    if not file or not file.filename:
        return jsonify({'error': 'PPT 파일을 선택해주세요.'}), 400

    if not file.filename.lower().endswith(('.pptx', '.ppt')):
        return jsonify({'error': '.pptx 또는 .ppt 파일만 업로드 가능합니다.'}), 400

    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    max_size = 50 * 1024 * 1024
    if file_size > max_size:
        return jsonify({'error': f'파일 크기가 50MB를 초과합니다. ({file_size // (1024*1024)}MB)'}), 400

    ensure_slides_dir()

    active_session = ActiveSession.query.filter_by(course_id=course_id, ended_at=None).first()

    deck = SlideDeck(
        course_id=course_id,
        session_id=active_session.id if active_session else None,
        file_name=file.filename,
        conversion_status='converting'
    )
    db.session.add(deck)
    db.session.commit()

    try:
        with tempfile.NamedTemporaryFile(suffix='.pptx', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        slide_count, deck_dir = convert_pptx_to_images(tmp_path, deck.id)

        deck.slide_count = slide_count
        deck.slides_dir = deck_dir
        deck.conversion_status = 'completed'
        db.session.commit()

        os.unlink(tmp_path)

        return jsonify({
            'success': True,
            'deck_id': deck.id,
            'slide_count': slide_count,
            'slides': deck.get_slide_urls(),
            'message': f'{slide_count}개의 슬라이드가 변환되었습니다.'
        })

    except Exception as e:
        deck.conversion_status = 'failed'
        deck.conversion_error = str(e)
        db.session.commit()
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        return jsonify({'error': f'변환 실패: {str(e)}'}), 500


@bp.route('/delete/<int:deck_id>', methods=['POST'])
@login_required
def delete_deck(deck_id):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)
    if not has_course_access(course, current_user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    delete_deck_images(deck.slides_dir)
    db.session.delete(deck)
    db.session.commit()

    return jsonify({'success': True, 'message': '슬라이드 덱이 삭제되었습니다.'})


@bp.route('/presenter/<int:deck_id>')
@login_required
def presenter_view(deck_id):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)
    if not has_course_access(course, current_user):
        flash('강사만 프레젠터 뷰를 사용할 수 있습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course.id))

    slides = deck.get_slide_urls()
    bookmarks = {b.slide_index: b for b in SlideBookmark.query.filter_by(deck_id=deck_id).all()}

    return render_template('sessions/slide_presenter.html',
                         deck=deck,
                         course=course,
                         slides=slides,
                         bookmarks=bookmarks)


@bp.route('/viewer/<int:deck_id>')
@login_required
def viewer_view(deck_id):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)

    is_enrolled = Enrollment.query.filter_by(course_id=course.id, user_id=current_user.id).first()
    is_instructor = has_course_access(course, current_user)

    if not is_enrolled and not is_instructor:
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if is_instructor:
        return redirect(url_for('slides.presenter_view', deck_id=deck_id))

    slides = deck.get_slide_urls()

    my_reactions = {}
    reactions = SlideReaction.query.filter_by(deck_id=deck_id, user_id=current_user.id).all()
    for r in reactions:
        my_reactions[r.slide_index] = r.reaction

    return render_template('sessions/slide_viewer.html',
                         deck=deck,
                         course=course,
                         slides=slides,
                         my_reactions=my_reactions)


@bp.route('/review/<int:deck_id>')
@login_required
def review_view(deck_id):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)
    if not has_course_access(course, current_user):
        flash('강사만 리뷰 페이지에 접근할 수 있습니다.', 'danger')
        return redirect(url_for('courses.view', course_id=course.id))

    slides = deck.get_slide_urls()
    bookmarks = {}
    for b in SlideBookmark.query.filter_by(deck_id=deck_id).all():
        bookmarks[b.slide_index] = b

    aggregates = {}
    for i in range(deck.slide_count):
        understood = SlideReaction.query.filter_by(deck_id=deck_id, slide_index=i, reaction='understood').count()
        question = SlideReaction.query.filter_by(deck_id=deck_id, slide_index=i, reaction='question').count()
        hard = SlideReaction.query.filter_by(deck_id=deck_id, slide_index=i, reaction='hard').count()
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


@bp.route('/review/<int:deck_id>/save-memo', methods=['POST'])
@login_required
def save_bookmark_memo(deck_id):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)
    if not has_course_access(course, current_user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    slide_index = data.get('slide_index')
    memo = data.get('memo', '')
    supplement_url = data.get('supplement_url', '')

    bookmark = SlideBookmark.query.filter_by(deck_id=deck_id, slide_index=slide_index).first()
    if not bookmark:
        bookmark = SlideBookmark(
            deck_id=deck_id,
            slide_index=slide_index,
            is_manual=True
        )
        db.session.add(bookmark)

    bookmark.memo = memo
    bookmark.supplement_url = supplement_url
    db.session.commit()

    return jsonify({'success': True})


@bp.route('/review/<int:deck_id>/toggle-bookmark', methods=['POST'])
@login_required
def toggle_manual_bookmark(deck_id):
    deck = SlideDeck.query.get_or_404(deck_id)
    course = Course.query.get(deck.course_id)
    if not has_course_access(course, current_user):
        return jsonify({'error': '권한이 없습니다.'}), 403

    data = request.get_json()
    slide_index = data.get('slide_index')

    bookmark = SlideBookmark.query.filter_by(deck_id=deck_id, slide_index=slide_index).first()
    if bookmark:
        if bookmark.is_auto and not bookmark.is_manual:
            bookmark.is_manual = True
        elif bookmark.is_manual and not bookmark.is_auto:
            db.session.delete(bookmark)
        else:
            bookmark.is_manual = not bookmark.is_manual
    else:
        bookmark = SlideBookmark(
            deck_id=deck_id,
            slide_index=slide_index,
            is_manual=True
        )
        db.session.add(bookmark)

    db.session.commit()

    return jsonify({'success': True})


@bp.route('/deck/<int:course_id>')
@login_required
def get_course_decks(course_id):
    course = Course.query.get_or_404(course_id)
    decks = SlideDeck.query.filter_by(course_id=course_id).order_by(SlideDeck.created_at.desc()).all()
    return jsonify({
        'decks': [{
            'id': d.id,
            'file_name': d.file_name,
            'slide_count': d.slide_count,
            'conversion_status': d.conversion_status,
            'current_slide_index': d.current_slide_index,
            'created_at': d.created_at.strftime('%Y-%m-%d %H:%M')
        } for d in decks]
    })
