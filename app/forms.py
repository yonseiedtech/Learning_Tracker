from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, IntegerField, SubmitField, DateTimeLocalField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from app.models import User

class RegistrationForm(FlaskForm):
    full_name = StringField('이름', validators=[DataRequired(message='이름을 입력하세요'), Length(min=2, max=120, message='2~120자 사이로 입력하세요')])
    email = StringField('이메일', validators=[DataRequired(message='이메일을 입력하세요'), Email(message='올바른 이메일 형식을 입력하세요')])
    phone = StringField('휴대폰 번호', validators=[DataRequired(message='휴대폰 번호를 입력하세요'), Length(min=10, max=20, message='올바른 휴대폰 번호를 입력하세요')])
    password = PasswordField('비밀번호', validators=[DataRequired(message='비밀번호를 입력하세요'), Length(min=6, message='최소 6자 이상 입력하세요')])
    confirm_password = PasswordField('비밀번호 확인', validators=[DataRequired(message='비밀번호 확인을 입력하세요'), EqualTo('password', message='비밀번호가 일치하지 않습니다')])
    role = SelectField('역할', choices=[('student', '학생'), ('instructor', '강사')])
    submit = SubmitField('회원가입')
    
    def validate_phone(self, phone):
        cleaned = ''.join(filter(str.isdigit, phone.data))
        if len(cleaned) < 10:
            raise ValidationError('올바른 휴대폰 번호를 입력하세요.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('이미 등록된 이메일입니다.')

class LoginForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(message='이메일을 입력하세요'), Email(message='올바른 이메일 형식을 입력하세요')])
    password = PasswordField('비밀번호', validators=[DataRequired(message='비밀번호를 입력하세요')])
    remember_id = BooleanField('아이디 저장')
    auto_login = BooleanField('자동 로그인')
    submit = SubmitField('로그인')

class ForgotPasswordForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(message='이메일을 입력하세요'), Email(message='올바른 이메일 형식을 입력하세요')])
    submit = SubmitField('비밀번호 재설정 링크 받기')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('새 비밀번호', validators=[DataRequired(message='새 비밀번호를 입력하세요'), Length(min=6, message='최소 6자 이상 입력하세요')])
    confirm_password = PasswordField('비밀번호 확인', validators=[DataRequired(message='비밀번호 확인을 입력하세요'), EqualTo('password', message='비밀번호가 일치하지 않습니다')])
    submit = SubmitField('비밀번호 변경')

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

class ProfileForm(FlaskForm):
    nickname = StringField('닉네임', validators=[Optional(), Length(max=80)])
    full_name = StringField('이름', validators=[Optional(), Length(max=120)])
    profile_url = StringField('프로필 주소', validators=[Optional(), Length(max=255)])
    bio = TextAreaField('자기소개', validators=[Optional(), Length(max=500)])
    submit = SubmitField('저장')

class BasicInfoForm(FlaskForm):
    email = StringField('이메일', validators=[DataRequired(message='이메일을 입력하세요'), Email(message='올바른 이메일 형식을 입력하세요')])
    phone = StringField('휴대폰 번호', validators=[Optional(), Length(max=20)])
    submit = SubmitField('저장')

class PasswordChangeForm(FlaskForm):
    current_password = PasswordField('현재 비밀번호', validators=[DataRequired(message='현재 비밀번호를 입력하세요')])
    new_password = PasswordField('새 비밀번호', validators=[DataRequired(message='새 비밀번호를 입력하세요'), Length(min=6, message='최소 6자 이상 입력하세요')])
    confirm_password = PasswordField('비밀번호 확인', validators=[DataRequired(message='비밀번호 확인을 입력하세요'), EqualTo('new_password', message='비밀번호가 일치하지 않습니다')])
    submit = SubmitField('비밀번호 변경')

class AdditionalInfoForm(FlaskForm):
    organization = StringField('소속', validators=[Optional(), Length(max=200)])
    position = StringField('직책', validators=[Optional(), Length(max=100)])
    job_title = StringField('직급', validators=[Optional(), Length(max=100)])
    submit = SubmitField('저장')

class LearningReviewForm(FlaskForm):
    title = StringField('제목', validators=[DataRequired(message='제목을 입력하세요'), Length(max=200)])
    content = TextAreaField('내용', validators=[DataRequired(message='내용을 입력하세요')])
    rating = SelectField('평점', choices=[(5, '5점'), (4, '4점'), (3, '3점'), (2, '2점'), (1, '1점')], coerce=int)
    submit = SubmitField('등록')

class QnAPostForm(FlaskForm):
    title = StringField('제목', validators=[DataRequired(message='제목을 입력하세요'), Length(max=200)])
    content = TextAreaField('내용', validators=[DataRequired(message='내용을 입력하세요')])
    submit = SubmitField('질문 등록')

class QnAAnswerForm(FlaskForm):
    content = TextAreaField('답변', validators=[DataRequired(message='답변 내용을 입력하세요')])
    submit = SubmitField('답변 등록')

class StudyGroupForm(FlaskForm):
    title = StringField('스터디명', validators=[DataRequired(message='스터디명을 입력하세요'), Length(max=200)])
    description = TextAreaField('설명', validators=[DataRequired(message='설명을 입력하세요')])
    category = SelectField('카테고리', choices=[
        ('programming', '프로그래밍'),
        ('data_science', '데이터 사이언스'),
        ('design', '디자인'),
        ('language', '외국어'),
        ('certification', '자격증'),
        ('general', '일반')
    ])
    max_members = IntegerField('최대 인원', validators=[DataRequired(message='최대 인원을 입력하세요')])
    meeting_type = SelectField('진행 방식', choices=[
        ('online', '온라인'),
        ('offline', '오프라인'),
        ('hybrid', '혼합')
    ])
    meeting_schedule = StringField('모임 일정', validators=[Optional(), Length(max=200)])
    tags = StringField('태그', validators=[Optional(), Length(max=200)])
    submit = SubmitField('스터디 만들기')

class CommentForm(FlaskForm):
    content = TextAreaField('댓글', validators=[DataRequired(message='내용을 입력하세요')])
    submit = SubmitField('댓글 등록')
