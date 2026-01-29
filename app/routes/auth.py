from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse
from datetime import timedelta
from app import db
from app.models import User
from app.forms import RegistrationForm, LoginForm

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
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
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
    flash('로그아웃되었습니다.', 'info')
    return redirect(url_for('auth.login'))
