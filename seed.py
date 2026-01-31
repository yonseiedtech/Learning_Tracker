from app import create_app, db
from app.models import User, Course, Checkpoint, Enrollment, Progress, Subject, SubjectEnrollment, SubjectMember, Organization, QuizQuestion
from datetime import datetime, timedelta
import random

def seed_database():
    app = create_app()
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        print("Creating organizations...")
        org1 = Organization(
            name='테크 아카데미',
            description='IT 전문 교육 기관'
        )
        org2 = Organization(
            name='비즈니스 스쿨',
            description='경영 및 비즈니스 교육 기관'
        )
        db.session.add(org1)
        db.session.add(org2)
        db.session.commit()
        
        print("Creating users...")
        
        system_admin = User(
            username='sysadmin',
            email='sysadmin@example.com',
            role='system_admin',
            full_name='시스템 관리자'
        )
        system_admin.set_password('password123')
        
        org_admin1 = User(
            username='orgadmin1',
            email='orgadmin1@example.com',
            role='org_admin',
            organization_id=org1.id,
            full_name='테크아카데미 관리자'
        )
        org_admin1.set_password('password123')
        
        org_admin2 = User(
            username='orgadmin2',
            email='orgadmin2@example.com',
            role='org_admin',
            organization_id=org2.id,
            full_name='비즈니스스쿨 관리자'
        )
        org_admin2.set_password('password123')
        
        instructor1 = User(
            username='instructor1',
            email='instructor1@example.com',
            role='instructor',
            organization_id=org1.id,
            full_name='김강사'
        )
        instructor1.set_password('password123')
        
        instructor2 = User(
            username='instructor2',
            email='instructor2@example.com',
            role='instructor',
            organization_id=org1.id,
            full_name='이강사'
        )
        instructor2.set_password('password123')
        
        instructor3 = User(
            username='instructor3',
            email='instructor3@example.com',
            role='instructor',
            organization_id=org2.id,
            full_name='박강사'
        )
        instructor3.set_password('password123')
        
        students = []
        for i in range(1, 11):
            org_id = org1.id if i <= 5 else org2.id
            student = User(
                username=f'student{i}',
                email=f'student{i}@example.com',
                role='student',
                organization_id=org_id,
                full_name=f'학습자{i}'
            )
            student.set_password('password123')
            students.append(student)
        
        db.session.add(system_admin)
        db.session.add(org_admin1)
        db.session.add(org_admin2)
        db.session.add(instructor1)
        db.session.add(instructor2)
        db.session.add(instructor3)
        for student in students:
            db.session.add(student)
        db.session.commit()
        
        print("Creating subjects...")
        subject1 = Subject(
            title='Python 프로그래밍 기초',
            description='Python 프로그래밍을 처음부터 배우는 과정입니다.',
            instructor_id=instructor1.id,
            organization_id=org1.id,
            invite_code='PYTHON01'
        )
        
        subject2 = Subject(
            title='웹개발 입문',
            description='HTML, CSS, JavaScript를 활용한 웹개발 기초 과정',
            instructor_id=instructor1.id,
            organization_id=org1.id,
            invite_code='WEBDEV01'
        )
        
        subject3 = Subject(
            title='데이터 분석 기초',
            description='데이터 분석과 시각화, 머신러닝 기초',
            instructor_id=instructor2.id,
            organization_id=org1.id,
            invite_code='DATASCI1'
        )
        
        subject4 = Subject(
            title='비즈니스 전략',
            description='경영 전략과 의사결정 과정',
            instructor_id=instructor3.id,
            organization_id=org2.id,
            invite_code='BIZ00001'
        )
        
        db.session.add(subject1)
        db.session.add(subject2)
        db.session.add(subject3)
        db.session.add(subject4)
        db.session.commit()
        
        for subj, inst in [(subject1, instructor1), (subject2, instructor1), (subject3, instructor2), (subject4, instructor3)]:
            member = SubjectMember(subject_id=subj.id, user_id=inst.id, role='instructor')
            db.session.add(member)
        db.session.commit()
        
        print("Creating courses (sessions)...")
        course1 = Course(
            title='1주차: Python 설치 및 환경 설정',
            description='개발 환경을 구축하고 첫 Python 프로그램을 작성합니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='live_session',
            week_number=1,
            invite_code='PY1WK001'
        )
        
        course2 = Course(
            title='2주차: 변수와 데이터 타입',
            description='문자열, 숫자, 불리언 등 기본 데이터 타입을 학습합니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='video',
            week_number=2,
            invite_code='PY1WK002',
            min_completion_time=60
        )
        
        course3 = Course(
            title='3주차: 제어문',
            description='if/else와 반복문을 마스터합니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='live_session',
            week_number=3,
            invite_code='PY1WK003'
        )
        
        course4 = Course(
            title='4주차: 학습 자료 - Python 문법 정리',
            description='Python 기본 문법을 정리한 학습 자료입니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='material',
            week_number=4,
            invite_code='PY1WK004',
            assignment_description='<h5>Python 기본 문법 정리</h5><ul><li>변수와 데이터 타입</li><li>연산자</li><li>조건문과 반복문</li><li>함수</li></ul><p>위 내용을 학습하고 완료 버튼을 눌러주세요.</p>'
        )
        
        course5 = Course(
            title='5주차: 과제 - 계산기 프로그램',
            description='간단한 계산기 프로그램을 작성하는 과제입니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='assignment',
            week_number=5,
            invite_code='PY1WK005',
            assignment_description='<h5>과제: 계산기 프로그램 만들기</h5><p>다음 요구사항을 충족하는 계산기 프로그램을 작성하세요:</p><ol><li>덧셈, 뺄셈, 곱셈, 나눗셈 기능</li><li>사용자 입력 받기</li><li>결과 출력</li></ol>',
            assignment_due_date=datetime.utcnow() + timedelta(days=7)
        )
        
        course6 = Course(
            title='6주차: 퀴즈 - Python 기초 테스트',
            description='지금까지 배운 내용을 확인하는 퀴즈입니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='quiz',
            week_number=6,
            invite_code='PY1WK006',
            quiz_time_limit=15,
            quiz_pass_score=60
        )
        
        course7 = Course(
            title='유튜브 강의: Python 소개',
            description='YouTube에서 Python 소개 영상을 시청합니다.',
            instructor_id=instructor1.id,
            subject_id=subject1.id,
            session_type='video',
            week_number=1,
            session_number=2,
            invite_code='PY1YT001',
            video_url='https://www.youtube.com/watch?v=Y8Tko2YC5hA',
            min_completion_time=120
        )
        
        db.session.add(course1)
        db.session.add(course2)
        db.session.add(course3)
        db.session.add(course4)
        db.session.add(course5)
        db.session.add(course6)
        db.session.add(course7)
        db.session.commit()
        
        print("Creating checkpoints...")
        python_checkpoints = [
            ('개발 환경 설정', 'Python과 VS Code 설치', 10),
            ('Hello World 출력', '첫 프로그램 작성하기', 15),
            ('변수 선언', '변수에 값 할당하기', 20),
        ]
        
        for i, (title, desc, est_min) in enumerate(python_checkpoints):
            cp = Checkpoint(
                course_id=course1.id,
                title=title,
                description=desc,
                order=i + 1,
                estimated_minutes=est_min
            )
            db.session.add(cp)
        
        db.session.commit()
        
        print("Creating quiz questions...")
        quiz_questions = [
            ('Python에서 변수를 선언할 때 사용하는 키워드는?', 'short_answer', None, 'x = 10 처럼 직접 할당', 10),
            ('print() 함수의 역할은?', 'multiple_choice', '화면에 출력\n파일 저장\n데이터 삭제\n변수 선언', '화면에 출력', 10),
            ('Python은 인터프리터 언어이다.', 'true_false', None, 'true', 10),
            ('리스트와 튜플의 차이점은 무엇인가?', 'short_answer', None, '리스트는 수정 가능, 튜플은 수정 불가', 20),
            ('for문에서 range(5)의 출력 범위는?', 'multiple_choice', '0부터 4까지\n1부터 5까지\n0부터 5까지\n1부터 4까지', '0부터 4까지', 10),
        ]
        
        for i, (question, q_type, options, answer, points) in enumerate(quiz_questions):
            q = QuizQuestion(
                course_id=course6.id,
                question_text=question,
                question_type=q_type,
                options=options,
                correct_answer=answer,
                points=points,
                order=i + 1
            )
            db.session.add(q)
        
        db.session.commit()
        
        print("Creating enrollments...")
        for student in students[:5]:
            enrollment = SubjectEnrollment(subject_id=subject1.id, user_id=student.id)
            db.session.add(enrollment)
            for course in [course1, course2, course3, course4, course5, course6, course7]:
                course_enroll = Enrollment(course_id=course.id, user_id=student.id)
                db.session.add(course_enroll)
        
        db.session.commit()
        
        print("\n" + "="*60)
        print("    테스트 계정 정보")
        print("="*60)
        print("\n[시스템 관리자] - 전체 시스템 관리")
        print(f"  이메일: sysadmin@example.com")
        print(f"  비밀번호: password123")
        
        print("\n[기관 관리자] - 소속 기관 과목/세션만 관리")
        print(f"  테크아카데미: orgadmin1@example.com")
        print(f"  비즈니스스쿨: orgadmin2@example.com")
        print(f"  비밀번호: password123 (공통)")
        
        print("\n[강사] - 과목 생성 및 수업 진행")
        print(f"  테크아카데미: instructor1@example.com, instructor2@example.com")
        print(f"  비즈니스스쿨: instructor3@example.com")
        print(f"  비밀번호: password123 (공통)")
        
        print("\n[학습자] - 과목 수강 및 학습")
        print(f"  테크아카데미: student1~5@example.com")
        print(f"  비즈니스스쿨: student6~10@example.com")
        print(f"  비밀번호: password123 (공통)")
        
        print("\n[샘플 초대 코드]")
        print(f"  Python 프로그래밍 기초: PYTHON01")
        print(f"  웹개발 입문: WEBDEV01")
        print(f"  데이터 분석 기초: DATASCI1")
        print(f"  비즈니스 전략: BIZ00001")
        print("\n" + "="*60)
        print("데이터베이스 시드 완료!")

if __name__ == '__main__':
    seed_database()
