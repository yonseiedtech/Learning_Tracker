from app import create_app, db
from app.models import User, Course, Checkpoint, Enrollment, Progress
from datetime import datetime, timedelta
import random

def seed_database():
    app = create_app()
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        print("Creating users...")
        instructor1 = User(
            username='instructor1',
            email='instructor1@example.com',
            role='instructor'
        )
        instructor1.set_password('password123')
        
        instructor2 = User(
            username='instructor2',
            email='instructor2@example.com',
            role='instructor'
        )
        instructor2.set_password('password123')
        
        students = []
        for i in range(1, 11):
            student = User(
                username=f'student{i}',
                email=f'student{i}@example.com',
                role='student'
            )
            student.set_password('password123')
            students.append(student)
        
        db.session.add(instructor1)
        db.session.add(instructor2)
        for student in students:
            db.session.add(student)
        db.session.commit()
        
        print("Creating courses...")
        course1 = Course(
            title='Introduction to Python',
            description='Learn Python programming from scratch. This course covers variables, data types, control flow, functions, and basic data structures.',
            instructor_id=instructor1.id,
            invite_code='PYTHON01'
        )
        
        course2 = Course(
            title='Web Development Basics',
            description='Master the fundamentals of web development including HTML, CSS, and JavaScript.',
            instructor_id=instructor1.id,
            invite_code='WEBDEV01'
        )
        
        course3 = Course(
            title='Data Science Fundamentals',
            description='Explore data analysis, visualization, and machine learning basics.',
            instructor_id=instructor2.id,
            invite_code='DATASCI1'
        )
        
        db.session.add(course1)
        db.session.add(course2)
        db.session.add(course3)
        db.session.commit()
        
        print("Creating checkpoints...")
        python_checkpoints = [
            ('Setup Development Environment', 'Install Python and VS Code', 10),
            ('Variables and Data Types', 'Learn about strings, numbers, and booleans', 20),
            ('Control Flow', 'Master if/else statements and loops', 25),
            ('Functions', 'Create and use functions effectively', 30),
            ('Lists and Dictionaries', 'Work with Python collections', 25),
            ('File Handling', 'Read and write files in Python', 20),
            ('Error Handling', 'Learn try/except blocks', 15),
            ('Final Project', 'Build a complete Python application', 45)
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
        
        web_checkpoints = [
            ('HTML Basics', 'Learn HTML tags and structure', 20),
            ('CSS Styling', 'Style your web pages with CSS', 25),
            ('Responsive Design', 'Make mobile-friendly layouts', 30),
            ('JavaScript Intro', 'Add interactivity with JavaScript', 35),
            ('DOM Manipulation', 'Modify page content dynamically', 25),
            ('Final Web Project', 'Build a complete website', 60)
        ]
        
        for i, (title, desc, est_min) in enumerate(web_checkpoints):
            cp = Checkpoint(
                course_id=course2.id,
                title=title,
                description=desc,
                order=i + 1,
                estimated_minutes=est_min
            )
            db.session.add(cp)
        
        db.session.commit()
        
        print("Creating enrollments...")
        for student in students[:8]:
            enrollment = Enrollment(course_id=course1.id, user_id=student.id)
            db.session.add(enrollment)
        
        for student in students[2:7]:
            enrollment = Enrollment(course_id=course2.id, user_id=student.id)
            db.session.add(enrollment)
        
        db.session.commit()
        
        print("Creating sample progress...")
        course1_checkpoints = Checkpoint.query.filter_by(course_id=course1.id).order_by(Checkpoint.order).all()
        
        for student in students[:8]:
            num_completed = random.randint(2, len(course1_checkpoints))
            for cp in course1_checkpoints[:num_completed]:
                started = datetime.utcnow() - timedelta(days=random.randint(1, 7), hours=random.randint(0, 23))
                duration = random.randint(int(cp.estimated_minutes * 0.7 * 60), int(cp.estimated_minutes * 1.5 * 60))
                completed = started + timedelta(seconds=duration)
                
                progress = Progress(
                    user_id=student.id,
                    checkpoint_id=cp.id,
                    mode='self_paced',
                    started_at=started,
                    completed_at=completed,
                    duration_seconds=duration
                )
                db.session.add(progress)
        
        db.session.commit()
        
        print("\n=== Seed Data Summary ===")
        print(f"Instructors: 2 (instructor1@example.com, instructor2@example.com)")
        print(f"Students: 10 (student1@example.com - student10@example.com)")
        print(f"Password for all users: password123")
        print(f"\nCourses:")
        print(f"  - {course1.title} (Invite Code: {course1.invite_code})")
        print(f"  - {course2.title} (Invite Code: {course2.invite_code})")
        print(f"  - {course3.title} (Invite Code: {course3.invite_code})")
        print("\nDatabase seeded successfully!")

if __name__ == '__main__':
    seed_database()
