import os
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth

_app = None
_db = None
_bucket = None


def init_firebase(app_config=None):
    global _app, _db, _bucket

    if _app is not None:
        return

    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', './firebase-service-account.json')

    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        cred = credentials.ApplicationDefault()

    bucket_name = ''
    if app_config:
        bucket_name = app_config.get('FIREBASE_STORAGE_BUCKET', '')
    if not bucket_name:
        bucket_name = os.environ.get('FIREBASE_STORAGE_BUCKET', '')

    options = {}
    if bucket_name:
        options['storageBucket'] = bucket_name

    _app = firebase_admin.initialize_app(cred, options=options if options else None)
    _db = firestore.client()

    if bucket_name:
        _bucket = storage.bucket()


def get_db():
    global _db
    if _db is None:
        init_firebase()
    return _db


def get_bucket():
    global _bucket
    if _bucket is None:
        init_firebase()
    return _bucket


def get_auth():
    return auth
