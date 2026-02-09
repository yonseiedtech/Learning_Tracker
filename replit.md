# 학습 진도 트래커 (Learning Progress Tracking Platform)

## Overview
학습 진도 트래커는 실시간 학습 진도 모니터링 시스템으로, 라이브 강의실 추적 및 자기주도 학습 분석 기능을 제공합니다. 이 플랫폼은 강사와 학생 모두에게 최적화된 학습 경험을 제공하며, Python Flask, Socket.IO, PostgreSQL을 기반으로 구축되었습니다. 주요 목표는 학습 효율성을 극대화하고, 개인화된 학습 경로를 지원하며, 교육 기관의 운영 효율성을 높이는 것입니다.

주요 기능은 다음과 같습니다:
- **과목/세션/세미나 계층 구조**: 
  - 과목(Subject): 여러 주차별 세션을 포함하는 상위 컨테이너
  - 세션(Course within Subject): 과목 내 개별 활동 (라이브, 영상, 자료, 과제, 퀴즈)
  - 세미나(Standalone Course): 과목에 속하지 않는 독립적인 1회성 강의
- **라이브 세션 예약**: 즉시 시작 또는 특정 시간 예약 기능
- **실시간 채팅 및 게시판**: 세션 중 실시간 소통 및 공지사항 관리
- **PPT/PDF 실시간 슬라이드 방송**: PPTX/PDF 업로드→이미지 변환, 강사-학습자 슬라이드 동기화, 이해도 피드백(👍/❓/😵), 문제 슬라이드 자동 북마크, 강의 후 리뷰 페이지, 인라인 프레젠터/뷰어 통합
- **실시간 Engagement Dashboard**: 반응 원형차트/막대 그래프 시각화, 추이 미니 라인차트, 해석 가이드, 임계값 기반 Smart Alert
- **Smart Slide Navigator**: 슬라이드 점프 바(미니맵), 검색 기능, 키보드 네비게이션(화살표/PageUp/Down/Home/End)
- **Lecture Progress & Time Manager**: 강의 타이머, 슬라이드별 소요 시간 추적, 예상 종료 시간 자동 계산, 시간 초과 알림
- **AI 기반 체크포인트 생성**: PPT/PDF, 영상, 음성 분석을 통한 자동 체크포인트 생성 및 전사문 편집 기능
- **역할 기반 접근 제어**: 시스템 관리자, 기관 관리자, 강사, 학습자로 구분된 권한 관리
- **자기주도 학습 모드**: 개인별 진도 및 학습 시간 측정, 체크포인트 완료 토글
- **통합 이용 안내 및 커뮤니티 기능**: 공지사항, FAQ, Q&A, 스터디 모집, 학습 리뷰 등

## User Preferences
I prefer the entire UI, messages, and labels to be in Korean.
I want the design to feature Glassmorphism effects with a navy gradient color scheme (`#0d1b3e` to `#1a3a5c`), using the Noto Sans KR font, rounded corners (12-24px border-radius), and floating card animations. The login page should have a learning-themed background image with a glass card overlay.
I want an integrated navigation system that includes a user dropdown menu (avatar + name + role), notification links, and theme toggle support across all pages.
I expect the system to support a light/dark theme toggle, with the preference saved locally.
For notifications, I prefer toast-style alerts in the top right corner with category-specific colors and icons, disappearing automatically after 5 seconds but also offering a manual close button, and having slide animations.

## System Architecture
The application is built with a Flask factory pattern, using SQLAlchemy for ORM with PostgreSQL as the database. Real-time functionalities like live session tracking and chat are handled via Flask-SocketIO with Eventlet for asynchronous support. User authentication is managed by Flask-Login with bcrypt for password hashing, supporting role-based access control (system_admin, org_admin, instructor, student).

### UI/UX Decisions
- **Design Language**: Glassmorphism with a navy gradient theme (`#0d1b3e` to `#1a3a5c`), Noto Sans KR font, rounded corners (12-24px border-radius), and floating card animations.
- **Brand Identity**: Modern dark theme with blue-purple gradients (`#3b82f6` → `#8b5cf6`) for a sleek, contemporary feel.
- **Responsiveness**: Mobile-optimized with responsive CSS and touch-friendly buttons.
- **Theming**: Light/Dark theme toggle available across all pages, preserving user preference via local storage.
- **Login Page**: Learning-themed background image with a glass card overlay.
- **Dashboards**: Personalized dashboards with learning statistics widgets (completion rate, study time, streak) and gamification elements (streaks, badges).
- **Notifications**: Toast-style notifications (success/error/warning/info) with auto-hide and manual close, slide animations.
- **Navigation**: Integrated navigation bar across all pages, including a user dropdown menu showing avatar, name, and role.

### Technical Implementations & Features
- **Core Structure**:
    - Subject-Course-Session hierarchy: `Subject` (main course) contains multiple `Course` (weekly sessions/modules).
    - `SubjectEnrollment` model for managing student registrations to subjects and their associated sessions.
- **Authentication & Authorization**:
    - Role-based access control: `system_admin`, `org_admin`, `instructor`, `student`.
    - Flask-Login for user sessions, `remember me` functionality for persistent login.
    - User account settings for profile management (image, nickname, personal info), password changes, and instructor verification requests.
- **Course & Session Management**:
    - Creation, deletion (soft delete), visibility toggling (public/private).
    - Diverse session types with dedicated UIs:
      - `live_session`: Real-time synchronized learning with checkpoints
      - `video`: Video player with watch log tracking (auto-complete at 80% for uploads, manual completion with page time tracking for YouTube)
      - `material`: Learning materials with file download and page time tracking
      - `assignment`: Assignment submission with file upload and grading workflow
      - `quiz`: Timed quizzes with multiple choice, true/false, and short answer questions
    - File uploads (base64 storage, 100MB limit) for video/material sessions.
    - Attendance tracking with configurable periods and tardiness allowances.
    - `LiveStatus` (`preparing`, `live`, `ended`) for real-time session state management.
    - `SessionCompletion` model for tracking manual completion across all non-live session types.
    - `VideoWatchLog` model for tracking video viewing progress and auto-completion.
    - `PageTimeLog` model for tracking time spent on pages (YouTube videos, materials).
- **Checkpoint System**:
    - Sequential learning objectives with estimated completion times.
    - AI-powered generation of checkpoints from PPT, PDF, video, and audio content using Gemini AI.
    - Manual completion toggling for students.
- **Live Mode**:
    - WebSocket-based real-time progress tracking for synchronous learning.
    - Real-time chat with message editing/deletion and mentions.
    - Live bulletin board for announcements during sessions.
- **Self-Study Mode**:
    - Independent progress tracking and time measurement.
    - Start/pause/resume/stop/reset timer functionality.
    - Pause elapsed time display showing how long paused.
    - Auto-end feature: Timer automatically ends and saves progress after 30 minutes of pause.
    - Auto-save: Timer saves progress on stop or reset actions.
- **Standalone Sessions (Seminars)**:
    - Independent sessions not attached to any Subject (subject_id is None).
    - Direct enrollment via invite codes from session list page.
    - Separate sections for instructors, enrolled, and public sessions.
- **Community & Support**:
    - `Community` section for learning reviews, Q&A (with adoption and resolution status), and study group recruitment.
    - `Guide` section including announcements, FAQ, Q&A, resources, updates, and suggestions.
- **Data Analytics**:
    - Completion rates, time spent analysis, CSV export.

### System Design Choices
- **PPT 슬라이드 방송 시스템**:
    - `SlideDeck` model: PPTX/PDF 파일 업로드 및 이미지 변환 관리 (course_id, session_id, slide_count, current_slide_index, conversion_status, estimated_duration_minutes)
    - `SlideReaction` model: 슬라이드별 학습자 이해도 피드백 (understood/question/hard/none)
    - `SlideBookmark` model: 문제 슬라이드 자동/수동 북마크 (is_auto, is_manual, memo, supplement_url)
    - PPTX→PDF→PNG 변환 파이프라인 (LibreOffice headless + pdf2image)
    - Socket.IO events: slide_changed, set_slide_reaction, slide_aggregate_updated, bookmark_updated
    - 프레젠터 뷰 (강사), 뷰어 (학습자), 리뷰 페이지
    - Routes: `/slides/` blueprint (upload, delete, presenter, viewer, review)
    - 파일 크기 제한: 50MB, 최대 슬라이드 수: 100장
- **Database Schema**: Utilizes `Subject`, `Course`, `Checkpoint`, `Progress`, `Attendance`, `User`, `SubjectMember`, `Notification`, `Guide`, `Community`, `SlideDeck`, `SlideReaction`, `SlideBookmark` models for comprehensive data management.
- **Asynchronous Operations**: Leverages Socket.IO and Eventlet for handling real-time, concurrent user interactions efficiently.
- **Modularity**: Application organized into blueprints (`auth.py`, `main.py`, `courses.py`, `checkpoints.py`, `progress.py`, `analytics.py`, `slides.py`) for better maintainability and scalability.

## External Dependencies
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket communication
- **PostgreSQL**: Relational database
- **SQLAlchemy**: ORM for database interactions
- **Flask-Login**: User session management
- **bcrypt**: Password hashing
- **Bootstrap 5**: Frontend framework for responsive design
- **Chart.js**: Data visualization
- **Eventlet**: Asynchronous I/O library
- **Noto Sans KR**: Custom font
- **Google Gemini AI**: For AI checkpoint generation and content analysis (via Replit AI Integrations)