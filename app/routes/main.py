from flask import Blueprint, render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from app.models import Course, Enrollment

bp = Blueprint('main', __name__)

@bp.route('/health')
def health():
    return jsonify({'status': 'ok'}), 200

@bp.route('/')
def index():
    if request.args.get('health') == '1':
        return 'OK', 200
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_instructor():
        courses = Course.query.filter_by(instructor_id=current_user.id).all()
        return render_template('dashboard/instructor.html', courses=courses)
    else:
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
        courses = [e.course for e in enrollments]
        return render_template('dashboard/student.html', courses=courses)
