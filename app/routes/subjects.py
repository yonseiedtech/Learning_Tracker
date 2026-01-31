from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import Subject, Course, Enrollment, SubjectEnrollment, SubjectMember, User
from app.forms import SubjectForm
from datetime import datetime
import io
from openpyxl import Workbook, load_workbook

bp = Blueprint('subjects', __name__, url_prefix='/subjects')

MAX_FILE_SIZE = 100 * 1024 * 1024

def has_subject_access(subject, user, roles=['instructor', 'assistant']):
    if subject.instructor_id == user.id:
        return True
    member = SubjectMember.query.filter_by(subject_id=subject.id, user_id=user.id).first()
    if member and member.role in roles:
        return True
    return False

@bp.route('/')
@login_required
def list_subjects():
    if current_user.is_instructor():
        enrolled_subjects = Subject.query.filter_by(instructor_id=current_user.id).filter(Subject.deleted_at.is_(None)).order_by(Subject.created_at.desc()).all()
        all_subjects = []
    else:
        enrolled_subject_ids = db.session.query(SubjectEnrollment.subject_id).filter(
            SubjectEnrollment.user_id == current_user.id
        ).all()
        enrolled_ids = [s[0] for s in enrolled_subject_ids]
        enrolled_subjects = Subject.query.filter(Subject.id.in_(enrolled_ids), Subject.deleted_at.is_(None), Subject.is_visible == True).all() if enrolled_ids else []
        all_subjects = Subject.query.filter(
            ~Subject.id.in_(enrolled_ids) if enrolled_ids else True,
            Subject.deleted_at.is_(None),
            Subject.is_visible == True
        ).order_by(Subject.created_at.desc()).all()
    
    return render_template('subjects/list.html', 
                          enrolled_subjects=enrolled_subjects, 
                          all_subjects=all_subjects,
                          is_instructor=current_user.is_instructor())

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_instructor():
        flash('강사만 과목을 생성할 수 있습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            title=form.title.data,
            description=form.description.data,
            instructor_id=current_user.id,
            invite_code=Subject.generate_invite_code()
        )
        db.session.add(subject)
        db.session.flush()
        
        member = SubjectMember(
            subject_id=subject.id,
            user_id=current_user.id,
            role='instructor'
        )
        db.session.add(member)
        db.session.commit()
        flash('과목이 생성되었습니다.', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    return render_template('subjects/create.html', form=form)

@bp.route('/<int:subject_id>')
@login_required
def view(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    if subject.deleted_at:
        if not (current_user.is_instructor() and subject.instructor_id == current_user.id):
            flash('해당 과목을 찾을 수 없습니다.', 'danger')
            return redirect(url_for('subjects.list_subjects'))
    
    if not subject.is_visible:
        if not (current_user.is_instructor() and subject.instructor_id == current_user.id):
            flash('해당 과목은 비공개 상태입니다.', 'warning')
            return redirect(url_for('subjects.list_subjects'))
    
    courses = subject.courses.filter(Course.deleted_at.is_(None)).order_by(Course.week_number.asc().nullslast(), Course.created_at.asc()).all()
    
    is_enrolled = False
    if not current_user.is_instructor():
        subject_enrollment = SubjectEnrollment.query.filter_by(
            subject_id=subject_id, 
            user_id=current_user.id
        ).first()
        is_enrolled = subject_enrollment is not None
    
    return render_template('subjects/view.html', subject=subject, courses=courses, is_enrolled=is_enrolled)

@bp.route('/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject.title = form.title.data
        subject.description = form.description.data
        db.session.commit()
        flash('과목이 수정되었습니다.', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    return render_template('subjects/edit.html', form=form, subject=subject)

@bp.route('/<int:subject_id>/add-course', methods=['GET', 'POST'])
@login_required
def add_course(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    from app.forms import CourseForm
    import base64
    
    form = CourseForm()
    
    if form.validate_on_submit():
        week_num = form.week_number.data if form.week_number.data else subject.courses.count() + 1
        
        course = Course(
            title=form.title.data,
            description=form.description.data,
            instructor_id=current_user.id,
            subject_id=subject.id,
            week_number=week_num,
            session_number=form.session_number.data,
            session_type=form.session_type.data,
            visibility=form.visibility.data,
            video_url=form.video_url.data if form.session_type.data == 'video' else None,
            assignment_description=form.assignment_description.data if form.session_type.data == 'assignment' else None,
            quiz_time_limit=form.quiz_time_limit.data if form.session_type.data == 'quiz' else None,
            quiz_pass_score=form.quiz_pass_score.data if form.session_type.data == 'quiz' else None,
            invite_code=Course.generate_invite_code()
        )
        
        if form.start_date.data:
            course.start_date = datetime.strptime(form.start_date.data, '%Y-%m-%dT%H:%M')
        if form.end_date.data:
            course.end_date = datetime.strptime(form.end_date.data, '%Y-%m-%dT%H:%M')
        if form.attendance_start.data:
            course.attendance_start = datetime.strptime(form.attendance_start.data, '%Y-%m-%dT%H:%M')
        if form.attendance_end.data:
            course.attendance_end = datetime.strptime(form.attendance_end.data, '%Y-%m-%dT%H:%M')
        if form.late_allowed.data and form.late_end.data:
            course.late_allowed = True
            course.late_end = datetime.strptime(form.late_end.data, '%Y-%m-%dT%H:%M')
        if form.assignment_due_date.data:
            course.assignment_due_date = datetime.strptime(form.assignment_due_date.data, '%Y-%m-%dT%H:%M')
        
        if form.session_type.data == 'video' and 'video_file' in request.files:
            video_file = request.files['video_file']
            if video_file and video_file.filename:
                file_content = video_file.read()
                if len(file_content) > MAX_FILE_SIZE:
                    flash('파일 크기가 100MB를 초과합니다.', 'danger')
                    return render_template('subjects/add_course.html', form=form, subject=subject)
                course.video_file_name = video_file.filename
                course.video_file_path = base64.b64encode(file_content).decode('utf-8')
                course.preparation_status = 'ready'
        elif form.session_type.data == 'video' and form.video_url.data:
            course.preparation_status = 'ready'
        
        if form.session_type.data == 'material' and 'material_file' in request.files:
            material_file = request.files['material_file']
            if material_file and material_file.filename:
                file_content = material_file.read()
                if len(file_content) > MAX_FILE_SIZE:
                    flash('파일 크기가 100MB를 초과합니다.', 'danger')
                    return render_template('subjects/add_course.html', form=form, subject=subject)
                course.material_file_name = material_file.filename
                ext = material_file.filename.rsplit('.', 1)[-1].lower() if '.' in material_file.filename else ''
                course.material_file_type = ext
                course.material_file_path = base64.b64encode(file_content).decode('utf-8')
                course.preparation_status = 'ready'
        
        if form.session_type.data == 'live_session':
            course.preparation_status = 'ready'
        
        db.session.add(course)
        db.session.commit()
        
        session_type_names = {
            'live_session': '라이브 세션',
            'video': '동영상 시청',
            'material': '학습 자료',
            'assignment': '과제 제출',
            'quiz': '퀴즈'
        }
        flash(f'{session_type_names.get(form.session_type.data, "세션")}이(가) 추가되었습니다.', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    
    return render_template('subjects/add_course.html', form=form, subject=subject)

@bp.route('/<int:subject_id>/regenerate-code', methods=['POST'])
@login_required
def regenerate_code(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    
    subject.invite_code = Subject.generate_invite_code()
    db.session.commit()
    return jsonify({'success': True, 'invite_code': subject.invite_code})

@bp.route('/<int:subject_id>/enroll', methods=['POST'])
@login_required
def enroll_subject(subject_id):
    if current_user.is_instructor():
        flash('강사는 과목 등록을 할 수 없습니다.', 'warning')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject = Subject.query.get_or_404(subject_id)
    
    if subject.deleted_at or not subject.is_visible:
        flash('해당 과목에 등록할 수 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    existing_enrollment = SubjectEnrollment.query.filter_by(
        subject_id=subject_id,
        user_id=current_user.id
    ).first()
    
    if existing_enrollment:
        flash('이미 해당 과목에 등록되어 있습니다.', 'info')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject_enrollment = SubjectEnrollment(
        subject_id=subject_id,
        user_id=current_user.id
    )
    db.session.add(subject_enrollment)
    
    courses = subject.courses.filter(Course.deleted_at.is_(None), Course.visibility != 'private').all()
    enrolled_count = 0
    for course in courses:
        if not current_user.is_enrolled(course):
            enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
            db.session.add(enrollment)
            enrolled_count += 1
    
    db.session.commit()
    flash(f'{subject.title} 과목에 등록되었습니다. ({enrolled_count}개 세션 자동 등록)', 'success')
    return redirect(url_for('subjects.view', subject_id=subject_id))


@bp.route('/<int:subject_id>/unenroll', methods=['POST'])
@login_required
def unenroll_subject(subject_id):
    if current_user.is_instructor():
        flash('강사는 과목 등록 취소를 할 수 없습니다.', 'warning')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject = Subject.query.get_or_404(subject_id)
    
    subject_enrollment = SubjectEnrollment.query.filter_by(
        subject_id=subject_id,
        user_id=current_user.id
    ).first()
    
    if not subject_enrollment:
        flash('해당 과목에 등록되어 있지 않습니다.', 'warning')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    db.session.delete(subject_enrollment)
    
    courses = subject.courses.all()
    for course in courses:
        enrollment = Enrollment.query.filter_by(
            course_id=course.id,
            user_id=current_user.id
        ).first()
        if enrollment:
            db.session.delete(enrollment)
    
    db.session.commit()
    flash(f'{subject.title} 과목 등록이 취소되었습니다.', 'success')
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/enroll-by-code', methods=['POST'])
@login_required
def enroll_by_code():
    if current_user.is_instructor():
        flash('강사는 과목 등록을 할 수 없습니다.', 'warning')
        return redirect(url_for('main.dashboard'))
    
    invite_code = request.form.get('invite_code', '').strip().upper()
    if not invite_code:
        flash('초대 코드를 입력하세요.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    subject = Subject.query.filter_by(invite_code=invite_code).first()
    if subject and not subject.deleted_at and subject.is_visible:
        existing_enrollment = SubjectEnrollment.query.filter_by(
            subject_id=subject.id,
            user_id=current_user.id
        ).first()
        
        if existing_enrollment:
            flash('이미 해당 과목에 등록되어 있습니다.', 'info')
            return redirect(url_for('subjects.view', subject_id=subject.id))
        
        subject_enrollment = SubjectEnrollment(
            subject_id=subject.id,
            user_id=current_user.id
        )
        db.session.add(subject_enrollment)
        
        courses = subject.courses.filter(Course.deleted_at.is_(None), Course.visibility != 'private').all()
        enrolled_count = 0
        for course in courses:
            if not current_user.is_enrolled(course):
                enrollment = Enrollment(user_id=current_user.id, course_id=course.id)
                db.session.add(enrollment)
                enrolled_count += 1
        
        db.session.commit()
        flash(f'{subject.title} 과목에 등록되었습니다. ({enrolled_count}개 세션 자동 등록)', 'success')
        return redirect(url_for('subjects.view', subject_id=subject.id))
    
    flash('유효하지 않은 초대 코드입니다.', 'danger')
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    subject.deleted_at = datetime.now()
    db.session.commit()
    flash(f'{subject.title} 과목이 삭제되었습니다.', 'success')
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/<int:subject_id>/toggle-visibility', methods=['POST'])
@login_required
def toggle_subject_visibility(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    subject.is_visible = not subject.is_visible
    db.session.commit()
    status = '공개' if subject.is_visible else '비공개'
    flash(f'{subject.title} 과목이 {status}로 변경되었습니다.', 'success')
    return redirect(url_for('subjects.view', subject_id=subject_id))


@bp.route('/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    subject_id = course.subject_id
    course.deleted_at = datetime.now()
    db.session.commit()
    flash(f'{course.title} 세션이 삭제되었습니다.', 'success')
    
    if subject_id:
        return redirect(url_for('subjects.view', subject_id=subject_id))
    return redirect(url_for('subjects.list_subjects'))


@bp.route('/course/<int:course_id>/toggle-visibility', methods=['POST'])
@login_required
def toggle_course_visibility(course_id):
    course = Course.query.get_or_404(course_id)
    if course.instructor_id != current_user.id:
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.list_subjects'))
    
    if course.visibility == 'private':
        course.visibility = 'public'
        status = '공개'
    else:
        course.visibility = 'private'
        status = '비공개'
    db.session.commit()
    flash(f'{course.title} 세션이 {status}로 변경되었습니다.', 'success')
    
    if course.subject_id:
        return redirect(url_for('subjects.view', subject_id=course.subject_id))
    return redirect(url_for('courses.view', course_id=course_id))


@bp.route('/<int:subject_id>/members')
@login_required
def members(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('접근 권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    members_list = SubjectMember.query.filter_by(subject_id=subject_id).all()
    
    member_data = {
        'instructors': [],
        'assistants': [],
        'students': []
    }
    
    for member in members_list:
        user = member.user
        data = {'member': member, 'user': user}
        if member.role == 'instructor':
            member_data['instructors'].append(data)
        elif member.role == 'assistant':
            member_data['assistants'].append(data)
        else:
            member_data['students'].append(data)
    
    enrolled_students = SubjectEnrollment.query.filter_by(subject_id=subject_id).all()
    student_users = [e.user for e in enrolled_students]
    
    return render_template('subjects/members.html', 
                          subject=subject, 
                          member_data=member_data,
                          enrolled_students=student_users)


@bp.route('/<int:subject_id>/members/add', methods=['POST'])
@login_required
def add_member(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    
    email = request.form.get('email')
    role = request.form.get('role', 'student')
    
    if role not in ['instructor', 'assistant', 'student']:
        flash('잘못된 역할입니다.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    user = User.query.filter_by(email=email).first()
    if not user:
        flash('해당 이메일의 사용자를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    existing = SubjectMember.query.filter_by(subject_id=subject_id, user_id=user.id).first()
    if existing:
        existing.role = role
        db.session.commit()
        flash(f'{user.display_name}의 역할이 {SubjectMember.get_role_display(role)}(으)로 변경되었습니다.', 'success')
    else:
        member = SubjectMember(subject_id=subject_id, user_id=user.id, role=role)
        db.session.add(member)
        
        subject_enrollment = SubjectEnrollment.query.filter_by(
            subject_id=subject_id, user_id=user.id
        ).first()
        if not subject_enrollment:
            subject_enrollment = SubjectEnrollment(subject_id=subject_id, user_id=user.id)
            db.session.add(subject_enrollment)
        
        if role == 'student':
            courses = Course.query.filter_by(subject_id=subject_id, deleted_at=None).filter(
                Course.visibility != 'private'
            ).all()
            enrolled_count = 0
            for course in courses:
                existing_enrollment = Enrollment.query.filter_by(
                    course_id=course.id, user_id=user.id
                ).first()
                if not existing_enrollment:
                    enrollment = Enrollment(course_id=course.id, user_id=user.id)
                    db.session.add(enrollment)
                    enrolled_count += 1
        
        db.session.commit()
        flash(f'{user.display_name}이(가) {SubjectMember.get_role_display(role)}(으)로 추가되었습니다.', 'success')
    
    return redirect(url_for('subjects.members', subject_id=subject_id))


@bp.route('/<int:subject_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
def remove_member(subject_id, member_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    member = SubjectMember.query.get_or_404(member_id)
    if member.subject_id != subject_id:
        flash('잘못된 요청입니다.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    user_email = member.user.email
    db.session.delete(member)
    db.session.commit()
    flash(f'{user_email}이(가) 역할에서 제외되었습니다.', 'success')
    return redirect(url_for('subjects.members', subject_id=subject_id))


@bp.route('/<int:subject_id>/members/<int:member_id>/change-role', methods=['POST'])
@login_required
def change_member_role(subject_id, member_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        return jsonify({'success': False, 'message': '권한이 없습니다.'}), 403
    
    member = SubjectMember.query.get_or_404(member_id)
    if member.subject_id != subject_id:
        return jsonify({'success': False, 'message': '잘못된 요청입니다.'}), 400
    
    new_role = request.form.get('role')
    if new_role not in ['instructor', 'assistant', 'student']:
        return jsonify({'success': False, 'message': '잘못된 역할입니다.'}), 400
    
    member.role = new_role
    db.session.commit()
    flash(f'{member.user.email}의 역할이 {SubjectMember.get_role_display(new_role)}(으)로 변경되었습니다.', 'success')
    return redirect(url_for('subjects.members', subject_id=subject_id))


@bp.route('/<int:subject_id>/members/excel-template')
@login_required
def download_member_template(subject_id):
    from flask import Response
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.view', subject_id=subject_id))
    
    wb = Workbook()
    ws = wb.active
    ws.title = '사용자 등록'
    
    ws['A1'] = '이메일 (필수)'
    ws['B1'] = '역할 (선택: instructor/assistant/student)'
    ws['C1'] = '이름 (신규 사용자시 필수)'
    
    from openpyxl.styles import Font, PatternFill
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color='E0E0E0', end_color='E0E0E0', fill_type='solid')
    for col in ['A', 'B', 'C']:
        ws[f'{col}1'].font = header_font
        ws[f'{col}1'].fill = header_fill
        ws.column_dimensions[col].width = 40
    
    example_font = Font(italic=True, color='888888')
    ws['A2'] = '(예시) example@email.com'
    ws['B2'] = '(예시) student'
    ws['C2'] = '(예시) 홍길동'
    for col in ['A', 'B', 'C']:
        ws[f'{col}2'].font = example_font
    
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment;filename=member_template_{subject_id}.xlsx'}
    )


@bp.route('/<int:subject_id>/members/upload-excel', methods=['POST'])
@login_required
def upload_members_excel(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if not has_subject_access(subject, current_user):
        flash('권한이 없습니다.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    if 'excel_file' not in request.files:
        flash('파일을 선택해주세요.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    file = request.files['excel_file']
    if file.filename == '':
        flash('파일을 선택해주세요.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        flash('엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.', 'danger')
        return redirect(url_for('subjects.members', subject_id=subject_id))
    
    try:
        wb = load_workbook(file)
        ws = wb.active
        
        added_count = 0
        updated_count = 0
        skipped_count = 0
        error_messages = []
        
        for row_num, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
            if not row or not row[0]:
                continue
                
            email = str(row[0]).strip()
            role = str(row[1]).strip().lower() if row[1] else 'student'
            name = str(row[2]).strip() if len(row) > 2 and row[2] else None
            
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                skipped_count += 1
                error_messages.append(f'행 {row_num}: {email} - 잘못된 이메일 형식')
                continue
            
            if role not in ['instructor', 'assistant', 'student']:
                role = 'student'
            
            user = User.query.filter_by(email=email).first()
            if not user:
                if not name:
                    skipped_count += 1
                    error_messages.append(f'행 {row_num}: {email} - 등록되지 않은 사용자 (신규 등록시 이름 필수)')
                    continue
                
                import secrets
                username = email.split('@')[0]
                base_username = username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                temp_password = secrets.token_urlsafe(8)
                user = User(
                    username=username,
                    email=email,
                    full_name=name,
                    role='student' if role == 'student' else 'instructor'
                )
                user.set_password(temp_password)
                db.session.add(user)
                db.session.flush()
                error_messages.append(f'행 {row_num}: {email} - 신규 사용자 생성 (임시 비밀번호: {temp_password})')
            
            existing = SubjectMember.query.filter_by(subject_id=subject_id, user_id=user.id).first()
            if existing:
                if existing.role != role:
                    existing.role = role
                    updated_count += 1
                else:
                    skipped_count += 1
            else:
                member = SubjectMember(subject_id=subject_id, user_id=user.id, role=role)
                db.session.add(member)
                
                subject_enrollment = SubjectEnrollment.query.filter_by(
                    subject_id=subject_id, user_id=user.id
                ).first()
                if not subject_enrollment:
                    subject_enrollment = SubjectEnrollment(subject_id=subject_id, user_id=user.id)
                    db.session.add(subject_enrollment)
                
                if role == 'student':
                    courses = Course.query.filter_by(subject_id=subject_id, deleted_at=None).filter(
                        Course.visibility != 'private'
                    ).all()
                    for course in courses:
                        existing_enrollment = Enrollment.query.filter_by(
                            course_id=course.id, user_id=user.id
                        ).first()
                        if not existing_enrollment:
                            enrollment = Enrollment(course_id=course.id, user_id=user.id)
                            db.session.add(enrollment)
                
                added_count += 1
        
        db.session.commit()
        
        message_parts = []
        if added_count > 0:
            message_parts.append(f'{added_count}명 추가')
        if updated_count > 0:
            message_parts.append(f'{updated_count}명 역할 변경')
        if skipped_count > 0:
            message_parts.append(f'{skipped_count}명 건너뜀')
        
        if message_parts:
            flash(f'엑셀 업로드 완료: {", ".join(message_parts)}', 'success')
        else:
            flash('처리할 데이터가 없습니다.', 'info')
        
        if error_messages and len(error_messages) <= 5:
            for msg in error_messages:
                flash(msg, 'warning')
        elif error_messages:
            flash(f'{len(error_messages)}개의 행에서 오류가 발생했습니다.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'파일 처리 중 오류가 발생했습니다: {str(e)}', 'danger')
    
    return redirect(url_for('subjects.members', subject_id=subject_id))
