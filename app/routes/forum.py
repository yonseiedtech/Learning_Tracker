from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, ForumPost, ForumComment
from datetime import datetime

bp = Blueprint('forum', __name__, url_prefix='/forum')

def user_has_course_access(user, course):
    if not course:
        return False
    if user.is_instructor() and course.instructor_id == user.id:
        return True
    return Enrollment.query.filter_by(user_id=user.id, course_id=course.id).first() is not None

@bp.route('/course/<int:course_id>')
@login_required
def list_posts(course_id):
    course = Course.query.get_or_404(course_id)
    if not user_has_course_access(current_user, course):
        flash('이 세미나에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    posts = ForumPost.query.filter_by(course_id=course_id).order_by(ForumPost.created_at.desc()).all()
    return render_template('forum/list.html', course=course, posts=posts)

@bp.route('/course/<int:course_id>/new', methods=['GET', 'POST'])
@login_required
def create_post(course_id):
    course = Course.query.get_or_404(course_id)
    if not user_has_course_access(current_user, course):
        flash('이 세미나에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        
        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.', 'danger')
            return render_template('forum/create.html', course=course)
        
        try:
            post = ForumPost(
                course_id=course_id,
                user_id=current_user.id,
                title=title,
                content=content
            )
            db.session.add(post)
            db.session.commit()
            flash('게시글이 작성되었습니다.', 'success')
            return redirect(url_for('forum.view_post', post_id=post.id))
        except Exception as e:
            db.session.rollback()
            flash('게시글 작성 중 오류가 발생했습니다.', 'danger')
            return render_template('forum/create.html', course=course)
    
    return render_template('forum/create.html', course=course)

@bp.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    course = post.course
    
    if not user_has_course_access(current_user, course):
        flash('이 게시글에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    comments = ForumComment.query.filter_by(post_id=post_id).order_by(ForumComment.created_at.asc()).all()
    return render_template('forum/view.html', post=post, course=course, comments=comments)

@bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = ForumPost.query.get_or_404(post_id)
    course = post.course
    
    if not user_has_course_access(current_user, course):
        flash('이 게시글에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    content = request.form.get('content', '').strip()
    if not content:
        flash('댓글 내용을 입력해주세요.', 'danger')
        return redirect(url_for('forum.view_post', post_id=post_id))
    
    comment = ForumComment(
        post_id=post_id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(comment)
    db.session.commit()
    flash('댓글이 작성되었습니다.', 'success')
    return redirect(url_for('forum.view_post', post_id=post_id))

@bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = ForumPost.query.get_or_404(post_id)
    course = post.course
    
    if post.user_id != current_user.id and course.instructor_id != current_user.id:
        flash('이 게시글을 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('forum.view_post', post_id=post_id))
    
    db.session.delete(post)
    db.session.commit()
    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('forum.list_posts', course_id=course.id))

@bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = ForumComment.query.get_or_404(comment_id)
    post = comment.post
    course = post.course
    
    if comment.user_id != current_user.id and course.instructor_id != current_user.id:
        flash('이 댓글을 삭제할 권한이 없습니다.', 'danger')
        return redirect(url_for('forum.view_post', post_id=post.id))
    
    db.session.delete(comment)
    db.session.commit()
    flash('댓글이 삭제되었습니다.', 'success')
    return redirect(url_for('forum.view_post', post_id=post.id))
