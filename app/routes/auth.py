from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from datetime import timedelta, datetime
import secrets
import base64
from app import db
from app.models import User
from app.forms import RegistrationForm, LoginForm, ForgotPasswordForm, ResetPasswordForm, ProfileForm, BasicInfoForm, PasswordChangeForm, AdditionalInfoForm

password_reset_tokens = {}

bp = Blueprint('auth', __name__, url_prefix='/auth')

def is_safe_url(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('', 'http', 'https') and ref_url.netloc == test_url.netloc

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.email.data.split('@')[0]
        base_username = username
        counter = 1
        while User.query.filter_by(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User(
            username=username,
            email=form.email.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        if form.role.data == 'instructor':
            flash('회원가입이 완료되었습니다! 강사 기능을 사용하려면 로그인 후 계정 설정에서 강사 인증을 요청해주세요.', 'success')
        else:
            flash('회원가입이 완료되었습니다! 로그인해주세요.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    
    # 저장된 이메일 쿠키에서 불러오기
    saved_email = request.cookies.get('saved_email', '')
    if request.method == 'GET' and saved_email:
        form.email.data = saved_email
        form.remember_id.data = True
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            # 자동 로그인 옵션에 따라 remember 설정
            remember = form.auto_login.data
            login_user(user, remember=remember, duration=timedelta(days=30) if remember else None)
            
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                flash('로그인되었습니다!', 'success')
                response = make_response(redirect(next_page))
            else:
                flash('로그인되었습니다!', 'success')
                response = make_response(redirect(url_for('main.dashboard')))
            
            # 아이디 저장 옵션 처리
            if form.remember_id.data:
                response.set_cookie('saved_email', str(form.email.data), max_age=60*60*24*365)  # 1년
            else:
                response.delete_cookie('saved_email')
            
            return response
        flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'danger')
    
    return render_template('auth/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('로그아웃되었습니다. 다음에 또 만나요!', 'success')
    return redirect(url_for('main.index'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = secrets.token_urlsafe(32)
            password_reset_tokens[token] = {
                'user_id': user.id,
                'email': form.email.data,
                'expires': datetime.utcnow() + timedelta(hours=1)
            }
            return redirect(url_for('auth.reset_password', token=token))
        flash('입력하신 이메일 주소로 비밀번호 재설정 안내를 확인해주세요.', 'info')
    
    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    token_data = password_reset_tokens.get(token)
    if not token_data:
        flash('유효하지 않거나 만료된 링크입니다.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if datetime.utcnow() > token_data['expires']:
        del password_reset_tokens[token]
        flash('링크가 만료되었습니다. 다시 시도해주세요.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.get(token_data['user_id'])
        if user:
            user.set_password(form.password.data)
            db.session.commit()
            del password_reset_tokens[token]
            flash('비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해주세요.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)

@bp.route('/account-settings', methods=['GET', 'POST'])
@login_required
def account_settings():
    profile_form = ProfileForm(prefix='profile')
    basic_info_form = BasicInfoForm(prefix='basic')
    password_form = PasswordChangeForm(prefix='password')
    additional_form = AdditionalInfoForm(prefix='additional')
    
    # Pre-populate forms with current data
    if request.method == 'GET':
        profile_form.nickname.data = current_user.nickname
        profile_form.full_name.data = current_user.full_name
        profile_form.profile_url.data = current_user.profile_url
        profile_form.bio.data = current_user.bio
        
        basic_info_form.email.data = current_user.email
        basic_info_form.phone.data = current_user.phone
        
        additional_form.organization.data = current_user.organization_name
        additional_form.position.data = current_user.position
        additional_form.job_title.data = current_user.job_title
    
    # Handle form submissions
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'profile':
            if profile_form.validate_on_submit():
                current_user.nickname = profile_form.nickname.data
                current_user.full_name = profile_form.full_name.data
                current_user.profile_url = profile_form.profile_url.data
                current_user.bio = profile_form.bio.data
                db.session.commit()
                flash('프로필이 저장되었습니다.', 'success')
                return redirect(url_for('auth.account_settings'))
        
        elif action == 'profile_image':
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename:
                    # Validate file type
                    allowed_extensions = {'png', 'jpg', 'jpeg'}
                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                    if ext not in allowed_extensions:
                        flash('PNG, JPG, JPEG 형식의 이미지만 업로드 가능합니다.', 'danger')
                        return redirect(url_for('auth.account_settings'))
                    
                    # Check file size (1MB limit)
                    file.seek(0, 2)
                    size = file.tell()
                    file.seek(0)
                    if size > 1 * 1024 * 1024:
                        flash('이미지 크기는 1MB 이하여야 합니다.', 'danger')
                        return redirect(url_for('auth.account_settings'))
                    
                    # Convert to base64
                    image_data = base64.b64encode(file.read()).decode('utf-8')
                    current_user.profile_image = f"data:image/{ext};base64,{image_data}"
                    db.session.commit()
                    flash('프로필 이미지가 업데이트되었습니다.', 'success')
                    return redirect(url_for('auth.account_settings'))
        
        elif action == 'basic_info':
            if basic_info_form.validate_on_submit():
                # Check if email already exists for another user
                if basic_info_form.email.data != current_user.email:
                    existing_user = User.query.filter_by(email=basic_info_form.email.data).first()
                    if existing_user:
                        flash('이미 사용 중인 이메일입니다.', 'danger')
                        return redirect(url_for('auth.account_settings'))
                
                current_user.email = basic_info_form.email.data
                current_user.phone = basic_info_form.phone.data
                db.session.commit()
                flash('기본 정보가 저장되었습니다.', 'success')
                return redirect(url_for('auth.account_settings'))
        
        elif action == 'password':
            if password_form.validate_on_submit():
                if not current_user.check_password(password_form.current_password.data):
                    flash('현재 비밀번호가 올바르지 않습니다.', 'danger')
                    return redirect(url_for('auth.account_settings'))
                
                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash('비밀번호가 변경되었습니다.', 'success')
                return redirect(url_for('auth.account_settings'))
        
        elif action == 'additional_info':
            if additional_form.validate_on_submit():
                current_user.organization_name = additional_form.organization.data
                current_user.position = additional_form.position.data
                current_user.job_title = additional_form.job_title.data
                db.session.commit()
                flash('추가 정보가 저장되었습니다.', 'success')
                return redirect(url_for('auth.account_settings'))
        
        elif action == 'request_verification':
            if not current_user.instructor_verified:
                current_user.verification_requested_at = datetime.utcnow()
                db.session.commit()
                flash('강사 인증 요청이 접수되었습니다. 관리자 승인을 기다려주세요.', 'info')
                return redirect(url_for('auth.account_settings'))
    
    return render_template('auth/account_settings.html',
                          profile_form=profile_form,
                          basic_info_form=basic_info_form,
                          password_form=password_form,
                          additional_form=additional_form)
