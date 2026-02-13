from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app.forms import LearningReviewForm, QnAPostForm, QnAAnswerForm, StudyGroupForm, CommentForm
from datetime import datetime

bp = Blueprint('community', __name__, url_prefix='/community')


@bp.route('/')
def index():
    tab = request.args.get('tab', 'reviews')

    reviews = dao.get_learning_reviews(limit=10)
    qna_posts = dao.get_qna_posts(limit=10)
    study_groups = [g for g in dao.get_study_groups(limit=20) if g.get('status') == 'recruiting'][:10]

    return render_template('community/index.html',
                          tab=tab,
                          reviews=reviews,
                          qna_posts=qna_posts,
                          study_groups=study_groups)


@bp.route('/reviews')
def reviews_list():
    reviews = dao.get_learning_reviews(limit=100)
    return render_template('community/reviews_list.html', reviews=reviews)


@bp.route('/reviews/new', methods=['GET', 'POST'])
@auth_required
def create_review():
    form = LearningReviewForm()
    from app.firestore_dao import get_db
    subjects = [doc.to_dict() | {'id': doc.id} for doc in get_db().collection('subjects').stream()]

    user = get_current_user()

    if form.validate_on_submit():
        review_data = {
            'user_id': user['uid'],
            'user_name': user.get('display_name', user.get('email', '')),
            'title': form.title.data,
            'content': form.content.data,
            'rating': form.rating.data,
            'subject_id': request.form.get('subject_id') or None,
            'course_id': request.form.get('course_id') or None,
            'views_count': 0,
            'likes_count': 0,
            'created_at': datetime.utcnow().isoformat()
        }
        review_id = dao.create_learning_review(review_data)
        flash('학습 리뷰가 등록되었습니다.', 'success')
        return redirect(url_for('community.review_detail', review_id=review_id))

    return render_template('community/review_form.html', form=form, subjects=subjects)


@bp.route('/reviews/<review_id>')
def review_detail(review_id):
    review = dao.get_learning_review(review_id)
    if not review:
        flash('리뷰를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    # Increment views_count
    dao.update_learning_review(review_id, {'views_count': review.get('views_count', 0) + 1})
    review['views_count'] = review.get('views_count', 0) + 1

    comment_form = CommentForm()
    comments = dao.get_review_comments(review_id)

    return render_template('community/review_detail.html',
                          review=review,
                          comment_form=comment_form,
                          comments=comments)


@bp.route('/reviews/<review_id>/comment', methods=['POST'])
@auth_required
def add_review_comment(review_id):
    review = dao.get_learning_review(review_id)
    if not review:
        flash('리뷰를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    form = CommentForm()
    user = get_current_user()

    if form.validate_on_submit():
        dao.create_review_comment({
            'review_id': review_id,
            'user_id': user['uid'],
            'user_name': user.get('display_name', user.get('email', '')),
            'content': form.content.data,
            'created_at': datetime.utcnow().isoformat()
        })
        flash('댓글이 등록되었습니다.', 'success')

    return redirect(url_for('community.review_detail', review_id=review_id))


@bp.route('/reviews/<review_id>/like', methods=['POST'])
@auth_required
def like_review(review_id):
    review = dao.get_learning_review(review_id)
    if not review:
        return {'error': '리뷰를 찾을 수 없습니다.'}, 404

    new_likes = review.get('likes_count', 0) + 1
    dao.update_learning_review(review_id, {'likes_count': new_likes})
    return {'likes_count': new_likes}


@bp.route('/qna')
def qna_list():
    filter_type = request.args.get('filter', 'all')

    qna_posts = dao.get_qna_posts(limit=100)

    if filter_type == 'resolved':
        qna_posts = [p for p in qna_posts if p.get('is_resolved')]
    elif filter_type == 'unresolved':
        qna_posts = [p for p in qna_posts if not p.get('is_resolved')]

    return render_template('community/qna_list.html', qna_posts=qna_posts, filter_type=filter_type)


@bp.route('/qna/new', methods=['GET', 'POST'])
@auth_required
def create_qna():
    form = QnAPostForm()
    from app.firestore_dao import get_db
    subjects = [doc.to_dict() | {'id': doc.id} for doc in get_db().collection('subjects').stream()]

    user = get_current_user()

    if form.validate_on_submit():
        try:
            post_data = {
                'user_id': user['uid'],
                'user_name': user.get('display_name', user.get('email', '')),
                'title': form.title.data,
                'content': form.content.data,
                'subject_id': request.form.get('subject_id') or None,
                'course_id': request.form.get('course_id') or None,
                'is_resolved': False,
                'views_count': 0,
                'created_at': datetime.utcnow().isoformat()
            }
            post_id = dao.create_qna_post(post_data)
            flash('질문이 등록되었습니다.', 'success')
            return redirect(url_for('community.qna_detail', post_id=post_id))
        except Exception as e:
            flash('질문 등록 중 오류가 발생했습니다.', 'danger')

    return render_template('community/qna_form.html', form=form, subjects=subjects)


@bp.route('/qna/<post_id>')
def qna_detail(post_id):
    post = dao.get_qna_post(post_id)
    if not post:
        flash('질문을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    # Increment views_count
    dao.update_qna_post(post_id, {'views_count': post.get('views_count', 0) + 1})
    post['views_count'] = post.get('views_count', 0) + 1

    answer_form = QnAAnswerForm()
    answers = dao.get_qna_answers(post_id)
    # Sort: accepted first, then by likes_count descending
    answers.sort(key=lambda a: (-int(a.get('is_accepted', False)), -a.get('likes_count', 0)))

    return render_template('community/qna_detail.html',
                          post=post,
                          answer_form=answer_form,
                          answers=answers)


@bp.route('/qna/<post_id>/answer', methods=['POST'])
@auth_required
def add_qna_answer(post_id):
    post = dao.get_qna_post(post_id)
    if not post:
        flash('질문을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    form = QnAAnswerForm()
    user = get_current_user()

    if form.validate_on_submit():
        dao.create_qna_answer({
            'post_id': post_id,
            'user_id': user['uid'],
            'user_name': user.get('display_name', user.get('email', '')),
            'content': form.content.data,
            'is_accepted': False,
            'likes_count': 0,
            'created_at': datetime.utcnow().isoformat()
        })
        flash('답변이 등록되었습니다.', 'success')

    return redirect(url_for('community.qna_detail', post_id=post_id))


@bp.route('/qna/<post_id>/accept/<answer_id>', methods=['POST'])
@auth_required
def accept_answer(post_id, answer_id):
    post = dao.get_qna_post(post_id)
    if not post:
        flash('질문을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    user = get_current_user()

    if post['user_id'] != user['uid']:
        flash('질문 작성자만 답변을 채택할 수 있습니다.', 'danger')
        return redirect(url_for('community.qna_detail', post_id=post_id))

    answer = dao.get_qna_answer(answer_id)
    if not answer:
        flash('답변을 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.qna_detail', post_id=post_id))

    if answer['post_id'] != post_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.qna_detail', post_id=post_id))

    dao.update_qna_answer(answer_id, {'is_accepted': True})
    dao.update_qna_post(post_id, {'is_resolved': True})
    flash('답변이 채택되었습니다.', 'success')

    return redirect(url_for('community.qna_detail', post_id=post_id))


@bp.route('/study-groups')
def study_groups_list():
    category = request.args.get('category', 'all')

    study_groups = dao.get_study_groups(limit=100)

    if category != 'all':
        study_groups = [g for g in study_groups if g.get('category') == category]

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
@auth_required
def create_study_group():
    form = StudyGroupForm()
    user = get_current_user()

    if form.validate_on_submit():
        try:
            group_data = {
                'creator_id': user['uid'],
                'creator_name': user.get('display_name', user.get('email', '')),
                'title': form.title.data,
                'description': form.description.data,
                'category': form.category.data,
                'max_members': form.max_members.data,
                'current_members': 1,
                'meeting_type': form.meeting_type.data,
                'meeting_schedule': form.meeting_schedule.data,
                'tags': form.tags.data,
                'status': 'recruiting',
                'created_at': datetime.utcnow().isoformat()
            }
            group_id = dao.create_study_group(group_data)

            dao.create_study_group_member({
                'group_id': group_id,
                'user_id': user['uid'],
                'user_name': user.get('display_name', user.get('email', '')),
                'status': 'approved',
                'created_at': datetime.utcnow().isoformat()
            })

            flash('스터디가 생성되었습니다.', 'success')
            return redirect(url_for('community.study_group_detail', group_id=group_id))
        except Exception as e:
            flash('스터디 생성 중 오류가 발생했습니다.', 'danger')

    return render_template('community/study_group_form.html', form=form)


@bp.route('/study-groups/<group_id>')
def study_group_detail(group_id):
    group = dao.get_study_group(group_id)
    if not group:
        flash('스터디를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    all_members = dao.get_study_group_members(group_id)
    members = [m for m in all_members if m.get('status') == 'approved']
    pending_members = [m for m in all_members if m.get('status') == 'pending']

    is_member = False
    is_creator = False
    pending_request = None

    user = get_current_user()
    if user:
        is_creator = group['creator_id'] == user['uid']
        membership = dao.get_study_group_member(group_id, user['uid'])
        if membership:
            if membership.get('status') == 'approved':
                is_member = True
            elif membership.get('status') == 'pending':
                pending_request = membership

    return render_template('community/study_group_detail.html',
                          group=group,
                          members=members,
                          pending_members=pending_members,
                          is_member=is_member,
                          is_creator=is_creator,
                          pending_request=pending_request)


@bp.route('/study-groups/<group_id>/join', methods=['POST'])
@auth_required
def join_study_group(group_id):
    group = dao.get_study_group(group_id)
    if not group:
        flash('스터디를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    user = get_current_user()

    existing = dao.get_study_group_member(group_id, user['uid'])

    if existing:
        if existing.get('status') == 'approved':
            flash('이미 스터디에 참여 중입니다.', 'warning')
        else:
            flash('이미 가입 신청을 했습니다.', 'warning')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    if group.get('current_members', 0) >= group.get('max_members', 0):
        flash('스터디 정원이 다 찼습니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    dao.create_study_group_member({
        'group_id': group_id,
        'user_id': user['uid'],
        'user_name': user.get('display_name', user.get('email', '')),
        'status': 'pending',
        'created_at': datetime.utcnow().isoformat()
    })

    flash('가입 신청이 완료되었습니다. 스터디장의 승인을 기다려주세요.', 'success')
    return redirect(url_for('community.study_group_detail', group_id=group_id))


@bp.route('/study-groups/<group_id>/approve/<member_id>', methods=['POST'])
@auth_required
def approve_member(group_id, member_id):
    group = dao.get_study_group(group_id)
    if not group:
        flash('스터디를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    user = get_current_user()

    if group['creator_id'] != user['uid']:
        flash('스터디장만 승인할 수 있습니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    # Verify the member belongs to this group
    all_members = dao.get_study_group_members(group_id)
    member = None
    for m in all_members:
        if m['id'] == member_id:
            member = m
            break

    if not member:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    if member.get('group_id') != group_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    # Update member status via dao - need to update the member document directly
    from app.firestore_dao import get_db
    get_db().collection('study_group_members').document(member_id).update({'status': 'approved'})

    # Increment current_members
    dao.update_study_group(group_id, {'current_members': group.get('current_members', 0) + 1})

    flash('멤버가 승인되었습니다.', 'success')
    return redirect(url_for('community.study_group_detail', group_id=group_id))


@bp.route('/study-groups/<group_id>/reject/<member_id>', methods=['POST'])
@auth_required
def reject_member(group_id, member_id):
    group = dao.get_study_group(group_id)
    if not group:
        flash('스터디를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('community.index'))

    user = get_current_user()

    if group['creator_id'] != user['uid']:
        flash('스터디장만 거절할 수 있습니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    # Verify the member belongs to this group
    all_members = dao.get_study_group_members(group_id)
    member = None
    for m in all_members:
        if m['id'] == member_id:
            member = m
            break

    if not member:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    if member.get('group_id') != group_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('community.study_group_detail', group_id=group_id))

    dao.delete_study_group_member(member_id)

    flash('가입 신청이 거절되었습니다.', 'info')
    return redirect(url_for('community.study_group_detail', group_id=group_id))
