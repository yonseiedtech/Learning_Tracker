from functools import wraps
from flask import request, redirect, url_for, flash, g, session
from app.firebase_init import get_auth, get_db


def _verify_session():
    """Verify Firebase session cookie and populate g.current_user."""
    session_cookie = session.get('firebase_session')
    if not session_cookie:
        return None

    auth = get_auth()
    try:
        decoded = auth.verify_session_cookie(session_cookie, check_revoked=True)
        uid = decoded['uid']

        db = get_db()
        user_doc = db.collection('users').document(uid).get()
        if not user_doc.exists:
            return None

        user_data = user_doc.to_dict()
        user_data['uid'] = uid
        user_data['id'] = uid
        user_data['is_authenticated'] = True
        return user_data
    except Exception:
        return None


class CurrentUser:
    """Proxy object providing attribute access to the current user dict."""

    def __init__(self, data=None):
        self._data = data or {}

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return self._data.get(name)

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    def get(self, key, default=None):
        return self._data.get(key, default)

    @property
    def is_authenticated(self):
        return bool(self._data)

    @property
    def uid(self):
        return self._data.get('uid', '')

    @property
    def id(self):
        return self._data.get('uid', '')

    @property
    def role(self):
        return self._data.get('role', 'student')

    @property
    def display_name(self):
        if self._data.get('nickname'):
            return self._data['nickname']
        if self._data.get('full_name'):
            return self._data['full_name']
        return self._data.get('username', '')

    @property
    def initial(self):
        name = self.display_name
        return name[0].upper() if name else '?'

    def is_student(self):
        return self.role == 'student'

    def is_instructor(self):
        return self.role in ('instructor', 'org_admin', 'system_admin')

    def is_org_admin(self):
        return self.role == 'org_admin'

    def is_system_admin(self):
        return self.role == 'system_admin'


def load_current_user():
    """Load current user into g before each request."""
    if hasattr(g, '_current_user'):
        return
    user_data = _verify_session()
    g._current_user = CurrentUser(user_data)


def get_current_user():
    if not hasattr(g, '_current_user'):
        load_current_user()
    return g._current_user


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user.is_authenticated:
            flash('로그인이 필요합니다.', 'info')
            return redirect(url_for('auth.login', next=request.url))
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user.is_authenticated:
                flash('로그인이 필요합니다.', 'info')
                return redirect(url_for('auth.login', next=request.url))
            if user.role not in roles:
                flash('접근 권한이 없습니다.', 'danger')
                return redirect(url_for('main.dashboard'))
            g.current_user = user
            return f(*args, **kwargs)
        return decorated
    return decorator
