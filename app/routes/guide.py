from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import GuidePost, GuideComment, GuideAttachment
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
    return current_user.is_authenticated and current_user.role == 'admin'


@bp.route('/')
@login_required
def index():
    category = request.args.get('category', 'notice')
    if category not in CATEGORIES:
        category = 'notice'
    
    posts = GuidePost.query.filter_by(category=category).order_by(
        GuidePost.is_pinned.desc(),
        GuidePost.created_at.desc()
    ).all()
    
    return render_template('guide/index.html',
                          posts=posts,
                          categories=CATEGORIES,
                          current_category=category,
                          is_admin=is_admin())


@bp.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = GuidePost.query.get_or_404(post_id)
    post.view_count += 1
    db.session.commit()
    
    comments = post.comments.order_by(GuideComment.created_at.asc()).all()
    
    return render_template('guide/view.html',
                          post=post,
                          comments=comments,
                          categories=CATEGORIES,
                          is_admin=is_admin())


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
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
        
        post = GuidePost(
            category=category,
            title=title,
            content=content,
            author_id=current_user.id,
            is_pinned=is_pinned
        )
        db.session.add(post)
        db.session.commit()
        
        flash('게시글이 작성되었습니다.', 'success')
        return redirect(url_for('guide.view_post', post_id=post.id))
    
    return render_template('guide/create.html',
                          category=category,
                          categories=CATEGORIES,
                          is_admin=is_admin())


@bp.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = GuidePost.query.get_or_404(post_id)
    
    if post.author_id != current_user.id and not is_admin():
        flash('수정 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.view_post', post_id=post_id))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        is_pinned = request.form.get('is_pinned') == 'on' and is_admin()
        
        if not title or not content:
            flash('제목과 내용을 모두 입력해주세요.', 'danger')
            return render_template('guide/edit.html', post=post, categories=CATEGORIES, is_admin=is_admin())
        
        post.title = title
        post.content = content
        post.is_pinned = is_pinned
        post.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('게시글이 수정되었습니다.', 'success')
        return redirect(url_for('guide.view_post', post_id=post_id))
    
    return render_template('guide/edit.html', post=post, categories=CATEGORIES, is_admin=is_admin())


@bp.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = GuidePost.query.get_or_404(post_id)
    
    if post.author_id != current_user.id and not is_admin():
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.view_post', post_id=post_id))
    
    category = post.category
    db.session.delete(post)
    db.session.commit()
    
    flash('게시글이 삭제되었습니다.', 'success')
    return redirect(url_for('guide.index', category=category))


@bp.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = GuidePost.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    
    if not content:
        flash('댓글 내용을 입력해주세요.', 'danger')
        return redirect(url_for('guide.view_post', post_id=post_id))
    
    comment = GuideComment(
        post_id=post_id,
        author_id=current_user.id,
        content=content,
        is_admin_reply=is_admin()
    )
    db.session.add(comment)
    
    if post.category == 'qna' and is_admin():
        post.is_answered = True
    
    db.session.commit()
    
    flash('댓글이 등록되었습니다.', 'success')
    return redirect(url_for('guide.view_post', post_id=post_id))


@bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = GuideComment.query.get_or_404(comment_id)
    
    if comment.author_id != current_user.id and not is_admin():
        flash('삭제 권한이 없습니다.', 'danger')
        return redirect(url_for('guide.view_post', post_id=comment.post_id))
    
    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    
    flash('댓글이 삭제되었습니다.', 'success')
    return redirect(url_for('guide.view_post', post_id=post_id))


@bp.route('/post/<int:post_id>/toggle-answered', methods=['POST'])
@login_required
def toggle_answered(post_id):
    if not is_admin():
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    
    post = GuidePost.query.get_or_404(post_id)
    post.is_answered = not post.is_answered
    db.session.commit()
    
    return jsonify({'success': True, 'is_answered': post.is_answered})
