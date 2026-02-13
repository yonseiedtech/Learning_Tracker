import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    FIREBASE_CREDENTIALS_PATH = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', './firebase-service-account.json')
    FIREBASE_STORAGE_BUCKET = os.environ.get('FIREBASE_STORAGE_BUCKET', '')
    FIREBASE_WEB_API_KEY = os.environ.get('FIREBASE_WEB_API_KEY', '')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '')
