# 학습 진도 트래커 (Learning Progress Tracking Platform)

## 개요
실시간 학습 진도 모니터링 시스템으로 라이브 강의실 추적과 자기주도 학습 분석 두 가지 모드를 지원합니다. Python Flask, Socket.IO, PostgreSQL, Bootstrap 5로 구축되었습니다.

### 주요 기능
- **과목/세션 계층 구조**: 과목(Subject) > 주차별 세션(Course) 구조로 강좌 관리
- **라이브 세션 예약**: 즉시 시작 또는 특정 시간 예약 기능
- **실시간 채팅**: 메시지 편집/삭제, @멘션, 전체 호출 기능
- **라이브 게시판**: 세션 중 공지사항 등록 및 상단 고정
- **전체 진행율 표시**: 강사/학생 화면에서 수업 진행율 확인
- **AI 체크포인트 생성**: Gemini AI 기반 자동 체크포인트 생성
  - PPT/PDF 분석으로 체크포인트 생성
  - 영상 분석 및 전사문 추출
  - 음성 파일 전사 및 체크포인트 생성
  - 전사문 편집 및 재생성 기능

## 언어 및 디자인
- **언어**: 한국어 (전체 UI, 메시지, 라벨)
- **디자인**: 
  - Glassmorphism 효과 (투명 배경, backdrop-filter)
  - 네이비 그라디언트 색상 (#0d1b3e ~ #1a3a5c 주요 테마)
  - Noto Sans KR 폰트
  - 둥근 모서리 (12-24px border-radius)
  - 부유 카드 애니메이션
  - 로그인 페이지: 학습 테마 배경 이미지 + 글래스 카드

## 프로젝트 구조
```
├── app/
│   ├── __init__.py          # Flask 앱 팩토리
│   ├── models.py             # SQLAlchemy 모델
│   ├── forms.py              # WTForms 정의 (한국어 라벨)
│   ├── events.py             # Socket.IO 이벤트 핸들러
│   ├── routes/
│   │   ├── auth.py           # 인증 라우트
│   │   ├── main.py           # 메인 대시보드
│   │   ├── courses.py        # 강좌 관리
│   │   ├── checkpoints.py    # 체크포인트 CRUD
│   │   ├── progress.py       # 진도 추적 API
│   │   └── analytics.py      # 분석 및 리포트
│   ├── templates/            # Jinja2 템플릿 (한국어)
│   └── static/               # CSS & JS 에셋
├── config.py                 # 앱 설정
├── main.py                   # 애플리케이션 진입점
├── seed.py                   # 데모 데이터 시더
└── .env.example              # 환경 변수 템플릿
```

## 주요 기능
- **인증**: 역할 기반 (강사/학생) Flask-Login
- **강좌 관리**: 강좌 생성, 초대 코드 발급, 학생 등록
- **체크포인트 시스템**: 순서가 있는 학습 목표, 예상 소요 시간
- **라이브 모드**: WebSocket 기반 실시간 진도 추적
- **자기주도 모드**: 개인별 진도 및 시간 측정
- **분석**: 완료율, 시간 분석, CSV 내보내기

## 실행 방법
```bash
python main.py
```
서버는 포트 5000에서 Socket.IO 지원과 함께 실행됩니다.

## 데모 계정
`python seed.py` 실행 후:
- **강사**: instructor1@example.com, instructor2@example.com
- **학생**: student1@example.com - student10@example.com
- **비밀번호**: password123 (모든 계정 공통)

**샘플 초대 코드**:
- Python 기초: PYTHON01
- 웹개발 기초: WEBDEV01
- 데이터과학: DATASCI1

## 기술 스택
- Flask + Flask-SocketIO
- PostgreSQL + SQLAlchemy
- Flask-Login + bcrypt (인증)
- Bootstrap 5 + Chart.js (프론트엔드)
- Eventlet (비동기 지원)
- Noto Sans KR (폰트)
- Google Gemini AI (Replit AI Integrations 사용)

## 환경 변수
- `DATABASE_URL`: PostgreSQL 연결 문자열
- `SESSION_SECRET`: Flask 세션 시크릿 키
- `AI_INTEGRATIONS_GEMINI_BASE_URL`: Gemini API URL (자동 설정)
- `AI_INTEGRATIONS_GEMINI_API_KEY`: Gemini API 키 (자동 설정)

## 최근 변경사항
- 2026-01-29: **자기주도 학습 시간 측정 기능 추가**
  - 체크포인트 완료 토글: 학생이 직접 완료/미완료 상태 변경 가능
  - 학습 시간 타이머: 시작/일시정지/재개/중단 버튼
  - 실시간 경과 시간 표시 (HH:MM:SS 형식)
  - Progress 모델에 paused_at, accumulated_seconds, is_paused 필드 추가
- 2026-01-29: **로그인 기능 강화 및 테마 변경**
  - 아이디 저장: 쿠키 기반 이메일 저장 (1년 유지)
  - 자동 로그인: Flask-Login remember 기능 (30일)
  - 로그인 페이지 배경: 학습 테마 이미지 + 오버레이 효과
  - 테마 색상: 보라-파랑에서 네이비 계통으로 전체 변경
- 2026-01-29: **UX 고도화** - 실리콘밸리 EdTech PM 관점 개선
  - 개인화 대시보드: 학습 통계 위젯 (완료율, 학습시간, 연속학습일)
  - 게이미피케이션: 연속 학습일 스트릭 시스템 + 달성 배지
  - 실시간 알림: 진행중/예정 라이브 세션 알림 센터
  - 활동 피드: 최근 학습 활동 실시간 표시 (강사용)
  - 모바일 최적화: 반응형 CSS, 터치 친화적 버튼
  - 온보딩 개선: Empty State에 단계별 가이드 추가
- 2026-01-29: 체크포인트 일괄 삭제 기능 추가
- 2026-01-29: AI 체크포인트 생성 기능 추가 (PPT, 영상, 음성 분석)
- 2026-01-29: 학생 체크포인트 완료 토글 기능 추가
- 2026-01-29: 라이브 세션 게시판 및 예약 기능 추가
- 2026-01-29: 전체 UI 한국어 번역 완료
- 2026-01-29: 최신 웹디자인 트렌드 적용 (글래스모피즘, 그라디언트, 모던 타이포그래피)
