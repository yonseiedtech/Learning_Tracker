from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from datetime import datetime

bp = Blueprint('guide', __name__, url_prefix='/guide')

CATEGORIES = {
    'notice': {'name': '공지사항', 'icon': 'bi-megaphone', 'admin_only': True},
    'faq': {'name': 'FAQ', 'icon': 'bi-question-circle', 'admin_only': True},
    'qna': {'name': 'Q&A', 'icon': 'bi-chat-dots', 'admin_only': False},
    'resources': {'name': '자료실', 'icon': 'bi-folder', 'admin_only': True},
    'updates': {'name': '업데이트 소식', 'icon': 'bi-newspaper', 'admin_only': True},
    'suggestions': {'name': '제안', 'icon': 'bi-lightbulb', 'admin_only': False}
}


def is_admin():
    user = get_current_user()
    return user.is_authenticated and user.role == 'admin'


@bp.route('/')
@auth_required
def index():
    category = request.args.get('category', 'notice')
    if category not in CATEGORIES:
        category = 'notice'

    posts = dao.get_guide_posts(category=category)
    # Enrich posts with comment_count
    for post in posts:
        post['comment_count'] = len(dao.get_guide_comments(post['id']))

    # Enrich posts with author data for templates
    dao.enrich_with_user(posts, 'author_id', 'author')

    return render_template('guide/index.html',
                           posts=posts,
                           categories=CATEGORIES,
                           current_category=category,
                           is_admin=is_admin())


@bp.route('/post/<post_id>')
@auth_required
def view_post(post_id):
    post = dao.get_guide_post(post_id)
    if not post:
        abort(404)

    # Increment view count
    view_count = post.get('view_count', 0) + 1
    dao.update_guide_post(post_id, {'view_count': view_count})
    post['view_count'] = view_count

    comments = dao.get_guide_comments(post_id)

    # Enrich post and comments with author data for templates
    dao.enrich_with_user([post], 'author_id', 'author')
    dao.enrich_with_user(comments, 'author_id', 'author')

    return render_template('guide/view.html',
                           post=post,
                           comments=comments,
                           categories=CATEGORIES,
                           is_admin=is_admin())


@bp.route('/create', methods=['GET', 'POST'])
@auth_required
def create_post():
    user = get_current_user()
    category = request.args.get('category', 'qna')

    if category not in CATEGORIES:
        flash('잘못된 카테고리입니다.', 'danger')
        return redirect(url_for('guide.index'))

    cat_info = CATEGORIES[category]
    if cat_info['admin_only'] and not is_admin():
        flash('해당 카테고리에 글을 작성할 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.index', category=category))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        is_pinned = request.form.get('is_pinned') == 'on' and is_admin()

        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.', 'danger')
            return render_template('guide/create.html',
                                   category=category,
                                   categories=CATEGORIES,
                                   is_admin=is_admin())

        post_id = dao.create_guide_post({
            'category': category,
            'title': title,
            'content': content,
            'author_id': user.id,
            'is_pinned': is_pinned,
            'view_count': 0,
            'is_answered': False,
            'created_at': datetime.utcnow(),
        })

        flash('게시글이 작성되었습니다.', 'success')
        return redirect(url_for('guide.view_post', post_id=post_id))

    return render_template('guide/create.html',
                           category=category,
                           categories=CATEGORIES,
                           is_admin=is_admin())


@bp.route('/post/<post_id>/edit', methods=['GET', 'POST'])
@auth_required
def edit_post(post_id):
    user = get_current_user()
    post = dao.get_guide_post(post_id)
    if not post:
        abort(404)

    if post['author_id'] != user.id and not is_admin():
        flash('수정 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.view_post', post_id=post_id))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        is_pinned = request.form.get('is_pinned') == 'on' and is_admin()

        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.', 'danger')
            return render_template('guide/edit.html', post=post, categories=CATEGORIES, is_admin=is_admin())

        dao.update_guide_post(post_id, {
            'title': title,
            'content': content,
            'is_pinned': is_pinned,
            'updated_at': datetime.utcnow(),
        })

        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('guide.view_post', post_id=post_id))

    return render_template('guide/edit.html', post=post, categories=CATEGORIES, is_admin=is_admin())


@bp.route('/post/<post_id>/delete', methods=['POST'])
@auth_required
def delete_post(post_id):
    user = get_current_user()
    post = dao.get_guide_post(post_id)
    if not post:
        abort(404)

    if post['author_id'] != user.id and not is_admin():
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.view_post', post_id=post_id))

    category = post['category']
    dao.delete_guide_post(post_id)

    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('guide.index', category=category))


@bp.route('/post/<post_id>/comment', methods=['POST'])
@auth_required
def add_comment(post_id):
    user = get_current_user()
    post = dao.get_guide_post(post_id)
    if not post:
        abort(404)

    content = request.form.get('content', '').strip()
    if not content:
        flash('댓글 내용을 입력해주세요.', 'danger')
        return redirect(url_for('guide.view_post', post_id=post_id))

    dao.create_guide_comment({
        'post_id': post_id,
        'author_id': user.id,
        'content': content,
        'is_admin_reply': is_admin(),
        'created_at': datetime.utcnow(),
    })

    if post.get('category') == 'qna' and is_admin():
        dao.update_guide_post(post_id, {'is_answered': True})

    flash('댓글이 등록되었습니다.', 'success')
    return redirect(url_for('guide.view_post', post_id=post_id))


@bp.route('/comment/<comment_id>/delete', methods=['POST'])
@auth_required
def delete_comment(comment_id):
    user = get_current_user()
    comment = dao.get_guide_comment(comment_id)
    if not comment:
        abort(404)

    if comment['author_id'] != user.id and not is_admin():
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.view_post', post_id=comment['post_id']))

    post_id = comment['post_id']
    dao.delete_guide_comment(comment_id)

    flash('댓글이 삭제되었습니다.', 'success')
    return redirect(url_for('guide.view_post', post_id=post_id))


@bp.route('/post/<post_id>/toggle-answered', methods=['POST'])
@auth_required
def toggle_answered(post_id):
    if not is_admin():
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403

    post = dao.get_guide_post(post_id)
    if not post:
        abort(404)

    new_value = not post.get('is_answered', False)
    dao.update_guide_post(post_id, {'is_answered': new_value})

    return jsonify({'success': True, 'is_answered': new_value})
