from flask import Blueprint, render_template, jsonify, Response
from flask_login import login_required, current_user
from app import db
from app.models import Course, Checkpoint, Progress, Enrollment
import csv
import io

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/instructor/<int:course_id>')
@login_required
def instructor_dashboard(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).order_by(Checkpoint.order).all()
    students = course.get_enrolled_students()
    total_students = len(students)
    
    stats = []
    for cp in checkpoints:
        completed_count = Progress.query.join(Enrollment, Progress.user_id == Enrollment.user_id).filter(
            Progress.checkpoint_id == cp.id,
            Progress.completed_at.isnot(None),
            Enrollment.course_id == course_id
        ).count()
        
        avg_duration = db.session.query(db.func.avg(Progress.duration_seconds)).filter(
            Progress.checkpoint_id == cp.id,
            Progress.duration_seconds.isnot(None)
        ).scalar() or 0
        
        completion_rate = (completed_count / total_students * 100) if total_students > 0 else 0
        
        stats.append({
            'checkpoint_id': cp.id,
            'title': cp.title,
            'completed_count': completed_count,
            'total_students': total_students,
            'completion_rate': round(completion_rate, 1),
            'avg_duration_seconds': round(avg_duration) if avg_duration else 0,
            'estimated_minutes': cp.estimated_minutes or 0
        })
    
    student_data = []
    for student in students:
        completed = Progress.query.filter(
            Progress.user_id == student.id,
            Progress.checkpoint_id.in_([cp.id for cp in checkpoints]),
            Progress.completed_at.isnot(None)
        ).count()
        
        student_data.append({
            'id': student.id,
            'username': student.username,
            'completed_checkpoints': completed,
            'total_checkpoints': len(checkpoints),
            'progress_percent': round(completed / len(checkpoints) * 100, 1) if checkpoints else 0
        })
    
    avg_progress = sum(s['progress_percent'] for s in student_data) / len(student_data) if student_data else 0
    lagging_students = [s for s in student_data if s['progress_percent'] < avg_progress * 0.7]
    
    return render_template('analytics/instructor.html', 
                         course=course, 
                         stats=stats, 
                         students=student_data,
                         lagging_students=lagging_students,
                         avg_progress=round(avg_progress, 1))

@bp.route('/student/<int:course_id>')
@login_required
def student_dashboard(course_id):
    course = Course.query.get_or_404(course_id)
    if not current_user.is_enrolled(course):
        return jsonify({'error': 'Not enrolled'}), 403
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).order_by(Checkpoint.order).all()
    
    my_progress = []
    total_time = 0
    completed_count = 0
    
    for cp in checkpoints:
        progress = Progress.query.filter_by(
            user_id=current_user.id,
            checkpoint_id=cp.id
        ).first()
        
        duration = progress.duration_seconds if progress and progress.duration_seconds else 0
        total_time += duration
        
        if progress and progress.completed_at:
            completed_count += 1
        
        my_progress.append({
            'checkpoint_id': cp.id,
            'title': cp.title,
            'order': cp.order,
            'estimated_minutes': cp.estimated_minutes or 0,
            'started': progress.started_at is not None if progress else False,
            'completed': progress.completed_at is not None if progress else False,
            'started_at': progress.started_at.isoformat() if progress and progress.started_at else None,
            'completed_at': progress.completed_at.isoformat() if progress and progress.completed_at else None,
            'duration_seconds': duration,
            'duration_minutes': round(duration / 60, 1) if duration else 0
        })
    
    sorted_by_duration = sorted([p for p in my_progress if p['duration_seconds'] > 0], 
                                key=lambda x: x['duration_seconds'], 
                                reverse=True)
    slowest_checkpoints = sorted_by_duration[:3]
    
    progress_percent = round(completed_count / len(checkpoints) * 100, 1) if checkpoints else 0
    
    course_avg = db.session.query(db.func.avg(Progress.duration_seconds)).join(
        Enrollment, Progress.user_id == Enrollment.user_id
    ).filter(
        Enrollment.course_id == course_id,
        Progress.checkpoint_id.in_([cp.id for cp in checkpoints]),
        Progress.duration_seconds.isnot(None)
    ).scalar() or 0
    
    return render_template('analytics/student.html',
                         course=course,
                         progress=my_progress,
                         progress_percent=progress_percent,
                         completed_count=completed_count,
                         total_checkpoints=len(checkpoints),
                         total_time_minutes=round(total_time / 60, 1),
                         slowest_checkpoints=slowest_checkpoints,
                         course_avg_seconds=round(course_avg))

@bp.route('/export/<int:course_id>')
@login_required
def export_csv(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).order_by(Checkpoint.order).all()
    students = course.get_enrolled_students()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    header = ['Student', 'Email']
    for cp in checkpoints:
        header.extend([f'{cp.title} - Started', f'{cp.title} - Completed', f'{cp.title} - Duration (min)'])
    writer.writerow(header)
    
    for student in students:
        row = [student.username, student.email]
        for cp in checkpoints:
            progress = Progress.query.filter_by(user_id=student.id, checkpoint_id=cp.id).first()
            if progress:
                row.append(progress.started_at.strftime('%Y-%m-%d %H:%M') if progress.started_at else '')
                row.append(progress.completed_at.strftime('%Y-%m-%d %H:%M') if progress.completed_at else '')
                row.append(round(progress.duration_seconds / 60, 1) if progress.duration_seconds else '')
            else:
                row.extend(['', '', ''])
        writer.writerow(row)
    
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=course_{course_id}_progress.csv'}
    )

@bp.route('/api/instructor/<int:course_id>')
@login_required
def instructor_api(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    checkpoints = Checkpoint.query.filter_by(course_id=course_id, deleted_at=None).order_by(Checkpoint.order).all()
    students = course.get_enrolled_students()
    total_students = len(students)
    
    checkpoint_stats = []
    for cp in checkpoints:
        completed_count = Progress.query.join(Enrollment, Progress.user_id == Enrollment.user_id).filter(
            Progress.checkpoint_id == cp.id,
            Progress.completed_at.isnot(None),
            Enrollment.course_id == course_id
        ).count()
        
        checkpoint_stats.append({
            'id': cp.id,
            'title': cp.title,
            'completed': completed_count,
            'total': total_students,
            'rate': round(completed_count / total_students * 100, 1) if total_students > 0 else 0
        })
    
    student_progress = []
    for student in students:
        progress_list = []
        for cp in checkpoints:
            p = Progress.query.filter_by(user_id=student.id, checkpoint_id=cp.id).first()
            progress_list.append({
                'checkpoint_id': cp.id,
                'completed': p.completed_at is not None if p else False
            })
        student_progress.append({
            'id': student.id,
            'username': student.username,
            'checkpoints': progress_list
        })
    
    return jsonify({
        'checkpoint_stats': checkpoint_stats,
        'student_progress': student_progress
    })
