import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def validate_env_variables():
    """Validate that all required environment variables are set"""
    required_vars = {
        'MPESA_CONSUMER_KEY': 'MPesa Consumer Key',
        'MPESA_CONSUMER_SECRET': 'MPesa Consumer Secret',
        'MPESA_PASSKEY': 'MPesa Passkey',
        'MPESA_SHORTCODE': 'MPesa Shortcode',
        'MONGODB_URI': 'MongoDB Connection URI',
        'FLASK_SECRET_KEY': 'Flask Secret Key'
    }
    
    missing_vars = []
    for var, name in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(name)
    
    if missing_vars:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}\n"
            "Please check your .env file or system environment variables."
        )

class Config:
    # Load sensitive data from environment variables
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    # Database names
    DB_DEGREE = 'courses_2'
    DB_DIPLOMA = 'dp_courses'
    DB_CERTIFICATE = 'cert_courses'
    DB_ARTISAN = 'art_courses'
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    PREFERRED_URL_SCHEME = 'https'
    
    # CORS settings
    CORS_ORIGINS = [
        'https://kuccps-courses.onrender.com',
        'https://kuccps.co.ke'
    ]
    
    # Rate limiting
    RATELIMIT_DEFAULT = "100 per minute"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Content Security Policy
    CONTENT_SECURITY_POLICY = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data: https:",
        'connect-src': "'self' https:",
        'font-src': "'self'",
        'object-src': "'none'",
        'media-src': "'self'",
        'frame-src': "'self'"
    }

class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    API_HOST = '0.0.0.0'
    API_PORT = int(os.getenv('PORT', 5000))

class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    API_HOST = '127.0.0.1'
    API_PORT = 5000
    SESSION_COOKIE_SECURE = False
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']

# Load and validate environment variables
validate_env_variables()

# Get the appropriate config based on environment
def get_config():
    env = os.getenv('FLASK_ENV', 'production')
    if env == 'development':
        return DevelopmentConfig
    return ProductionConfig