import os
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = True
    
    # Session Configuration
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # MongoDB Configuration
    MONGO_URI = os.getenv('MONGO_URI',"mongodb://localhost:27017/")
    DATABASE_NAME = 'online_exam_proctor'
    
    # Upload Configuration
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
    # Exam Configuration
    EXAM_DURATION = 30  # minutes
    VIOLATION_THRESHOLD = 50  # suspicious score threshold
    
    # Proctoring Settings
    FACE_DETECTION_INTERVAL = 5  # seconds
    TAB_SWITCH_PENALTY = 7
    FACE_MISSING_PENALTY = 5
    MULTIPLE_FACES_PENALTY = 10
