from flask import (Blueprint, render_template, redirect, url_for, flash,
                     request, make_response, session, current_app)
from urllib.parse import urlparse
from datetime import timedelta, datetime, timezone
import secrets
import requests as http_requests

from app.decorators import auth_required, get_current_user
from app.firebase_init import get_auth
from app import firestore_dao as dao
from app.services.storage import upload_profile_image, get_signed_url
from app.forms import (RegistrationForm, LoginForm, ForgotPasswordForm,
                        ResetPasswordForm, ProfileForm, BasicInfoForm,
                        PasswordChangeForm, AdditionalInfoForm)

password_reset_tokens = {}

bp = Blueprint('auth', __name__, url_prefix='/auth')

FIREBASE_SIGN_IN_URL = (
    'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword'
)


def _firebase_sign_in(email, password):
    """Verify email/password via Firebase Auth REST API.

    Returns the ID token on success, or None on failure.
    """
    api_key = current_app.config.get('FIREBASE_WEB_API_KEY')
    if not api_key:
        return None

    resp = http_requests.post(
        f'{FIREBASE_SIGN_IN_URL}?key={api_key}',
        json={
            'email': email,
            'password': password,
            'returnSecureToken': True,
        },
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json().get('idToken')
    return None


def is_safe_url(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('', 'http', 'https') and ref_url.netloc == test_url.netloc


@bp.route('/register', methods=['GET', 'POST'])
def register():
    current_user = get_current_user()
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.email.data.split('@')[0]
        base_username = username
        counter = 1
        while dao.get_user_by_username(username):
            username = f"{base_username}{counter}"
            counter += 1

        auth = get_auth()
        try:
            firebase_user = auth.create_user(
                email=form.email.data,
                password=form.password.data,
            )
        except Exception as e:
            flash(f'회원가입 중 오류가 발생했습니다: {e}', 'danger')
            return render_template('auth/register.html', form=form)

        uid = firebase_user.uid
        dao.create_user(uid, {
            'username': username,
            'email': form.email.data,
            'full_name': form.full_name.data,
            'phone': form.phone.data,
            'role': form.role.data,
            'nickname': None,
            'profile_url': None,
            'profile_image': None,
            'profile_image_path': None,
            'bio': None,
            'organization_name': None,
            'position': None,
            'job_title': None,
            'instructor_verified': False,
            'verification_requested_at': None,
        })

        if form.role.data == 'instructor':
            flash('회원가입이 완료되었습니다! 강사 기능을 사용하려면 로그인 후 계정 설정에서 강사 인증을 요청해주세요.', 'success')
        else:
            flash('회원가입이 완료되었습니다! 로그인해주세요.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    current_user = get_current_user()
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()

    # 저장된 이메일 쿠키에서 불러오기
    saved_email = request.cookies.get('saved_email', '')
    if request.method == 'GET' and saved_email:
        form.email.data = saved_email
        form.remember_id.data = True

    if form.validate_on_submit():
        # Verify credentials via Firebase Auth REST API
        id_token = _firebase_sign_in(form.email.data, form.password.data)
        if id_token:
            auth = get_auth()
            try:
                # Create a session cookie from the ID token
                expires_in = timedelta(days=5)
                session_cookie = auth.create_session_cookie(
                    id_token, expires_in=expires_in
                )
                session['firebase_session'] = session_cookie

                next_page = request.args.get('next')
                if next_page and is_safe_url(next_page):
                    flash('로그인되었습니다!', 'success')
                    response = make_response(redirect(next_page))
                else:
                    flash('로그인되었습니다!', 'success')
                    response = make_response(redirect(url_for('main.dashboard')))

                # 아이디 저장 옵션 처리
                if form.remember_id.data:
                    response.set_cookie(
                        'saved_email', str(form.email.data),
                        max_age=60 * 60 * 24 * 365,  # 1년
                    )
                else:
                    response.delete_cookie('saved_email')

                return response
            except Exception:
                flash('로그인 처리 중 오류가 발생했습니다.', 'danger')
        else:
            flash('이메일 또는 비밀번호가 올바르지 않습니다.', 'danger')

    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@auth_required
def logout():
    session.pop('firebase_session', None)
    flash('로그아웃되었습니다. 다음에 또 만나요!', 'success')
    return redirect(url_for('main.index'))


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    current_user = get_current_user()
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = dao.get_user_by_email(form.email.data)
        if user:
            token = secrets.token_urlsafe(32)
            password_reset_tokens[token] = {
                'uid': user['id'],
                'email': form.email.data,
                'expires': datetime.now(timezone.utc) + timedelta(hours=1),
            }
            return redirect(url_for('auth.reset_password', token=token))
        flash('입력하신 이메일 주소로 비밀번호 재설정 안내를 확인해주세요.', 'info')

    return render_template('auth/forgot_password.html', form=form)


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    current_user = get_current_user()
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    token_data = password_reset_tokens.get(token)
    if not token_data:
        flash('유효하지 않거나 만료된 링크입니다.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if datetime.now(timezone.utc) > token_data['expires']:
        del password_reset_tokens[token]
        flash('링크가 만료되었습니다. 다시 시도해주세요.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        uid = token_data['uid']
        auth = get_auth()
        try:
            auth.update_user(uid, password=form.password.data)
            del password_reset_tokens[token]
            flash('비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해주세요.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            flash('비밀번호 변경 중 오류가 발생했습니다.', 'danger')

    return render_template('auth/reset_password.html', form=form)


@bp.route('/account-settings', methods=['GET', 'POST'])
@auth_required
def account_settings():
    current_user = get_current_user()

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
                dao.update_user(current_user.uid, {
                    'nickname': profile_form.nickname.data,
                    'full_name': profile_form.full_name.data,
                    'profile_url': profile_form.profile_url.data,
                    'bio': profile_form.bio.data,
                })
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

                    # Upload to Firebase Storage
                    file_data = file.read()
                    storage_path = upload_profile_image(
                        current_user.uid, file_data, ext
                    )
                    signed_url = get_signed_url(storage_path)

                    dao.update_user(current_user.uid, {
                        'profile_image': signed_url,
                        'profile_image_path': storage_path,
                    })
                    flash('프로필 이미지가 업데이트되었습니다.', 'success')
                    return redirect(url_for('auth.account_settings'))

        elif action == 'basic_info':
            if basic_info_form.validate_on_submit():
                # Check if email already exists for another user
                if basic_info_form.email.data != current_user.email:
                    existing_user = dao.get_user_by_email(basic_info_form.email.data)
                    if existing_user and existing_user['id'] != current_user.uid:
                        flash('이미 사용 중인 이메일입니다.', 'danger')
                        return redirect(url_for('auth.account_settings'))

                    # Update email in Firebase Auth as well
                    auth = get_auth()
                    try:
                        auth.update_user(
                            current_user.uid,
                            email=basic_info_form.email.data,
                        )
                    except Exception:
                        flash('이메일 변경 중 오류가 발생했습니다.', 'danger')
                        return redirect(url_for('auth.account_settings'))

                dao.update_user(current_user.uid, {
                    'email': basic_info_form.email.data,
                    'phone': basic_info_form.phone.data,
                })
                flash('기본 정보가 저장되었습니다.', 'success')
                return redirect(url_for('auth.account_settings'))

        elif action == 'password':
            if password_form.validate_on_submit():
                # Verify current password via Firebase REST API
                id_token = _firebase_sign_in(
                    current_user.email,
                    password_form.current_password.data,
                )
                if not id_token:
                    flash('현재 비밀번호가 올바르지 않습니다.', 'danger')
                    return redirect(url_for('auth.account_settings'))

                auth = get_auth()
                try:
                    auth.update_user(
                        current_user.uid,
                        password=password_form.new_password.data,
                    )
                    flash('비밀번호가 변경되었습니다.', 'success')
                except Exception:
                    flash('비밀번호 변경 중 오류가 발생했습니다.', 'danger')
                return redirect(url_for('auth.account_settings'))

        elif action == 'additional_info':
            if additional_form.validate_on_submit():
                dao.update_user(current_user.uid, {
                    'organization_name': additional_form.organization.data,
                    'position': additional_form.position.data,
                    'job_title': additional_form.job_title.data,
                })
                flash('추가 정보가 저장되었습니다.', 'success')
                return redirect(url_for('auth.account_settings'))

        elif action == 'request_verification':
            if not current_user.instructor_verified:
                dao.update_user(current_user.uid, {
                    'verification_requested_at': datetime.now(timezone.utc),
                })
                flash('강사 인증 요청이 접수되었습니다. 관리자 승인을 기다려주세요.', 'info')
                return redirect(url_for('auth.account_settings'))

    return render_template('auth/account_settings.html',
                           profile_form=profile_form,
                           basic_info_form=basic_info_form,
                           password_form=password_form,
                           additional_form=additional_form)
