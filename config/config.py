import os
from pathlib import Path

class BaseConfig:
    """Base configuration."""
    # Project paths
    BASE_DIR = Path(__file__).parent.parent
    INSTANCE_DIR = BASE_DIR / 'instance'
    PHOTO_STORAGE_PATH = INSTANCE_DIR / 'photos'

    # API configurations
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Flask configurations
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Image processing configurations
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    MAX_IMAGE_SIZE = (1920, 1080)  # Max dimensions for stored images
    
    # TTS configurations
    TTS_LANGUAGE_CODE = "en-US"
    TTS_VOICE_NAME = "en-US-Neural2-C"
    TTS_SPEAKING_RATE = 0.9
    
    # Captioning configurations
    CAPTION_MAX_LENGTH = 1000
    CAPTION_TEMPERATURE = 0.7

class DevelopmentConfig(BaseConfig):
    """Development configuration."""
    DEBUG = True
    TESTING = False

class TestingConfig(BaseConfig):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    # Use temporary directory for test photos
    PHOTO_STORAGE_PATH = Path('/tmp/test_photos')

class ProductionConfig(BaseConfig):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    # Production-specific settings
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB max file size
