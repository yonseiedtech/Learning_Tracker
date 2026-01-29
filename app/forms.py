from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, IntegerField, SubmitField, DateTimeLocalField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models import User

class RegistrationForm(FlaskForm):
    username = StringField('사용자명', validators=[DataRequired(message='사용자명을 입력하세요'), Length(min=3, max=80, message='3~80자 사이로 입력하세요')])
    email = StringField('이메일', validators=[DataRequired(message='이메일을 입력하세요'), Email(message='올바른 이메일 형식을 입력하세요')])
    password = PasswordField('비밀번호', validators=[DataRequired(message='비밀번호를 입력하세요'), Length(min=6, message='최소 6자 이상 입력하세요')])
    confirm_password = PasswordField('비밀번호 확인', validators=[DataRequired(message='비밀번호 확인을 입력하세요'), EqualTo('password', message='비밀번호가 일치하지 않습니다')])
    role = SelectField('역할', choices=[('student', '학생'), ('instructor', '강사')])
    submit = SubmitField('회원가입')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('이미 사용 중인 사용자명입니다.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('이미 등록된 이메일입니다.')

class LoginForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(message='이메일을 입력하세요'), Email(message='올바른 이메일 형식을 입력하세요')])
    password = PasswordField('비밀번호', validators=[DataRequired(message='비밀번호를 입력하세요')])
    submit = SubmitField('로그인')

class CourseForm(FlaskForm):
    title = StringField('강좌명', validators=[DataRequired(message='강좌명을 입력하세요'), Length(max=200)])
    description = TextAreaField('설명', validators=[Optional()])
    submit = SubmitField('저장')

class EnrollForm(FlaskForm):
    invite_code = StringField('초대 코드', validators=[DataRequired(message='초대 코드를 입력하세요'), Length(min=8, max=8, message='8자리 코드를 입력하세요')])
    submit = SubmitField('수강 신청')

class CheckpointForm(FlaskForm):
    title = StringField('제목', validators=[DataRequired(message='제목을 입력하세요'), Length(max=200)])
    description = TextAreaField('설명', validators=[Optional()])
    estimated_minutes = IntegerField('예상 소요 시간 (분)', validators=[Optional()])
    submit = SubmitField('저장')

class SubjectForm(FlaskForm):
    title = StringField('과목명', validators=[DataRequired(message='과목명을 입력하세요'), Length(max=200)])
    description = TextAreaField('설명', validators=[Optional()])
    submit = SubmitField('저장')

class SessionScheduleForm(FlaskForm):
    session_type = SelectField('세션 유형', choices=[('immediate', '즉시 시작'), ('scheduled', '예약 시작')])
    scheduled_at = StringField('예약 시간', validators=[Optional()])
    submit = SubmitField('세션 시작')

class LiveSessionPostForm(FlaskForm):
    title = StringField('제목', validators=[DataRequired(message='제목을 입력하세요'), Length(max=200)])
    content = TextAreaField('내용', validators=[DataRequired(message='내용을 입력하세요')])
    pinned = BooleanField('상단 고정')
    submit = SubmitField('등록')

class LiveSessionCommentForm(FlaskForm):
    content = TextAreaField('댓글', validators=[DataRequired(message='내용을 입력하세요')])
    submit = SubmitField('댓글 작성')
