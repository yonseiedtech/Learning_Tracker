# Learning Progress Tracking Platform

## Overview
Real-time learning progress monitoring system with dual operational modes: live classroom tracking and self-paced learning analytics. Built with Python Flask, Socket.IO for real-time updates, PostgreSQL database, and Bootstrap 5 frontend.

## Project Structure
```
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── models.py             # SQLAlchemy models
│   ├── forms.py              # WTForms definitions
│   ├── events.py             # Socket.IO event handlers
│   ├── routes/
│   │   ├── auth.py           # Authentication routes
│   │   ├── main.py           # Main dashboard routes
│   │   ├── courses.py        # Course management
│   │   ├── checkpoints.py    # Checkpoint CRUD
│   │   ├── progress.py       # Progress tracking API
│   │   └── analytics.py      # Analytics & reports
│   ├── templates/            # Jinja2 templates
│   └── static/               # CSS & JS assets
├── config.py                 # App configuration
├── main.py                   # Application entry point
├── seed.py                   # Demo data seeder
└── .env.example              # Environment template
```

## Key Features
- **Authentication**: Role-based (instructor/student) with Flask-Login
- **Course Management**: Create courses, generate invite codes, enroll students
- **Checkpoint System**: Ordered learning milestones with estimated durations
- **Live Mode**: Real-time WebSocket-based classroom progress tracking
- **Self-Paced Mode**: Individual progress with time tracking
- **Analytics**: Completion rates, time analysis, CSV export

## Running the Application
```bash
python main.py
```
The server runs on port 5000 with Socket.IO support.

## Demo Credentials
After running `python seed.py`:
- **Instructors**: instructor1@example.com, instructor2@example.com
- **Students**: student1@example.com - student10@example.com
- **Password**: password123 (for all accounts)

## Tech Stack
- Flask + Flask-SocketIO
- PostgreSQL with SQLAlchemy
- Flask-Login + bcrypt for auth
- Bootstrap 5 + Chart.js frontend
- Eventlet for async support

## Environment Variables
- `DATABASE_URL`: PostgreSQL connection string
- `SESSION_SECRET`: Flask session secret key
