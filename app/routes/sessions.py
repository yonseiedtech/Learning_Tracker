from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from app import db
from app.models import Course, Enrollment, VideoWatchLog, SessionCompletion, PageTimeLog, AssignmentSubmission, QuizQuestion, QuizAttempt, SubjectMember
from datetime import datetime
import base64
import io
import re

bp = Blueprint('sessions', __name__, url_prefix='/sessions')

def has_course_access(course, user, roles=['instructor', 'assistant']):
    if course.instructor_id == user.id:
        return True
    if course.subject_id:
        member = SubjectMember.query.filter_by(subject_id=course.subject_id, user_id=user.id).first()
        if member and member.role in roles:
            return True
    return False

def get_youtube_video_id(url):
    if not url:
        return None
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

@bp.route('/<int:course_id>/video')
@login_required
def video_session(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'video':
        flash('동영상 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))
    
    if not current_user.is_instructor() and not current_user.is_enrolled(course):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    is_instructor = has_course_access(course, current_user)
    
    watch_log = VideoWatchLog.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    completion = SessionCompletion.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    youtube_id = get_youtube_video_id(course.video_url) if course.video_url else None
    is_youtube = youtube_id is not None
    
    return render_template('sessions/video.html',
                         course=course,
                         watch_log=watch_log,
                         completion=completion,
                         is_instructor=is_instructor,
                         is_youtube=is_youtube,
                         youtube_id=youtube_id)

@bp.route('/<int:course_id>/video/stream')
@login_required
def video_stream(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not course.video_file_path:
        return jsonify({'error': '동영상 파일이 없습니다.'}), 404
    
    if not current_user.is_instructor() and not current_user.is_enrolled(course):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    try:
        video_data = base64.b64decode(course.video_file_path)
        return send_file(
            io.BytesIO(video_data),
            mimetype='video/mp4',
            as_attachment=False
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<int:course_id>/video/log', methods=['POST'])
@login_required
def log_video_watch(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_enrolled(course) and not has_course_access(course, current_user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    data = request.get_json()
    watched_seconds = data.get('watched_seconds', 0)
    total_duration = data.get('total_duration', 0)
    last_position = data.get('last_position', 0)
    
    watch_log = VideoWatchLog.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if not watch_log:
        watch_log = VideoWatchLog(
            course_id=course_id,
            user_id=current_user.id
        )
        db.session.add(watch_log)
    
    watch_log.watched_seconds = max(watch_log.watched_seconds, watched_seconds)
    watch_log.total_duration = total_duration
    watch_log.last_position = last_position
    watch_log.play_count += 1 if data.get('is_new_play') else 0
    
    if total_duration > 0:
        watch_log.watch_percentage = min(100.0, (watch_log.watched_seconds / total_duration) * 100)
    
    db.session.commit()
    
    auto_completed = False
    if watch_log.is_completed:
        completion = SessionCompletion.query.filter_by(
            course_id=course_id,
            user_id=current_user.id
        ).first()
        if not completion:
            completion = SessionCompletion(
                course_id=course_id,
                user_id=current_user.id,
                completion_type='auto_video',
                time_spent_seconds=watched_seconds
            )
            db.session.add(completion)
            db.session.commit()
            auto_completed = True
    
    return jsonify({
        'success': True,
        'watch_percentage': watch_log.watch_percentage,
        'is_completed': watch_log.is_completed,
        'auto_completed': auto_completed
    })

@bp.route('/<int:course_id>/material')
@login_required
def material_session(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'material':
        flash('학습 자료 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))
    
    if not current_user.is_instructor() and not current_user.is_enrolled(course):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    is_instructor = has_course_access(course, current_user)
    
    completion = SessionCompletion.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    page_time = PageTimeLog.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    return render_template('sessions/material.html',
                         course=course,
                         completion=completion,
                         page_time=page_time,
                         is_instructor=is_instructor)

@bp.route('/<int:course_id>/material/download')
@login_required
def material_download(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not course.material_file_path:
        flash('파일이 없습니다.', 'warning')
        return redirect(url_for('sessions.material_session', course_id=course_id))
    
    if not current_user.is_instructor() and not current_user.is_enrolled(course):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    try:
        file_data = base64.b64decode(course.material_file_path)
        return send_file(
            io.BytesIO(file_data),
            mimetype=course.material_file_type or 'application/octet-stream',
            as_attachment=True,
            download_name=course.material_file_name or 'material'
        )
    except Exception as e:
        flash(f'파일 다운로드 오류: {str(e)}', 'danger')
        return redirect(url_for('sessions.material_session', course_id=course_id))

@bp.route('/<int:course_id>/assignment')
@login_required
def assignment_session(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'assignment':
        flash('과제 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))
    
    if not current_user.is_instructor() and not current_user.is_enrolled(course):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    is_instructor = has_course_access(course, current_user)
    
    completion = SessionCompletion.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    submission = AssignmentSubmission.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    all_submissions = None
    if is_instructor:
        all_submissions = AssignmentSubmission.query.filter_by(course_id=course_id).all()
    
    return render_template('sessions/assignment.html',
                         course=course,
                         completion=completion,
                         submission=submission,
                         is_instructor=is_instructor,
                         all_submissions=all_submissions,
                         now=datetime.utcnow())

@bp.route('/<int:course_id>/assignment/submit', methods=['POST'])
@login_required
def submit_assignment(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'assignment':
        return jsonify({'error': '과제 세션이 아닙니다.'}), 400
    
    if not current_user.is_enrolled(course):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    content = request.form.get('content', '')
    file = request.files.get('file')
    
    submission = AssignmentSubmission.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if not submission:
        submission = AssignmentSubmission(
            course_id=course_id,
            user_id=current_user.id
        )
        db.session.add(submission)
    
    submission.content = content
    submission.submitted_at = datetime.utcnow()
    
    if file and file.filename:
        file_data = file.read()
        if len(file_data) > 100 * 1024 * 1024:
            return jsonify({'error': '파일 크기가 100MB를 초과합니다.'}), 400
        submission.file_path = base64.b64encode(file_data).decode('utf-8')
        submission.file_name = file.filename
    
    db.session.commit()
    
    flash('과제가 제출되었습니다.', 'success')
    return redirect(url_for('sessions.assignment_session', course_id=course_id))

@bp.route('/<int:course_id>/quiz')
@login_required
def quiz_session(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'quiz':
        flash('퀴즈 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))
    
    if not current_user.is_instructor() and not current_user.is_enrolled(course):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    is_instructor = has_course_access(course, current_user)
    
    completion = SessionCompletion.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    questions = QuizQuestion.query.filter_by(course_id=course_id).order_by(QuizQuestion.order).all()
    
    attempt = QuizAttempt.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).order_by(QuizAttempt.started_at.desc()).first()
    
    all_attempts = None
    if is_instructor:
        all_attempts = QuizAttempt.query.filter_by(course_id=course_id).all()
    
    return render_template('sessions/quiz.html',
                         course=course,
                         completion=completion,
                         questions=questions,
                         attempt=attempt,
                         is_instructor=is_instructor,
                         all_attempts=all_attempts)

@bp.route('/<int:course_id>/quiz/start', methods=['POST'])
@login_required
def start_quiz(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'quiz':
        return jsonify({'error': '퀴즈 세션이 아닙니다.'}), 400
    
    if not current_user.is_enrolled(course):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    existing = QuizAttempt.query.filter_by(
        course_id=course_id,
        user_id=current_user.id,
        completed_at=None
    ).first()
    
    if existing:
        return jsonify({'success': True, 'attempt_id': existing.id})
    
    questions = QuizQuestion.query.filter_by(course_id=course_id).all()
    max_score = sum(q.points for q in questions)
    
    attempt = QuizAttempt(
        course_id=course_id,
        user_id=current_user.id,
        max_score=max_score
    )
    db.session.add(attempt)
    db.session.commit()
    
    return jsonify({'success': True, 'attempt_id': attempt.id})

@bp.route('/<int:course_id>/quiz/submit', methods=['POST'])
@login_required
def submit_quiz(course_id):
    course = Course.query.get_or_404(course_id)
    
    if course.session_type != 'quiz':
        return jsonify({'error': '퀴즈 세션이 아닙니다.'}), 400
    
    if not current_user.is_enrolled(course):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    attempt = QuizAttempt.query.filter_by(
        course_id=course_id,
        user_id=current_user.id,
        completed_at=None
    ).first()
    
    if not attempt:
        return jsonify({'error': '진행 중인 퀴즈가 없습니다.'}), 400
    
    answers = request.get_json().get('answers', {})
    questions = QuizQuestion.query.filter_by(course_id=course_id).all()
    
    score = 0
    for q in questions:
        user_answer = answers.get(str(q.id), '')
        if user_answer.strip().lower() == q.correct_answer.strip().lower():
            score += q.points
    
    import json
    attempt.answers = json.dumps(answers)
    attempt.score = score
    attempt.completed_at = datetime.utcnow()
    
    db.session.commit()
    
    passed = False
    if course.quiz_pass_score:
        passed = score >= course.quiz_pass_score
    else:
        passed = score >= (attempt.max_score * 0.6)
    
    if passed:
        completion = SessionCompletion.query.filter_by(
            course_id=course_id,
            user_id=current_user.id
        ).first()
        if not completion:
            completion = SessionCompletion(
                course_id=course_id,
                user_id=current_user.id,
                completion_type='quiz_pass'
            )
            db.session.add(completion)
            db.session.commit()
    
    return jsonify({
        'success': True,
        'score': score,
        'max_score': attempt.max_score,
        'passed': passed
    })

@bp.route('/<int:course_id>/complete', methods=['POST'])
@login_required
def mark_complete(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_enrolled(course) and not has_course_access(course, current_user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    data = request.get_json() or {}
    time_spent = data.get('time_spent_seconds', 0)
    
    completion = SessionCompletion.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if completion:
        return jsonify({'success': True, 'message': '이미 완료되었습니다.'})
    
    completion = SessionCompletion(
        course_id=course_id,
        user_id=current_user.id,
        completion_type='manual',
        time_spent_seconds=time_spent
    )
    db.session.add(completion)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '완료 처리되었습니다.'})

@bp.route('/<int:course_id>/uncomplete', methods=['POST'])
@login_required
def mark_uncomplete(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_enrolled(course) and not has_course_access(course, current_user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    completion = SessionCompletion.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if completion:
        db.session.delete(completion)
        db.session.commit()
    
    return jsonify({'success': True, 'message': '완료 취소되었습니다.'})

@bp.route('/<int:course_id>/log-time', methods=['POST'])
@login_required
def log_page_time(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not current_user.is_enrolled(course) and not has_course_access(course, current_user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403
    
    data = request.get_json() or {}
    seconds = data.get('seconds', 0)
    
    page_time = PageTimeLog.query.filter_by(
        course_id=course_id,
        user_id=current_user.id
    ).first()
    
    if not page_time:
        page_time = PageTimeLog(
            course_id=course_id,
            user_id=current_user.id
        )
        db.session.add(page_time)
    
    page_time.total_seconds += seconds
    page_time.last_active_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'total_seconds': page_time.total_seconds
    })
