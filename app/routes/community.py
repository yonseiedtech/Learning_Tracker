from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import LearningReview, ReviewComment, QnAPost, QnAAnswer, StudyGroup, StudyGroupMember, Subject, Course
from app.forms import LearningReviewForm, QnAPostForm, QnAAnswerForm, StudyGroupForm, CommentForm

bp = Blueprint('community', __name__, url_prefix='/community')

@bp.route('/')
def index():
    tab = request.args.get('tab', 'reviews')
    
    reviews = LearningReview.query.order_by(LearningReview.created_at.desc()).limit(10).all()
    qna_posts = QnAPost.query.order_by(QnAPost.created_at.desc()).limit(10).all()
    study_groups = StudyGroup.query.filter_by(status='recruiting').order_by(StudyGroup.created_at.desc()).limit(10).all()
    
    return render_template('community/index.html',
                          tab=tab,
                          reviews=reviews,
                          qna_posts=qna_posts,
                          study_groups=study_groups)

@bp.route('/reviews')
def reviews_list():
    page = request.args.get('page', 1, type=int)
    reviews = LearningReview.query.order_by(LearningReview.created_at.desc()).paginate(page=page, per_page=12)
    return render_template('community/reviews_list.html', reviews=reviews)

@bp.route('/reviews/new', methods=['GET', 'POST'])
@login_required
def create_review():
    form = LearningReviewForm()
    subjects = Subject.query.all()
    
    if form.validate_on_submit():
        review = LearningReview(
            user_id=current_user.id,
            title=form.title.data,
            content=form.content.data,
            rating=form.rating.data,
            subject_id=request.form.get('subject_id') or None,
            course_id=request.form.get('course_id') or None
        )
        db.session.add(review)
        db.session.commit()
        flash('학습 리뷰가 등록되었습니다.', 'success')
        return redirect(url_for('community.review_detail', review_id=review.id))
    
    return render_template('community/review_form.html', form=form, subjects=subjects)

@bp.route('/reviews/<int:review_id>')
def review_detail(review_id):
    review = LearningReview.query.get_or_404(review_id)
    review.views_count += 1
    db.session.commit()
    
    comment_form = CommentForm()
    comments = review.comments.order_by(ReviewComment.created_at.asc()).all()
    
    return render_template('community/review_detail.html', 
                          review=review, 
                          comment_form=comment_form,
                          comments=comments)

@bp.route('/reviews/<int:review_id>/comment', methods=['POST'])
@login_required
def add_review_comment(review_id):
    review = LearningReview.query.get_or_404(review_id)
    form = CommentForm()
    
    if form.validate_on_submit():
        comment = ReviewComment(
            review_id=review_id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(comment)
        db.session.commit()
        flash('댓글이 등록되었습니다.', 'success')
    
    return redirect(url_for('community.review_detail', review_id=review_id))

@bp.route('/reviews/<int:review_id>/like', methods=['POST'])
@login_required
def like_review(review_id):
    review = LearningReview.query.get_or_404(review_id)
    review.likes_count += 1
    db.session.commit()
    return {'likes_count': review.likes_count}

@bp.route('/qna')
def qna_list():
    page = request.args.get('page', 1, type=int)
    filter_type = request.args.get('filter', 'all')
    
    query = QnAPost.query
    if filter_type == 'resolved':
        query = query.filter_by(is_resolved=True)
    elif filter_type == 'unresolved':
        query = query.filter_by(is_resolved=False)
    
    qna_posts = query.order_by(QnAPost.created_at.desc()).paginate(page=page, per_page=12)
    return render_template('community/qna_list.html', qna_posts=qna_posts, filter_type=filter_type)

@bp.route('/qna/new', methods=['GET', 'POST'])
@login_required
def create_qna():
    form = QnAPostForm()
    subjects = Subject.query.all()
    
    if form.validate_on_submit():
        try:
            post = QnAPost(
                user_id=current_user.id,
                title=form.title.data,
                content=form.content.data,
                subject_id=request.form.get('subject_id') or None,
                course_id=request.form.get('course_id') or None
            )
            db.session.add(post)
            db.session.commit()
            flash('질문이 등록되었습니다.', 'success')
            return redirect(url_for('community.qna_detail', post_id=post.id))
        except Exception as e:
            db.session.rollback()
            flash('질문 등록 중 오류가 발생했습니다.', 'danger')
    
    return render_template('community/qna_form.html', form=form, subjects=subjects)

@bp.route('/qna/<int:post_id>')
def qna_detail(post_id):
    post = QnAPost.query.get_or_404(post_id)
    post.views_count += 1
    db.session.commit()
    
    answer_form = QnAAnswerForm()
    answers = post.answers.order_by(QnAAnswer.is_accepted.desc(), QnAAnswer.likes_count.desc()).all()
    
    return render_template('community/qna_detail.html',
                          post=post,
                          answer_form=answer_form,
                          answers=answers)

@bp.route('/qna/<int:post_id>/answer', methods=['POST'])
@login_required
def add_qna_answer(post_id):
    post = QnAPost.query.get_or_404(post_id)
    form = QnAAnswerForm()
    
    if form.validate_on_submit():
        answer = QnAAnswer(
            post_id=post_id,
            user_id=current_user.id,
            content=form.content.data
        )
        db.session.add(answer)
        db.session.commit()
        flash('답변이 등록되었습니다.', 'success')
    
    return redirect(url_for('community.qna_detail', post_id=post_id))

@bp.route('/qna/<int:post_id>/accept/<int:answer_id>', methods=['POST'])
@login_required
def accept_answer(post_id, answer_id):
    post = QnAPost.query.get_or_404(post_id)
    
    if post.user_id != current_user.id:
        flash('질문 작성자만 답변을 채택할 수 있습니다.', 'danger')
        return redirect(url_for('community.qna_detail', post_id=post_id))
    
    answer = QnAAnswer.query.get_or_404(answer_id)
    if answer.post_id != post_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.qna_detail', post_id=post_id))
    
    answer.is_accepted = True
    post.is_resolved = True
    db.session.commit()
    flash('답변이 채택되었습니다.', 'success')
    
    return redirect(url_for('community.qna_detail', post_id=post_id))

@bp.route('/study-groups')
def study_groups_list():
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', 'all')
    
    query = StudyGroup.query
    if category != 'all':
        query = query.filter_by(category=category)
    
    study_groups = query.order_by(StudyGroup.created_at.desc()).paginate(page=page, per_page=12)
    
    categories = [
        ('all', '전체'),
        ('programming', '프로그래밍'),
        ('data_science', '데이터 사이언스'),
        ('design', '디자인'),
        ('language', '외국어'),
        ('certification', '자격증'),
        ('general', '일반')
    ]
    
    return render_template('community/study_groups_list.html', 
                          study_groups=study_groups,
                          categories=categories,
                          current_category=category)

@bp.route('/study-groups/new', methods=['GET', 'POST'])
@login_required
def create_study_group():
    form = StudyGroupForm()
    
    if form.validate_on_submit():
        try:
            group = StudyGroup(
                creator_id=current_user.id,
                title=form.title.data,
                description=form.description.data,
                category=form.category.data,
                max_members=form.max_members.data,
                meeting_type=form.meeting_type.data,
                meeting_schedule=form.meeting_schedule.data,
                tags=form.tags.data
            )
            db.session.add(group)
            db.session.commit()
            
            member = StudyGroupMember(
                group_id=group.id,
                user_id=current_user.id,
                status='approved'
            )
            db.session.add(member)
            db.session.commit()
            
            flash('스터디가 생성되었습니다.', 'success')
            return redirect(url_for('community.study_group_detail', group_id=group.id))
        except Exception as e:
            db.session.rollback()
            flash('스터디 생성 중 오류가 발생했습니다.', 'danger')
    
    return render_template('community/study_group_form.html', form=form)

@bp.route('/study-groups/<int:group_id>')
def study_group_detail(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    members = group.members.filter_by(status='approved').all()
    pending_members = group.members.filter_by(status='pending').all()
    
    is_member = False
    is_creator = group.creator_id == current_user.id if current_user.is_authenticated else False
    pending_request = None
    
    if current_user.is_authenticated:
        membership = StudyGroupMember.query.filter_by(
            group_id=group_id,
            user_id=current_user.id
        ).first()
        if membership:
            if membership.status == 'approved':
                is_member = True
            elif membership.status == 'pending':
                pending_request = membership
    
    return render_template('community/study_group_detail.html',
                          group=group,
                          members=members,
                          pending_members=pending_members,
                          is_member=is_member,
                          is_creator=is_creator,
                          pending_request=pending_request)

@bp.route('/study-groups/<int:group_id>/join', methods=['POST'])
@login_required
def join_study_group(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    
    existing = StudyGroupMember.query.filter_by(
        group_id=group_id,
        user_id=current_user.id
    ).first()
    
    if existing:
        if existing.status == 'approved':
            flash('이미 스터디에 참여 중입니다.', 'warning')
        else:
            flash('이미 가입 신청을 했습니다.', 'warning')
        return redirect(url_for('community.study_group_detail', group_id=group_id))
    
    if group.current_members >= group.max_members:
        flash('스터디 정원이 다 찼습니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))
    
    member = StudyGroupMember(
        group_id=group_id,
        user_id=current_user.id,
        status='pending'
    )
    db.session.add(member)
    db.session.commit()
    
    flash('가입 신청이 완료되었습니다. 스터디장의 승인을 기다려주세요.', 'success')
    return redirect(url_for('community.study_group_detail', group_id=group_id))

@bp.route('/study-groups/<int:group_id>/approve/<int:member_id>', methods=['POST'])
@login_required
def approve_member(group_id, member_id):
    group = StudyGroup.query.get_or_404(group_id)
    
    if group.creator_id != current_user.id:
        flash('스터디장만 승인할 수 있습니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))
    
    member = StudyGroupMember.query.get_or_404(member_id)
    if member.group_id != group_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))
    
    member.status = 'approved'
    group.current_members += 1
    db.session.commit()
    
    flash('멤버가 승인되었습니다.', 'success')
    return redirect(url_for('community.study_group_detail', group_id=group_id))

@bp.route('/study-groups/<int:group_id>/reject/<int:member_id>', methods=['POST'])
@login_required
def reject_member(group_id, member_id):
    group = StudyGroup.query.get_or_404(group_id)
    
    if group.creator_id != current_user.id:
        flash('스터디장만 거절할 수 있습니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))
    
    member = StudyGroupMember.query.get_or_404(member_id)
    if member.group_id != group_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))
    
    db.session.delete(member)
    db.session.commit()
    
    flash('가입 신청이 거절되었습니다.', 'info')
    return redirect(url_for('community.study_group_detail', group_id=group_id))
