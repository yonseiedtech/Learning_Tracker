from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from datetime import datetime

bp = Blueprint('forum', __name__, url_prefix='/forum')


def user_has_course_access(user, course):
    if not course:
        return False
    if user.is_instructor() and course['instructor_id'] == user.id:
        return True
    return dao.is_enrolled(user.id, course['id'])


@bp.route('/course/<course_id>')
@auth_required
def list_posts(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not user_has_course_access(user, course):
        flash('이 세미나에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    posts = dao.get_forum_posts_by_course(course_id)
    return render_template('forum/list.html', course=course, posts=posts)


@bp.route('/course/<course_id>/new', methods=['GET', 'POST'])
@auth_required
def create_post(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        abort(404)
    if not user_has_course_access(user, course):
        flash('이 세미나에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.', 'danger')
            return render_template('forum/create.html', course=course)

        try:
            post_id = dao.create_forum_post({
                'course_id': course_id,
                'user_id': user.id,
                'title': title,
                'content': content,
                'created_at': datetime.utcnow(),
            })
            flash('게시글이 작성되었습니다.', 'success')
            return redirect(url_for('forum.view_post', post_id=post_id))
        except Exception:
            flash('게시글 작성 중 오류가 발생했습니다.', 'danger')
            return render_template('forum/create.html', course=course)

    return render_template('forum/create.html', course=course)


@bp.route('/post/<post_id>')
@auth_required
def view_post(post_id):
    user = get_current_user()
    post = dao.get_forum_post(post_id)
    if not post:
        abort(404)

    course = dao.get_course(post['course_id'])
    if not course:
        abort(404)

    if not user_has_course_access(user, course):
        flash('이 게시글에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    comments = dao.get_forum_comments(post_id)
    return render_template('forum/view.html', post=post, course=course, comments=comments)


@bp.route('/post/<post_id>/comment', methods=['POST'])
@auth_required
def add_comment(post_id):
    user = get_current_user()
    post = dao.get_forum_post(post_id)
    if not post:
        abort(404)

    course = dao.get_course(post['course_id'])
    if not course:
        abort(404)

    if not user_has_course_access(user, course):
        flash('이 게시글에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    content = request.form.get('content', '').strip()
    if not content:
        flash('댓글 내용을 입력해주세요.', 'danger')
        return redirect(url_for('forum.view_post', post_id=post_id))

    dao.create_forum_comment({
        'post_id': post_id,
        'user_id': user.id,
        'content': content,
        'created_at': datetime.utcnow(),
    })
    flash('댓글이 작성되었습니다.', 'success')
    return redirect(url_for('forum.view_post', post_id=post_id))


@bp.route('/post/<post_id>/delete', methods=['POST'])
@auth_required
def delete_post(post_id):
    user = get_current_user()
    post = dao.get_forum_post(post_id)
    if not post:
        abort(404)

    course = dao.get_course(post['course_id'])
    if not course:
        abort(404)

    if post['user_id'] != user.id and course['instructor_id'] != user.id:
        flash('이 게시글을 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('forum.view_post', post_id=post_id))

    dao.delete_forum_post(post_id)
    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('forum.list_posts', course_id=course['id']))


@bp.route('/comment/<comment_id>/delete', methods=['POST'])
@auth_required
def delete_comment(comment_id):
    user = get_current_user()
    comment = dao.get_forum_comment(comment_id)
    if not comment:
        abort(404)

    post = dao.get_forum_post(comment['post_id'])
    if not post:
        abort(404)

    course = dao.get_course(post['course_id'])
    if not course:
        abort(404)

    if comment['user_id'] != user.id and course['instructor_id'] != user.id:
        flash('이 댓글을 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('forum.view_post', post_id=post['id']))

    dao.delete_forum_comment(comment_id)
    flash('댓글이 삭제되었습니다.', 'success')
    return redirect(url_for('forum.view_post', post_id=post['id']))
