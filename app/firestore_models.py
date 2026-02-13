"""
Firestore document models using Python dataclasses.

Replaces SQLAlchemy-based models.py with dataclass-based document models
suitable for Google Cloud Firestore. Each model includes:
  - An `id` field for the Firestore document ID
  - A `to_dict()` instance method for serialization
  - A `from_dict(data, doc_id)` classmethod for deserialization
  - Sensible defaults for all fields

Datetime fields are kept as native datetime objects since Firestore
handles them natively.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _parse_datetime(value) -> Optional[datetime]:
    """Convert a value to datetime. Accepts datetime objects, ISO-format
    strings, and Firestore DatetimeWithNanoseconds objects."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle ISO format strings (with or without trailing Z)
        value = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    # Firestore DatetimeWithNanoseconds is a datetime subclass, handled above
    return None


def _now() -> datetime:
    return datetime.utcnow()


# ===========================================================================
# 1. Organization
# ===========================================================================

@dataclass
class Organization:
    id: Optional[str] = None
    name: str = ""
    description: Optional[str] = None
    logo: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "logo": self.logo,
            "is_active": self.is_active,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Organization:
        return cls(
            id=doc_id,
            name=data.get("name", ""),
            description=data.get("description"),
            logo=data.get("logo"),
            is_active=data.get("is_active", True),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 2. User
# ===========================================================================

@dataclass
class User:
    id: Optional[str] = None          # Firestore document ID
    uid: Optional[str] = None         # Firebase Auth UID (same as id in most cases)
    username: str = ""
    email: str = ""
    role: str = "student"
    organization_id: Optional[str] = None

    # Profile fields
    profile_image: Optional[str] = None
    nickname: Optional[str] = None
    full_name: Optional[str] = None
    profile_url: Optional[str] = None
    bio: Optional[str] = None

    # Basic info
    phone: Optional[str] = None

    # Additional info
    organization_name: Optional[str] = None
    position: Optional[str] = None
    job_title: Optional[str] = None

    # Instructor verification
    instructor_verified: bool = False
    verification_requested_at: Optional[datetime] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # -- Properties ----------------------------------------------------------

    @property
    def display_name(self) -> str:
        if self.nickname:
            return self.nickname
        if self.full_name:
            return self.full_name
        return self.username

    @property
    def initial(self) -> str:
        name = self.display_name
        if name:
            return name[0].upper()
        return "?"

    # -- Role helpers --------------------------------------------------------

    def is_student(self) -> bool:
        return self.role == "student"

    def is_instructor(self) -> bool:
        return self.role in ("instructor", "org_admin", "system_admin")

    def is_org_admin(self) -> bool:
        return self.role == "org_admin"

    def is_system_admin(self) -> bool:
        return self.role == "system_admin"

    def can_access_subject(self, subject_data: Dict[str, Any]) -> bool:
        """Check access using a subject dict (or Subject dataclass with
        organization_id and instructor_id attributes)."""
        if self.is_system_admin():
            return True
        org_id = (subject_data.get("organization_id")
                  if isinstance(subject_data, dict)
                  else getattr(subject_data, "organization_id", None))
        instr_id = (subject_data.get("instructor_id")
                    if isinstance(subject_data, dict)
                    else getattr(subject_data, "instructor_id", None))
        if self.is_org_admin() and org_id == self.organization_id:
            return True
        if instr_id == self.id:
            return True
        return False

    # -- Serialization -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uid": self.uid,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "organization_id": self.organization_id,
            "profile_image": self.profile_image,
            "nickname": self.nickname,
            "full_name": self.full_name,
            "profile_url": self.profile_url,
            "bio": self.bio,
            "phone": self.phone,
            "organization_name": self.organization_name,
            "position": self.position,
            "job_title": self.job_title,
            "instructor_verified": self.instructor_verified,
            "verification_requested_at": self.verification_requested_at,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> User:
        return cls(
            id=doc_id,
            uid=data.get("uid"),
            username=data.get("username", ""),
            email=data.get("email", ""),
            role=data.get("role", "student"),
            organization_id=data.get("organization_id"),
            profile_image=data.get("profile_image"),
            nickname=data.get("nickname"),
            full_name=data.get("full_name"),
            profile_url=data.get("profile_url"),
            bio=data.get("bio"),
            phone=data.get("phone"),
            organization_name=data.get("organization_name"),
            position=data.get("position"),
            job_title=data.get("job_title"),
            instructor_verified=data.get("instructor_verified", False),
            verification_requested_at=_parse_datetime(data.get("verification_requested_at")),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 3. Subject
# ===========================================================================

@dataclass
class Subject:
    id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    instructor_id: Optional[str] = None
    organization_id: Optional[str] = None
    invite_code: str = ""
    is_visible: bool = True
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Denormalized
    instructor_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "instructor_id": self.instructor_id,
            "organization_id": self.organization_id,
            "invite_code": self.invite_code,
            "is_visible": self.is_visible,
            "deleted_at": self.deleted_at,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
            "instructor_name": self.instructor_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Subject:
        return cls(
            id=doc_id,
            title=data.get("title", ""),
            description=data.get("description"),
            instructor_id=data.get("instructor_id"),
            organization_id=data.get("organization_id"),
            invite_code=data.get("invite_code", ""),
            is_visible=data.get("is_visible", True),
            deleted_at=_parse_datetime(data.get("deleted_at")),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            instructor_name=data.get("instructor_name"),
        )


# ===========================================================================
# 4. Course
# ===========================================================================

@dataclass
class Course:
    id: Optional[str] = None
    subject_id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    week_number: Optional[int] = None
    session_number: Optional[int] = None
    order_number: Optional[int] = None
    instructor_id: Optional[str] = None
    invite_code: str = ""
    deleted_at: Optional[datetime] = None
    session_type: str = "live_session"

    # Schedule / visibility
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    attendance_start: Optional[datetime] = None
    attendance_end: Optional[datetime] = None
    late_allowed: bool = False
    late_end: Optional[datetime] = None
    visibility: str = "public"
    prerequisite_course_id: Optional[str] = None

    # Video
    video_url: Optional[str] = None
    video_file_path: Optional[str] = None
    video_file_name: Optional[str] = None

    # Material
    material_file_path: Optional[str] = None
    material_file_name: Optional[str] = None
    material_file_type: Optional[str] = None

    # Assignment
    assignment_description: Optional[str] = None
    assignment_due_date: Optional[datetime] = None

    # Quiz
    quiz_time_limit: Optional[int] = None
    quiz_pass_score: Optional[int] = None

    # Completion
    min_completion_time: Optional[int] = None

    # Status
    preparation_status: str = "not_ready"

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "title": self.title,
            "description": self.description,
            "week_number": self.week_number,
            "session_number": self.session_number,
            "order_number": self.order_number,
            "instructor_id": self.instructor_id,
            "invite_code": self.invite_code,
            "deleted_at": self.deleted_at,
            "session_type": self.session_type,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "attendance_start": self.attendance_start,
            "attendance_end": self.attendance_end,
            "late_allowed": self.late_allowed,
            "late_end": self.late_end,
            "visibility": self.visibility,
            "prerequisite_course_id": self.prerequisite_course_id,
            "video_url": self.video_url,
            "video_file_path": self.video_file_path,
            "video_file_name": self.video_file_name,
            "material_file_path": self.material_file_path,
            "material_file_name": self.material_file_name,
            "material_file_type": self.material_file_type,
            "assignment_description": self.assignment_description,
            "assignment_due_date": self.assignment_due_date,
            "quiz_time_limit": self.quiz_time_limit,
            "quiz_pass_score": self.quiz_pass_score,
            "min_completion_time": self.min_completion_time,
            "preparation_status": self.preparation_status,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Course:
        return cls(
            id=doc_id,
            subject_id=data.get("subject_id"),
            title=data.get("title", ""),
            description=data.get("description"),
            week_number=data.get("week_number"),
            session_number=data.get("session_number"),
            order_number=data.get("order_number"),
            instructor_id=data.get("instructor_id"),
            invite_code=data.get("invite_code", ""),
            deleted_at=_parse_datetime(data.get("deleted_at")),
            session_type=data.get("session_type", "live_session"),
            start_date=_parse_datetime(data.get("start_date")),
            end_date=_parse_datetime(data.get("end_date")),
            attendance_start=_parse_datetime(data.get("attendance_start")),
            attendance_end=_parse_datetime(data.get("attendance_end")),
            late_allowed=data.get("late_allowed", False),
            late_end=_parse_datetime(data.get("late_end")),
            visibility=data.get("visibility", "public"),
            prerequisite_course_id=data.get("prerequisite_course_id"),
            video_url=data.get("video_url"),
            video_file_path=data.get("video_file_path"),
            video_file_name=data.get("video_file_name"),
            material_file_path=data.get("material_file_path"),
            material_file_name=data.get("material_file_name"),
            material_file_type=data.get("material_file_type"),
            assignment_description=data.get("assignment_description"),
            assignment_due_date=_parse_datetime(data.get("assignment_due_date")),
            quiz_time_limit=data.get("quiz_time_limit"),
            quiz_pass_score=data.get("quiz_pass_score"),
            min_completion_time=data.get("min_completion_time"),
            preparation_status=data.get("preparation_status", "not_ready"),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 5. Enrollment
# ===========================================================================

@dataclass
class Enrollment:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    enrolled_at: Optional[datetime] = None
    status: str = "approved"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "enrolled_at": self.enrolled_at or _now(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Enrollment:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            enrolled_at=_parse_datetime(data.get("enrolled_at")),
            status=data.get("status", "approved"),
        )


# ===========================================================================
# 6. Checkpoint
# ===========================================================================

@dataclass
class Checkpoint:
    id: Optional[str] = None
    course_id: Optional[str] = None
    title: str = ""
    description: Optional[str] = None
    order: int = 0
    estimated_minutes: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "description": self.description,
            "order": self.order,
            "estimated_minutes": self.estimated_minutes,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
            "deleted_at": self.deleted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Checkpoint:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            title=data.get("title", ""),
            description=data.get("description"),
            order=data.get("order", 0),
            estimated_minutes=data.get("estimated_minutes"),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            deleted_at=_parse_datetime(data.get("deleted_at")),
        )


# ===========================================================================
# 7. Progress
# ===========================================================================

@dataclass
class Progress:
    id: Optional[str] = None
    user_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    mode: str = "self_paced"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    paused_at: Optional[datetime] = None
    accumulated_seconds: int = 0
    is_paused: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "checkpoint_id": self.checkpoint_id,
            "mode": self.mode,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "paused_at": self.paused_at,
            "accumulated_seconds": self.accumulated_seconds,
            "is_paused": self.is_paused,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Progress:
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            checkpoint_id=data.get("checkpoint_id"),
            mode=data.get("mode", "self_paced"),
            started_at=_parse_datetime(data.get("started_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            duration_seconds=data.get("duration_seconds"),
            paused_at=_parse_datetime(data.get("paused_at")),
            accumulated_seconds=data.get("accumulated_seconds", 0),
            is_paused=data.get("is_paused", False),
        )


# ===========================================================================
# 8. ActiveSession
# ===========================================================================

@dataclass
class ActiveSession:
    id: Optional[str] = None
    course_id: Optional[str] = None
    mode: str = "live"
    session_type: str = "immediate"
    live_status: str = "preparing"
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    current_checkpoint_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "mode": self.mode,
            "session_type": self.session_type,
            "live_status": self.live_status,
            "scheduled_at": self.scheduled_at,
            "started_at": self.started_at or _now(),
            "ended_at": self.ended_at,
            "current_checkpoint_id": self.current_checkpoint_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> ActiveSession:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            mode=data.get("mode", "live"),
            session_type=data.get("session_type", "immediate"),
            live_status=data.get("live_status", "preparing"),
            scheduled_at=_parse_datetime(data.get("scheduled_at")),
            started_at=_parse_datetime(data.get("started_at")),
            ended_at=_parse_datetime(data.get("ended_at")),
            current_checkpoint_id=data.get("current_checkpoint_id"),
        )


# ===========================================================================
# 9. UnderstandingStatus
# ===========================================================================

@dataclass
class UnderstandingStatus:
    id: Optional[str] = None
    user_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    session_id: Optional[str] = None
    status: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> UnderstandingStatus:
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            checkpoint_id=data.get("checkpoint_id"),
            session_id=data.get("session_id"),
            status=data.get("status", ""),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 10. ChatMessage
# ===========================================================================

@dataclass
class ChatMessage:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    message: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "message": self.message,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> ChatMessage:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            message=data.get("message", ""),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 11. ForumPost
# ===========================================================================

@dataclass
class ForumPost:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    title: str = ""
    content: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> ForumPost:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 12. ForumComment
# ===========================================================================

@dataclass
class ForumComment:
    id: Optional[str] = None
    post_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    content: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> ForumComment:
        return cls(
            id=doc_id,
            post_id=data.get("post_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            content=data.get("content", ""),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 13. LiveSessionPost
# ===========================================================================

@dataclass
class LiveSessionPost:
    id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    title: str = ""
    content: str = ""
    pinned: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "title": self.title,
            "content": self.content,
            "pinned": self.pinned,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> LiveSessionPost:
        return cls(
            id=doc_id,
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            pinned=data.get("pinned", False),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 14. LiveSessionComment
# ===========================================================================

@dataclass
class LiveSessionComment:
    id: Optional[str] = None
    post_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    content: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> LiveSessionComment:
        return cls(
            id=doc_id,
            post_id=data.get("post_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            content=data.get("content", ""),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 15. Attendance
# ===========================================================================

@dataclass
class Attendance:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    status: str = "present"
    checked_at: Optional[datetime] = None
    checked_by_id: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "status": self.status,
            "checked_at": self.checked_at or _now(),
            "checked_by_id": self.checked_by_id,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Attendance:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            status=data.get("status", "present"),
            checked_at=_parse_datetime(data.get("checked_at")),
            checked_by_id=data.get("checked_by_id"),
            notes=data.get("notes"),
        )


# ===========================================================================
# 16. LearningReview
# ===========================================================================

@dataclass
class LearningReview:
    id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    course_id: Optional[str] = None
    subject_id: Optional[str] = None
    title: str = ""
    content: str = ""
    rating: int = 5
    likes_count: int = 0
    views_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "course_id": self.course_id,
            "subject_id": self.subject_id,
            "title": self.title,
            "content": self.content,
            "rating": self.rating,
            "likes_count": self.likes_count,
            "views_count": self.views_count,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> LearningReview:
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            course_id=data.get("course_id"),
            subject_id=data.get("subject_id"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            rating=data.get("rating", 5),
            likes_count=data.get("likes_count", 0),
            views_count=data.get("views_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 17. ReviewComment
# ===========================================================================

@dataclass
class ReviewComment:
    id: Optional[str] = None
    review_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    content: str = ""
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> ReviewComment:
        return cls(
            id=doc_id,
            review_id=data.get("review_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            content=data.get("content", ""),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 18. QnAPost
# ===========================================================================

@dataclass
class QnAPost:
    id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    course_id: Optional[str] = None
    subject_id: Optional[str] = None
    title: str = ""
    content: str = ""
    is_resolved: bool = False
    views_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "user_name": self.user_name,
            "course_id": self.course_id,
            "subject_id": self.subject_id,
            "title": self.title,
            "content": self.content,
            "is_resolved": self.is_resolved,
            "views_count": self.views_count,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> QnAPost:
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            course_id=data.get("course_id"),
            subject_id=data.get("subject_id"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            is_resolved=data.get("is_resolved", False),
            views_count=data.get("views_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 19. QnAAnswer
# ===========================================================================

@dataclass
class QnAAnswer:
    id: Optional[str] = None
    post_id: Optional[str] = None
    user_id: Optional[str] = None
    user_name: Optional[str] = None  # denormalized
    content: str = ""
    is_accepted: bool = False
    likes_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "is_accepted": self.is_accepted,
            "likes_count": self.likes_count,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> QnAAnswer:
        return cls(
            id=doc_id,
            post_id=data.get("post_id"),
            user_id=data.get("user_id"),
            user_name=data.get("user_name"),
            content=data.get("content", ""),
            is_accepted=data.get("is_accepted", False),
            likes_count=data.get("likes_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 20. StudyGroup
# ===========================================================================

@dataclass
class StudyGroup:
    id: Optional[str] = None
    creator_id: Optional[str] = None
    creator_name: Optional[str] = None  # denormalized
    title: str = ""
    description: str = ""
    category: str = "general"
    max_members: int = 10
    current_members: int = 1
    status: str = "recruiting"
    meeting_type: str = "online"
    meeting_schedule: Optional[str] = None
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "creator_id": self.creator_id,
            "creator_name": self.creator_name,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "max_members": self.max_members,
            "current_members": self.current_members,
            "status": self.status,
            "meeting_type": self.meeting_type,
            "meeting_schedule": self.meeting_schedule,
            "tags": self.tags or [],
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> StudyGroup:
        tags = data.get("tags")
        # Handle tags stored as comma-separated string (legacy) or list
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        return cls(
            id=doc_id,
            creator_id=data.get("creator_id"),
            creator_name=data.get("creator_name"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            max_members=data.get("max_members", 10),
            current_members=data.get("current_members", 1),
            status=data.get("status", "recruiting"),
            meeting_type=data.get("meeting_type", "online"),
            meeting_schedule=data.get("meeting_schedule"),
            tags=tags,
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 21. StudyGroupMember
# ===========================================================================

@dataclass
class StudyGroupMember:
    id: Optional[str] = None
    group_id: Optional[str] = None
    user_id: Optional[str] = None
    status: str = "pending"
    joined_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "user_id": self.user_id,
            "status": self.status,
            "joined_at": self.joined_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> StudyGroupMember:
        return cls(
            id=doc_id,
            group_id=data.get("group_id"),
            user_id=data.get("user_id"),
            status=data.get("status", "pending"),
            joined_at=_parse_datetime(data.get("joined_at")),
        )


# ===========================================================================
# 22. SubjectEnrollment
# ===========================================================================

@dataclass
class SubjectEnrollment:
    id: Optional[str] = None
    subject_id: Optional[str] = None
    user_id: Optional[str] = None
    status: str = "pending"
    role: str = "student"
    enrolled_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "user_id": self.user_id,
            "status": self.status,
            "role": self.role,
            "enrolled_at": self.enrolled_at or _now(),
            "approved_at": self.approved_at,
            "rejected_at": self.rejected_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> SubjectEnrollment:
        return cls(
            id=doc_id,
            subject_id=data.get("subject_id"),
            user_id=data.get("user_id"),
            status=data.get("status", "pending"),
            role=data.get("role", "student"),
            enrolled_at=_parse_datetime(data.get("enrolled_at")),
            approved_at=_parse_datetime(data.get("approved_at")),
            rejected_at=_parse_datetime(data.get("rejected_at")),
        )


# ===========================================================================
# 23. SubjectMember
# ===========================================================================

@dataclass
class SubjectMember:
    id: Optional[str] = None
    subject_id: Optional[str] = None
    user_id: Optional[str] = None
    role: str = "student"
    created_at: Optional[datetime] = None

    @staticmethod
    def get_role_display(role: str) -> str:
        role_map = {
            "instructor": "\uac15\uc0ac",
            "assistant": "\uc870\uad50",
            "student": "\ud559\uc2b5\uc790",
        }
        return role_map.get(role, role)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "user_id": self.user_id,
            "role": self.role,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> SubjectMember:
        return cls(
            id=doc_id,
            subject_id=data.get("subject_id"),
            user_id=data.get("user_id"),
            role=data.get("role", "student"),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 24. GuidePost
# ===========================================================================

@dataclass
class GuidePost:
    id: Optional[str] = None
    category: str = ""
    title: str = ""
    content: str = ""
    author_id: Optional[str] = None
    author_name: Optional[str] = None  # denormalized
    is_pinned: bool = False
    is_answered: bool = False
    view_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "title": self.title,
            "content": self.content,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "is_pinned": self.is_pinned,
            "is_answered": self.is_answered,
            "view_count": self.view_count,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> GuidePost:
        return cls(
            id=doc_id,
            category=data.get("category", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            author_id=data.get("author_id"),
            author_name=data.get("author_name"),
            is_pinned=data.get("is_pinned", False),
            is_answered=data.get("is_answered", False),
            view_count=data.get("view_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 25. GuideComment
# ===========================================================================

@dataclass
class GuideComment:
    id: Optional[str] = None
    post_id: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None  # denormalized
    content: str = ""
    is_admin_reply: bool = False
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "content": self.content,
            "is_admin_reply": self.is_admin_reply,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> GuideComment:
        return cls(
            id=doc_id,
            post_id=data.get("post_id"),
            author_id=data.get("author_id"),
            author_name=data.get("author_name"),
            content=data.get("content", ""),
            is_admin_reply=data.get("is_admin_reply", False),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 26. GuideAttachment
# ===========================================================================

@dataclass
class GuideAttachment:
    id: Optional[str] = None
    post_id: Optional[str] = None
    filename: str = ""
    original_filename: str = ""
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    storage_path: Optional[str] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "post_id": self.post_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "storage_path": self.storage_path,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> GuideAttachment:
        return cls(
            id=doc_id,
            post_id=data.get("post_id"),
            filename=data.get("filename", ""),
            original_filename=data.get("original_filename", ""),
            file_size=data.get("file_size"),
            file_type=data.get("file_type"),
            storage_path=data.get("storage_path"),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 27. QuizQuestion
# ===========================================================================

@dataclass
class QuizQuestion:
    id: Optional[str] = None
    course_id: Optional[str] = None
    question_text: str = ""
    question_type: str = "multiple_choice"
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    points: int = 1
    order: int = 0
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "options": self.options or [],
            "correct_answer": self.correct_answer,
            "points": self.points,
            "order": self.order,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> QuizQuestion:
        options = data.get("options")
        # Handle options stored as JSON string (legacy)
        if isinstance(options, str):
            import json
            try:
                options = json.loads(options)
            except (json.JSONDecodeError, TypeError):
                options = []
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            question_text=data.get("question_text", ""),
            question_type=data.get("question_type", "multiple_choice"),
            options=options,
            correct_answer=data.get("correct_answer"),
            points=data.get("points", 1),
            order=data.get("order", 0),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 28. QuizAttempt
# ===========================================================================

@dataclass
class QuizAttempt:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    score: int = 0
    max_score: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    answers: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "score": self.score,
            "max_score": self.max_score,
            "started_at": self.started_at or _now(),
            "completed_at": self.completed_at,
            "answers": self.answers or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> QuizAttempt:
        answers = data.get("answers")
        # Handle answers stored as JSON string (legacy)
        if isinstance(answers, str):
            import json
            try:
                answers = json.loads(answers)
            except (json.JSONDecodeError, TypeError):
                answers = {}
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            score=data.get("score", 0),
            max_score=data.get("max_score", 0),
            started_at=_parse_datetime(data.get("started_at")),
            completed_at=_parse_datetime(data.get("completed_at")),
            answers=answers,
        )


# ===========================================================================
# 29. AssignmentSubmission
# ===========================================================================

@dataclass
class AssignmentSubmission:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    content: Optional[str] = None
    storage_path: Optional[str] = None
    file_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    score: Optional[int] = None
    feedback: Optional[str] = None
    graded_at: Optional[datetime] = None
    graded_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "content": self.content,
            "storage_path": self.storage_path,
            "file_name": self.file_name,
            "submitted_at": self.submitted_at or _now(),
            "score": self.score,
            "feedback": self.feedback,
            "graded_at": self.graded_at,
            "graded_by": self.graded_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> AssignmentSubmission:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            content=data.get("content"),
            storage_path=data.get("storage_path"),
            file_name=data.get("file_name"),
            submitted_at=_parse_datetime(data.get("submitted_at")),
            score=data.get("score"),
            feedback=data.get("feedback"),
            graded_at=_parse_datetime(data.get("graded_at")),
            graded_by=data.get("graded_by"),
        )


# ===========================================================================
# 30. VideoWatchLog
# ===========================================================================

@dataclass
class VideoWatchLog:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    watched_seconds: int = 0
    total_duration: Optional[int] = None
    watch_percentage: float = 0.0
    last_position: int = 0
    play_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "watched_seconds": self.watched_seconds,
            "total_duration": self.total_duration,
            "watch_percentage": self.watch_percentage,
            "last_position": self.last_position,
            "play_count": self.play_count,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> VideoWatchLog:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            watched_seconds=data.get("watched_seconds", 0),
            total_duration=data.get("total_duration"),
            watch_percentage=data.get("watch_percentage", 0.0),
            last_position=data.get("last_position", 0),
            play_count=data.get("play_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 31. SessionCompletion
# ===========================================================================

@dataclass
class SessionCompletion:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    completed_at: Optional[datetime] = None
    completion_type: str = "manual"
    time_spent_seconds: int = 0
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "completed_at": self.completed_at or _now(),
            "completion_type": self.completion_type,
            "time_spent_seconds": self.time_spent_seconds,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> SessionCompletion:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            completed_at=_parse_datetime(data.get("completed_at")),
            completion_type=data.get("completion_type", "manual"),
            time_spent_seconds=data.get("time_spent_seconds", 0),
            notes=data.get("notes"),
        )


# ===========================================================================
# 32. PageTimeLog
# ===========================================================================

@dataclass
class PageTimeLog:
    id: Optional[str] = None
    course_id: Optional[str] = None
    user_id: Optional[str] = None
    total_seconds: int = 0
    last_active_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "user_id": self.user_id,
            "total_seconds": self.total_seconds,
            "last_active_at": self.last_active_at or _now(),
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> PageTimeLog:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            user_id=data.get("user_id"),
            total_seconds=data.get("total_seconds", 0),
            last_active_at=_parse_datetime(data.get("last_active_at")),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 33. SlideDeck
# ===========================================================================

@dataclass
class SlideDeck:
    id: Optional[str] = None
    course_id: Optional[str] = None
    session_id: Optional[str] = None
    file_name: str = ""
    slide_count: int = 0
    current_slide_index: int = 0
    conversion_status: str = "pending"
    conversion_error: Optional[str] = None
    slides_dir: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    flag_threshold_count: int = 5
    flag_threshold_rate: float = 0.25
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "course_id": self.course_id,
            "session_id": self.session_id,
            "file_name": self.file_name,
            "slide_count": self.slide_count,
            "current_slide_index": self.current_slide_index,
            "conversion_status": self.conversion_status,
            "conversion_error": self.conversion_error,
            "slides_dir": self.slides_dir,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "flag_threshold_count": self.flag_threshold_count,
            "flag_threshold_rate": self.flag_threshold_rate,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> SlideDeck:
        return cls(
            id=doc_id,
            course_id=data.get("course_id"),
            session_id=data.get("session_id"),
            file_name=data.get("file_name", ""),
            slide_count=data.get("slide_count", 0),
            current_slide_index=data.get("current_slide_index", 0),
            conversion_status=data.get("conversion_status", "pending"),
            conversion_error=data.get("conversion_error"),
            slides_dir=data.get("slides_dir"),
            estimated_duration_minutes=data.get("estimated_duration_minutes"),
            flag_threshold_count=data.get("flag_threshold_count", 5),
            flag_threshold_rate=data.get("flag_threshold_rate", 0.25),
            created_at=_parse_datetime(data.get("created_at")),
        )


# ===========================================================================
# 34. SlideReaction
# ===========================================================================

@dataclass
class SlideReaction:
    id: Optional[str] = None
    deck_id: Optional[str] = None
    user_id: Optional[str] = None
    slide_index: int = 0
    reaction: str = "none"
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deck_id": self.deck_id,
            "user_id": self.user_id,
            "slide_index": self.slide_index,
            "reaction": self.reaction,
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> SlideReaction:
        return cls(
            id=doc_id,
            deck_id=data.get("deck_id"),
            user_id=data.get("user_id"),
            slide_index=data.get("slide_index", 0),
            reaction=data.get("reaction", "none"),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 35. SlideBookmark
# ===========================================================================

@dataclass
class SlideBookmark:
    id: Optional[str] = None
    deck_id: Optional[str] = None
    slide_index: int = 0
    is_auto: bool = False
    is_manual: bool = False
    reason: Optional[str] = None
    memo: Optional[str] = None
    supplement_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deck_id": self.deck_id,
            "slide_index": self.slide_index,
            "is_auto": self.is_auto,
            "is_manual": self.is_manual,
            "reason": self.reason,
            "memo": self.memo,
            "supplement_url": self.supplement_url,
            "created_at": self.created_at or _now(),
            "updated_at": self.updated_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> SlideBookmark:
        return cls(
            id=doc_id,
            deck_id=data.get("deck_id"),
            slide_index=data.get("slide_index", 0),
            is_auto=data.get("is_auto", False),
            is_manual=data.get("is_manual", False),
            reason=data.get("reason"),
            memo=data.get("memo"),
            supplement_url=data.get("supplement_url"),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )


# ===========================================================================
# 36. Notification
# ===========================================================================

@dataclass
class Notification:
    id: Optional[str] = None
    user_id: Optional[str] = None
    type: str = ""
    title: str = ""
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    is_read: bool = False
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "data": self.data or {},
            "is_read": self.is_read,
            "created_at": self.created_at or _now(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], doc_id: Optional[str] = None) -> Notification:
        return cls(
            id=doc_id,
            user_id=data.get("user_id"),
            type=data.get("type", ""),
            title=data.get("title", ""),
            message=data.get("message"),
            data=data.get("data"),
            is_read=data.get("is_read", False),
            created_at=_parse_datetime(data.get("created_at")),
        )
