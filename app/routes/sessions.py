from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from app.decorators import auth_required, get_current_user
from app import firestore_dao as dao
from app.services.storage import download_file, get_signed_url, upload_assignment
from datetime import datetime
import io
import re

bp = Blueprint('sessions', __name__, url_prefix='/sessions')

def has_course_access(course, user, roles=None):
    if roles is None:
        roles = ['instructor', 'assistant']
    if course.get('instructor_id') == user.uid:
        return True
    if course.get('subject_id'):
        member = dao.get_subject_member(course['subject_id'], user.uid)
        if member and member.get('role') in roles:
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

@bp.route('/<course_id>/video')
@auth_required
def video_session(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') not in ['video', 'video_external']:
        flash('동영상 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))

    is_instructor_user = has_course_access(course, user)
    if not is_instructor_user and not dao.is_enrolled(user.uid, course['id']):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    is_instructor = has_course_access(course, user)

    watch_log = dao.get_watch_log(course_id, user.uid)

    completion = dao.get_session_completion(course_id, user.uid)

    youtube_id = get_youtube_video_id(course.get('video_url')) if course.get('video_url') else None
    is_youtube = youtube_id is not None

    page_time = dao.get_page_time_log(course_id, user.uid)

    dao.enrich_course(course)
    return render_template('sessions/video.html',
                         course=course,
                         watch_log=watch_log,
                         completion=completion,
                         is_instructor=is_instructor,
                         is_youtube=is_youtube,
                         youtube_id=youtube_id,
                         page_time=page_time)

@bp.route('/<course_id>/video/stream')
@auth_required
def video_stream(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if not course.get('video_file_path'):
        return jsonify({'error': '동영상 파일이 없습니다.'}), 404

    is_instructor_user = has_course_access(course, user)
    if not is_instructor_user and not dao.is_enrolled(user.uid, course['id']):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    try:
        signed_url = get_signed_url(course['video_file_path'])
        return redirect(signed_url)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/<course_id>/video/log', methods=['POST'])
@auth_required
def log_video_watch(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if not dao.is_enrolled(user.uid, course['id']) and not has_course_access(course, user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    data = request.get_json()
    watched_seconds = data.get('watched_seconds', 0)
    total_duration = data.get('total_duration', 0)
    last_position = data.get('last_position', 0)

    watch_log = dao.get_watch_log(course_id, user.uid)

    if not watch_log:
        watch_log = {
            'watched_seconds': 0,
            'total_duration': 0,
            'last_position': 0,
            'play_count': 0,
            'watch_percentage': 0.0
        }

    new_watched_seconds = max(watch_log.get('watched_seconds', 0), watched_seconds)
    new_play_count = watch_log.get('play_count', 0) + (1 if data.get('is_new_play') else 0)

    watch_percentage = watch_log.get('watch_percentage', 0.0)
    if total_duration > 0:
        watch_percentage = min(100.0, (new_watched_seconds / total_duration) * 100)

    dao.create_or_update_watch_log(course_id, user.uid, {
        'watched_seconds': new_watched_seconds,
        'total_duration': total_duration,
        'last_position': last_position,
        'play_count': new_play_count,
        'watch_percentage': watch_percentage
    })

    return jsonify({
        'success': True,
        'watch_percentage': watch_percentage,
        'watched_seconds': new_watched_seconds
    })

@bp.route('/<course_id>/material')
@auth_required
def material_session(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') != 'material':
        flash('학습 자료 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))

    is_instructor_user = has_course_access(course, user)
    if not is_instructor_user and not dao.is_enrolled(user.uid, course['id']):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    is_instructor = has_course_access(course, user)

    completion = dao.get_session_completion(course_id, user.uid)

    page_time = dao.get_page_time_log(course_id, user.uid)

    dao.enrich_course(course)
    return render_template('sessions/material.html',
                         course=course,
                         completion=completion,
                         page_time=page_time,
                         is_instructor=is_instructor)

@bp.route('/<course_id>/material/download')
@auth_required
def material_download(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if not course.get('material_file_path'):
        flash('파일이 없습니다.', 'warning')
        return redirect(url_for('sessions.material_session', course_id=course_id))

    is_instructor_user = has_course_access(course, user)
    if not is_instructor_user and not dao.is_enrolled(user.uid, course['id']):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    try:
        signed_url = get_signed_url(course['material_file_path'])
        return redirect(signed_url)
    except Exception as e:
        flash(f'파일 다운로드 오류: {str(e)}', 'danger')
        return redirect(url_for('sessions.material_session', course_id=course_id))

@bp.route('/<course_id>/assignment')
@auth_required
def assignment_session(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') != 'assignment':
        flash('과제 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))

    is_instructor_user = has_course_access(course, user)
    if not is_instructor_user and not dao.is_enrolled(user.uid, course['id']):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    is_instructor = has_course_access(course, user)

    completion = dao.get_session_completion(course_id, user.uid)

    submission = dao.get_submission(course_id, user.uid)

    all_submissions = None
    if is_instructor:
        all_submissions = dao.get_submissions_by_course(course_id)

    page_time = dao.get_page_time_log(course_id, user.uid)

    dao.enrich_course(course)
    if all_submissions:
        dao.enrich_with_user(all_submissions)
    return render_template('sessions/assignment.html',
                         course=course,
                         completion=completion,
                         submission=submission,
                         is_instructor=is_instructor,
                         all_submissions=all_submissions,
                         page_time=page_time,
                         now=datetime.utcnow())

@bp.route('/<course_id>/assignment/submit', methods=['POST'])
@auth_required
def submit_assignment(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') != 'assignment':
        return jsonify({'error': '과제 세션이 아닙니다.'}), 400

    if not dao.is_enrolled(user.uid, course['id']):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    content = request.form.get('content', '')
    file = request.files.get('file')

    submission_data = {
        'content': content,
        'submitted_at': datetime.utcnow()
    }

    if file and file.filename:
        file_data = file.read()
        if len(file_data) > 100 * 1024 * 1024:
            return jsonify({'error': '파일 크기가 100MB를 초과합니다.'}), 400
        storage_path = upload_assignment(course_id, user.uid, file_data, file.filename)
        submission_data['file_path'] = storage_path
        submission_data['file_name'] = file.filename

    dao.create_or_update_submission(course_id, user.uid, submission_data)

    flash('과제가 제출되었습니다.', 'success')
    return redirect(url_for('sessions.assignment_session', course_id=course_id))

@bp.route('/<course_id>/quiz')
@auth_required
def quiz_session(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') != 'quiz':
        flash('퀴즈 세션이 아닙니다.', 'warning')
        return redirect(url_for('courses.view', course_id=course_id))

    is_instructor_user = has_course_access(course, user)
    if not is_instructor_user and not dao.is_enrolled(user.uid, course['id']):
        flash('이 세션에 접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    is_instructor = has_course_access(course, user)

    completion = dao.get_session_completion(course_id, user.uid)

    questions = dao.get_quiz_questions(course_id)

    attempt = dao.get_quiz_attempt(course_id, user.uid, completed=None)

    all_attempts = None
    if is_instructor:
        all_attempts = dao.get_quiz_attempts_by_course(course_id)

    dao.enrich_course(course)
    if all_attempts:
        dao.enrich_with_user(all_attempts)
    return render_template('sessions/quiz.html',
                         course=course,
                         completion=completion,
                         questions=questions,
                         attempt=attempt,
                         is_instructor=is_instructor,
                         all_attempts=all_attempts)

@bp.route('/<course_id>/quiz/start', methods=['POST'])
@auth_required
def start_quiz(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') != 'quiz':
        return jsonify({'error': '퀴즈 세션이 아닙니다.'}), 400

    if not dao.is_enrolled(user.uid, course['id']):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    existing = dao.get_quiz_attempt(course_id, user.uid, completed=False)

    if existing:
        return jsonify({'success': True, 'attempt_id': existing['id']})

    questions = dao.get_quiz_questions(course_id)
    max_score = sum(q.get('points', 0) for q in questions)

    attempt_id = dao.create_quiz_attempt({
        'course_id': course_id,
        'user_id': user.uid,
        'max_score': max_score,
        'started_at': datetime.utcnow(),
        'completed_at': None,
        'score': None,
        'answers': None
    })

    return jsonify({'success': True, 'attempt_id': attempt_id})

@bp.route('/<course_id>/quiz/submit', methods=['POST'])
@auth_required
def submit_quiz(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if course.get('session_type') != 'quiz':
        return jsonify({'error': '퀴즈 세션이 아닙니다.'}), 400

    if not dao.is_enrolled(user.uid, course['id']):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    attempt = dao.get_quiz_attempt(course_id, user.uid, completed=False)

    if not attempt:
        return jsonify({'error': '진행 중인 퀴즈가 없습니다.'}), 400

    answers = request.get_json().get('answers', {})
    questions = dao.get_quiz_questions(course_id)

    score = 0
    for q in questions:
        user_answer = answers.get(str(q['id']), '')
        if user_answer.strip().lower() == q['correct_answer'].strip().lower():
            score += q.get('points', 0)

    dao.update_quiz_attempt(attempt['id'], {
        'answers': answers,
        'score': score,
        'completed_at': datetime.utcnow()
    })

    max_score = attempt.get('max_score', 0)
    passed = False
    if course.get('quiz_pass_score'):
        passed = score >= course['quiz_pass_score']
    else:
        passed = score >= (max_score * 0.6)

    if passed:
        completion = dao.get_session_completion(course_id, user.uid)
        if not completion:
            dao.create_session_completion({
                'course_id': course_id,
                'user_id': user.uid,
                'completion_type': 'quiz_pass',
                'completed_at': datetime.utcnow()
            })

    return jsonify({
        'success': True,
        'score': score,
        'max_score': max_score,
        'passed': passed,
        'attempt_id': attempt['id']
    })

@bp.route('/<course_id>/quiz/result/<attempt_id>')
@auth_required
def quiz_result(course_id, attempt_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    attempt = dao.get_quiz_attempt(course_id, user.uid, completed=None)
    # If attempt_id doesn't match, try fetching by ID directly
    # For now, we look up attempts for this course and find the right one
    all_attempts = dao.get_quiz_attempts_by_course(course_id)
    attempt = None
    for a in all_attempts:
        if a['id'] == attempt_id:
            attempt = a
            break

    if not attempt:
        flash('잘못된 접근입니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if attempt.get('course_id') != course_id:
        flash('잘못된 접근입니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if attempt.get('user_id') != user.uid and not has_course_access(course, user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('main.dashboard'))

    if not attempt.get('completed_at'):
        flash('아직 완료되지 않은 퀴즈입니다.', 'warning')
        return redirect(url_for('sessions.quiz_session', course_id=course_id))

    questions = dao.get_quiz_questions(course_id)

    # In Firestore, answers are stored as a dict directly (not JSON string)
    user_answers = attempt.get('answers') or {}

    correct_count = 0
    question_results = []
    for q in questions:
        user_answer = user_answers.get(str(q['id']), '')
        is_correct = user_answer.strip().lower() == q['correct_answer'].strip().lower()
        if is_correct:
            correct_count += 1
        question_results.append({
            'question': q,
            'user_answer': user_answer,
            'is_correct': is_correct
        })

    passed = False
    if course.get('quiz_pass_score'):
        passed = attempt.get('score', 0) >= course['quiz_pass_score']
    else:
        passed = attempt.get('score', 0) >= (attempt.get('max_score', 0) * 0.6)

    if passed:
        comment = "축하합니다! 퀴즈를 통과했습니다. 다음 학습으로 진행하세요."
    else:
        wrong_count = len(questions) - correct_count
        if wrong_count <= len(questions) * 0.2:
            comment = "조금만 더 노력하면 합격할 수 있습니다! 틀린 문제를 다시 확인해보세요."
        elif wrong_count <= len(questions) * 0.5:
            comment = "학습 내용을 한 번 더 복습하고 다시 도전해보세요. 핵심 개념 위주로 정리하면 도움이 됩니다."
        else:
            comment = "학습 자료를 처음부터 다시 꼼꼼하게 살펴보세요. 필요하다면 관련 보충 자료도 함께 학습해보세요."

    dao.enrich_course(course)
    return render_template('sessions/quiz_result.html',
                         course=course,
                         attempt=attempt,
                         questions=questions,
                         question_results=question_results,
                         correct_count=correct_count,
                         passed=passed,
                         comment=comment)

@bp.route('/<course_id>/complete', methods=['POST'])
@auth_required
def mark_complete(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if not dao.is_enrolled(user.uid, course['id']) and not has_course_access(course, user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    data = request.get_json() or {}
    time_spent = data.get('time_spent_seconds', 0)

    completion = dao.get_session_completion(course_id, user.uid)

    if completion:
        return jsonify({'success': True, 'message': '이미 완료되었습니다.'})

    dao.create_session_completion({
        'course_id': course_id,
        'user_id': user.uid,
        'completion_type': 'manual',
        'time_spent_seconds': time_spent,
        'completed_at': datetime.utcnow()
    })

    return jsonify({'success': True, 'message': '완료 처리되었습니다.'})

@bp.route('/<course_id>/uncomplete', methods=['POST'])
@auth_required
def mark_uncomplete(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if not dao.is_enrolled(user.uid, course['id']) and not has_course_access(course, user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    completion = dao.get_session_completion(course_id, user.uid)

    if completion:
        dao.delete_session_completion(course_id, user.uid)

    return jsonify({'success': True, 'message': '완료 취소되었습니다.'})

@bp.route('/<course_id>/log-time', methods=['POST'])
@auth_required
def log_page_time(course_id):
    user = get_current_user()
    course = dao.get_course(course_id)
    if not course:
        return jsonify({'error': 'Course not found'}), 404

    if not dao.is_enrolled(user.uid, course['id']) and not has_course_access(course, user):
        return jsonify({'error': '접근 권한이 없습니다.'}), 403

    data = request.get_json() or {}
    seconds = data.get('seconds', 0)

    page_time = dao.get_page_time_log(course_id, user.uid)

    current_total = (page_time.get('total_seconds', 0) if page_time else 0) + seconds

    dao.create_or_update_page_time_log(course_id, user.uid, {
        'total_seconds': current_total,
        'last_active_at': datetime.utcnow()
    })

    auto_completed = False
    min_time = course.get('min_completion_time') or 60

    if course.get('session_type') in ['video', 'video_external'] and current_total >= min_time:
        completion = dao.get_session_completion(course_id, user.uid)
        if not completion:
            dao.create_session_completion({
                'course_id': course_id,
                'user_id': user.uid,
                'completion_type': 'auto_time',
                'time_spent_seconds': current_total,
                'completed_at': datetime.utcnow()
            })
            auto_completed = True

    return jsonify({
        'success': True,
        'total_seconds': current_total,
        'auto_completed': auto_completed,
        'min_completion_time': min_time
    })
