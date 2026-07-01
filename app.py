import os
import base64
from datetime import datetime, timedelta
from flask_caching import Cache
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response, Response
from pymongo import MongoClient
from courses import get_user_courses, save_user_courses
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
from bson import ObjectId
import requests
from guide_routes import register_guides
from flask import send_from_directory
from requests.auth import HTTPBasicAuth
import json
import re
import google.genai as genai
from google.genai import types
import random                           
import time
import hashlib
import logging
import threading
import gzip
from io import BytesIO
from queue import Queue
from cloudinary_config import init_cloudinary, upload_screenshot, delete_screenshot, get_screenshot_url
from pdf_generator import generate_courses_pdf
from email_service import send_courses_report, send_manual_activation_email, queue_courses_report


# --- Configuration and Setup ---
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key_not_for_production')

# Set SERVER_NAME for proper URL generation
# This is critical for url_for() to work correctly with _external=True
PRODUCTION_DOMAIN = 'www.kuccpscourses.co.ke'
if os.getenv('FLASK_ENV') == 'production':
    app.config['SERVER_NAME'] = PRODUCTION_DOMAIN

# Performance optimizations
app.config['JSON_SORT_KEYS'] = False  # Avoid sorting JSON keys
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year cache for static files
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['TRAP_EXCEPTIONS_ON_HANDLER_FAILURE'] = False
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max upload size

app.config.update(
    SESSION_TYPE='filesystem',
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_REFRESH_EACH_REQUEST=True,
    PREFERRED_URL_SCHEME='https'
)


# Try to import redis, but don't fail if not available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ redis module not installed, using simple cache")
# Configure cache - use Redis if available, fall back to simple for development
# Configure cache - use Redis if available, fall back to simple for development
# Configure cache - use Redis if available, fall back to simple for development
REDIS_URL = os.getenv('REDIS_URL')
if REDIS_URL and REDIS_AVAILABLE:
    try:
        # Test Redis connection
        test_redis = redis.from_url(REDIS_URL)
        test_redis.ping()
        
        cache_config = {
            'CACHE_TYPE': 'RedisCache',
            'CACHE_REDIS_URL': REDIS_URL,
            'CACHE_DEFAULT_TIMEOUT': 300,
            'CACHE_KEY_PREFIX': 'kuccps_'
        }
        print("✅ Redis cache enabled and connected")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}, falling back to simple cache")
        cache_config = {
            'CACHE_TYPE': 'simple',
            'CACHE_DEFAULT_TIMEOUT': 300
        }
elif REDIS_URL and not REDIS_AVAILABLE:
    print("⚠️ REDIS_URL set but redis module not installed. Install with: pip install redis")
    cache_config = {
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': 300
    }
else:
    cache_config = {
        'CACHE_TYPE': 'simple',
        'CACHE_DEFAULT_TIMEOUT': 300
    }
    print("⚠️ Redis not available, using in-memory cache (not recommended for production)")
cache = Cache(app, config=cache_config)
# ============================================
# CACHE CLEARING FUNCTIONS
# ============================================

def clear_all_cache():
    """Clear all server-side cache (both Redis and simple)"""
    try:
        cache.clear()
        print("✅ Server-side cache cleared successfully")
        return True
    except Exception as e:
        print(f"❌ Error clearing server-side cache: {str(e)}")
        return False
    
def get_openrouter_fallback(user_message):
    """Efficient OpenRouter with caching and rate limit handling"""
    try:
        OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
        if not OPENROUTER_API_KEY:
            print("⚠️ OPENROUTER_API_KEY not found in environment")
            return None
        
        # Use auto-router for best availability
        models_to_try = [
            "openrouter/free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "openai/gpt-oss-120b:free",
        ]
        
        condensed_prompt = """You are the official AI assistant for KUCCPS Courses Checker (kuccpscourses.co.ke). 

KEY PLATFORM INFORMATION:
- First category check: KES 200
- Additional categories: KES 100 each
- Payment: M-PESA STK Push
- 6 categories: Degree(C+), Diploma(C-), KMTC(C-), TTC(C), Certificate(D+), Artisan(D/E)
- 5000+ courses, 200+ institutions
- Email: kuccpscourses@gmail.com | Phone: +254750732841

OFFICIAL KUCCPS INFO:
- Application fee: KES 1,500 (eCitizen)
- Website: students.kuccps.net
- Degree: C+ minimum | Diploma: C- | Certificate: D+ | Artisan: D/E
- Cluster points: A=12, A-=11, B+=10, B=9, B-=8, C+=7, C=6, C-=5, D+=4, D=3

Be helpful, friendly, and concise (2-3 sentences). Answer from a student's perspective.

User question: {user_message}"""
        
        for model in models_to_try:
            try:
                print(f"🔄 Trying OpenRouter model: {model}")
                
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://www.studentsplacement.co.ke",
                        "X-Title": "KUCCPS Courses Checker",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": condensed_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "temperature": 0.5,
                        "max_tokens": 500,
                        "top_p": 0.9
                    },
                    timeout=15
                )
                
                print(f"📥 Response status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result['choices'][0]['message']['content'].strip()
                    
                    if ai_response and len(ai_response) > 20:
                        print(f"✅ Got GOOD response from OpenRouter {model}")
                        return ai_response
                    else:
                        print(f"⚠️ Response from {model} was too short or empty")
                        continue
                        
                elif response.status_code == 429:
                    print(f"⚠️ Rate limited on {model}, trying next model...")
                    time.sleep(1)
                    continue
                    
                elif response.status_code == 401:
                    print(f"❌ Invalid API key! Please check OPENROUTER_API_KEY in .env")
                    return None
                    
                else:
                    print(f"❌ Model {model} failed with status {response.status_code}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"⏱️ OpenRouter model {model} timed out")
                continue
            except Exception as e:
                print(f"❌ OpenRouter model {model} error: {e}")
                continue
        
        print("⚠️ All OpenRouter models failed")
        return None
        
    except Exception as e:
        print(f"❌ OpenRouter critical error: {e}")
        return None

def clear_cdn_cache_headers(response):
    """Set headers to clear CDN cache on next request"""
    # Cloudflare cache clearing headers
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Cloudflare specific
    response.headers['CF-Cache-Control'] = 'no-cache'
    
    return response
# Add this with your other caches
search_cache = {}
search_cache_timestamps = {}
SEARCH_CACHE_DURATION = 3600  # Cache search results for 1 hour
def is_legitimate_manual_activation(email, index_number):
    """
    Check if a manual activation is legitimate (created by admin)
    Returns True only for activations created via admin panel
    """
    if not database_connected or admin_activations_collection is None:
        return False
    
    try:
        activation = admin_activations_collection.find_one({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ],
            'is_active': True,
            'status': 'active'
        })
        
        if not activation:
            return False
        
        # Only allow activations that are:
        # 1. Created by admin (not 'callback_auto' or 'system')
        # 2. Have is_legitimate_manual flag set to True
        activation_type = activation.get('activation_type', '')
        is_legitimate = activation.get('is_legitimate_manual', False)
        
        # 🔥 FIX: Accept 'manual' AND 'admin_manual' as legitimate
        if activation_type in ['admin_manual', 'manual'] or is_legitimate:
            print(f"✅ Legitimate manual activation found for {email} (type: {activation_type})")
            return True
        else:
            print(f"⚠️ Found automatic activation (type: {activation_type}) - IGNORING")
            return False
            
    except Exception as e:
        print(f"❌ Error checking activation legitimacy: {e}")
        return False
def get_cached_or_search(query):
    """Get cached search results or perform new search"""
    
    message_hash = hashlib.md5(query.encode()).hexdigest()
    
    # Check cache
    if message_hash in search_cache:
        cache_time = search_cache_timestamps.get(message_hash)
        if cache_time and (datetime.now() - cache_time).total_seconds() < SEARCH_CACHE_DURATION:
            print(f"✅ Using cached search for: {query[:30]}...")
            return search_cache[message_hash]
    
    # Perform search
    result = search_kuccps_info(query)
    
    # Cache the result
    if result:
        search_cache[message_hash] = result
        search_cache_timestamps[message_hash] = datetime.now()
    
    return result

# Go# ============================================
# GOOGLE GEMINI CONFIGURATION - SECURE VERSION
# ============================================

# Load Gemini API key from environment variables ONLY
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Validate Gemini API key at startup
if not GEMINI_API_KEY:
    print("⚠️ ⚠️ ⚠️ CRITICAL SECURITY WARNING ⚠️ ⚠️ ⚠️")
    print("❌ GEMINI_API_KEY not found in environment variables!")
    print("💡 Please add GEMINI_API_KEY to your .env file")
    print("🔑 Example: GEMINI_API_KEY=AIzaSyCobIL_Z8Jjfr4A2CEazVOefQA4a42kEhc")
    print("⚠️ AI features will be disabled until key is configured")
    print("=" * 50)
else:
    print(f"✅ Gemini API key loaded successfully from environment")
    print(f"🔑 Key preview: {GEMINI_API_KEY[:10]}... (first 10 chars only)")
    print(f"📊 Daily limit: 1500 requests (free tier)")
if os.getenv('CLOUDINARY_CLOUD_NAME'):
    try:
        init_cloudinary()
        CLOUDINARY_ENABLED = True
        print("✅ Cloudinary is enabled and configured")
    except Exception as e:
        print(f"⚠️ Cloudinary initialization failed: {e}")
        CLOUDINARY_ENABLED = False
else:
    CLOUDINARY_ENABLED = False
    print("⚠️ Cloudinary not configured, screenshots will not be saved")


# Gemini model configuration
GEMINI_MODEL = "gemini-1.5-flash"  # Fast, free, reliable

# Cache for Gemini responses
gemini_response_cache = {}
gemini_cache_timestamps = {}
SEARCH_CACHE_DURATION = 3600  # Cache search results for 1 hour

# Rate limiting for Gemini
gemini_calls_today = 0
gemini_calls_today_reset = datetime.now().date()
MAX_GEMINI_DAILY = 1500  # Google's free tier limit

# Configure simple logging for AI calls
logging.basicConfig(filename='ai_calls.log', level=logging.INFO, 
                    format='%(asctime)s %(levelname)s: %(message)s')

print(f"📅 Today's date: {gemini_calls_today_reset}")
print(f"🔄 Gemini daily counter initialized at 0")
print("=" * 50)

# Configure simple logging for AI calls
logging.basicConfig(filename='ai_calls.log', level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# ============================================
# PERFORMANCE OPTIMIZATION MIDDLEWARE
# ============================================
@app.route('/admin/get-screenshot-url/<issue_id>')
def get_screenshot_url_route(issue_id):
    """Get screenshot URL for an issue"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        from bson import ObjectId
        
        # Find the issue
        issue = payment_issues_collection.find_one({'_id': ObjectId(issue_id)})
        
        if not issue:
            return jsonify({'success': False, 'error': 'Issue not found'}), 404
        
        # Check for Cloudinary URL first
        screenshot_url = issue.get('screenshot_url')
        if screenshot_url:
            # Validate the URL is accessible
            import requests
            try:
                # Quick check if URL is valid
                response = requests.head(screenshot_url, timeout=5)
                if response.status_code == 200:
                    return jsonify({
                        'success': True,
                        'url': screenshot_url,
                        'public_id': issue.get('screenshot_public_id'),
                        'storage': 'cloudinary',
                        'valid': True
                    })
                else:
                    print(f"⚠️ Cloudinary URL returned status {response.status_code}")
            except Exception as e:
                print(f"⚠️ Could not verify Cloudinary URL: {e}")
            
            # Return URL anyway, let frontend handle
            return jsonify({
                'success': True,
                'url': screenshot_url,
                'storage': 'cloudinary',
                'valid': True
            })
        
        # Check for base64 screenshot
        screenshot_data = issue.get('screenshot')
        if screenshot_data:
            # Validate base64 data
            if screenshot_data.startswith('data:image'):
                # Check if the base64 data is complete
                try:
                    # Extract the base64 part
                    if ',' in screenshot_data:
                        base64_part = screenshot_data.split(',')[1]
                        # Try to decode first few bytes to validate
                        import base64
                        test_decode = base64.b64decode(base64_part[:100])
                        if test_decode:
                            return jsonify({
                                'success': True,
                                'url': screenshot_data,  # Return base64 directly
                                'storage': 'base64',
                                'size': len(screenshot_data)
                            })
                except Exception as e:
                    print(f"❌ Invalid base64 data: {e}")
                    return jsonify({
                        'success': False,
                        'error': 'Invalid screenshot data - corrupted',
                        'needs_migration': True
                    }), 400
            
            return jsonify({
                'success': True,
                'url': screenshot_data,
                'storage': 'base64'
            })
        
        return jsonify({'success': False, 'error': 'No screenshot available'}), 404
        
    except Exception as e:
        print(f"❌ Error getting screenshot URL: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/admin/migrate-screenshot/<issue_id>', methods=['POST'])
def migrate_screenshot_route(issue_id):
    """Migrate a single screenshot to Cloudinary"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        from bson import ObjectId
        
        issue = payment_issues_collection.find_one({'_id': ObjectId(issue_id)})
        
        if not issue:
            return jsonify({'success': False, 'error': 'Issue not found'}), 404
        
        # Check if already migrated
        if issue.get('screenshot_url'):
            return jsonify({'success': True, 'message': 'Already migrated', 'url': issue['screenshot_url']})
        
        # Get base64 screenshot
        screenshot_data = issue.get('screenshot')
        if not screenshot_data or not screenshot_data.startswith('data:image'):
            return jsonify({'success': False, 'error': 'No valid screenshot to migrate'}), 400
        
        # Migrate to Cloudinary
        email = issue.get('email', 'unknown')
        receipt = issue.get('mpesa_receipt', 'unknown')
        index_number = issue.get('index_number', 'unknown')
        
        screenshot_url, public_id, info = upload_screenshot(
            screenshot_data, email, receipt, index_number
        )
        
        if screenshot_url:
            # Update database
            payment_issues_collection.update_one(
                {'_id': ObjectId(issue_id)},
                {'$set': {
                    'screenshot_url': screenshot_url,
                    'screenshot_public_id': public_id,
                    'screenshot_info': info,
                    'migrated_to_cloudinary': True,
                    'migrated_at': datetime.now()
                },
                '$unset': {'screenshot': ''}}
            )
            
            return jsonify({
                'success': True,
                'url': screenshot_url,
                'message': 'Screenshot migrated to Cloudinary'
            })
        else:
            return jsonify({'success': False, 'error': 'Migration failed'}), 500
        
    except Exception as e:
        print(f"❌ Error migrating screenshot: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/debug-models')
def debug_models():
    """List all available models and test them"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Get all models
        all_models = list(client.models.list())
        
        # Test each model with a simple prompt
        test_results = {}
        test_prompt = "Say 'OK' if you can read this."
        
        for model_info in all_models[:5]:  # Test first 5 models
            model_name = model_info.name
            try:
                # Try without 'models/' prefix first
                clean_name = model_name.replace('models/', '')
                
                response = client.models.generate_content(
                    model=clean_name,
                    contents=test_prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=10,
                        temperature=0.1
                    )
                )
                
                test_results[model_name] = {
                    'clean_name': clean_name,
                    'success': bool(response and response.text),
                    'response': response.text if response and response.text else None
                }
            except Exception as e:
                test_results[model_name] = {
                    'clean_name': clean_name,
                    'success': False,
                    'error': str(e)
                }
        
        return jsonify({
            'api_key_configured': True,
            'total_models': len(all_models),
            'model_names': [m.name for m in all_models[:20]],  # First 20 models
            'test_results': test_results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# --- Constants ---
# --- Constants ---
SUBJECTS = {
    # Core Subjects (Group 1)
    'mathematics': 'MAT',
    'english': 'ENG', 
    'kiswahili': 'KIS',
    'kenya_sign_language': 'KSL',  # Kenya Sign Language
    
    # Sciences (Group 2)
    'biology': 'BIO',
    'physics': 'PHY',
    'chemistry': 'CHE',
    
    # Humanities (Group 3)
    'geography': 'GEO',
    'history': 'HAG',  # History & Government
    'cre': 'CRE',
    'ire': 'IRE',
    'hre': 'HRE',
    
    # Technical & Applied (Group 4 & 5)
    'general_science': 'GSC',  # General Science
    'home_science': 'HSC',  # Home Science
    'art_design': 'ARD',  # Art & Design
    'agriculture': 'AGR',
    'woodwork': 'WW',  # Woodwork
    'metalwork': 'MW',  # Metalwork
    'building_construction': 'BC',  # Building Construction
    'power_mechanics': 'PM',  # Power Mechanics
    'electricity': 'ECT',  # Electricity
    'drawing_design': 'DRD',  # Drawing & Design
    'aviation': 'AVT',  # Aviation
    'computer_studies': 'CMP',  # Computer Studies
    
    # Languages
    'french': 'FRE',
    'german': 'GER',
    'arabic': 'ARB',
    
    # Others
    'business_studies': 'BST',  # Business Studies
    'music': 'MUC',
}
GRADE_VALUES = {
    'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8, 'C+': 7, 'C': 6, 'C-': 5,
    'D+': 4, 'D': 3, 'D-': 2, 'E': 1
}
CLUSTER_NAMES = {
    'cluster_1': 'Law',
    'cluster_2': 'Business, Hospitality, Tourism And Related',
    'cluster_3': 'Communication, Media, Languages, Public Relations, International Relations, Film, Graphics And Related',
    'cluster_4': 'Geosciences And Related',
    'cluster_5': 'Engineering, Engineering Technology, Energy And Related',
    'cluster_6': 'Architecture, Quantity Survey, Building Construction, Urban Planning And Related',
    'cluster_7': 'Computer Science, Cyber Security, Information Technology And Related',
    'cluster_8': 'Agricultural Economics, Agribusiness And Related',
    'cluster_9': 'General Sciences, Biological Sciences, Physics, Chemistry And Related',
    'cluster_10': 'Acturial Science, Mathematics, Statistics And Related',
    'cluster_11': 'Interior Design, Fashion Design, Textile And Related',
    'cluster_12': 'Sports Science And Related',
    'cluster_13': 'Medicine, Nursing, Dentistry, Pharmacy, Health Sciences And Related',
    'cluster_14': 'History, Archeology, Geography And Related',
    'cluster_15': 'Agriculture, Animal Health, Food Science And Nutrition, Environmental Sciences, Natural Resources And Related',
    'cluster_16': 'Music And Related',
    'cluster_17': 'Education And Related',
    'cluster_18': 'Religious Studies, Theology, Islamic Studies And Related'
}
CLUSTERS = [f"cluster_{i}" for i in range(1, 19)]

DIPLOMA_COLLECTIONS = [
    "Agricultural_Sciences_Related", "Animal_Health_Related", "Applied_Sciences",
    "Building_Construction_Related", "Business_Related", "Clothing_Fashion_Textile",
    "Computing_IT_Related", "Education_Related", "Engineering_Technology_Related",
    "Environmental_Sciences", "Food_Science_Related", "Graphics_MediaStudies_Related",
    "Health_Sciences_Related", "HairDressing_Beauty_Therapy", "Hospitality_Hotel_Tourism_Related",
    "Library_Information_Science", "Natural_Sciences_Related", "Nutrition_Dietetics",
    "Social_Sciences", "Tax_Custom_Administration", "Technical_Courses"
]

KMTC_COLLECTIONS = ["kmtc_courses"]
TTC_COLLECTIONS = ["ttc"]

CERTIFICATE_COLLECTIONS = [
    "Agricultural_Sciences", "Applied_Sciences", "Building_Construction_Related",
    "Business_Related", "Clothing_Fashion_Textile", "Computing_IT_Related",
    "Engineering_Technology_Related", "Environmental_Sciences", "Food_Science_Related",
    "Graphics_MediaStudies_Related", "HairDressing_Beauty_Therapy", "Health_Sciences_Related",
    "Hospitality_Hotel_Tourism_Related", "Library_Information_Science",
    "Natural_Sciences_Related", "Nutrition_Dietetics", "Social_Sciences", "Tax_Custom_Administration"
]

ARTISAN_COLLECTIONS = [
    "Business_Related",
    "Building_Construction_Related",
    "Engineering_Technology_Related",
    "Food_Science_Related",
    "Social_Sciences",
    "Applied_Sciences",
    "IT_Related",
    "Hospitality_Hotel_Tourism_Related",
    "Clothing_Fashion_Textile",
    "Agricultural_Sciences_Related",
    "Technical_Courses",
    "Hair_Dressing_Beauty_Therapy"
]


# --- Database Connections ---
MONGODB_URI = os.getenv('MONGODB_URI')

# Initialize database variables
db = None
db_user_data = None
db_diploma = None
db_kmtc = None
db_Teachers = None 
db_certificate = None
db_artisan = None
user_payments_collection = None
user_courses_collection = None
user_baskets_collection = None
admin_activations_collection = None
database_connected = False
client = None
payment_issues_collection = None

def initialize_database():
    """Initialize database connections with robust error handling and fixed index creation"""
    global db, db_user_data, db_diploma, db_kmtc, db_certificate, db_artisan, db_Teachers
    global user_payments_collection, user_courses_collection, user_baskets_collection, admin_activations_collection, payment_issues_collection
    global database_connected, client
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempting to connect to MongoDB (attempt {attempt + 1}/{max_retries})...")
            
            client = MongoClient(
                MONGODB_URI,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=60000,
                socketTimeoutMS=60000,
                retryWrites=True,
                retryReads=True,
                maxPoolSize=50
            )
            
            # Test the connection
            client.admin.command('ping')
            print("✅ Successfully connected to MongoDB")
            
            # Initialize databases
            db = client['Degree']
            db_user_data = client['user_data']
            db_diploma = client['diploma']
            db_kmtc = client['kmtc']
            db_certificate = client['certificate']
            db_artisan = client['artisan']
            db_Teachers = client['Teachers']
            
            # Initialize collections
            collections_initialized = True
            
            # Define partial filter for indexes
            partial_filter = {
                'email': {'$type': 'string'},
                'index_number': {'$type': 'string'},
                'level': {'$type': 'string'}
            }
            
            # ===== USER COURSES COLLECTION =====
            try:
                user_courses_collection = db_user_data['user_courses']
                print("✅ User courses collection initialized")
                
                # Create indexes for user_courses
                existing_indexes = list(user_courses_collection.list_indexes())
                desired_key = {'email': 1, 'index_number': 1, 'level': 1}
                
                # Drop any conflicting indexes
                for index in existing_indexes:
                    index_name = index.get('name', '')
                    index_keys = index.get('key', {})
                    index_unique = index.get('unique', False)
                    index_partial = index.get('partialFilterExpression', None)
                    
                    if index_keys == desired_key:
                        needs_drop = False
                        if index_name != 'unique_courses_email_index_level':
                            needs_drop = True
                        elif not index_unique or index_partial != partial_filter:
                            needs_drop = True
                        
                        if needs_drop:
                            try:
                                print(f"🔄 Dropping existing courses index '{index_name}' due to conflict")
                                user_courses_collection.drop_index(index_name)
                                print(f"✅ Dropped courses index '{index_name}'")
                            except Exception as drop_err:
                                print(f"⚠️ Could not drop courses index '{index_name}': {drop_err}")
                
                # Create unique partial index
                try:
                    user_courses_collection.create_index(
                        [("email", 1), ("index_number", 1), ("level", 1)],
                        name='unique_courses_email_index_level',
                        unique=True,
                        partialFilterExpression=partial_filter
                    )
                    print("✅ Unique partial user_courses index created")
                except Exception as create_err:
                    print(f"❌ Error creating unique index: {create_err}")
                    # Fallback to non-unique index
                    try:
                        user_courses_collection.create_index(
                            [("email", 1), ("index_number", 1), ("level", 1)],
                            name='non_unique_courses_email_index_level',
                            unique=False
                        )
                        print("✅ Created non-unique courses index as fallback")
                    except Exception as fallback_error:
                        print(f"⚠️ Fallback index creation failed: {fallback_error}")
                        
            except Exception as e:
                print(f"❌ Error initializing user_courses collection: {str(e)}")
                user_courses_collection = None
                collections_initialized = False
            
            # ===== USER PAYMENTS COLLECTION =====
            try:
                user_payments_collection = db_user_data['user_payments']
                print("✅ User payments collection initialized")
                
                # Create indexes for user_payments
                existing_indexes = list(user_payments_collection.list_indexes())
                desired_key = {'email': 1, 'index_number': 1, 'level': 1}
                
                # Drop any conflicting indexes
                for index in existing_indexes:
                    index_name = index.get('name', '')
                    index_keys = index.get('key', {})
                    index_unique = index.get('unique', False)
                    index_partial = index.get('partialFilterExpression', None)
                    
                    if index_keys == desired_key:
                        needs_drop = False
                        if index_name != 'unique_email_index_level':
                            needs_drop = True
                        elif not index_unique or index_partial != partial_filter:
                            needs_drop = True
                        
                        if needs_drop:
                            try:
                                print(f"🔄 Dropping existing payments index '{index_name}' due to conflict")
                                user_payments_collection.drop_index(index_name)
                                print(f"✅ Dropped payments index '{index_name}'")
                            except Exception as drop_err:
                                print(f"⚠️ Could not drop payments index '{index_name}': {drop_err}")
                
                # Create unique partial index
                try:
                    user_payments_collection.create_index(
                        [("email", 1), ("index_number", 1), ("level", 1)],
                        name='unique_email_index_level',
                        unique=True,
                        partialFilterExpression=partial_filter
                    )
                    print("✅ Unique partial user_payments index created")
                except Exception as create_err:
                    print(f"❌ Error creating unique index: {create_err}")
                    try:
                        user_payments_collection.create_index(
                            [("email", 1), ("index_number", 1), ("level", 1)],
                            name='non_unique_email_index_level',
                            unique=False
                        )
                        print("✅ Created non-unique payments index as fallback")
                    except Exception as fallback_error:
                        print(f"⚠️ Fallback index creation failed: {fallback_error}")
                
                # Create transaction_ref index
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'transaction_ref': 1}]
                    if existing and existing[0].get('name') != 'transaction_ref_index':
                        try:
                            user_payments_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_payments_collection.create_index([("transaction_ref", 1)], name='transaction_ref_index')
                    print("✅ Transaction_ref index created")
                except Exception as ie:
                    print(f"❌ Failed to create transaction_ref index: {str(ie)}")
                
                # Create payment_confirmed index
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'payment_confirmed': 1}]
                    if existing and existing[0].get('name') != 'payment_confirmed_index':
                        try:
                            user_payments_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_payments_collection.create_index([("payment_confirmed", 1)], name='payment_confirmed_index')
                    print("✅ Payment_confirmed index created")
                except Exception as ie:
                    print(f"❌ Failed to create payment_confirmed index: {str(ie)}")
                    
            except Exception as e:
                print(f"❌ Error initializing user_payments collection: {str(e)}")
                user_payments_collection = None
                collections_initialized = False
            
            # ===== USER BASKETS COLLECTION =====
            try:
                user_baskets_collection = db_user_data['user_baskets']
                print("✅ User baskets collection initialized")
                
                existing_indexes = list(user_baskets_collection.list_indexes())
                
                # Index for index_number
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'index_number': 1}]
                    if existing and existing[0].get('name') != 'basket_index_number':
                        try:
                            user_baskets_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_baskets_collection.create_index([("index_number", 1)], name='basket_index_number')
                    print("✅ Basket index_number index created")
                except Exception as e:
                    print(f"❌ Failed to create basket index_number index: {str(e)}")
                
                # Index for email
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'email': 1}]
                    if existing and existing[0].get('name') != 'basket_email':
                        try:
                            user_baskets_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_baskets_collection.create_index([("email", 1)], name='basket_email')
                    print("✅ Basket email index created")
                except Exception as e:
                    print(f"❌ Failed to create basket email index: {str(e)}")
                
                # Index for created_at
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'created_at': 1}]
                    if existing and existing[0].get('name') != 'basket_created_at':
                        try:
                            user_baskets_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_baskets_collection.create_index([("created_at", 1)], name='basket_created_at')
                    print("✅ Basket created_at index created")
                except Exception as e:
                    print(f"❌ Failed to create basket created_at index: {str(e)}")
                    
            except Exception as e:
                print(f"❌ Error initializing user_baskets collection: {str(e)}")
                user_baskets_collection = None
                collections_initialized = False
            
            # ===== ADMIN ACTIVATIONS COLLECTION =====
            try:
                admin_activations_collection = db_user_data['admin_activations']
                print("✅ Admin activations collection initialized")
                
                existing_indexes = list(admin_activations_collection.list_indexes())
                
                # Index for index_number
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'index_number': 1}]
                    if existing and existing[0].get('name') != 'activation_index_number':
                        try:
                            admin_activations_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    admin_activations_collection.create_index([("index_number", 1)], name='activation_index_number')
                    print("✅ Activation index_number index created")
                except Exception as e:
                    print(f"❌ Failed to create activation index_number index: {str(e)}")
                
                # Index for mpesa_receipt
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'mpesa_receipt': 1}]
                    if existing and existing[0].get('name') != 'activation_mpesa_receipt':
                        try:
                            admin_activations_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    admin_activations_collection.create_index([("mpesa_receipt", 1)], name='activation_mpesa_receipt')
                    print("✅ Activation mpesa_receipt index created")
                except Exception as e:
                    print(f"❌ Failed to create activation mpesa_receipt index: {str(e)}")
                
                # Index for is_active
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'is_active': 1}]
                    if existing and existing[0].get('name') != 'activation_is_active':
                        try:
                            admin_activations_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    admin_activations_collection.create_index([("is_active", 1)], name='activation_is_active')
                    print("✅ Activation is_active index created")
                except Exception as e:
                    print(f"❌ Failed to create activation is_active index: {str(e)}")
                    
            except Exception as e:
                print(f"❌ Error initializing admin_activations collection: {str(e)}")
                admin_activations_collection = None
                collections_initialized = False
            
            # ===== PAYMENT ISSUES COLLECTION =====
            try:
                payment_issues_collection = db_user_data['payment_issues']
                print("✅ Payment issues collection initialized")
                
                existing_indexes = list(payment_issues_collection.list_indexes())
                
                # Index for status
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'status': 1}]
                    if not existing:
                        payment_issues_collection.create_index([("status", 1)], name='status_index')
                        print("✅ Payment issues status index created")
                except Exception as e:
                    print(f"❌ Failed to create status index: {str(e)}")
                
                # Index for index_number
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'index_number': 1}]
                    if not existing:
                        payment_issues_collection.create_index([("index_number", 1)], name='index_number_index')
                        print("✅ Payment issues index_number index created")
                except Exception as e:
                    print(f"❌ Failed to create index_number index: {str(e)}")
                
                # Index for created_at (descending for recent first)
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'created_at': -1}]
                    if not existing:
                        payment_issues_collection.create_index([("created_at", -1)], name='created_at_index')
                        print("✅ Payment issues created_at index created")
                except Exception as e:
                    print(f"❌ Failed to create created_at index: {str(e)}")
                
                # Index for email
                try:
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'email': 1}]
                    if not existing:
                        payment_issues_collection.create_index([("email", 1)], name='email_index')
                        print("✅ Payment issues email index created")
                except Exception as e:
                    print(f"❌ Failed to create email index: {str(e)}")
                    
            except Exception as e:
                print(f"❌ Error initializing payment_issues collection: {str(e)}")
                payment_issues_collection = None
                collections_initialized = False
            
            database_connected = collections_initialized
            
            if collections_initialized:
                print("🎉 All database collections initialized successfully!")
            else:
                print("⚠️ Some collections failed to initialize, running in partial mode")
            
            return collections_initialized
            
        except Exception as e:
            print(f"❌ Database connection error (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
                continue
            else:
                database_connected = False
                print("❌ Failed to connect to MongoDB after multiple attempts")
                return False

# Initialize database
database_connected = initialize_database()       

_collection_name_cache = {}
 
def get_available_collections(db_instance, db_key):
    """Get and cache available collection names for a database"""
    if db_key not in _collection_name_cache:
        try:
            _collection_name_cache[db_key] = set(db_instance.list_collection_names())
        except Exception:
            _collection_name_cache[db_key] = set()
    return _collection_name_cache[db_key]
 
    return course
def refresh_collection_cache():
    """Call this if you add new collections at runtime"""
    _collection_name_cache.clear()

def create_missing_courses_indexes():
    """Create indexes for faster missing courses queries"""
    if not database_connected:
        return
    
    try:
        # Index for payments collection
        if user_payments_collection is not None:
            # Compound index for faster lookups
            user_payments_collection.create_index([
                ('mpesa_receipt', 1),
                ('email', 1),
                ('index_number', 1),
                ('level', 1)
            ], name='idx_missing_courses_search')
            
            # Index for created_at sorting
            user_payments_collection.create_index([('created_at', -1)], name='idx_payments_created_at')
            
            print("✅ Created indexes for payments collection")
        
        # Index for user_courses collection
        if user_courses_collection is not None:
            user_courses_collection.create_index([
                ('email', 1),
                ('index_number', 1),
                ('level', 1)
            ], name='idx_user_courses_lookup')
            
            print("✅ Created indexes for user_courses collection")
            
    except Exception as e:
        print(f"⚠️ Index creation error: {e}")

course_processing_lock = threading.Lock()
course_processing_cache = {}  
register_guides(app) 

course_processing_queue = Queue()
course_processing_status = {}
def background_course_processor():
    """
    Fast background processor.
    - Marks status 'completed' RIGHT AFTER generation (no DB save of courses)
    - Sends email in a separate daemon thread
    - Deduplicates jobs using the status map
    """
    print("✅ Background course processor started (no-DB-save version)")
    while True:
        try:
            job = course_processing_queue.get(block=True)
 
            if job is None:
                course_processing_queue.task_done()
                continue
 
            email        = job.get('email')
            index_number = job.get('index_number')
            flow         = job.get('flow')
            mpesa_receipt = job.get('mpesa_receipt')
 
            if not email or not index_number or not flow:
                print(f"⚠️ Invalid job: missing required fields")
                course_processing_queue.task_done()
                continue
 
            cache_key = f"{email}_{index_number}_{flow}"
 
            # Skip if already completed
            existing = course_processing_status.get(cache_key, {})
            if isinstance(existing, dict) and existing.get('status') == 'completed':
                print(f"✅ Already completed for {flow}: {email}")
                course_processing_queue.task_done()
                continue
 
            # Mark as processing
            course_processing_status[cache_key] = {
                'status': 'processing',
                'started_at': datetime.now()
            }
 
            print(f"🔄 Processing {flow} for {email}")
            start_time = time.time()
 
            # ── Get grades from DB ──
            user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(
                email, index_number, flow
            )
 
            # Fallback to job payload grades
            if not user_grades:
                user_grades         = job.get('user_grades', {})
                user_mean_grade     = job.get('user_mean_grade')
                user_cluster_points = job.get('user_cluster_points', {})
 
            if not user_grades:
                print(f"❌ No grades found for {flow}: {email}")
                course_processing_status[cache_key] = {
                    'status': 'failed',
                    'error': 'No grades found',
                    'failed_at': datetime.now()
                }
                course_processing_queue.task_done()
                continue
 
            # ── Generate courses ──
            qualifying_courses = []
            try:
                qualifying_courses = _generate_courses_for_flow(
                    flow, user_grades, user_mean_grade, user_cluster_points
                )
            except Exception as gen_err:
                print(f"❌ Course generation error for {flow}: {gen_err}")
                import traceback
                traceback.print_exc()
 
            elapsed = time.time() - start_time
            print(f"✅ {flow} generated {len(qualifying_courses)} courses in {elapsed:.2f}s — NOT saving to DB")
 
            # ── Store courses ONLY in memory status map for retrieval ──
            # (no DB write — show_results will regenerate on demand)
            course_processing_status[cache_key] = {
                'status': 'completed',
                'courses': qualifying_courses,          # kept in memory for the session
                'courses_count': len(qualifying_courses),
                'completed_at': datetime.now(),
                'elapsed_seconds': elapsed
            }
 
            # ── Send email in background (non-blocking) ──
            if email and mpesa_receipt:
                threading.Thread(
                    target=send_results_email_background,
                    args=(email, index_number, flow, qualifying_courses, mpesa_receipt),
                    daemon=True
                ).start()
 
            course_processing_queue.task_done()
 
        except Exception as e:
            print(f"❌ Background processor error: {e}")
            import traceback
            traceback.print_exc()
# Start background processor thread
background_thread = threading.Thread(target=background_course_processor, daemon=True)
background_thread.start()
print("✅ Background course processor started")
def _stringify_course_codes(course: dict) -> dict:
    """Cast programme_code / course_code to str in-place, return course."""
    for field in ('programme_code', 'course_code'):
        if field in course and course[field] is not None:
            course[field] = str(course[field])
def _generate_courses_for_flow(flow, user_grades, user_mean_grade, user_cluster_points):
    """Run the correct qualification function for a given flow."""
    if flow == 'degree':
        return get_qualifying_courses(user_grades, user_cluster_points or {})
    elif flow == 'diploma':
        return get_qualifying_diploma_courses(user_grades, user_mean_grade)
    elif flow == 'certificate':
        return get_qualifying_certificate_courses(user_grades, user_mean_grade)
    elif flow == 'artisan':
        return get_qualifying_artisan_courses(user_grades, user_mean_grade)
    elif flow == 'kmtc':
        return get_qualifying_kmtc_courses(user_grades, user_mean_grade)
    elif flow == 'ttc':
        return get_qualifying_ttc(user_grades, user_mean_grade)
    return []
 
def process_courses_after_payment(email, index_number, flow, mpesa_receipt=None):
    """
    Queue course processing after payment confirmation.
    Guards against duplicate queuing using in-memory status map.
    """
    cache_key = f"{email}_{index_number}_{flow}"
 
    # Skip if already in any active state
    existing = course_processing_status.get(cache_key, {})
    if isinstance(existing, dict):
        status = existing.get('status')
        if status in ('pending', 'processing', 'completed'):
            print(f"✅ {flow} courses already {status} for {email}")
            return
 
    # Mark as pending immediately to prevent duplicate queuing
    course_processing_status[cache_key] = {
        'status': 'pending',
        'queued_at': datetime.now()
    }
 
    course_processing_queue.put({
        'email': email,
        'index_number': index_number,
        'flow': flow,
        'mpesa_receipt': mpesa_receipt
    })
    print(f"✅ {flow} queued for {email}")
 
# ============================================
# USER VALIDATION & DUPLICATE PREVENTION
# ============================================
from concurrent.futures import ThreadPoolExecutor, as_completed
 
COURSE_PROJECTION = {
    "_id": 1,
    "programme_name": 1,
    "course_name": 1,
    "programme_code": 1,
    "course_code": 1,
    "institution_name": 1,
    "minimum_grade": 1,
    "minimum_subject_requirements": 1,
    "cut_off_points": 1,
    "cluster": 1,
    "duration": 1,
}
def _handle_manual_activation(activation_record, email, index_number, flow, original_mpesa_receipt):
    """
    Handle manual activation flow - bypass payment and go directly to course generation.
    Returns a Flask response object.
    """
    print(f"✅ Manual activation: processing {flow} for {email}")
    print(f"💰 Original receipt: {original_mpesa_receipt}")
 
    # ── Reset session to minimal safe state ──
    session.clear()
    session['email'] = email
    session['index_number'] = index_number
    session['current_flow'] = flow
    session['current_level'] = flow
    session[f'paid_{flow}'] = True
    session['initialized'] = True
    session['last_activity'] = datetime.now().isoformat()
    session['_permanent'] = True
 
    # Store manual activation info
    session['manual_activation_active'] = True
    session['manual_activation_receipt'] = original_mpesa_receipt
    session['manual_activation_id'] = str(activation_record.get('_id'))
    session['mpesa_receipt'] = original_mpesa_receipt
    session['verified_receipt'] = original_mpesa_receipt
    session.modified = True
 
    # ── Create payment record with original receipt ──
    create_manual_activation_payment(email, index_number, flow, original_mpesa_receipt)
 
    # ── Mark activation as used ──
    if database_connected and admin_activations_collection is not None:
        try:
            admin_activations_collection.update_one(
                {'_id': activation_record['_id']},
                {'$set': {
                    'is_active': False,
                    'used_for_flow': flow,
                    'used_at': datetime.now(),
                    'status': 'used'
                }}
            )
            print(f"✅ Manual activation marked as used for {flow}")
        except Exception as e:
            print(f"⚠️ Could not mark activation used: {e}")
 
    # ── Queue course generation ──
    process_courses_after_payment(email, index_number, flow, original_mpesa_receipt)
 
    flash("✅ Access verified! Generating your courses…", "success")
    return redirect(url_for('payment_wait', flow=flow, transaction_ref='manual'))
 
def validate_user_uniqueness(email, index_number, flow):
    """Validate that email and index_number are uniquely paired"""
    if not database_connected:
        return True, "Database not available, proceeding with caution"
    
    try:
        # Check if email is already associated with a DIFFERENT index number
        email_exists = user_payments_collection.find_one({
            'email': email,
            'index_number': {'$ne': index_number}  # Different index number
        })
        
        if email_exists:
            existing_index = email_exists.get('index_number')
            return False, f"This email ({email}) is already registered with index number {existing_index}. Each email can only be used with ONE index number."
        
        # Check if index number is already associated with a DIFFERENT email
        index_exists = user_payments_collection.find_one({
            'index_number': index_number,
            'email': {'$ne': email}  # Different email
        })
        
        if index_exists:
            existing_email = index_exists.get('email')
            return False, f"This index number ({index_number}) is already registered with email {existing_email}. Each index number can only be used with ONE email."
        
        return True, "User validation passed"
        
    except Exception as e:
        print(f"❌ Error validating user uniqueness: {str(e)}")
        return True, "Validation error, proceeding with caution"

def has_user_paid_for_category_strict(email, index_number, category):
    """Strict check - user cannot view category unless they actually paid for it"""
    
    # Check payments in database (INCLUDE manual activations)
    if database_connected and user_payments_collection is not None:
        try:
            # 🔥 FIX: Remove the exclusion of manual activations
            real_payment = user_payments_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': category,
                'payment_confirmed': True
                # Removed: 'is_manual_activation': {'$ne': True}
            })
            
            if real_payment:
                print(f"✅ User {email} has payment (or manual activation) for {category}")
                return True
            else:
                print(f"⚠️ User {email} has NO payment for {category}")
                return False
                
        except Exception as e:
            print(f"❌ Error checking category payment: {str(e)}")
    
    # Check session as fallback
    if session.get(f'paid_{category}'):
        print(f"⚠️ Session shows paid for {category} but no DB record")
        return False
    
    return False

def get_user_paid_categories_strict(email, index_number):
    """Get all categories user has already paid for (including manual activations)"""
    paid_categories = []
    
    if not database_connected:
        for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
            if session.get(f'paid_{level}'):
                paid_categories.append(level)
        return paid_categories
    
    try:
        # 🔥 FIX: Include ALL payments (both normal and manual)
        payments = user_payments_collection.find({
            'email': email,
            'index_number': index_number,
            'payment_confirmed': True
            # Removed the manual activation exclusion
        })
        
        for payment in payments:
            level = payment.get('level')
            if level and level not in paid_categories:
                paid_categories.append(level)
                
    except Exception as e:
        print(f"❌ Error getting paid categories: {str(e)}")
    
    return paid_categories
def save_payment_issue(email, index_number, mpesa_receipt, screenshot_data=None):
    """Save payment issue - store screenshot in Cloudinary"""
    print(f"💾 Saving payment issue for {email}")
    
    # Upload screenshot to Cloudinary if provided
    screenshot_url = None
    screenshot_public_id = None
    screenshot_info = None
    
    if screenshot_data and CLOUDINARY_ENABLED:
        screenshot_url, screenshot_public_id, screenshot_info = upload_screenshot(
            screenshot_data, email, mpesa_receipt, index_number
        )
    
    # Create issue record (without base64 screenshot)
    issue_record = {
        'email': email,
        'index_number': index_number,
        'mpesa_receipt': mpesa_receipt,
        'screenshot_url': screenshot_url,
        'screenshot_public_id': screenshot_public_id,  # Store for deletion
        'screenshot_info': screenshot_info,  # Store metadata
        'status': 'pending',
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'processed_by': None,
        'processed_at': None,
        'notes': None,
        'has_screenshot': bool(screenshot_url),
        'storage_type': 'cloudinary' if screenshot_url else None
    }
    
    if database_connected and payment_issues_collection is not None:
        try:
            result = payment_issues_collection.insert_one(issue_record)
            print(f"✅ Payment issue saved with ID: {result.inserted_id}")
            if screenshot_url:
                print(f"   📸 Screenshot in Cloudinary: {screenshot_url}")
                print(f"   📊 Size: {screenshot_info.get('bytes', 0) if screenshot_info else 0} bytes")
            return result.inserted_id
        except Exception as e:
            print(f"❌ Error saving payment issue: {str(e)}")
            # Clean up Cloudinary upload if database save fails
            if screenshot_public_id:
                delete_screenshot(screenshot_public_id)
            return None
    else:
        # Session fallback
        session_key = f'payment_issue_{int(datetime.now().timestamp())}'
        # Don't store screenshot data in session
        issue_record['screenshot'] = None
        session[session_key] = issue_record
        print(f"✅ Payment issue saved to session: {session_key}")
        return session_key


def mark_activation_as_used(email, index_number, flow):
    """Mark manual activation as used so it can't be reused"""
    try:
        if database_connected and admin_activations_collection is not None:
            result = admin_activations_collection.update_one(
                {
                    '$or': [
                        {'email': email},
                        {'index_number': index_number}
                    ],
                    'is_active': True,
                    'status': 'active'
                },
                {
                    '$set': {
                        'is_active': False,
                        'used_for_flow': flow,
                        'used_at': datetime.now(),
                        'status': 'used'
                    }
                }
            )
            if result.modified_count > 0:
                print(f"✅ Manual activation marked as used for {email} - {flow}")
                return True
            else:
                print(f"⚠️ No active activation found to mark as used for {email}")
                return False
    except Exception as e:
        print(f"❌ Error marking activation as used: {str(e)}")
        return False
def check_courses_exist_for_payment(email, index_number, level):
    """Check if courses exist for a given payment"""
    if not database_connected or user_courses_collection is None:
        return False
    
    try:
        courses_data = user_courses_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        })
        return courses_data is not None and len(courses_data.get('courses', [])) > 0
    except Exception as e:
        print(f"❌ Error checking courses: {str(e)}")
        return False

def get_pending_payment_issues():
    """Get all pending payment issues for admin"""
    if not database_connected or payment_issues_collection is None:
        return []
    
    try:
        issues = list(payment_issues_collection.find({'status': 'pending'}).sort('created_at', -1))
        
        # Convert ObjectId to string for JSON
        for issue in issues:
            if '_id' in issue and isinstance(issue['_id'], ObjectId):
                issue['_id'] = str(issue['_id'])
        
        return issues
    except Exception as e:
        print(f"❌ Error getting pending payment issues: {str(e)}")
        return []
def approve_payment_issue(issue_id, admin_username):
    """Approve a payment issue and create manual activation"""
    if not database_connected or payment_issues_collection is None:
        return False
    
    try:
        # Get the issue
        issue = payment_issues_collection.find_one({'_id': issue_id, 'status': 'pending'})
        
        if not issue:
            print(f"❌ Payment issue not found: {issue_id}")
            return False
        
        # Update issue status
        result = payment_issues_collection.update_one(
            {'_id': issue_id},
            {'$set': {
                'status': 'approved',
                'processed_by': admin_username,
                'processed_at': datetime.now(),
                'updated_at': datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            print(f"✅ Payment issue approved: {issue_id}")
            
            # Create manual activation
            email = issue.get('email')
            index_number = issue.get('index_number')
            mpesa_receipt = issue.get('mpesa_receipt')
            
            if email and index_number and mpesa_receipt:
                activation_record = {
                    'email': email,
                    'index_number': index_number,
                    'mpesa_receipt': mpesa_receipt,
                    'activation_type': 'payment_issue_approval',
                    'activated_by': admin_username,
                    'activated_at': datetime.now(),
                    'is_active': True,
                    'status': 'active',
                    'used_for_flow': None,
                    'used_at': None,
                    'issue_id': str(issue_id),
                    'screenshot_url': issue.get('screenshot_url')  # Keep reference
                }
                
                if admin_activations_collection is not None:
                    admin_activations_collection.insert_one(activation_record)
                    print(f"✅ Manual activation created for {email}")
                
                return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error approving payment issue: {str(e)}")
        return False

def delete_payment_issue(issue_id, admin_username):
    """Delete a payment issue and remove screenshot from Cloudinary"""
    if not database_connected or payment_issues_collection is None:
        return False
    
    try:
        # Get the issue to get screenshot public_id
        issue = payment_issues_collection.find_one({'_id': issue_id})
        
        # Delete screenshot from Cloudinary if exists
        if issue and issue.get('screenshot_public_id') and CLOUDINARY_ENABLED:
            delete_screenshot(issue['screenshot_public_id'])
            print(f"🗑️ Deleted screenshot from Cloudinary: {issue['screenshot_public_id']}")
        
        # Update or delete database record
        result = payment_issues_collection.update_one(
            {'_id': issue_id},
            {'$set': {
                'status': 'deleted',
                'processed_by': admin_username,
                'processed_at': datetime.now(),
                'updated_at': datetime.now(),
                'notes': 'Payment issue deleted - screenshot removed from Cloudinary'
            }}
        )
        
        if result.modified_count > 0:
            print(f"✅ Payment issue deleted: {issue_id}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error deleting payment issue: {str(e)}")
        return False
def get_cached_payment_stats():
    """Get cached payment statistics"""
    cache_key = 'payment_stats'
    cached_stats = cache.get(cache_key)
    
    if cached_stats:
        return cached_stats
    
    stats = {
        'total': 0,
        'pending': 0,
        'approved': 0,
        'deleted': 0
    }
    
    if database_connected and payment_issues_collection is not None:
        try:
            # Use aggregation for faster stats
            pipeline = [
                {'$group': {
                    '_id': '$status',
                    'count': {'$sum': 1}
                }}
            ]
            
            results = list(payment_issues_collection.aggregate(pipeline))
            
            for result in results:
                status = result['_id']
                count = result['count']
                if status == 'pending':
                    stats['pending'] = count
                elif status == 'approved':
                    stats['approved'] = count
                elif status == 'deleted':
                    stats['deleted'] = count
            
            stats['total'] = stats['pending'] + stats['approved'] + stats['deleted']
            
        except Exception as e:
            print(f"❌ Error calculating stats: {str(e)}")
    
    # Cache for 5 minutes
    cache.set(cache_key, stats, timeout=300)
    
    return stats
def check_legitimate_payment_only(email, index_number, requested_level):
    """
    Verify user only has access to categories they actually paid for
    Returns: (is_allowed, list_of_paid_categories, error_message)
    """
    if not database_connected:
        return True, [], None
    
    try:
        # Get ALL real payments for this user (confirmed, not manual)
        real_payments = list(user_payments_collection.find({
            'index_number': index_number,
            'payment_confirmed': True,
            'is_manual_activation': {'$ne': True}  # Exclude manual activations
        }))
        
        paid_categories = [p.get('level') for p in real_payments if p.get('level')]
        
        # Check if requested level is actually paid for
        if requested_level in paid_categories:
            return True, paid_categories, None
        else:
            return False, paid_categories, f"You have only paid for: {', '.join(paid_categories).upper()}. To access {requested_level.upper()}, please pay KES 100."
            
    except Exception as e:
        print(f"❌ Error checking legitimate payment: {e}")
        return True, [], None  # Allow on error to avoid blocking legitimate users
def get_all_payment_issues(status=None):
    """Get all payment issues with optional status filter"""
    if not database_connected or payment_issues_collection is None:
        return []
    
    try:
        query = {}
        if status:
            query['status'] = status
        
        issues = list(payment_issues_collection.find(query).sort('created_at', -1))
        
        # Convert ObjectId to string
        for issue in issues:
            if '_id' in issue and isinstance(issue['_id'], ObjectId):
                issue['_id'] = str(issue['_id'])
        
        return issues
    except Exception as e:
        print(f"❌ Error getting payment issues: {str(e)}")
        return []
@app.route('/submit-payment-issue', methods=['POST'])
def submit_payment_issue():
    """Handle payment issue submission from users with automatic verification"""
    try:
        # Log the request size for debugging
        print(f"📦 Request content length: {request.content_length} bytes")
        
        email = request.form.get('email', '').strip().lower()
        index_number = request.form.get('index_number', '').strip()
        mpesa_receipt = request.form.get('mpesa_receipt', '').strip().upper()
        screenshot = request.form.get('screenshot', '')  # Base64 encoded screenshot
        
        # Validate inputs
        if not email or not index_number or not mpesa_receipt:
            return jsonify({
                'success': False,
                'error': 'Please fill in all required fields'
            })
        
        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({
                'success': False,
                'error': 'Please enter a valid email address'
            })
        
        # Validate index number format
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            return jsonify({
                'success': False,
                'error': 'Invalid index number format. Must be 11 digits, slash, 4 digits (e.g., 12345678901/2024)'
            })
        
        # Validate M-Pesa receipt format
        if len(mpesa_receipt) != 10 or not mpesa_receipt.isalnum():
            return jsonify({
                'success': False,
                'error': 'Invalid M-Pesa receipt format. Must be 10 alphanumeric characters (e.g., RJ89A5LBQ2)'
            })
        
        # ============================================
        # CHECK IF MPESA RECEIPT EXISTS IN DATABASE
        # ============================================
        payment_found = False
        paid_courses_levels = []
        paid_courses_data = {}
        
        if database_connected and user_payments_collection is not None:
            try:
                # Find all payments with this receipt (across all levels)
                payments = user_payments_collection.find({
                    'mpesa_receipt': mpesa_receipt,
                    'payment_confirmed': True
                })
                
                payments_list = list(payments)
                if payments_list:
                    payment_found = True
                    print(f"✅ Found {len(payments_list)} payment(s) with receipt {mpesa_receipt}")
                    
                    for payment in payments_list:
                        level = payment.get('level')
                        if level:
                            paid_courses_levels.append(level)
                            
                            # Check if courses exist for this level
                            if user_courses_collection is not None:
                                courses_data = user_courses_collection.find_one({
                                    'email': email,
                                    'index_number': index_number,
                                    'level': level
                                })
                                
                                if courses_data and courses_data.get('courses'):
                                    paid_courses_data[level] = {
                                        'courses': courses_data['courses'],
                                        'count': len(courses_data['courses'])
                                    }
                                    print(f"📚 Found {len(courses_data['courses'])} {level} courses")
                                else:
                                    print(f"⚠️ No courses found for {level} level")
                                    paid_courses_data[level] = {'courses': [], 'count': 0}
                else:
                    print(f"❌ No confirmed payment found with receipt {mpesa_receipt}")
                    
            except Exception as e:
                print(f"❌ Error checking payment in database: {str(e)}")
        
        # ============================================
        # IF PAYMENT FOUND AND COURSES EXIST
        # ============================================
        if payment_found and paid_courses_data:
            # Check if at least one level has courses
            has_courses = any(data['count'] > 0 for data in paid_courses_data.values())
            
            if has_courses:
                print(f"✅ Payment and courses verified for receipt {mpesa_receipt}")
                
                # Send email to user with instructions to access their courses
                email_sent = send_payment_issue_resolution_email(
                    email, index_number, mpesa_receipt, paid_courses_levels, paid_courses_data
                )
                
                # Delete any pending issues with this receipt (auto-resolve)
                if database_connected and payment_issues_collection is not None:
                    try:
                        result = payment_issues_collection.delete_many({
                            'mpesa_receipt': mpesa_receipt,
                            'status': 'pending'
                        })
                        if result.deleted_count > 0:
                            print(f"✅ Auto-resolved and deleted {result.deleted_count} pending issue(s) for receipt {mpesa_receipt}")
                    except Exception as e:
                        print(f"⚠️ Error deleting resolved issues: {e}")
                
                # Prepare course access instructions
                course_list_html = ""
                for level, data in paid_courses_data.items():
                    if data['count'] > 0:
                        course_list_html += f"""
                        <li><strong>{level.upper()}</strong>: {data['count']} courses found</li>
                        """
                
                return jsonify({
                    'success': True,
                    'auto_resolved': True,
                    'message': 'Your payment has been verified! Check your email for instructions to access your courses.',
                    'courses_found': True,
                    'levels': paid_courses_levels,
                    'email_sent': email_sent,
                    'redirect_url': url_for('verified_results_dashboard', index=index_number, receipt=mpesa_receipt)
                })
            else:
                # Payment found but no courses - need admin review
                print(f"⚠️ Payment found but no courses for receipt {mpesa_receipt}")
                issue_id = save_payment_issue(email, index_number, mpesa_receipt, screenshot)
                
                return jsonify({
                    'success': True,
                    'auto_resolved': False,
                    'message': 'Your payment was found but courses were not generated. Our team will review and activate your account within 6 hours.',
                    'issue_id': str(issue_id) if issue_id else None,
                    'wait_time': 6
                })
        
        # ============================================
        # NO PAYMENT FOUND - Save as pending issue
        # ============================================
        else:
            print(f"⚠️ No payment found with receipt {mpesa_receipt}, saving as pending issue")
            issue_id = save_payment_issue(email, index_number, mpesa_receipt, screenshot)
            
            if issue_id:
                return jsonify({
                    'success': True,
                    'auto_resolved': False,
                    'message': 'Your payment issue has been submitted successfully. Our team will review it within 6 hours.',
                    'wait_time': 6,
                    'issue_id': str(issue_id) if issue_id else None
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to submit payment issue. Please try again later.'
                })
        
    except Exception as e:
        print(f"❌ Error submitting payment issue: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'An error occurred. Please try again later.'
        })


def send_payment_issue_resolution_email(email, index_number, mpesa_receipt, paid_levels, courses_data):
    """Send email to user when payment issue is auto-resolved with instructions to access courses"""
    try:
        subject = "Your KUCCPS Payment Has Been Verified - Access Your Courses"
        
        # Build course list HTML
        courses_html = ""
        for level, data in courses_data.items():
            if data['count'] > 0:
                courses_html += f"""
                <div style="background: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>{level.upper()} Courses</strong> ({data['count']} courses found)
                </div>
                """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Payment Verified - Access Your Courses</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Payment Verified!</h1>
                <p style="color: white; margin: 5px 0 0;">Your courses are ready</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                <p>Dear Student,</p>
                
                <p>Great news! We have verified your M-Pesa payment and your courses are ready to view.</p>
                
                <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>✅ Your Payment Details:</strong></p>
                    <p style="margin: 5px 0;">📧 Email: <strong>{email}</strong></p>
                    <p style="margin: 5px 0;">📝 KCSE Index Number: <strong>{index_number}</strong></p>
                    <p style="margin: 5px 0;">💰 M-Pesa Receipt: <strong>{mpesa_receipt}</strong></p>
                    <p style="margin: 5px 0;">📚 Paid Categories: <strong>{', '.join(paid_levels).upper()}</strong></p>
                </div>
                
                <p><strong>To access your courses:</strong></p>
                <ol>
                    <li>Go to <a href="https://www.studentsplacement.co.ke">https://www.studentsplacement.co.ke</a></li>
                    <li>Click the <strong>"Already Made Payment"</strong> button on the homepage</li>
                    <li>Enter your M-Pesa receipt number: <strong>{mpesa_receipt}</strong></li>
                    <li>Enter your KCSE index number: <strong>{index_number}</strong></li>
                    <li>Your course results will be displayed instantly!</li>
                </ol>
                
                {courses_html}
                
                <div style="background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #0056b3;">
                        <strong>💡 Tip:</strong> You can also re-enter your grades for any of these categories and the system will recognize your payment.
                    </p>
                </div>
                
                <p>Need help? Contact our support team:</p>
                <ul>
                    <li>Email: kuccpscourses@gmail.com</li>
                    <li>Phone: +254750732841</li>
                </ul>
                
                <hr style="margin: 20px 0;">
                
                <p style="font-size: 12px; color: #666; text-align: center;">
                    © 2025 KUCCPS Courses Checker. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email via Brevo
        email_sent = send_brevo_email(email, "Student", subject, html_content)
        
        if email_sent:
            print(f"✅ Resolution email sent to {email}")
            return True
        else:
            print(f"⚠️ Failed to send resolution email to {email}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending resolution email: {str(e)}")
        return False
@app.route('/admin/payment-issues')
def admin_payment_issues():
    """Admin page to manage payment issues with pagination"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Initialize variables
    pending_issues = []
    total_pending = 0
    total_pages = 1
    stats = {'total': 0, 'pending': 0, 'approved': 0, 'deleted': 0}
    
    # Check if database is connected and collection exists
    if database_connected and payment_issues_collection is not None:
        try:
            # Get total count
            total_pending = payment_issues_collection.count_documents({'status': 'pending'})
            
            # Get paginated results
            cursor = payment_issues_collection.find(
                {'status': 'pending'}
            ).sort('created_at', -1).skip((page - 1) * per_page).limit(per_page)
            
            pending_issues = list(cursor)
            
            # Convert ObjectId to string for JSON
            for issue in pending_issues:
                if '_id' in issue and isinstance(issue['_id'], ObjectId):
                    issue['_id'] = str(issue['_id'])
            
            # Calculate statistics
            stats['total'] = payment_issues_collection.count_documents({})
            stats['pending'] = total_pending
            stats['approved'] = payment_issues_collection.count_documents({'status': 'approved'})
            stats['deleted'] = payment_issues_collection.count_documents({'status': 'deleted'})
            
        except Exception as e:
            print(f"❌ Error loading payment issues: {str(e)}")
            flash(f"Error loading payment issues: {str(e)}", "error")
            # Show sample data for debugging
            pending_issues = get_sample_payment_issues()
            stats = {'total': 1, 'pending': 1, 'approved': 0, 'deleted': 0}
            total_pending = 1
    else:
        # If database not connected, show sample data for testing
        print("⚠️ Database not connected or payment_issues_collection is None")
        flash("Database connection issue. Using sample data for testing. Please check your MongoDB connection.", "warning")
        
        # Sample data for testing when database is not available
        pending_issues = get_sample_payment_issues()
        stats = {'total': 1, 'pending': 1, 'approved': 0, 'deleted': 0}
        total_pending = 1
    
    # Calculate pagination
    if total_pending > 0:
        total_pages = (total_pending + per_page - 1) // per_page
    else:
        total_pages = 1
    
    return render_template('admin_payment_issues.html', 
                         issues=pending_issues,
                         stats=stats,
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_pending=total_pending)
def get_screenshot_thumbnail(issue):
    """Get thumbnail URL for screenshot (for admin panel)"""
    public_id = issue.get('screenshot_public_id')
    if not public_id or not CLOUDINARY_ENABLED:
        return None
    
    # Generate thumbnail transformation
    try:
        from cloudinary.utils import cloudinary_url
        url, _ = cloudinary_url(
            public_id,
            width=150,
            height=150,
            crop='thumb',
            gravity='auto',
            format='jpg',
            quality='auto'
        )
        return url
    except:
        return issue.get('screenshot_url')
def get_sample_payment_issues():
    """Return sample payment issues for testing when database is not connected"""
    return [
        {
            '_id': 'sample1',
            'email': 'test@example.com',
            'index_number': '12345678901/2024',
            'mpesa_receipt': 'SAMPLE12345',
            'screenshot': None,
            'created_at': datetime.now(),
            'status': 'pending'
        },
        {
            '_id': 'sample2',
            'email': 'student@example.com',
            'index_number': '98765432109/2024',
            'mpesa_receipt': 'SAMPLE67890',
            'screenshot': None,
            'created_at': datetime.now(),
            'status': 'pending'
        }
    ]
@app.route('/api/manual-activation-advanced', methods=['POST'])
def api_manual_activation_advanced():
    """Advanced manual activation API - deletes old payment and creates activation"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        index_number = data.get('index_number', '').strip()
        mpesa_receipt = data.get('mpesa_receipt', '').strip().upper()
        activation_type = data.get('activation_type', 'admin_manual')  # Default to admin_manual
        send_email = data.get('send_email', True)
        
        # Validation
        if not email or not index_number or not mpesa_receipt:
            return jsonify({'success': False, 'error': 'All fields are required'})
        
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            return jsonify({'success': False, 'error': 'Invalid index number format'})
        
        if len(mpesa_receipt) != 10 or not mpesa_receipt.isalnum():
            return jsonify({'success': False, 'error': 'Invalid M-Pesa receipt format'})
        
        print(f"🔧 Advanced manual activation: {email}, {index_number}, {mpesa_receipt}")
        
        payment_deleted = False
        courses_deleted = False
        
        # STEP 1: Delete ALL existing payment records for this user/level
        if database_connected and user_payments_collection is not None:
            try:
                result = user_payments_collection.delete_many({
                    '$or': [
                        {'email': email},
                        {'index_number': index_number}
                    ]
                })
                if result.deleted_count > 0:
                    payment_deleted = True
                    print(f"✅ Deleted {result.deleted_count} payment records for {index_number}")
            except Exception as e:
                print(f"⚠️ Error deleting payments: {e}")
        
        # STEP 2: Delete existing courses (to start fresh)
        if database_connected and user_courses_collection is not None:
            try:
                result = user_courses_collection.delete_many({
                    '$or': [
                        {'email': email},
                        {'index_number': index_number}
                    ]
                })
                if result.deleted_count > 0:
                    courses_deleted = True
                    print(f"✅ Deleted {result.deleted_count} course records for {index_number}")
            except Exception as e:
                print(f"⚠️ Error deleting courses: {e}")
        
        # STEP 3: Create new activation record with CORRECT activation_type
        activation_saved = False
        activation_id = None
        
        if database_connected and admin_activations_collection is not None:
            try:
                # Deactivate any existing activations
                admin_activations_collection.update_many(
                    {'index_number': index_number},
                    {'$set': {'is_active': False, 'status': 'superseded'}}
                )
                
                # Create new activation with 'admin_manual' type
                activation_record = {
                    'email': email,
                    'index_number': index_number,
                    'mpesa_receipt': mpesa_receipt,
                    'original_receipt': mpesa_receipt,
                    'activation_type': 'admin_manual',  # 🔥 CRITICAL: Changed from 'manual' to 'admin_manual'
                    'activated_by': session.get('admin_username', 'admin'),
                    'activated_at': datetime.now(),
                    'is_active': True,
                    'status': 'active',
                    'used_for_flow': None,
                    'used_at': None,
                    'payment_deleted': payment_deleted,
                    'courses_deleted': courses_deleted,
                    'email_sent': False,
                    'is_legitimate_manual': True  # 🔥 CRITICAL: Mark as legitimate
                }
                
                result = admin_activations_collection.insert_one(activation_record)
                if result.inserted_id:
                    activation_saved = True
                    activation_id = result.inserted_id
                    print(f"✅ Manual activation created with receipt: {mpesa_receipt} (type: admin_manual, legitimate: True)")
                    
                    # Verify the record was saved correctly
                    saved_record = admin_activations_collection.find_one({'_id': result.inserted_id})
                    if saved_record:
                        print(f"   Verified - activation_type: {saved_record.get('activation_type')}")
                        print(f"   Verified - is_legitimate_manual: {saved_record.get('is_legitimate_manual')}")
                else:
                    print(f"❌ Failed to create activation record")
                    
            except Exception as e:
                print(f"❌ Error creating activation: {e}")
                return jsonify({'success': False, 'error': f'Failed to create activation: {str(e)}'})
        
        # STEP 4: Create payment record for the user (so they don't need to pay)
        payment_created = False
        if activation_saved:
            try:
                # Create a payment record for the user
                payment_record = {
                    'email': email,
                    'index_number': index_number,
                    'level': None,  # Will be set when user chooses category
                    'mpesa_receipt': mpesa_receipt,
                    'transaction_ref': f"MANUAL_{mpesa_receipt}",
                    'payment_amount': 0,  # No charge for manual activation
                    'payment_confirmed': True,  # 🔥 CRITICAL: Set to True
                    'payment_method': 'manual_activation',
                    'activated_by': session.get('admin_username', 'admin'),
                    'created_at': datetime.now(),
                    'payment_date': datetime.now(),
                    'is_manual_activation': True,
                    'original_receipt': mpesa_receipt
                }
                
                # Check if payment record already exists
                existing_payment = user_payments_collection.find_one({
                    'email': email,
                    'index_number': index_number
                })
                
                if existing_payment:
                    # Update existing payment record
                    result = user_payments_collection.update_one(
                        {'_id': existing_payment['_id']},
                        {'$set': payment_record}
                    )
                    if result.modified_count > 0:
                        payment_created = True
                        print(f"✅ Updated existing payment record for {email}")
                else:
                    # Create new payment record
                    result = user_payments_collection.insert_one(payment_record)
                    if result.inserted_id:
                        payment_created = True
                        print(f"✅ Created new payment record for {email}")
                        
            except Exception as e:
                print(f"⚠️ Error creating payment record: {e}")
        
        # STEP 5: Send email if requested
        email_sent = False
        if activation_saved and send_email:
            try:
                subject = "Your KUCCPS Account Has Been Activated"
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Account Activated</title>
                </head>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #27ae60;">Account Activated!</h2>
                        <p>Dear Student,</p>
                        <p>Your account has been <strong>manually activated</strong>. You can now access your courses.</p>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                            <p><strong>Your Details:</strong></p>
                            <p>📧 Email: {email}</p>
                            <p>📝 Index: {index_number}</p>
                            <p>💰 Receipt: <strong>{mpesa_receipt}</strong></p>
                        </div>
                        <p><strong>To access your courses:</strong></p>
                        <ol>
                            <li>Go to <a href="https://www.studentsplacement.co.ke">www.kuccpscourses.co.ke</a></li>
                            <li>Select your course category (Degree, Diploma, KMTC, etc.)</li>
                            <li>Enter your KCSE grades</li>
                            <li>Enter your email: <strong>{email}</strong></li>
                            <li>Enter your KCSE Index Number: <strong>{index_number}</strong></li>
                            <li>The system will detect your manual activation and generate your courses instantly!</li>
                        </ol>
                        <p>You will NOT be charged again.</p>
                        <hr>
                        <p style="font-size: 12px; color: #666;">KUCCPS Courses Checker Support</p>
                    </div>
                </body>
                </html>
                """
                
                email_sent = send_brevo_email(email, "Student", subject, html_content)
                if email_sent:
                    admin_activations_collection.update_one(
                        {'_id': activation_id},
                        {'$set': {'email_sent': True, 'email_sent_at': datetime.now()}}
                    )
                    print(f"✅ Email sent to {email}")
                else:
                    print(f"⚠️ Email failed to send to {email}")
                    
            except Exception as e:
                print(f"⚠️ Email error: {e}")
        
        return jsonify({
            'success': True,
            'email': email,
            'index_number': index_number,
            'mpesa_receipt': mpesa_receipt,
            'activation_type': 'admin_manual',
            'is_legitimate_manual': True,
            'payment_deleted': payment_deleted,
            'courses_deleted': courses_deleted,
            'payment_created': payment_created,
            'email_sent': email_sent,
            'message': f'User {email} activated successfully with admin_manual type'
        })
        
    except Exception as e:
        print(f"❌ Error in advanced manual activation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
@app.route('/admin/view-screenshot/<issue_id>')
def admin_view_screenshot(issue_id):
    """View screenshot in admin panel"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        from bson import ObjectId
        
        issue = payment_issues_collection.find_one({'_id': ObjectId(issue_id)})
        
        if not issue:
            flash("Issue not found", "error")
            return redirect(url_for('admin_payment_issues'))
        
        screenshot_url = issue.get('screenshot_url')
        
        if not screenshot_url:
            flash("No screenshot available for this issue", "warning")
            return redirect(url_for('admin_payment_issues'))
        
        return render_template('admin_view_screenshot.html', 
                             issue=issue, 
                             screenshot_url=screenshot_url)
    
    except Exception as e:
        print(f"❌ Error viewing screenshot: {str(e)}")
        flash("Error loading screenshot", "error")
        return redirect(url_for('admin_payment_issues'))

@app.route('/api/deactivate-activation', methods=['POST'])
def api_deactivate_activation():
    """Deactivate a manual activation"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        index_number = data.get('index_number')
        
        if not index_number:
            return jsonify({'success': False, 'error': 'Index number required'})
        
        if database_connected and admin_activations_collection is not None:
            result = admin_activations_collection.update_many(
                {'index_number': index_number, 'is_active': True},
                {'$set': {'is_active': False, 'status': 'deactivated', 'deactivated_at': datetime.now()}}
            )
            
            if result.modified_count > 0:
                return jsonify({'success': True, 'message': f'Deactivated {result.modified_count} activation(s)'})
        
        return jsonify({'success': False, 'error': 'No active activation found'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
@app.route('/admin/check-resolve-issue/<issue_id>', methods=['POST'])
def check_and_resolve_issue(issue_id):
    """Check a single issue and resolve if payment and courses exist"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        if not database_connected or payment_issues_collection is None:
            return jsonify({'success': False, 'error': 'Database not connected'})
        
        # Convert string ID to ObjectId
        try:
            from bson import ObjectId
            obj_id = ObjectId(issue_id)
        except:
            return jsonify({'success': False, 'error': 'Invalid issue ID format'})
        
        issue = payment_issues_collection.find_one({'_id': obj_id, 'status': 'pending'})
        
        if not issue:
            return jsonify({'success': False, 'error': 'Issue not found or already processed'})
        
        email = issue.get('email')
        index_number = issue.get('index_number')
        mpesa_receipt = issue.get('mpesa_receipt')
        
        # Check if payment exists
        payment_found = False
        paid_levels = []
        courses_exist = False
        
        if user_payments_collection is not None:
            payments = list(user_payments_collection.find({
                'mpesa_receipt': mpesa_receipt,
                'payment_confirmed': True
            }))
            
            if payments:
                payment_found = True
                for payment in payments:
                    level = payment.get('level')
                    if level:
                        paid_levels.append(level)
                        
                        if user_courses_collection is not None:
                            courses_data = user_courses_collection.find_one({
                                'email': email,
                                'index_number': index_number,
                                'level': level
                            })
                            if courses_data and courses_data.get('courses'):
                                courses_exist = True
        
        if payment_found and courses_exist:
            # Resolve the issue
            payment_issues_collection.update_one(
                {'_id': obj_id},
                {'$set': {
                    'status': 'resolved',
                    'resolved_at': datetime.now(),
                    'resolved_by': session.get('admin_username', 'admin'),
                    'resolution_type': 'manual_check',
                    'notes': 'Manually verified - payment and courses exist'
                }}
            )
            
            # Send email
            email_sent = send_issue_resolution_email(email, index_number, mpesa_receipt, paid_levels)
            
            return jsonify({
                'success': True,
                'message': f'Issue resolved! User notified: {email_sent}',
                'payment_found': True,
                'courses_exist': True,
                'email_sent': email_sent
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Cannot resolve - Payment found: {payment_found}, Courses exist: {courses_exist}',
                'payment_found': payment_found,
                'courses_exist': courses_exist
            })
            
    except Exception as e:
        print(f"❌ Error checking issue: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})




@app.route('/admin/batch-resolve-issues', methods=['POST'])
def batch_resolve_existing_issues():
    """Batch process all existing pending payment issues"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        if not database_connected or payment_issues_collection is None:
            return jsonify({'success': False, 'error': 'Database not connected'})
        
        # Get all pending issues
        pending_issues = list(payment_issues_collection.find({'status': 'pending'}))
        
        processed_count = 0
        resolved_count = 0
        pending_count = 0
        emails_sent = 0
        
        for issue in pending_issues:
            processed_count += 1
            email = issue.get('email')
            index_number = issue.get('index_number')
            mpesa_receipt = issue.get('mpesa_receipt')
            
            if not email or not index_number or not mpesa_receipt:
                pending_count += 1
                continue
            
            # Check if payment exists in database
            payment_found = False
            paid_levels = []
            courses_exist = False
            
            if user_payments_collection is not None:
                payments = list(user_payments_collection.find({
                    'mpesa_receipt': mpesa_receipt,
                    'payment_confirmed': True
                }))
                
                if payments:
                    payment_found = True
                    for payment in payments:
                        level = payment.get('level')
                        if level:
                            paid_levels.append(level)
                            
                            # Check if courses exist
                            if user_courses_collection is not None:
                                courses_data = user_courses_collection.find_one({
                                    'email': email,
                                    'index_number': index_number,
                                    'level': level
                                })
                                if courses_data and courses_data.get('courses'):
                                    courses_exist = True
            
            # If payment found AND courses exist, resolve the issue
            if payment_found and courses_exist:
                # Update issue status
                payment_issues_collection.update_one(
                    {'_id': issue['_id']},
                    {'$set': {
                        'status': 'resolved',
                        'resolved_at': datetime.now(),
                        'resolved_by': 'batch_processor',
                        'resolution_type': 'auto_resolved',
                        'notes': 'Auto-resolved by batch processor - Payment and courses verified'
                    }}
                )
                
                # Send email to user
                email_sent = send_issue_resolution_email(email, index_number, mpesa_receipt, paid_levels)
                if email_sent:
                    emails_sent += 1
                
                resolved_count += 1
                print(f"✅ Auto-resolved issue for {email} - Receipt: {mpesa_receipt}")
            else:
                pending_count += 1
                print(f"⚠️ Issue still pending for {email} - Receipt: {mpesa_receipt} (Payment found: {payment_found}, Courses exist: {courses_exist})")
        
        return jsonify({
            'success': True,
            'processed': processed_count,
            'resolved': resolved_count,
            'pending': pending_count,
            'emails_sent': emails_sent,
            'message': f'Processed {processed_count} issues. Resolved {resolved_count}. Still pending: {pending_count}.'
        })
        
    except Exception as e:
        print(f"❌ Error in batch resolve: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

def send_issue_resolution_email(email, index_number, mpesa_receipt, paid_levels):
    """Send email notification for resolved payment issue"""
    try:
        subject = "Your KUCCPS Payment Issue Has Been Resolved"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Payment Issue Resolved</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Issue Resolved!</h1>
                <p style="color: white; margin: 5px 0 0;">Your courses are ready</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                <p>Dear Student,</p>
                
                <p>Your previously submitted payment issue has been <strong>resolved</strong>. Your courses are now ready to view.</p>
                
                <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>✅ Your Verified Details:</strong></p>
                    <p style="margin: 5px 0;">📧 Email: <strong>{email}</strong></p>
                    <p style="margin: 5px 0;">📝 KCSE Index Number: <strong>{index_number}</strong></p>
                    <p style="margin: 5px 0;">💰 M-Pesa Receipt: <strong>{mpesa_receipt}</strong></p>
                    <p style="margin: 5px 0;">📚 Verified Categories: <strong>{', '.join(paid_levels).upper()}</strong></p>
                </div>
                
                <p><strong>To access your courses now:</strong></p>
                <ol>
                    <li>Go to <a href="https://www.studentsplacement.co.ke">https://www.studentsplacement.co.ke</a></li>
                    <li>Click the <strong>"Already Made Payment"</strong> button</li>
                    <li>Enter your M-Pesa receipt: <strong>{mpesa_receipt}</strong></li>
                    <li>Enter your index number: <strong>{index_number}</strong></li>
                    <li>Your courses will be displayed immediately!</li>
                </ol>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #856404;">
                        <strong>📌 Note:</strong> You can also re-enter your grades for any category and the system will recognize your payment automatically.
                    </p>
                </div>
                
                <hr style="margin: 20px 0;">
                
                <p style="font-size: 12px; color: #666; text-align: center;">
                    Need help? Contact us: kuccpscourses@gmail.com | +254750732841<br>
                    © 2025 KUCCPS Courses Checker. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """
        
        # Use your existing email sending function
        email_sent = send_brevo_email(email, "Student", subject, html_content)
        
        if email_sent:
            print(f"✅ Resolution email sent to {email}")
            return True
        else:
            print(f"⚠️ Failed to send resolution email to {email}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending resolution email: {str(e)}")
        return False

@app.route('/admin/process-payment-issue/<issue_id>', methods=['POST'])
def process_payment_issue(issue_id):
    """Process a payment issue (approve or delete)"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    action = request.form.get('action')
    admin_username = session.get('admin_username', 'admin')
    
    try:
        from bson import ObjectId
        obj_id = ObjectId(issue_id)
    except:
        flash("Invalid issue ID", "error")
        return redirect(url_for('admin_payment_issues'))
    
    if action == 'approve':
        success = approve_payment_issue(obj_id, admin_username)
        if success:
            flash("Payment issue approved and manual activation created", "success")
        else:
            flash("Failed to approve payment issue", "error")
    
    elif action == 'delete':
        success = delete_payment_issue(obj_id, admin_username)
        if success:
            flash("Payment issue deleted", "success")
        else:
            flash("Failed to delete payment issue", "error")
    
    return redirect(url_for('admin_payment_issues'))

@app.route('/admin/payment-issues/all')
def admin_all_payment_issues():
    """View all payment issues with filtering"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    status = request.args.get('status', 'all')
    
    if status == 'all':
        issues = get_all_payment_issues()
    else:
        issues = get_all_payment_issues(status)
    
    return render_template('admin_all_payment_issues.html', 
                         issues=issues,
                         current_status=status)

# --- News Model ---
# --- News Model ---
def create_news_collection():
    """Initialize news collection with indexes"""
    global database_connected, db_user_data
    
    # SAFE CHECK: Use explicit None/False comparisons
    if database_connected is False:
        print("❌ Database connection flag is False")
        return None
    
    # Don't check 'client' - instead check if we can access the database
    if db_user_data is None:
        print("❌ Database not properly initialized")
        return None
    
    try:
        # Create or get news collection
        news_collection = db_user_data['news_articles']
        
        # Create indexes
        existing_indexes = list(news_collection.list_indexes())
        
        # Index for published status and ordering
        existing = [i for i in existing_indexes if i.get('key', {}) == {'is_published': 1, 'published_at': -1}]
        if not existing:
            news_collection.create_index([("is_published", 1), ("published_at", -1)], name='published_news_index')
        
        # Index for featured news
        existing = [i for i in existing_indexes if i.get('key', {}) == {'is_featured': 1, 'published_at': -1}]
        if not existing:
            news_collection.create_index([("is_featured", 1), ("published_at", -1)], name='featured_news_index')
        
        print("✅ News collection initialized with indexes")
        return news_collection
    except Exception as e:
        print(f"❌ Error creating news collection: {str(e)}")
        return None
# Initialize news collection
news_collection = create_news_collection()

def get_user_courses_data(email, index_number, level):
    """Get user courses from database with better validation"""
    courses_data = None
    
    # Try database first
    if database_connected:
        try:
            courses_data = user_courses_collection.find_one({
                'email': email, 
                'index_number': index_number, 
                'level': level
            })
            
            if courses_data and 'courses' in courses_data:
                # Validate and convert courses
                valid_courses = []
                for course in courses_data['courses']:
                    if course and isinstance(course, dict):
                        course_dict = dict(course)
                        if '_id' in course_dict and isinstance(course_dict['_id'], ObjectId):
                            course_dict['_id'] = str(course_dict['_id'])
                        valid_courses.append(course_dict)
                
                courses_data['courses'] = valid_courses
                courses_data['courses_count'] = len(valid_courses)
                print(f"✅ Loaded {len(valid_courses)} courses from database for {level}")
                
        except Exception as e:
            print(f"❌ Error getting user courses from database: {str(e)}")
    
    # Fallback to session
    if not courses_data or not courses_data.get('courses'):
        session_key = f'{level}_courses_{index_number}'
        courses_data = session.get(session_key)
        
        if courses_data and 'courses' in courses_data:
            print(f"✅ Loaded {len(courses_data['courses'])} courses from session for {level}")
    
    return courses_data

def get_qualifying_ttc(user_grades, user_mean_grade):
    """FAST version – codes always strings."""
    if not database_connected:
        return []
    qualifying_courses = []
    try:
        available = get_available_collections(db_Teachers, 'ttc')
        for collection_name in TTC_COLLECTIONS:
            if collection_name not in available:
                continue
            collection = db_Teachers[collection_name]
            for course in collection.find({}, COURSE_PROJECTION):
                if check_diploma_course_qualification(course, user_grades, user_mean_grade):
                    c = dict(course)
                    c['collection'] = collection_name
                    if '_id' in c:
                        c['_id'] = str(c['_id'])
                    _stringify_course_codes(c)
                    qualifying_courses.append(c)
    except Exception as e:
        print(f"⚠️ TTC error: {e}")
    print(f"📚 TTC: found {len(qualifying_courses)} courses")
    return qualifying_courses
 
# --- Session Management Functions ---
def init_session():
    """Initialize or reset session with default values"""
    session.permanent = True  # Use permanent session with lifetime from config
    if 'initialized' not in session:
        session['initialized'] = True
        session['last_activity'] = datetime.now().isoformat()
        session['courses_loaded_from_db'] = False

def clear_session_data(partial=False):
    """Clear session data with option to preserve critical fields"""
    critical_fields = {
        # User identification fields
        'email', 'index_number', 'verified_payment', 
        'verified_index', 'verified_receipt', 
        'current_flow', 'current_level',
        
        # Grade and cluster data fields
        'degree_grades', 'degree_cluster_points', 'degree_data_submitted',
        'diploma_grades', 'diploma_mean_grade', 'diploma_data_submitted',
        'certificate_grades', 'certificate_mean_grade', 'certificate_data_submitted',
        'artisan_grades', 'artisan_mean_grade', 'artisan_data_submitted',
        'kmtc_grades', 'kmtc_mean_grade', 'kmtc_data_submitted',
        'ttc_grades', 'ttc_mean_grade', 'ttc_data_submitted'
    }
    
    if partial:
        # Save critical data
        saved_data = {k: session[k] for k in critical_fields if k in session}
        
        # Clear session
        session.clear()
        
        # Restore critical data
        session.update(saved_data)
    else:
        # Complete clear
        session.clear()
    
    # Reinitialize session
    init_session()

@app.route('/sitemap-index.xml')
@cache.cached(timeout=86400)
def sitemap_index():
    """Generate sitemap index"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://www.studentsplacement.co.ke/sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://www.studentsplacement.co.ke/sitemap-guides.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://www.studentsplacement.co.ke/sitemap-news.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://www.studentsplacement.co.ke/sitemap-courses.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
</sitemapindex>'''
    
    response = make_response(xml)
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response


@app.before_request
def enforce_www_and_https():
    """Enforce www subdomain for production domain only"""
    # Skip health check endpoint
    if request.path == '/health':
        return None
    
    # Get the host
    host = request.host.split(':')[0]  # Remove port if present
    
    # Skip all redirects for test/localhost domains
    if host.endswith('.fly.dev') or host == 'localhost' or host == '127.0.0.1':
        return None
    
    # Only apply www redirect to production domain (kuccpscourses.co.ke -> www.kuccpscourses.co.ke)
    if host == 'kuccpscourses.co.ke':
        # Redirect non-www to www
        scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
        url = f'{scheme}://www.{host}{request.full_path}'
        return redirect(url, code=301)

@app.before_request
def check_session_timeout():
    """Check for session timeout and handle accordingly"""
    if 'last_activity' in session:
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(minutes=30):
            clear_session_data()
            return redirect(url_for('index'))
    
    session['last_activity'] = datetime.now().isoformat()

def get_canonical_url(route_name, **kwargs):
    """
    Generate a guaranteed canonical URL with https and www.
    This ensures consistency for Google Search Console and SEO.
    """
    try:
        # Generate the URL using Flask's url_for with _external=True
        url = url_for(route_name, _external=True, _scheme='https', **kwargs)
        
        # Ensure HTTPS
        url = url.replace('http://', 'https://')
        
        # Ensure www subdomain for production domain
        if 'kuccpscourses.co.ke' in url and not 'www.' in url:
            url = url.replace('https://www.studentsplacement.co.ke', 'https://www.studentsplacement.co.ke')
        
        # Remove trailing slash for consistency (except for root)
        if url != 'https://www.studentsplacement.co.ke/' and url.endswith('/'):
            url = url.rstrip('/')
        
        print(f"✅ Generated canonical URL for {route_name}: {url}")
        return url
    except Exception as e:
        print(f"⚠️ Error generating canonical URL for {route_name}: {str(e)}")
        # Fallback to explicit URL construction
        fallback_url = f"https://www.studentsplacement.co.ke{url_for(route_name, **kwargs)}"
        if fallback_url.endswith('/') and fallback_url != 'https://www.studentsplacement.co.ke/':
            fallback_url = fallback_url.rstrip('/')
        print(f"⚠️ Using fallback canonical URL: {fallback_url}")
        return fallback_url
# --- Helper Classes ---
class JSONEncoder:
    """Custom JSON encoder for handling MongoDB ObjectId"""
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

app.json_encoder = JSONEncoder

# --- Helper Functions ---
def parse_grade(grade_str):
    """Parse grade string, handling unexpected formats"""
    if not grade_str:
        return None
    if grade_str in GRADE_VALUES:
        return grade_str
    if '/' in grade_str:
        parts = grade_str.split('/')
        for part in parts:
            if part in GRADE_VALUES:
                return part
    return None

def meets_requirement(requirement_key, requirement_grade, user_grades):
    """Check if user meets a single requirement (handles / for either/or)"""
    parsed_grade = parse_grade(requirement_grade)
    if not parsed_grade:
        return False
        
    if '/' in requirement_key:
        alternatives = requirement_key.split('/')
        for subject in alternatives:
            if subject in user_grades:
                if GRADE_VALUES[user_grades[subject]] >= GRADE_VALUES[parsed_grade]:
                    return True
        return False
    else:
        if requirement_key in user_grades:
            return GRADE_VALUES[user_grades[requirement_key]] >= GRADE_VALUES[parsed_grade]
        return False

def check_course_qualification(course, user_grades, user_cluster_points):
    """Check if user qualifies for a specific course based on subjects and cluster points"""
    requirements = course.get('minimum_subject_requirements', {})
    
    subject_qualified = True
    if requirements:
        for subject_key, required_grade in requirements.items():
            if not meets_requirement(subject_key, required_grade, user_grades):
                subject_qualified = False
                break
    
    cluster_qualified = True
    cluster_name = course.get('cluster', '')
    cut_off_points = course.get('cut_off_points', 0)
    
    if cluster_name and cut_off_points:
        user_points = user_cluster_points.get(cluster_name, 0)
        if user_points < cut_off_points:
            cluster_qualified = False
    
    return subject_qualified and cluster_qualified

def check_diploma_course_qualification(course, user_grades, user_mean_grade):
    """Check if user qualifies for a specific diploma course based on mean grade and subject requirements"""
    mean_grade_qualified = True
    min_mean_grade = course.get('minimum_grade', {}).get('mean_grade')
    
    if min_mean_grade:
        if GRADE_VALUES[user_mean_grade] < GRADE_VALUES[min_mean_grade]:
            mean_grade_qualified = False
    
    subject_qualified = True
    requirements = course.get('minimum_subject_requirements', {})
    
    if requirements:
        for subject_key, required_grade in requirements.items():
            if not meets_requirement(subject_key, required_grade, user_grades):
                subject_qualified = False
                break
    
    return mean_grade_qualified and subject_qualified

def check_certificate_course_qualification(course, user_grades, user_mean_grade):
    """Check if user qualifies for a specific certificate course based on mean grade and subject requirements"""
    return check_diploma_course_qualification(course, user_grades, user_mean_grade)

def check_artisan_course_qualification(course, user_grades, user_mean_grade):
    """Check if user qualifies for a specific artisan course"""
    mean_grade_qualified = True
    min_mean_grade = course.get('minimum_grade', {}).get('mean_grade')
    
    if min_mean_grade:
        # Artisan courses accept D plain, D-, or E
        allowed_grades = ['D', 'D-', 'E']
        if user_mean_grade not in allowed_grades:
            user_value = GRADE_VALUES.get(user_mean_grade, 0)
            required_value = GRADE_VALUES.get(min_mean_grade, 0)
            if user_value < required_value:
                mean_grade_qualified = False
    
    subject_qualified = True
    requirements = course.get('minimum_subject_requirements', {})
    
    if requirements:
        for subject_key, required_grade in requirements.items():
            if not meets_requirement(subject_key, required_grade, user_grades):
                subject_qualified = False
                break
    
    return mean_grade_qualified and subject_qualified

def save_user_grades_before_payment(email, index_number, flow, grades_data, mean_grade=None, cluster_points=None):
    """Store grades in database BEFORE payment to ensure background processor can access them"""
    if not database_connected:
        return False
    
    try:
        # Create grades collection if it doesn't exist
        if 'user_grades' not in db_user_data.list_collection_names():
            grades_collection = db_user_data.create_collection('user_grades')
        else:
            grades_collection = db_user_data['user_grades']
        
        record = {
            'email': email,
            'index_number': index_number,
            'level': flow,
            'grades': grades_data,
            'mean_grade': mean_grade,
            'cluster_points': cluster_points or {},
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        result = grades_collection.update_one(
            {'email': email, 'index_number': index_number, 'level': flow},
            {'$set': record},
            upsert=True
        )
        print(f"✅ Grades stored in database BEFORE payment for {flow}: {email}")
        return True
    except Exception as e:
        print(f"❌ Error storing grades before payment: {str(e)}")
        return False



def get_gemini_response(user_message):
    """Get AI response from Google Gemini with COMPLETE knowledge base"""
    global gemini_calls_today, gemini_calls_today_reset, last_api_call_time
    
    try:
        # Initialize last call time for rate limiting
        if 'last_api_call_time' not in globals():
            global last_api_call_time
            last_api_call_time = 0
        
        # Rate limiting
        current_time = time.time()
        time_since_last_call = current_time - last_api_call_time
        if time_since_last_call < 1:
            wait_time = 1 - time_since_last_call
            print(f"⏱️ Rate limiting: waiting {wait_time:.1f}s between calls")
            time.sleep(wait_time)
        
        # Reset daily counter if needed
        today = datetime.now().date()
        if today != gemini_calls_today_reset:
            gemini_calls_today = 0
            gemini_calls_today_reset = today
            print(f"📅 Daily counter reset. New day: {today}")
        
        # Check cache first
        message_hash = hashlib.md5(user_message.encode()).hexdigest()
        if message_hash in gemini_response_cache:
            cache_time = gemini_cache_timestamps.get(message_hash)
            if cache_time and (datetime.now() - cache_time).total_seconds() < 86400:
                print(f"✅ Using cached Gemini response")
                return gemini_response_cache[message_hash]
        
        # Rate limit check
        if gemini_calls_today >= MAX_GEMINI_DAILY:
            print(f"⚠️ Daily Gemini limit reached ({MAX_GEMINI_DAILY})")
            return get_openrouter_fallback(user_message)
        
        print(f"🤖 Calling Gemini API (call #{gemini_calls_today + 1} today)...")
        
        # Configure the client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # ========== CONCISE SYSTEM PROMPT - FIXED VERSION ==========
        system_prompt = f"""You are the official AI assistant for KUCCPS Courses Checker (kuccpscourses.co.ke). 

IMPORTANT: You MUST answer as this specific platform's assistant, NOT as a general AI.

ABOUT KUCCPS COURSES CHECKER:
- Website: kuccpscourses.co.ke
- Helps Kenyan students find courses matching their KCSE grades
- 6 categories: Degree (C+), Diploma (C-), KMTC (C-), TTC (C), Certificate (D+), Artisan (D/E)
- First category: KES 200, Additional categories: KES 100 each
- Payment: M-PESA STK Push
- 5000+ courses, 200+ institutions, 50,000+ students helped
- Features: Course basket, AI chat, email reports, PDF exports

HOW TO USE:
1. Choose a category (Degree, Diploma, etc.)
2. Enter your KCSE grades
3. Enter email and KCSE index number
4. Pay via M-PESA (KES 200 first, KES 100 additional)
5. View results instantly
6. Save courses to basket

OFFICIAL KUCCPS INFO (Different from this platform):
- Application fee: KES 1,500 via eCitizen
- Official portal: students.kuccps.net
- Degree: C+ minimum, Diploma: C-, Certificate: D+, Artisan: D/E

SUPPORT:
- Email: kuccpscourses@gmail.com
- Phone: +254750732841
- Live chat available on website

RULES:
- Answer as the KUCCPS Courses Checker assistant
- Be helpful, friendly, and concise (2-4 sentences)
- Use "you" and "your" (student perspective)
- If asked about official KUCCPS, explain the difference
- For payment issues, suggest using receipt verification

User question: {user_message}

Answer as the KUCCPS Courses Checker assistant:"""

        # Try multiple models
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-flash-001']
        
        for model_name in models_to_try:
            try:
                print(f"🔄 Trying model: {model_name}")
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=system_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.5,
                        max_output_tokens=500,  # Reduced for faster, focused responses
                        top_p=0.9
                    )
                )
                
                if response and response.text:
                    ai_response = response.text.strip()
                    
                    # Cache the response
                    gemini_response_cache[message_hash] = ai_response
                    gemini_cache_timestamps[message_hash] = datetime.now()
                    gemini_calls_today += 1
                    last_api_call_time = time.time()
                    
                    print(f"✅ Got response from {model_name} ({len(ai_response)} chars)")
                    return ai_response
                    
            except Exception as e:
                print(f"❌ Model {model_name} failed: {str(e)}")
                continue
        
        # If all Gemini models failed, try OpenRouter
        print("⚠️ All Gemini models failed, trying OpenRouter fallback...")
        openrouter_response = get_openrouter_fallback(user_message)
        if openrouter_response:
            return openrouter_response
        
        # Ultimate fallback
        return get_curated_response(user_message)
        
    except Exception as e:
        print(f"❌ Critical error in get_gemini_response: {str(e)}")
        import traceback
        traceback.print_exc()
        
        try:
            return get_openrouter_fallback(user_message)
        except:
            return get_curated_response(user_message)
def get_curated_response(user_message):
    """Return curated responses based on common questions - COMPREHENSIVE KNOWLEDGE BASE"""
    user_message_lower = user_message.lower()
    
    # ============================================
    # COMPUTER SCIENCE - DETAILED RESPONSE
    # ============================================
    if "computer science" in user_message_lower:
        return """Computer Science Degree Programs in Kenya

REQUIREMENTS:
- KCSE Mean Grade: C+ (minimum)
- Subject Requirements: C+ in Mathematics, C+ in English, C+ in Physics or Physical Sciences
- Cluster Points: 35-42 points depending on university

TOP UNIVERSITIES AND CUT-OFF POINTS:
1. University of Nairobi (UoN) - Cut-off: 38-42 points
2. Kenyatta University - Cut-off: 36-40 points
3. JKUAT - Cut-off: 35-39 points
4. Strathmore University - Cut-off: 38-43 points
5. Technical University of Kenya - Cut-off: 34-38 points
6. Murang'a University - Cut-off: 32-36 points
7. Dedan Kimathi University - Cut-off: 33-37 points

DURATION: 4 years

CAREER OPPORTUNITIES:
- Software Developer/Engineer
- Data Scientist/Analyst
- Cybersecurity Analyst
- Systems Architect
- IT Consultant
- Database Administrator
- Network Administrator

Use our Degree course checker (KES 200 first category, KES 100 additional) to see all Computer Science programs matching your exact KCSE grades. Visit www.kuccpscourses.co.ke/degree to get started."""
    
    # ============================================
    # NURSING - DETAILED RESPONSE
    # ============================================
    elif "nursing" in user_message_lower:
        return """Nursing Programs in Kenya

DIPLOMA IN NURSING (KRCHN) - KMTC:
- KCSE Mean Grade: C plain (not C-)
- Subject Requirements: C plain in English, Biology, and Chemistry
- Mathematics/Physics: C-
- Duration: 3 years including clinical training
- Campuses: 70+ KMTC campuses nationwide
- Cut-off: Highly competitive (B plain average)

DEGREE IN NURSING (BSc Nursing):
- KCSE Mean Grade: C+ minimum
- Subject Requirements: B in Biology, B in Chemistry, C+ in English, C+ in Mathematics/Physics
- Duration: 4 years
- Top Universities: UoN, Kenyatta, Moi, JKUAT, Amref

CAREER PATH:
- Registered Nurse (KRCHN)
- Clinical Nurse Specialist
- Nurse Educator
- Hospital Administrator
- Public Health Nurse

Use our KMTC course checker (KES 200) to see all nursing programs matching your grades. Visit www.kuccpscourses.co.ke/kmtc"""
    
    # ============================================
    # ENGINEERING - DETAILED RESPONSE
    # ============================================
    elif "engineering" in user_message_lower:
        if "civil" in user_message_lower:
            return """Civil Engineering - Complete Guide

REQUIREMENTS:
- KCSE Mean Grade: C+
- Subject Requirements: C+ in Mathematics, Physics, Chemistry
- Cluster Points: 36-40 points

TOP UNIVERSITIES:
1. University of Nairobi - Cut-off: 38-42 points
2. JKUAT - Cut-off: 36-40 points
3. Technical University of Kenya - Cut-off: 35-39 points
4. Moi University - Cut-off: 35-39 points

DURATION: 5 years

CAREER: Structural Engineer, Project Manager, Construction Engineer, Water Engineer

Use our Degree course checker at www.kuccpscourses.co.ke/degree"""
        
        elif "mechanical" in user_message_lower:
            return """Mechanical Engineering - Complete Guide

REQUIREMENTS:
- KCSE Mean Grade: C+
- Subject Requirements: C+ in Mathematics, Physics, Chemistry
- Cluster Points: 38-42 points

TOP UNIVERSITIES:
1. University of Nairobi - Cut-off: 40-43 points
2. JKUAT - Cut-off: 38-42 points
3. Moi University - Cut-off: 37-41 points

DURATION: 5 years

CAREER: Mechanical Engineer, Automotive Engineer, Manufacturing Engineer, HVAC Engineer

Use our Degree course checker at www.kuccpscourses.co.ke/degree"""
        
        elif "electrical" in user_message_lower:
            return """Electrical Engineering - Complete Guide

REQUIREMENTS:
- KCSE Mean Grade: C+
- Subject Requirements: C+ in Mathematics, Physics, Chemistry
- Cluster Points: 38-43 points

TOP UNIVERSITIES:
1. University of Nairobi - Cut-off: 40-44 points
2. JKUAT - Cut-off: 38-42 points
3. Technical University of Kenya - Cut-off: 37-41 points

DURATION: 5 years

CAREER: Electrical Engineer, Power Systems Engineer, Electronics Engineer

Use our Degree course checker at www.kuccpscourses.co.ke/degree"""
        
        else:
            return """Engineering Programs in Kenya - Complete Guide

GENERAL REQUIREMENTS:
- KCSE Mean Grade: C+ minimum
- Subject Requirements: C+ in Mathematics, Physics, Chemistry
- Duration: 5 years

TYPES OF ENGINEERING AND CUT-OFF POINTS:
1. Civil Engineering - 36-40 points (UoN, JKUAT, TUK)
2. Mechanical Engineering - 38-42 points (UoN, JKUAT, Moi)
3. Electrical Engineering - 38-43 points (UoN, JKUAT, TUK)
4. Chemical Engineering - 38-42 points (UoN, Moi)
5. Computer Engineering - 35-40 points (JKUAT, TUK)
6. Mechatronic Engineering - 36-40 points (JKUAT, TUK)
7. Petroleum Engineering - 40-45 points (TUK)

Use our Degree course checker (KES 200) at www.kuccpscourses.co.ke/degree to see all engineering programs matching your grades."""
    
    # ============================================
    # BUSINESS COURSES
    # ============================================
    elif "business" in user_message_lower or "commerce" in user_message_lower or "accounting" in user_message_lower:
        return """Business Programs in Kenya

BACHELOR OF COMMERCE (B.Com):
- KCSE Mean Grade: C+
- Subject Requirements: C+ in Mathematics, C+ in English
- Cluster Points: 30-38 points
- Duration: 4 years

TOP UNIVERSITIES AND CUT-OFF:
1. University of Nairobi - 35-38 points
2. Kenyatta University - 33-37 points
3. Moi University - 30-35 points
4. JKUAT - 32-36 points
5. Strathmore University - 35-40 points

SPECIALIZATIONS:
- Accounting
- Finance
- Marketing
- Human Resource Management
- Operations Management
- International Business

DIPLOMA IN BUSINESS:
- Requirements: C- mean grade
- Duration: 2 years
- Institutions: National polytechnics, Technical colleges

CAREER OPPORTUNITIES:
Accountant, Financial Analyst, Marketing Manager, HR Manager, Business Consultant

Use our course checker at www.kuccpscourses.co.ke/diploma or www.kuccpscourses.co.ke/degree"""
    
    # ============================================
    # LAW
    # ============================================
    elif "law" in user_message_lower or "lawyer" in user_message_lower:
        return """Bachelor of Laws (LLB) - Complete Guide

REQUIREMENTS:
- KCSE Mean Grade: B plain minimum (highly competitive)
- Subject Requirements: B in English, B in Kiswahili or History/CRE
- Cluster Points: 40-48 points
- Duration: 4 years (plus 1 year at Kenya School of Law)

TOP UNIVERSITIES AND CUT-OFF:
1. University of Nairobi - 44-48 points
2. Moi University - 42-46 points
3. Kenyatta University - 41-45 points
4. Catholic University - 40-44 points
5. Kabarak University - 38-42 points

CAREER PATH:
- Advocate/Lawyer
- Magistrate/Judge
- Legal Counsel
- Prosecutor
- Law Lecturer

Note: After LLB, you must complete a Postgraduate Diploma at Kenya School of Law (KSL) to practice as an advocate.

Use our Degree course checker at www.kuccpscourses.co.ke/degree"""
    
    # ============================================
    # MEDICINE
    # ============================================
    elif "medicine" in user_message_lower or "mbchb" in user_message_lower or "doctor" in user_message_lower:
        return """Bachelor of Medicine and Surgery (MBChB) - Complete Guide

REQUIREMENTS:
- KCSE Mean Grade: B+ minimum (very competitive)
- Subject Requirements: B in Biology, B in Chemistry, B in Mathematics/Physics, B in English
- Cluster Points: 42-48 points
- Duration: 6 years (including internship)

TOP UNIVERSITIES AND CUT-OFF:
1. University of Nairobi - 46-48 points
2. Moi University - 44-47 points
3. Kenyatta University - 43-46 points
4. Maseno University - 42-45 points
5. Egerton University - 41-44 points

CAREER PATH:
- Medical Doctor
- Surgeon
- Specialist (Pediatrician, Cardiologist, etc.)
- Medical Researcher
- Public Health Officer

Use our Degree course checker at www.kuccpscourses.co.ke/degree to see if you qualify for medicine programs."""
    
    # ============================================
    # KMTC COURSES
    # ============================================
    elif "kmtc" in user_message_lower:
        if "clinical" in user_message_lower:
            return """Diploma in Clinical Medicine and Surgery - KMTC

REQUIREMENTS:
- KCSE Mean Grade: C plain
- Subject Requirements: C in Biology, C in Chemistry, C in English
- Duration: 3 years
- Campuses: 70+ KMTC campuses nationwide

CAREER: Clinical Officer, Medical Officer

Use our KMTC course checker at www.kuccpscourses.co.ke/kmtc"""
        elif "pharmacy" in user_message_lower:
            return """Diploma in Pharmacy - KMTC

REQUIREMENTS:
- KCSE Mean Grade: C plain
- Subject Requirements: C in Biology, C in Chemistry, C in English/Mathematics
- Duration: 3 years

CAREER: Pharmaceutical Technologist, Pharmacy Assistant

Use our KMTC course checker at www.kuccpscourses.co.ke/kmtc"""
        else:
            return """KMTC (Kenya Medical Training College) Programs

KMTC offers healthcare diplomas and certificates across 70+ campuses in Kenya.

POPULAR PROGRAMS AND REQUIREMENTS:
1. Diploma in Nursing (KRCHN) - C plain, English/Biology/Chemistry C plain
2. Diploma in Clinical Medicine - C plain, Biology/Chemistry C
3. Diploma in Pharmacy - C plain, Biology/Chemistry C
4. Diploma in Medical Laboratory - C plain, Biology/Chemistry C
5. Diploma in Health Records - C- plain
6. Diploma in Environmental Health - C- plain
7. Certificate in Community Health - D+

DURATION: 2-3 years depending on program

Use our KMTC course checker (KES 200) at www.kuccpscourses.co.ke/kmtc to see all programs matching your KCSE grades."""
    
    # ============================================
    # TTC COURSES
    # ============================================
    elif "ttc" in user_message_lower or "teacher training" in user_message_lower:
        return """Teacher Training College (TTC) Programs

PTE (Primary Teacher Education):
- Requirements: C mean grade
- Duration: 2 years
- Subjects: Two teaching subjects
- Colleges: Thogoto, Meru, Machakos, Asumbi, etc.

ECDE (Early Childhood Development):
- Requirements: C- mean grade
- Duration: 2 years

DIPLOMA IN SECONDARY EDUCATION:
- Requirements: Degree + C+ in KCSE
- Duration: 2 years

CAREER: Primary/Secondary School Teacher (TSC employment)

Use our TTC course checker (KES 200) at www.kuccpscourses.co.ke/ttc"""
    
    # ============================================
    # CLUSTER POINTS EXPLANATION
    # ============================================
    elif "cluster points" in user_message_lower or "cluster" in user_message_lower:
        return """Cluster Points Explained

WHAT ARE CLUSTER POINTS?
Cluster points are your score based on your best 4 subjects in specific subject combinations required for a degree program.

GRADE CONVERSION TABLE:
A = 12 points
A- = 11 points
B+ = 10 points
B = 9 points
B- = 8 points
C+ = 7 points
C = 6 points
C- = 5 points
D+ = 4 points
D = 3 points
D- = 2 points
E = 1 point

COMMON CLUSTERS:
1. Engineering: Math, Physics, Chemistry (36-48 points required)
2. Medicine: Biology, Chemistry, Math/Physics (38-48 points)
3. Law: English, History, CRE (28-40 points)
4. Business: Math, English, Business Studies (30-42 points)
5. Education: Two teaching subjects + English (24-36 points)

HOW TO CALCULATE:
Add points for your 4 best subjects in the required cluster. Example: B in Math (9) + B- in Physics (8) + C+ in Chemistry (7) = 24 points

Visit our guide at www.kuccpscourses.co.ke/guides/cluster-points-explained for more details."""
    
    # ============================================
    # KUCCPS APPLICATION PROCESS
    # ============================================
    elif "kuccps application" in user_message_lower or "how to apply to kuccps" in user_message_lower:
        return """KUCCPS Application Process - Step by Step

STEP 1: Visit students.kuccps.net
STEP 2: Create account with KCSE index number and exam year
STEP 3: Fill personal details (name, contacts, etc.)
STEP 4: Verify your KCSE results (system auto-fetches)
STEP 5: Select up to 6 degree choices or 4 diploma/certificate choices
STEP 6: Enter official 7-digit programme codes carefully
STEP 7: Pay KES 1,500 via eCitizen (M-PESA PayBill 820201)
STEP 8: Enter eCitizen Payment Reference Code (NOT M-PESA transaction code)
STEP 9: Submit and save confirmation
STEP 10: Monitor placement results (August-October)

IMPORTANT DATES:
- April: Application opens
- July 15th: Application deadline
- August-October: Placement results released

Note: Our platform (www.kuccpscourses.co.ke) helps you find which courses you qualify for BEFORE applying. The KES 1,500 is the official KUCCPS fee, separate from our KES 200 course checking fee."""
    
    # ============================================
    # ABOUT THE PLATFORM
    # ============================================
    elif "what is kuccps courses checker" in user_message_lower or "about this platform" in user_message_lower:
        return """About KUCCPS Courses Checker

KUCCPS Courses Checker (www.kuccpscourses.co.ke) is an online tool that helps Kenyan students find university, college, and vocational courses that match their KCSE grades.

WHAT WE DO:
- You enter your KCSE grades once
- Our system instantly shows you ALL courses you qualify for
- You can compare programs, save favorites to basket, and plan your future

WHAT WE ARE NOT:
- NOT the official KUCCPS portal (that's students.kuccps.net for applications)
- NOT an admission guarantee (you still need to apply through KUCCPS)
- NOT a paid service for browsing (basic features are free)

PRICING:
- First category check: KES 200
- Additional categories: KES 100 each
- Payment: M-PESA STK Push

FEATURES:
- 6 categories: Degree, Diploma, KMTC, TTC, Certificate, Artisan
- 5000+ courses, 200+ institutions
- AI chat support 24/7
- Course basket to save favorites
- Email results as PDF

Contact: kuccpscourses@gmail.com | Phone: +254750732841"""
    
    # ============================================
    # PRICING QUESTIONS
    # ============================================
    elif any(word in user_message_lower for word in ["how much", "cost", "price", "payment", "kes"]):
        return """KUCCPS Courses Checker Pricing

FIRST CATEGORY: KES 200
- Choose any category (Degree, Diploma, KMTC, TTC, Certificate, or Artisan)
- Get instant access to ALL matching courses in that category

ADDITIONAL CATEGORIES: KES 100 each
- Add more categories at a discounted rate
- Example: Diploma (KES 200) + Certificate (KES 100) = KES 300 total

WHAT YOU GET:
- Complete list of courses matching your KCSE grades
- Institution names, programme codes, cut-off points
- Subject requirements for each course
- Unlimited browsing and filtering
- Save courses to basket
- Export results as PDF

PAYMENT METHOD:
M-PESA STK Push - enter your phone number, receive prompt, enter PIN, instant results

OFFICIAL KUCCPS FEE (separate):
KES 1,500 via eCitizen for actual application placement

Use the "Already Made Payment" button if you've paid but didn't get results - enter your receipt number to access your courses."""
    
    # ============================================
    # DIPLOMA COURSES GENERAL
    # ============================================
    elif "diploma" in user_message_lower and "course" in user_message_lower:
        return """Diploma Courses in Kenya

REQUIREMENTS:
- Minimum KCSE mean grade: C-
- Most diplomas accept C plain
- Some specialized diplomas may require higher grades

POPULAR DIPLOMA PROGRAMS:
1. Diploma in ICT/Computer Science - C-
2. Diploma in Engineering (Civil, Mechanical, Electrical) - C-
3. Diploma in Nursing (KMTC) - C plain
4. Diploma in Business Management - C-
5. Diploma in Building Technology - C-
6. Diploma in Accountancy - C-
7. Diploma in Hospitality Management - C-
8. Diploma in Human Resource Management - C-

DURATION: 2 years

INSTITUTIONS:
- National polytechnics (Kenya, Mombasa, Eldoret, Kisumu, etc.)
- Technical Training Institutes (TVETs)
- KMTC campuses for health diplomas

CAREER BENEFITS:
- Shorter duration than degree (2 years vs 4 years)
- More practical, hands-on training
- Lower tuition costs
- Direct entry into workforce
- Pathway to degree through recognition of prior learning

Use our Diploma course checker (KES 200) at www.kuccpscourses.co.ke/diploma to see all programs matching your grades."""
    
    # ============================================
    # CERTIFICATE COURSES
    # ============================================
    elif "certificate" in user_message_lower:
        return """Certificate Courses in Kenya

REQUIREMENTS:
- Minimum KCSE mean grade: D+
- Very accessible - most students qualify

POPULAR CERTIFICATE PROGRAMS:
1. Certificate in ICT/Computer Packages - D+
2. Certificate in Business Administration - D+
3. Certificate in Sales and Marketing - D+
4. Certificate in Food and Beverage - D+
5. Certificate in Front Office Operations - D+
6. Certificate in Hairdressing and Beauty Therapy - D+
7. Certificate in Plumbing - D+
8. Certificate in Electrical Installation - D+
9. Certificate in Fashion Design - D+
10. Certificate in Early Childhood Education (ECDE) - D+

DURATION: 1-2 years

CAREER OUTCOMES:
- Entry-level positions in companies
- Self-employment opportunities
- Foundation for diploma studies

COST: Generally KES 20,000-50,000 per year at TVETs (government-subsidized)

Use our Certificate course checker (KES 200) at www.kuccpscourses.co.ke/certificate to see all programs matching your grades."""
    
    # ============================================
    # ARTISAN COURSES
    # ============================================
    elif "artisan" in user_message_lower:
        return """Artisan Courses in Kenya

REQUIREMENTS:
- KCSE mean grade: D plain, D-, or E (most accessible option)
- No specific subject requirements

POPULAR ARTISAN COURSES:
1. Plumbing and Pipe Fitting - D plain
2. Electrical Installation - D plain
3. Welding and Fabrication - D plain
4. Carpentry and Joinery - D plain
5. Masonry and Building Construction - D plain
6. Automotive Mechanics - D plain
7. Hairdressing and Beauty Therapy - D plain
8. Fashion Design and Garment Making - D plain
9. Motor Vehicle Mechanics - D plain
10. Refrigeration and Air Conditioning - D plain

DURATION: 6 months to 2 years

INSTITUTIONS: TVETs, youth polytechnics, vocational training centers

CAREER PATHS:
- Self-employment (start your own business)
- Construction industry
- Manufacturing sector
- Apprenticeship opportunities

GOVERNMENT SUPPORT: Many artisan courses are government-subsidized

Use our Artisan course checker (KES 200) at www.kuccpscourses.co.ke/artisan to see all programs matching your grades."""
    
    # ============================================
    # HOW TO USE THE PLATFORM
    # ============================================
    elif "how to use" in user_message_lower or "how does it work" in user_message_lower:
        return """How to Use KUCCPS Courses Checker - Step by Step

STEP 1: Choose a Category
- Visit www.kuccpscourses.co.ke
- Click on Degree, Diploma, KMTC, TTC, Certificate, or Artisan

STEP 2: Enter Your KCSE Grades
- Fill in your subject grades from the dropdown menus
- Select your overall mean grade
- Click "Submit Grades"

STEP 3: Enter Your Details
- Email address (to track your session and retrieve results later)
- KCSE Index Number (format: 12345678901/2024)
- Click "Continue to Payment"

STEP 4: Make Payment
- First category: KES 200, Additional categories: KES 100
- Enter your M-Pesa phone number (07XXXXXXXX)
- Click "Proceed to Payment"
- Enter your M-Pesa PIN on your phone
- Payment processes in 2-5 seconds

STEP 5: View Your Results
- See all courses you qualify for
- Filter by cluster (Engineering, Medicine, Business, etc.)
- Click "Add to Basket" to save favorites

STEP 6: Use Your Basket
- Save multiple courses for comparison
- Export as PDF or print
- Share with parents or counselors

ALREADY PAID? Use the "Already Made Payment" button - enter your receipt number and index number to access your results instantly.

Need help? Use the AI chat (bottom-right corner), email kuccpscourses@gmail.com, or call +254750732841."""
    
    # ============================================
    # SCHOLARSHIPS
    # ============================================
    elif "scholarship" in user_message_lower or "financial aid" in user_message_lower:
        return """Scholarships and Financial Aid in Kenya

GOVERNMENT FUNDING:
- HELB Loans: Apply at www.hef.co.ke
  - University: Up to KES 60,000 per year
  - TVET: Up to KES 40,000 per year
- CDF Bursaries: Apply through your local MP's office
- NG-CDF Scholarships: Merit-based and needs-based

UNIVERSITY SCHOLARSHIPS:
- Merit-based (top KCSE performers)
- Sports scholarships (talented athletes)
- Need-based financial aid
- Departmental awards

PRIVATE SCHOLARSHIPS:
- Equity Bank "Wings to Fly" (top performers from disadvantaged backgrounds)
- KCB Foundation (2jiajiri program)
- Safaricom Foundation
- Mastercard Foundation
- Kenya Airways (aviation courses)
- Various NGO scholarships

HOW TO APPLY:
1. Check eligibility requirements
2. Gather required documents (KCSE certificate, ID, parents' income docs)
3. Submit applications by deadlines (usually January-March)
4. Follow up on application status

Use our course checker to find courses that qualify for specific scholarships."""
    
    # ============================================
    # CONTACT INFORMATION
    # ============================================
    elif "contact" in user_message_lower or "support" in user_message_lower or "help" in user_message_lower:
        return """Contact KUCCPS Courses Checker Support

EMAIL: kuccpscourses@gmail.com
- Response time: 2-4 hours

PHONE: +254750732841
- Hours: Monday-Friday, 8 AM - 6 PM
- Voicemail available 24/7

LIVE CHAT:
- Click the AI chat button (bottom-right corner of any page)
- Available 24/7, instant responses

SOCIAL MEDIA:
- Twitter: @kuccpschecker
- Facebook: KUCCPS Courses Checker

WHATSAPP GROUP:
- Join our community for quick support: [link on website]

FOR PAYMENT ISSUES:
- Use the "Payment Issues? Get Help" button (red floating button on the left)
- Submit your M-Pesa receipt and screenshot
- Our team will respond within 6 hours

OFFICIAL KUCCPS CONTACT (for applications):
- Website: students.kuccps.net
- Phone: 020 5137400
- Email: info@kuccps.ac.ke

We're here to help you find your perfect course!"""
    
    # ============================================
    # DEFAULT RESPONSE
    # ============================================
    else:
        return """Welcome to KUCCPS Courses Checker! I'm here to help you find courses matching your KCSE grades.

Visit our website: www.kuccpscourses.co.ke

I can answer questions about:
- Specific courses (Computer Science, Nursing, Engineering, Law, Medicine, Business, etc.)
- Course requirements (grades, cluster points, cut-off points)
- Universities and colleges in Kenya (UoN, Kenyatta, JKUAT, KMTC, TTC, etc.)
- How to use our platform (step-by-step guide)
- Pricing (KES 200 first category, KES 100 additional)
- KUCCPS application process (official)
- Diploma, Certificate, and Artisan programs
- Scholarships and financial aid
- Cluster points calculation

What specific course or topic would you like to learn about?

Example questions you can ask:
- "Tell me about Computer Science at University of Nairobi"
- "What are the requirements for nursing at KMTC?"
- "How do I calculate cluster points?"
- "What diploma courses can I do with C plain?"
- "Tell me about engineering programs in Kenya"

Just type your question and I'll give you detailed information specific to your needs!"""
@app.route('/test-simple')
def test_simple():
    """Ultra-simple test to verify API works"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Try the simplest possible request
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents='Say "hello"'
        )
        
        return jsonify({
            'success': bool(response and response.text),
            'response': response.text if response and response.text else None,
            'response_type': str(type(response)) if response else None,
            'has_text': hasattr(response, 'text') if response else False
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__
        })
@app.route('/check-version')
def check_version():
    import google.genai
    return jsonify({
        'version': google.genai.__version__,
        'location': google.genai.__file__
    })
def get_available_models():
    """Helper function to list available models"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        models = client.models.list()
        return [m.name for m in models][:10]  # Return first 10
    except:
        return []
def get_chatbot_response(user_message):
    """Optimized: OpenRouter primary, Gemini secondary with proper fallback"""
    
    print(f"🤖 Processing: '{user_message}'")
    
    # Try OpenRouter FIRST
    openrouter_response = get_openrouter_fallback(user_message)
    if openrouter_response:
        print("✅ Using OpenRouter response")
        return openrouter_response
    
    # If OpenRouter fails, try Gemini
    print("⚠️ OpenRouter failed, trying Gemini as fallback...")
    gemini_response = get_gemini_response(user_message)
    if gemini_response:
        print("✅ Using Gemini response")
        return gemini_response
    
    # Ultimate fallback - curated responses
    print("⚠️ Both OpenRouter and Gemini failed, using curated response")
    return get_curated_response(user_message)
def get_enhanced_chatbot_response(user_message):
    """
    Enhanced chatbot that uses:
    1. OpenRouter (primary - unlimited)
    2. Gemini (secondary - high quality, limited)
    3. Web search (tertiary - real-time info)
    4. Curated responses (final fallback)
    """
    
    print(f"🤖 Processing: '{user_message}'")
    
    # Check if this is a time-sensitive question that needs current info
    time_sensitive_keywords = [
        "deadline", "cut off", "cut-off", "2026", "current", "latest",
        "today", "now", "recent", "new", "announced", "opening", "closing"
    ]
    
    needs_current_info = any(keyword in user_message.lower() for keyword in time_sensitive_keywords)
    
    # If it needs current info, search the web first
    if needs_current_info:
        print("🔍 Time-sensitive question detected, searching web first...")
        web_result = search_kuccps_info(user_message)
        if web_result:
            return web_result
    
    # Otherwise, try AI services in order
    # Step 1: Try OpenRouter (unlimited)
    openrouter_response = get_openrouter_fallback(user_message)
    if openrouter_response and is_quality_response(openrouter_response):
        return openrouter_response
    
    # Step 2: Try Gemini (high quality)
    gemini_response = get_gemini_response(user_message)
    if gemini_response and is_quality_response(gemini_response):
        return gemini_response
    
    # Step 3: If AI responses are generic, search the web
    print("🔍 AI responses were generic, searching web for current info...")
    web_response = search_kuccps_info(user_message)
    if web_response:
        return web_response
    
    # Step 4: Ultimate fallback to curated responses
    return get_curated_response(user_message)

def is_quality_response(response):
    """Check if the response is actually helpful"""
    if not response or len(response) < 30:
        return False
    
    generic_phrases = [
        "i'm here to help",
        "i can help you with",
        "what would you like to know",
        "ask me about",
        "how can i assist",
        "i'm not sure",
        "i don't have that information"
    ]
    
    response_lower = response.lower()
    
    # If it contains generic phrases, it's low quality
    if any(phrase in response_lower for phrase in generic_phrases):
        return False
    
    # If it has links or specific numbers, it's probably good
    if 'http' in response_lower or any(char.isdigit() for char in response):
        return True
    
    return True  # Default to true if not obviously bad
from serpapi import GoogleSearch
import json

def search_kuccps_info(query):
    """
    Search for KUCCPS-related information with targeted sources
    Uses SERPAPI for reliable, formatted search results
    """
    try:
        SERPAPI_KEY = os.getenv('SERPAPI_KEY')
        if not SERPAPI_KEY:
            print("⚠️ SERPAPI key not configured")
            return None
            
        print(f"🔍 Searching for: '{query}'")
        
        # Target specific Kenyan education sites for better results
        site_filters = [
            "site:kuccps.ac.ke",
            "site:kmtc.ac.ke", 
            "site:education.go.ke",
            "site:universities.or.ke",
            "KUCCPS Kenya",
            "KMTC admission"
        ]
        
        # Construct search query with filters
        search_query = f"{query} {' OR '.join(site_filters[:3])}"
        
        params = {
            "q": search_query,
            "api_key": SERPAPI_KEY,
            "num": 5,  # Get top 5 results
            "gl": "ke",  # Geolocation Kenya
            "hl": "en",  # Language English
            "google_domain": "google.co.ke"  # Use Kenya Google
        }
        
        search = GoogleSearch(params)
        results = search.get_dict()
        
        if "organic_results" in results:
            organic_results = results["organic_results"]
            
            if organic_results:
                return format_search_results(organic_results, query)
            else:
                print("⚠️ No search results found")
                return None
        else:
            print(f"⚠️ Unexpected response format: {results.keys()}")
            return None
            
    except Exception as e:
        print(f"❌ Error searching: {str(e)}")
        return None
    
def send_manual_activation_results_email(email, index_number, flow, qualifying_courses, mpesa_receipt):
    """Send PDF results email for manually activated users using Brevo only"""
    try:
        from pdf_generator import generate_courses_pdf
        from email_service import send_courses_report
        
        print(f"📧 Sending manual activation results to {email}")
        print(f"📚 Courses: {len(qualifying_courses)}")
        print(f"💰 Using receipt: {mpesa_receipt}")
        
        if not qualifying_courses:
            print(f"⚠️ No courses to send for {email}")
            return False
        
        courses_by_level = {flow: qualifying_courses}
        
        # Generate PDF with the original receipt
        pdf_buffer = generate_courses_pdf(
            email=email,
            index_number=index_number,
            courses_by_level=courses_by_level,
            total_courses=len(qualifying_courses),
            mpesa_receipt=mpesa_receipt
        )
        
        if not pdf_buffer:
            print(f"❌ Failed to generate PDF for {email}")
            return False
        
        # Send email with PDF attachment using Brevo
        success = send_courses_report(
            email=email,
            index_number=index_number,
            courses_by_level=courses_by_level,
            total_courses=len(qualifying_courses),
            mpesa_receipt=mpesa_receipt,
            pdf_buffer=pdf_buffer,
            is_manual_activation=True
        )
        
        if pdf_buffer:
            pdf_buffer.close()
        
        if success:
            print(f"✅ PDF results email sent to {email} with receipt: {mpesa_receipt}")
            # Mark as notified
            mark_user_notified(email, index_number, flow)
        else:
            print(f"⚠️ Failed to send PDF email to {email}")
            
        return success
            
    except Exception as e:
        print(f"❌ Error sending manual activation email: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
def mark_activation_as_used(email, index_number, flow):
    """Mark manual activation as used so it can't be reused"""
    try:
        if database_connected and admin_activations_collection is not None:
            result = admin_activations_collection.update_one(
                {
                    '$or': [
                        {'email': email},
                        {'index_number': index_number}
                    ],
                    'is_active': True
                },
                {
                    '$set': {
                        'is_active': False,
                        'used_for_flow': flow,
                        'used_at': datetime.now(),
                        'status': 'used'
                    }
                }
            )
            if result.modified_count > 0:
                print(f"✅ Manual activation marked as used for {email} - {flow}")
    except Exception as e:
        print(f"❌ Error marking activation as used: {str(e)}")

def format_search_results(results, query):
    """Format search results into a helpful, natural response"""
    
    if not results:
        return None
    
    # Extract the most relevant information
    top_results = results[:3]  # Use top 3 results
    
    # Build a natural response
    response = f"**Here's what I found about '{query}' from current sources:**\n\n"
    
    for i, result in enumerate(top_results, 1):
        title = result.get('title', '')
        snippet = result.get('snippet', '')
        link = result.get('link', '')
        
        # Clean up the snippet (remove ellipsis, etc.)
        snippet = snippet.replace('...', '').strip()
        
        response += f"**{title}**\n"
        response += f"📌 {snippet}\n"
        
        # Extract domain for credibility
        if 'kuccps.ac.ke' in link:
            response += f"🔗 [Official KUCCPS Source]({link})\n\n"
        elif 'kmtc.ac.ke' in link:
            response += f"🔗 [Official KMTC Source]({link})\n\n"
        elif 'education.go.ke' in link:
            response += f"🔗 [Ministry of Education Source]({link})\n\n"
        else:
            response += f"🔗 [Source]({link})\n\n"
    
    response += "\n*Note: This information is from recent web searches. For official applications, always verify with KUCCPS directly.*"
    
    return response
def get_current_course_requirements(course_name):
    """Get up-to-date requirements for specific courses"""
    queries = {
        "nursing": "KMTC nursing requirements 2026 admission",
        "engineering": "KUCCPS engineering cut off points 2026",
        "medicine": "Bachelor of Medicine and Surgery requirements Kenya 2026",
        "education": "Primary Teacher Education requirements 2026",
        "ict": "Diploma ICT requirements KUCCPS 2026"
    }
    
    # Find matching query
    search_query = queries.get(course_name.lower(), f"{course_name} KUCCPS requirements 2026")
    return search_kuccps_info(search_query)

def get_current_deadlines():
    """Get current KUCCPS application deadlines"""
    return search_kuccps_info("KUCCPS application deadline 2026")

def get_cut_off_points(course, university):
    """Get current cut-off points for specific courses"""
    query = f"{course} {university} cut off points 2026"
    return search_kuccps_info(query)
# --- Course Qualification Functions ---
def _query_degree_cluster(args):
    collection_name, db, user_grades, user_cluster_points = args
    try:
        collection = db[collection_name]
        results = []
        for course in collection.find({}, COURSE_PROJECTION):
            course_with_cluster = dict(course)
            course_with_cluster['cluster'] = collection_name
            if '_id' in course_with_cluster:
                course_with_cluster['_id'] = str(course_with_cluster['_id'])
            if check_course_qualification(course_with_cluster, user_grades, user_cluster_points):
                results.append(course_with_cluster)
        return results
    except Exception as e:
        print(f"⚠️ Error in degree cluster {collection_name}: {e}")
        return []
 
def get_qualifying_courses(user_grades, user_cluster_points):
    """FAST parallel degree version – codes always strings."""
    if not database_connected:
        return []
    available = get_available_collections(db, 'degree')
    clusters_to_query = [c for c in CLUSTERS if c in available]
 
    qualifying_courses = []
    args_list = [(c, db, user_grades, user_cluster_points) for c in clusters_to_query]
 
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_query_degree_cluster, args): args[0] for args in args_list}
        for future in as_completed(futures):
            try:
                results = future.result()
                for course in results:
                    _stringify_course_codes(course)
                qualifying_courses.extend(results)
            except Exception as e:
                print(f"⚠️ Degree future error: {e}")
 
    print(f"📚 Degree: found {len(qualifying_courses)} courses (parallel)")
    return qualifying_courses
 
 

def _query_diploma_collection(args):
    """Worker: query one diploma collection and return qualifying courses"""
    collection_name, db_diploma, user_grades, user_mean_grade = args
    try:
        collection = db_diploma[collection_name]
        results = []
        for course in collection.find({}, COURSE_PROJECTION):
            if check_diploma_course_qualification(course, user_grades, user_mean_grade):
                c = dict(course)
                c['collection'] = collection_name
                if '_id' in c:
                    c['_id'] = str(c['_id'])
                results.append(c)
        return results
    except Exception as e:
        print(f"⚠️ Error in diploma collection {collection_name}: {e}")
        return []
 
def get_qualifying_diploma_courses(user_grades, user_mean_grade):
    """FAST parallel version – codes always strings."""
    if not database_connected:
        return []
    available = get_available_collections(db_diploma, 'diploma')
    collections_to_query = [c for c in DIPLOMA_COLLECTIONS if c in available]
 
    qualifying_courses = []
    args_list = [(c, db_diploma, user_grades, user_mean_grade) for c in collections_to_query]
 
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_query_diploma_collection, args): args[0] for args in args_list}
        for future in as_completed(futures):
            try:
                results = future.result()
                for course in results:
                    _stringify_course_codes(course)
                qualifying_courses.extend(results)
            except Exception as e:
                print(f"⚠️ Diploma future error: {e}")
 
    print(f"📚 Diploma: found {len(qualifying_courses)} courses (parallel)")
    return qualifying_courses
 
 

def get_qualifying_kmtc_courses(user_grades, user_mean_grade):
    """FAST version – codes always strings."""
    if not database_connected:
        return []
    qualifying_courses = []
    try:
        available = get_available_collections(db_kmtc, 'kmtc')
        if 'kmtc_courses' not in available:
            return []
        collection = db_kmtc['kmtc_courses']
        for course in collection.find({}, COURSE_PROJECTION):
            if check_diploma_course_qualification(course, user_grades, user_mean_grade):
                c = dict(course)
                if '_id' in c:
                    c['_id'] = str(c['_id'])
                _stringify_course_codes(c)
                qualifying_courses.append(c)
    except Exception as e:
        print(f"⚠️ KMTC error: {e}")
    print(f"📚 KMTC: found {len(qualifying_courses)} courses")
    return qualifying_courses

def _query_certificate_collection(args):
    collection_name, db_certificate, user_grades, user_mean_grade = args
    try:
        collection = db_certificate[collection_name]
        results = []
        for course in collection.find({}, COURSE_PROJECTION):
            if check_certificate_course_qualification(course, user_grades, user_mean_grade):
                c = dict(course)
                c['collection'] = collection_name
                if '_id' in c:
                    c['_id'] = str(c['_id'])
                results.append(c)
        return results
    except Exception as e:
        print(f"⚠️ Error in certificate collection {collection_name}: {e}")
        return []
 
def get_qualifying_certificate_courses(user_grades, user_mean_grade):
    """FAST parallel version – codes always strings."""
    if not database_connected:
        return []
    available = get_available_collections(db_certificate, 'certificate')
    collections_to_query = [c for c in CERTIFICATE_COLLECTIONS if c in available]
 
    qualifying_courses = []
    args_list = [(c, db_certificate, user_grades, user_mean_grade) for c in collections_to_query]
 
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_query_certificate_collection, args): args[0] for args in args_list}
        for future in as_completed(futures):
            try:
                results = future.result()
                for course in results:
                    _stringify_course_codes(course)
                qualifying_courses.extend(results)
            except Exception as e:
                print(f"⚠️ Certificate future error: {e}")
 
    print(f"📚 Certificate: found {len(qualifying_courses)} courses (parallel)")
    return qualifying_courses
 
 

def _query_artisan_collection(args):
    collection_name, db_artisan, user_grades, user_mean_grade = args
    try:
        collection = db_artisan[collection_name]
        results = []
        for course in collection.find({}, COURSE_PROJECTION):
            if check_artisan_course_qualification(course, user_grades, user_mean_grade):
                c = dict(course)
                c['collection'] = collection_name
                if '_id' in c:
                    c['_id'] = str(c['_id'])
                results.append(c)
        return results
    except Exception as e:
        print(f"⚠️ Error in artisan collection {collection_name}: {e}")
        return []
 
def get_qualifying_artisan_courses(user_grades, user_mean_grade):
    """FAST parallel version – codes always strings."""
    if not database_connected:
        return []
    available = get_available_collections(db_artisan, 'artisan')
    collections_to_query = [c for c in ARTISAN_COLLECTIONS if c in available]
 
    qualifying_courses = []
    args_list = [(c, db_artisan, user_grades, user_mean_grade) for c in collections_to_query]
 
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_query_artisan_collection, args): args[0] for args in args_list}
        for future in as_completed(futures):
            try:
                results = future.result()
                for course in results:
                    _stringify_course_codes(course)
                qualifying_courses.extend(results)
            except Exception as e:
                print(f"⚠️ Artisan future error: {e}")
 
    print(f"📚 Artisan: found {len(qualifying_courses)} courses (parallel)")
    return qualifying_courses
 

# --- Database Operations ---



@app.route('/debug/user-courses')
def debug_user_courses():
    """Debug endpoint to inspect stored courses for a user (email, index_number, level required as query args).
    Returns DB record and session record for comparison."""
    email = request.args.get('email')
    index_number = request.args.get('index_number')
    level = request.args.get('level')
    if not (email and index_number and level):
        return jsonify({'success': False, 'error': 'email, index_number and level query parameters are required'}), 400

    db_rec = None
    sess_rec = None
    try:
        if database_connected and user_courses_collection is not None:
            db_rec = user_courses_collection.find_one({'email': email, 'index_number': index_number, 'level': level})
            if db_rec and 'courses' in db_rec:
                # convert ObjectId to str for JSON
                for c in db_rec['courses']:
                    if '_id' in c and isinstance(c['_id'], ObjectId):
                        c['_id'] = str(c['_id'])
    except Exception as e:
        print(f"❌ Debug: error reading DB record: {e}")

    try:
        session_key = f'{level}_courses_{index_number}'
        sess_rec = session.get(session_key)
    except Exception:
        sess_rec = None

    return jsonify({'success': True, 'db_record': db_rec, 'session_record': sess_rec})


def generate_sitemap():
    """Generate accurate sitemap with only existing routes"""
    base_url = 'https://www.studentsplacement.co.ke'
    today = datetime.now().strftime('%Y-%m-%d')
    
    # ONLY include routes that actually exist in your Flask app
    static_pages = [
        {'path': '/', 'priority': '1.0', 'freq': 'daily'},
        {'path': '/degree', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/diploma', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/certificate', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/artisan', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/kmtc', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/ttc', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/about', 'priority': '0.7', 'freq': 'monthly'},
        {'path': '/contact', 'priority': '0.7', 'freq': 'monthly'},
        {'path': '/user-guide', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/news', 'priority': '0.8', 'freq': 'daily'},
        {'path': '/results', 'priority': '0.6', 'freq': 'weekly'},
        {'path': '/basket', 'priority': '0.6', 'freq': 'weekly'},
    ]
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for page in static_pages:
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{base_url}{page["path"]}</loc>')
        xml_parts.append(f'    <lastmod>{today}</lastmod>')
        xml_parts.append(f'    <changefreq>{page["freq"]}</changefreq>')
        xml_parts.append(f'    <priority>{page["priority"]}</priority>')
        xml_parts.append('  </url>')
    
    xml_parts.append('</urlset>')
    
    return '\n'.join(xml_parts)

def generate_comprehensive_sitemap():
    """Generate comprehensive sitemap with ONLY crawlable pages"""
    base_url = 'https://www.studentsplacement.co.ke'
    today = datetime.now().strftime('%Y-%m-%d')
    
    # ONLY public, accessible pages
    static_pages = [
        {'path': '/', 'priority': '1.0', 'freq': 'daily'},
        {'path': '/degree', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/diploma', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/certificate', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/artisan', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/kmtc', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/ttc', 'priority': '0.9', 'freq': 'weekly'},
        {'path': '/about', 'priority': '0.7', 'freq': 'monthly'},
        {'path': '/contact', 'priority': '0.7', 'freq': 'monthly'},
        {'path': '/user-guide', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/news', 'priority': '0.8', 'freq': 'daily'},
    ]
    
    # Add guide pages
    guide_pages = [
        {'path': '/guides/how-to-check-kuccps-courses-2026', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/kuccps-cluster-points-explained', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/kcse-grades-university-admission', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/diploma-courses-kenya-2026', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/certificate-courses-requirements', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/kmtc-courses-admission-2026', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/artisan-courses-2026', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/ttc-teacher-training-courses', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/kuccps-application-process', 'priority': '0.8', 'freq': 'monthly'},
        {'path': '/guides/scholarships-opportunities-2026', 'priority': '0.8', 'freq': 'monthly'},
    ]
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for page in static_pages + guide_pages:
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{base_url}{page["path"]}</loc>')
        xml_parts.append(f'    <lastmod>{today}</lastmod>')
        xml_parts.append(f'    <changefreq>{page["freq"]}</changefreq>')
        xml_parts.append(f'    <priority>{page["priority"]}</priority>')
        xml_parts.append('  </url>')
    
    xml_parts.append('</urlset>')
    
    return '\n'.join(xml_parts)

from datetime import datetime
from flask import make_response

@app.route('/sitemap.xml')
@cache.cached(timeout=86400)
def sitemap_main():
    """Generate main sitemap"""
    base_url = 'https://www.studentsplacement.co.ke'
    today = datetime.now().strftime('%Y-%m-%d')
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # All main URLs with priorities
    pages = [
        # Homepage
        {'path': '/', 'lastmod': today, 'freq': 'daily', 'priority': '1.0'},
        
        # Primary Course Pages
        {'path': '/degree', 'lastmod': today, 'freq': 'weekly', 'priority': '0.95'},
        {'path': '/diploma', 'lastmod': today, 'freq': 'weekly', 'priority': '0.95'},
        {'path': '/certificate', 'lastmod': today, 'freq': 'weekly', 'priority': '0.95'},
        {'path': '/artisan', 'lastmod': today, 'freq': 'weekly', 'priority': '0.95'},
        {'path': '/kmtc', 'lastmod': today, 'freq': 'weekly', 'priority': '0.95'},
        {'path': '/ttc', 'lastmod': today, 'freq': 'weekly', 'priority': '0.95'},
        
        # Information Pages
        {'path': '/about', 'lastmod': today, 'freq': 'monthly', 'priority': '0.7'},
        {'path': '/contact', 'lastmod': today, 'freq': 'monthly', 'priority': '0.6'},
        {'path': '/user-guide', 'lastmod': today, 'freq': 'monthly', 'priority': '0.7'},
        
        # News & Updates
        {'path': '/news', 'lastmod': today, 'freq': 'daily', 'priority': '0.8'},
        
        # Other Public Pages
        {'path': '/offline', 'lastmod': today, 'freq': 'never', 'priority': '0.4'},
    ]
    
    for page in pages:
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{base_url}{page["path"]}</loc>')
        xml_parts.append(f'    <lastmod>{page["lastmod"]}</lastmod>')
        xml_parts.append(f'    <changefreq>{page["freq"]}</changefreq>')
        xml_parts.append(f'    <priority>{page["priority"]}</priority>')
        xml_parts.append('  </url>')
    
    xml_parts.append('</urlset>')
    
    response = make_response('\n'.join(xml_parts))
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response


@app.route('/sitemap-guides.xml')
@cache.cached(timeout=86400)
def sitemap_guides():
    """Generate sitemap for guides"""
    base_url = 'https://www.studentsplacement.co.ke'
    today = datetime.now().strftime('%Y-%m-%d')
    
    guides_pages = [
        {'path': '/guides/', 'priority': '0.9', 'freq': 'monthly'},
        {'path': '/guides/cluster-points-explained', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/kcse-admission-requirements', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/diploma-courses-kenya', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/certificate-courses-requirements', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/kmtc-courses-admission', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/artisan-courses-kenya', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/ttc-teacher-training-courses', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/kuccps-application-process', 'priority': '0.85', 'freq': 'monthly'},
        {'path': '/guides/scholarships-opportunities', 'priority': '0.85', 'freq': 'monthly'},
    ]
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    for page in guides_pages:
        xml_parts.append('  <url>')
        xml_parts.append(f'    <loc>{base_url}{page["path"]}</loc>')
        xml_parts.append(f'    <lastmod>{today}</lastmod>')
        xml_parts.append(f'    <changefreq>{page["freq"]}</changefreq>')
        xml_parts.append(f'    <priority>{page["priority"]}</priority>')
        xml_parts.append('  </url>')
    
    xml_parts.append('</urlset>')
    
    response = make_response('\n'.join(xml_parts))
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response

@app.route('/sitemap-news.xml')
@cache.cached(timeout=86400)
def sitemap_news():
    """Generate sitemap for news articles"""
    base_url = 'https://www.studentsplacement.co.ke'
    today = datetime.now().strftime('%Y-%m-%d')
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    try:
        if 'news_collection' in locals() or 'news_collection' in globals():
            # Get published articles
            articles = news_collection.find({'is_published': True}).sort('published_at', -1).limit(100)
            
            for article in articles:
                article_id = str(article.get('_id', ''))
                article_title = article.get('title', '').lower().replace(' ', '-')[:50]
                published_date = article.get('published_at', datetime.now())
                if isinstance(published_date, datetime):
                    published_date = published_date.strftime('%Y-%m-%d')
                else:
                    published_date = today
                
                xml_parts.append('  <url>')
                xml_parts.append(f'    <loc>{base_url}/news/{article_id}</loc>')
                xml_parts.append(f'    <lastmod>{published_date}</lastmod>')
                xml_parts.append(f'    <changefreq>never</changefreq>')
                xml_parts.append(f'    <priority>0.7</priority>')
                xml_parts.append('  </url>')
    except Exception as e:
        print(f"Error generating news sitemap: {e}")
    
    xml_parts.append('</urlset>')
    
    response = make_response('\n'.join(xml_parts))
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response

def get_user_grades_from_db(email, index_number, level):
    """Retrieve user grades from database for background processing"""
    if not database_connected:
        print(f"❌ Database not connected, cannot retrieve grades")
        return None, None, None
    
    try:
        # Check if user_grades collection exists
        if 'user_grades' not in db_user_data.list_collection_names():
            print(f"⚠️ user_grades collection doesn't exist yet")
            return None, None, None
        
        grades_collection = db_user_data['user_grades']
        grade_data = grades_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        })
        
        if grade_data:
            print(f"✅ Found grades in database for {level}: {email}")
            print(f"   Grades: {len(grade_data.get('grades', {}))} subjects")
            print(f"   Mean Grade: {grade_data.get('mean_grade')}")
            return (
                grade_data.get('grades', {}),
                grade_data.get('mean_grade'),
                grade_data.get('cluster_points', {})
            )
        else:
            print(f"⚠️ No grades found in database for {level}: {email}")
            return None, None, None
            
    except Exception as e:
        print(f"❌ Error retrieving grades: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None
@app.route('/robots.txt')
@cache.cached(timeout=86400) 
def robots():
    """Generate robots.txt"""
    robots_content = '''User-agent: *
Allow: /


Disallow: /admin/
Disallow: /debug/
Disallow: /api/
Disallow: /enter-details/
Disallow: /results/
Disallow: /verified-dashboard
Disallow: /verified-results/
Disallow: /payment/
Disallow: /payment-wait/
Disallow: /check-payment/
Disallow: /check-payment-status/
Disallow: /check-courses-ready/
Disallow: /mpesa/
Disallow: /clear-session
Disallow: /temp-bypass/
Disallow: /collection-courses/
Disallow: /search-courses/
Disallow: /add-to-basket
Disallow: /remove-from-basket
Disallow: /clear-basket
Disallow: /save-basket
Disallow: /reset-basket
Disallow: /load-basket
Disallow: /get-basket
Disallow: /manifest.json
Disallow: /service-worker.js
Disallow: /submit-grades
Disallow: /submit-diploma-grades
Disallow: /submit-certificate-grades
Disallow: /submit-artisan-grades
Disallow: /submit-kmtc-grades
Disallow: /submit-ttc-grades

Sitemap: https://www.studentsplacement.co.ke/sitemap-index.xml
Sitemap: https://www.studentsplacement.co.ke/sitemap.xml
Sitemap: https://www.studentsplacement.co.ke/sitemap-guides.xml
Sitemap: https://www.studentsplacement.co.ke/sitemap-news.xml
Sitemap: https://www.studentsplacement.co.ke/sitemap-courses.xml

Crawl-delay: 1

User-agent: Googlebot
Crawl-delay: 0.5'''
    
    response = make_response(robots_content)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    return response
def update_sitemap_dates():
    """Update lastmod dates in sitemap - run this periodically"""
    # This would typically be called from a cron job or scheduler
    print(f"🔄 Updating sitemap dates: {datetime.now().strftime('%Y-%m-%d')}")
    # In production, you might want to update specific pages
    # based on when they were actually modified
    
    # For now, we're using dynamic dates in generate_sitemap()
    return True

@app.context_processor
def inject_global_vars():
    """Inject global variables into all templates"""
    base_url = request.url_root.rstrip('/')
    
    return {
        'site_name': 'KUCCPS Courses Checker',
        'site_description': 'Find KUCCPS courses that match your KCSE grades. Degree, Diploma, Certificate, KMTC, Artisan and TTC programs in Kenya.',
        'site_url': base_url,
        'current_year': datetime.now().year,
        'request': request,
        'current_path': request.path,
        'full_url': request.url,
        'og_image_url': f"{base_url}{url_for('static', filename='images/og-image.jpg')}",
        'twitter_image_url': f"{base_url}{url_for('static', filename='images/twitter-card.jpg')}",
        'get_canonical_url': get_canonical_url
    }
@app.context_processor
def inject_flash_visibility():
    """Control flash message visibility based on route - PREVENTS flashes on payment pages"""
    
    # Routes where flash messages should NEVER appear
    FLASH_BLOCKED_ROUTES = {
        # Payment flow - CRITICAL: These pages should never show flashes
        'payment', 'payment_wait', 'check_payment_status', 
        'ultra_fast_check', 'goto_results', 'check_courses_ready',
        
        # MPesa endpoints
        'mpesa_callback', 'mpesa_confirmation', 'mpesa_validation',
        
        # API endpoints
        'chat_api', 'submit_payment_issue', 'verify_payment',
        'api_manual_activation_advanced', 'api_deactivate_activation',
        
        # Debug endpoints
        'debug_session', 'debug_database', 'debug_basket_status',
        'debug_admin_activations', 'debug_user_courses',
        
        # System endpoints
        'robots', 'sitemap_main', 'sitemap_guides', 'sitemap_news',
        'sitemap_courses', 'sitemap_index', 'manifest', 
        'serve_service_worker', 'offline', 'health', 'ping', 'keep_alive',
        
        # Admin API endpoints
        'api_pending_issues_count', 'api_recent_activity', 'api_system_stats',
        'api_missing_courses_count', 'api_confirmed_missing_courses',
        'api_missing_courses_send_email', 'api_missing_courses_activate_and_notify',
        'api_missing_courses_regenerate', 'api_missing_courses_delete',
        'api_missing_courses_fix_notified_user'
    }
    
    current_endpoint = request.endpoint
    
    # Special handling for payment paths
    if request.path.startswith('/payment') or request.path.startswith('/payment-wait'):
        show_flash = False
    # Special handling for M-Pesa paths
    elif request.path.startswith('/mpesa'):
        show_flash = False
    # Special handling for API paths
    elif request.path.startswith('/api/') or request.path.startswith('/debug/'):
        show_flash = False
    # Check by endpoint name
    elif current_endpoint in FLASH_BLOCKED_ROUTES:
        show_flash = False
    else:
        # Show flashes on all other GET requests (user-facing pages)
        show_flash = request.method == 'GET'
    
    return {'show_flash_messages': show_flash}
@app.before_request
def manage_session():
    """Manage session state and handle page refreshes"""
    # Initialize session if needed
    if 'initialized' not in session:
        init_session()
    
    # Check for session timeout
    if 'last_activity' in session:
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(minutes=30):
            clear_session_data()
            return redirect(url_for('index'))
    
    # Update last activity
    session['last_activity'] = datetime.now().isoformat()
    
    # Handle page refresh for course pages
    if request.endpoint in ['results', 'basket']:
        # Get current user info
        email = session.get('email')
        index_number = session.get('index_number')
        current_level = session.get('current_level')
        
        if email and index_number and current_level:
            # Only clear session course data if it exists in database
            if database_connected:
                courses_data = get_user_courses_data(email, index_number, current_level)
                if courses_data and courses_data.get('courses'):
                    # Clear session course data to get fresh data from DB
                    session_key = f'{current_level}_courses_{index_number}'
                    session.pop(session_key, None)
                    print(f"🔄 Refreshing courses from database for {current_level}")
                else:
                    # Keep session data since no DB data exists
                    print(f"ℹ️ Keeping session courses for {current_level} - not in database")
    
    # Protect critical session data
    protected_keys = [
        'email', 'index_number', 'verified_payment', 'verified_index', 
        'verified_receipt', 'current_flow', 'current_level'
    ]
    
    # For basket operations, protect critical data
    if request.endpoint == 'clear_basket':
        request.protected_session_data = {
            k: session[k] for k in protected_keys if k in session
        }


@app.after_request
def restore_protected_data(response):
    """Restore protected session data after request"""
    if hasattr(request, 'protected_session_data'):
        for key, value in request.protected_session_data.items():
            if key not in session or session[key] != value:
                session[key] = value
    return response

def update_transaction_ref(email, index_number, level, transaction_ref):
    """Update transaction reference for user - WITHOUT confirming payment"""
    print(f"💾 Updating transaction ref for {email}, {index_number}, {level}: {transaction_ref}")
    
    if not database_connected:
        session_key = f'{level}_payment_{index_number}'
        if session_key in session:
            session[session_key]['transaction_ref'] = transaction_ref
            session[session_key]['payment_confirmed'] = False  # 🔥 Ensure not confirmed
        else:
            # Create new payment record in session
            session[session_key] = {
                'email': email,
                'index_number': index_number,
                'level': level,
                'transaction_ref': transaction_ref,
                'payment_amount': session.get('payment_amount', 1),
                'payment_confirmed': False,  # 🔥 Critical: Not confirmed
                'created_at': datetime.now().isoformat()
            }
        print(f"✅ Transaction reference updated in session: {transaction_ref}")
        return
        
    try:
        result = user_payments_collection.update_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'$set': {
                'transaction_ref': transaction_ref,
                'payment_confirmed': False,  # 🔥 Critical: Not confirmed
                'updated_at': datetime.now()
            }},
            upsert=True
        )
        print(f"✅ Transaction reference updated in database: {transaction_ref}")
    except Exception as e:
        print(f"❌ Error updating transaction reference: {str(e)}")
        # Fallback to session
        session_key = f'{level}_payment_{index_number}'
        session[session_key] = {
            'email': email,
            'index_number': index_number,
            'level': level,
            'transaction_ref': transaction_ref,
            'payment_amount': session.get('payment_amount', 1),
            'payment_confirmed': False,
            'created_at': datetime.now().isoformat()
        }
def check_existing_user_data(email, index_number):
    """Check if user details already exist in the database"""
    if not database_connected:
        return False
        
    try:
        # Check if user has any payment records
        existing_payments = user_payments_collection.find_one({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ],
            'payment_confirmed': True
        })
        
        # Check if user has any course records
        existing_courses = user_courses_collection.find_one({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ]
        })
        
        return existing_payments is not None or existing_courses is not None
        
    except Exception as e:
        print(f"❌ Error checking existing user data: {str(e)}")
        return False


def mark_payment_confirmed(transaction_ref, mpesa_receipt=None):
    """Mark payment as confirmed - ONLY with valid M-Pesa receipt"""
    if not mpesa_receipt:
        print(f"❌ Cannot confirm payment without M-Pesa receipt: {transaction_ref}")
        return False
        
    print(f"🔍 Confirming payment: {transaction_ref} with receipt: {mpesa_receipt}")
    
    if not database_connected:
        payment_found = False
        for key in list(session.keys()):
            if isinstance(session.get(key), dict) and session[key].get('transaction_ref') == transaction_ref:
                session[key]['payment_confirmed'] = True
                session[key]['mpesa_receipt'] = mpesa_receipt
                session[key]['payment_date'] = datetime.now().isoformat()
                
                level = session[key].get('level')
                if level:
                    session[f'paid_{level}'] = True
                    print(f"✅ Session marked as paid for {level}")
                
                payment_found = True
                break
        return payment_found
        
    try:
        result = user_payments_collection.update_one(
            {'transaction_ref': transaction_ref},
            {'$set': {
                'payment_confirmed': True,
                'mpesa_receipt': mpesa_receipt,
                'payment_date': datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            print(f"✅ Payment confirmed in database: {transaction_ref} with receipt: {mpesa_receipt}")
            
            # Also update session for consistency
            payment_data = user_payments_collection.find_one({'transaction_ref': transaction_ref})
            if payment_data:
                level = payment_data.get('level')
                if level:
                    session[f'paid_{level}'] = True
                    print(f"✅ Session updated for {level}")
            
            return True
        else:
            print(f"⚠️ No payment found with transaction ref: {transaction_ref}")
            return False
            
    except Exception as e:
        print(f"❌ Error marking payment confirmed: {str(e)}")
        return False

# Add these functions to update tracking status

def mark_user_notified(email, index_number, level, notification_type='email'):
    """Mark that a user has been notified about missing courses"""
    try:
        if not database_connected:
            return False
        
        # Create or update notification tracking collection
        if 'user_notifications' not in db_user_data.list_collection_names():
            notifications_collection = db_user_data.create_collection('user_notifications')
        else:
            notifications_collection = db_user_data['user_notifications']
        
        notification_record = {
            'email': email,
            'index_number': index_number,
            'level': level,
            'notification_type': notification_type,
            'notified_at': datetime.now(),
            'status': 'sent'
        }
        
        notifications_collection.update_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'$set': notification_record},
            upsert=True
        )
        print(f"✅ Marked {email} as notified for {level}")
        return True
    except Exception as e:
        print(f"❌ Error marking notification: {str(e)}")
        return False

def mark_user_activated(email, index_number, level, activation_type='admin_manual'):
    """Mark that a user has been manually activated"""
    try:
        if not database_connected:
            return False
        
        # Create or update activation tracking collection
        if 'user_activations_tracking' not in db_user_data.list_collection_names():
            activations_tracking = db_user_data.create_collection('user_activations_tracking')
        else:
            activations_tracking = db_user_data['user_activations_tracking']
        
        activation_record = {
            'email': email,
            'index_number': index_number,
            'level': level,
            'activation_type': activation_type,
            'activated_by': session.get('admin_username', 'admin'),
            'activated_at': datetime.now(),
            'status': 'activated'
        }
        
        activations_tracking.update_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'$set': activation_record},
            upsert=True
        )
        print(f"✅ Marked {email} as activated for {level}")
        return True
    except Exception as e:
        print(f"❌ Error marking activation: {str(e)}")
        return False

def check_if_notified(email, index_number, level):
    """Check if user has already been notified"""
    try:
        if not database_connected:
            return False
        
        if 'user_notifications' not in db_user_data.list_collection_names():
            return False
        
        notifications_collection = db_user_data['user_notifications']
        notification = notifications_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        })
        
        return notification is not None
    except Exception as e:
        print(f"❌ Error checking notification status: {str(e)}")
        return False

def check_if_activated(email, index_number, level):
    """Check if user has already been manually activated for this level"""
    try:
        if not database_connected:
            return False
        
        # Check in admin_activations collection
        if admin_activations_collection is not None:
            activation = admin_activations_collection.find_one({
                'email': email,
                'index_number': index_number,
                'is_active': True
            })
            if activation:
                return True
        
        # Check in tracking collection
        if 'user_activations_tracking' in db_user_data.list_collection_names():
            activations_tracking = db_user_data['user_activations_tracking']
            tracking = activations_tracking.find_one({
                'email': email,
                'index_number': index_number,
                'level': level
            })
            return tracking is not None
        
        return False
    except Exception as e:
        print(f"❌ Error checking activation status: {str(e)}")
        return False

def mark_payment_confirmed_by_account(account_number, mpesa_receipt, amount=None):
    """Mark payment as confirmed by account number (index number) - for Paybill payments"""
    if not database_connected:
        for key in session:
            if session[key].get('index_number') == account_number:
                session[key]['payment_confirmed'] = True
                session[key]['mpesa_receipt'] = mpesa_receipt
                if amount:
                    session[key]['payment_amount'] = amount
                return True
        return False
        
    try:
        update_data = {
            'payment_confirmed': True,
            'mpesa_receipt': mpesa_receipt,
            'payment_date': datetime.now()
        }
        if amount:
            update_data['payment_amount'] = amount
            
        result = user_payments_collection.update_one(
            {'index_number': account_number},
            {'$set': update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        print(f"❌ Error marking payment confirmed by account: {str(e)}")
        return False

# --- Course Processing & Qualification Functions ---


def send_results_email_background(email, index_number, flow, qualifying_courses, mpesa_receipt):
    """
    Runs in a daemon thread spawned by the background processor.
    Generates PDF and sends via Brevo. Any failure is logged only.
    Never blocks the caller.
    """
    try:
        from pdf_generator import generate_courses_pdf
        from email_service import send_courses_report
 
        print(f"📧 Sending email to {email} ({flow}, {len(qualifying_courses)} courses)")
 
        courses_by_level = {flow: qualifying_courses}
 
        pdf_buffer = generate_courses_pdf(
            email=email,
            index_number=index_number,
            courses_by_level=courses_by_level,
            total_courses=len(qualifying_courses),
            mpesa_receipt=mpesa_receipt
        )
 
        success = send_courses_report(
            email=email,
            index_number=index_number,
            courses_by_level=courses_by_level,
            total_courses=len(qualifying_courses),
            mpesa_receipt=mpesa_receipt,
            pdf_buffer=pdf_buffer
        )
 
        # Close buffer regardless of outcome
        if pdf_buffer:
            try:
                pdf_buffer.close()
            except Exception:
                pass
 
        if success:
            print(f"✅ Email sent to {email} ({flow})")
        else:
            print(f"⚠️  Email failed for {email} ({flow}) — Brevo may have rejected")
 
    except Exception as e:
        # CRITICAL: never re-raise — this is a daemon thread
        print(f"❌ send_results_email_background error for {email}: {e}")
        import traceback
        traceback.print_exc()
 


def process_courses_async(email, index_number, flow, mpesa_receipt):
    """Background async course processing (called from callback)"""
    try:
        print(f"🔄 Async processing started for {flow}: {email}")
        
        # Get grades from database (since session may not be available in background thread)
        user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(email, index_number, flow)
        
        if not user_grades:
            print(f"⚠️ No grades found in database for {flow}, checking session fallback")
            # Try to get from session if this is running in request context
            try:
                if flow == 'degree':
                    user_grades = session.get('degree_grades', {})
                    user_cluster_points = session.get('degree_cluster_points', {})
                elif flow == 'diploma':
                    user_grades = session.get('diploma_grades', {})
                    user_mean_grade = session.get('diploma_mean_grade', '')
                elif flow == 'certificate':
                    user_grades = session.get('certificate_grades', {})
                    user_mean_grade = session.get('certificate_mean_grade', '')
                elif flow == 'artisan':
                    user_grades = session.get('artisan_grades', {})
                    user_mean_grade = session.get('artisan_mean_grade', '')
                elif flow == 'kmtc':
                    user_grades = session.get('kmtc_grades', {})
                    user_mean_grade = session.get('kmtc_mean_grade', '')
                elif flow == 'ttc':
                    user_grades = session.get('ttc_grades', {})
                    user_mean_grade = session.get('ttc_mean_grade', '')
            except:
                pass
        
        if not user_grades:
            print(f"❌ No grades available for {flow}, cannot process")
            return
        
        # Queue the job with the retrieved data
        job_data = {
            'email': email,
            'index_number': index_number,
            'flow': flow,
            'mpesa_receipt': mpesa_receipt,
            'user_grades': user_grades,
            'user_mean_grade': user_mean_grade,
            'user_cluster_points': user_cluster_points
        }
        
        course_processing_queue.put(job_data)
        print(f"✅ {flow} queued from async callback")
        
    except Exception as e:
        print(f"❌ Async processing error: {str(e)}")
        import traceback
        traceback.print_exc()

# Add this function BEFORE process_courses_after_payment (at module level)
def send_results_email(email, index_number, courses_by_level, total_courses, mpesa_receipt=None):
    """Send results email with PDF attachment"""
    try:
        from pdf_generator import generate_courses_pdf
        from email_service import send_courses_report
        
        print(f"📧 Attempting to send email to {email} with {total_courses} courses...")
        
        # Generate PDF
        pdf_buffer = generate_courses_pdf(
            email=email,
            index_number=index_number,
            courses_by_level=courses_by_level,
            total_courses=total_courses,
            mpesa_receipt=mpesa_receipt
        )
        
        # Send email
        success = send_courses_report(
            email=email,
            index_number=index_number,
            courses_by_level=courses_by_level,
            total_courses=total_courses,
            mpesa_receipt=mpesa_receipt,
            pdf_buffer=pdf_buffer
        )
        
        if success:
            print(f"✅ Results email sent to {email} with {total_courses} courses")
            # Mark email as sent in session to avoid duplicates
            email_sent_key = f"email_sent_{email}_{index_number}"
            session[email_sent_key] = True
            return True
        else:
            print(f"⚠️ Failed to send results email to {email}")
            return False
            
    except Exception as e:
        print(f"❌ Error in send_results_email: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_consolidated_results_email(email, index_number, mpesa_receipt):
    """Send consolidated email with all paid categories"""
    try:
        from pdf_generator import generate_courses_pdf
        from email_service import send_courses_report
        
        # Get all paid categories for this user
        all_courses_by_level = {}
        total_courses = 0
        
        if database_connected:
            levels = ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']
            
            for level in levels:
                courses_data = user_courses_collection.find_one({
                    'email': email,
                    'index_number': index_number,
                    'level': level
                })
                
                if courses_data and courses_data.get('courses'):
                    all_courses_by_level[level] = courses_data['courses']
                    total_courses += len(courses_data['courses'])
        
        if total_courses > 0:
            print(f"📧 Sending consolidated email with {total_courses} courses across {len(all_courses_by_level)} levels")
            
            # Generate PDF with all courses
            pdf_buffer = generate_courses_pdf(
                email=email,
                index_number=index_number,
                courses_by_level=all_courses_by_level,
                total_courses=total_courses,
                mpesa_receipt=mpesa_receipt
            )
            
            # Send email
            success = send_courses_report(
                email=email,
                index_number=index_number,
                courses_by_level=all_courses_by_level,
                total_courses=total_courses,
                mpesa_receipt=mpesa_receipt,
                pdf_buffer=pdf_buffer
            )
            
            if success:
                print(f"✅ Consolidated email sent to {email}")
                # Mark email as sent
                email_sent_key = f"email_sent_{email}_{index_number}"
                session[email_sent_key] = True
                return True
            else:
                print(f"⚠️ Failed to send consolidated email to {email}")
                return False
        else:
            print(f"⚠️ No courses found to send in consolidated email for {email}")
            return False
            
    except Exception as e:
        print(f"❌ Error in send_consolidated_results_email: {e}")
        import traceback
        traceback.print_exc()
        return False



# --- MPesa API Credentials ---
MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')
MPESA_SHORTCODE = os.getenv('MPESA_SHORTCODE')

# --- Payment Functions ---
def get_mpesa_access_token():
    """Get MPesa access token for authentication with better error handling"""
    consumer_key = MPESA_CONSUMER_KEY
    consumer_secret = MPESA_CONSUMER_SECRET
    
    print(f"🔑 Getting MPesa access token...")
    print(f"🔑 Consumer Key: {consumer_key[:10]}...")
    
    try:
        response = requests.get(
            "https://api.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials",
            auth=HTTPBasicAuth(consumer_key, consumer_secret),
            timeout=30
        )
        
        print(f"📥 OAuth response status: {response.status_code}")
        print(f"📥 OAuth response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            print(f"❌ MPesa OAuth failed with status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            return None
            
        resp_json = response.json()
        access_token = resp_json.get('access_token')
        
        if not access_token:
            print('❌ No access_token in MPesa OAuth response')
            print(f"📄 Full response: {resp_json}")
            return None
            
        print("✅ MPesa access token obtained successfully")
        print(f"🔑 Token: {access_token[:50]}...")
        return access_token
        
    except requests.exceptions.Timeout:
        print('❌ MPesa OAuth timeout')
        return None
    except requests.exceptions.ConnectionError:
        print('❌ MPesa OAuth connection error')
        return None
    except Exception as e:
        print(f'❌ MPesa OAuth error: {str(e)}')
        import traceback
        traceback.print_exc()
        return None


def save_user_payment(email, index_number, level, transaction_ref=None, amount=1):
    """Save user payment information to payments collection"""
    if not database_connected:
        session_key = f'{level}_payment_{index_number}'
        session[session_key] = {
            'email': email,
            'index_number': index_number,
            'level': level,
            'transaction_ref': transaction_ref,
            'payment_amount': amount,
            'payment_confirmed': False,
            'created_at': datetime.now().isoformat()
        }
        return
        
    payment_record = {
        'email': email,
        'index_number': index_number,
        'level': level,
        'transaction_ref': transaction_ref,
        'payment_amount': amount,
        'payment_confirmed': False,
        'created_at': datetime.now()
    }
    
    try:
        result = user_payments_collection.update_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'$set': payment_record},
            upsert=True
        )
        print(f"✅ Payment record saved for {email}, amount: {amount}")
    except Exception as e:
        print(f"❌ Error saving user payment: {str(e)}")
        session_key = f'{level}_payment_{index_number}'
        session[session_key] = payment_record

def update_transaction_ref(email, index_number, level, transaction_ref):
    """Update transaction reference for user"""
    if not database_connected:
        session_key = f'{level}_payment_{index_number}'
        if session_key in session:
            session[session_key]['transaction_ref'] = transaction_ref
        return
        
    try:
        result = user_payments_collection.update_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'$set': {
                'transaction_ref': transaction_ref,
                'payment_confirmed': False
            }}
        )
        print(f"✅ Transaction reference updated: {transaction_ref}")
    except Exception as e:
        print(f"❌ Error updating transaction reference: {str(e)}")

def get_user_payment(email, index_number, level):
    """Get user payment info from database with fallback to session"""
    if database_connected:
        try:
            payment_data = user_payments_collection.find_one(
                {'email': email, 'index_number': index_number, 'level': level}
            )
            if payment_data:
                return payment_data
        except Exception as e:
            print(f"❌ Error getting user payment from database: {str(e)}")
    
    session_key = f'{level}_payment_{index_number}'
    return session.get(session_key)
@app.route('/debug/openrouter-key')
def debug_openrouter_key():
    """Debug OpenRouter API key"""
    OPENROUTER_API_KEY = "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"
    
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
        )
        
        return jsonify({
            'key_exists': bool(OPENROUTER_API_KEY),
            'key_preview': OPENROUTER_API_KEY[:15] + '...' if OPENROUTER_API_KEY else None,
            'status_code': response.status_code,
            'response': response.json() if response.status_code == 200 else response.text,
            'is_valid': response.status_code == 200
        })
    except Exception as e:
        return jsonify({
            'key_exists': bool(OPENROUTER_API_KEY),
            'key_preview': OPENROUTER_API_KEY[:15] + '...' if OPENROUTER_API_KEY else None,
            'error': str(e),
            'is_valid': False
        })
# --- Session Management Functions ---

def initiate_stk_push(phone, amount=1, flow=None):
    """Initiate MPesa STK push payment with proper state management"""
    print(f"📱 Initiating STK push for phone: {phone}, amount: {amount}, flow: {flow}")
    
    try:
        # Get flow from session if not provided
        if flow is None:
            flow = session.get('current_flow', 'unknown')
            print(f"🔍 Flow from session: {flow}")
        
        # Format phone number
        if phone.startswith('0') and len(phone) == 10:
            phone = '254' + phone[1:]
        elif phone.startswith('+254') and len(phone) == 13:
            phone = phone[1:]
        elif len(phone) == 9:
            phone = '254' + phone
        elif len(phone) == 12 and phone.startswith('254'):
            # Already in correct format
            pass
        else:
            return {'error': 'Invalid phone number format'}
    
        print(f"📞 Formatted phone: {phone}")
        
        # Validate amount
        if amount <= 0:
            return {'error': 'Invalid amount'}
        
        # Get access token
        access_token = get_mpesa_access_token()
        if not access_token:
            return {'error': 'Failed to get MPesa access token'}
            
        # Prepare STK push request
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        business_short_code = MPESA_SHORTCODE
        passkey = MPESA_PASSKEY
        
        print(f"🔑 Using ShortCode: {business_short_code}")
        print(f"🔑 Passkey available: {'Yes' if passkey else 'No'}")
        
        data_to_encode = business_short_code + passkey + timestamp
        password = base64.b64encode(data_to_encode.encode()).decode('utf-8')
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        index_number = session.get('index_number', 'KUCCPS')
        email = session.get('email', 'unknown@example.com')
        
        
        if os.environ.get('FLASK_ENV') == 'production' or 'render.com' in os.environ.get('RENDER_EXTERNAL_HOSTNAME', ''):
            base_url = 'https://www.studentsplacement.co.ke'
        else:
            ngrok_url = os.getenv('NGROK_URL')
            if ngrok_url:
                base_url = ngrok_url
                print(f"🔗 Using ngrok URL for callbacks: {base_url}")
            else:
                base_url = 'https://www.studentsplacement.co.ke'
                print(f"⚠️ NGROK_URL not set, using production URL: {base_url}")
        
        callback_url = f"{base_url}/mpesa/callback"
        
        payload = {
            "BusinessShortCode": business_short_code,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": business_short_code,
            "PhoneNumber": phone,
            "CallBackURL": callback_url,
            "AccountReference": index_number,
            "TransactionDesc": f"Course Qualification - Ksh {amount}"
        }
        
        print(f"📤 Sending STK push request to MPesa...")
        print(f"📞 Phone: {phone}")
        print(f"💰 Amount: {amount}")
        print(f"🎯 Flow: {flow}")
        print(f"📝 Account Reference: {index_number}")
        print(f"🔗 Callback URL: {callback_url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        # Send request with timeout
        response = requests.post(
            "https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"📥 MPesa response status: {response.status_code}")
        print(f"📥 MPesa response headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ STK Push initiated successfully")
            print(f"📋 MPesa Response: {json.dumps(result, indent=2)}")
            
            # Check for specific error codes in success response
            if result.get('ResponseCode') == '0':
                print(f"🎯 STK Push sent to customer successfully")
                
                # 🔥 CRITICAL: Ensure payment is NOT marked as confirmed yet
                transaction_ref = result.get('CheckoutRequestID')
                
                if transaction_ref and email and index_number:
                    # Update transaction ref but keep payment as NOT confirmed
                    update_transaction_ref(email, index_number, flow, transaction_ref)
                    # Explicitly set payment as not confirmed
                    session[f'paid_{flow}'] = False
                    session['payment_confirmed'] = False
                    print(f"🔐 Payment state set to PENDING for transaction: {transaction_ref}")
                    
                    # Verify the payment record was updated correctly
                    user_payment = get_user_payment(email, index_number, flow)
                    if user_payment:
                        print(f"✅ Payment record updated - Confirmed: {user_payment.get('payment_confirmed', False)}, Transaction: {user_payment.get('transaction_ref')}")
                    else:
                        print(f"❌ Failed to verify payment record update")
                
                return result
            else:
                error_code = result.get('ResponseCode')
                error_message = result.get('ResponseDescription') or result.get('errorMessage') or 'Unknown error'
                print(f"❌ STK Push failed with code {error_code}: {error_message}")
                return {'error': f'MPesa Error {error_code}: {error_message}'}
        else:
            # Handle HTTP errors
            error_message = f'MPesa API returned status {response.status_code}'
            print(f"❌ {error_message}")
            
            # Try to get more details from response
            try:
                error_details = response.json()
                print(f"📄 Error details: {json.dumps(error_details, indent=2)}")
                return {'error': error_message, 'details': error_details}
            except:
                print(f"📄 Response text: {response.text}")
                return {'error': error_message, 'details': response.text}
        
    except requests.exceptions.Timeout:
        error_msg = "MPesa API request timed out"
        print(f"❌ {error_msg}")
        return {'error': error_msg}
        
    except requests.exceptions.ConnectionError:
        error_msg = "Failed to connect to MPesa API"
        print(f"❌ {error_msg}")
        return {'error': error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error initiating STK push: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return {'error': error_msg}

def check_manual_activation(email, index_number, flow=None):
    """Check if user has manual activation from admin and mark as expired after use"""
    print(f"🔍 Checking manual activation for: {email}, {index_number}, flow: {flow}")
    
    # First check session for manual activations
    session_key = f'manual_activation_{index_number}'
    if session.get(session_key):
        print(f"✅ Manual activation found in session for {index_number}")
        
        # If flow is specified and we're using the activation, mark it as used
        if flow and database_connected and admin_activations_collection is not None:
            try:
                # Mark as used in database
                result = admin_activations_collection.update_one(
                    {
                        'index_number': index_number,
                        'is_active': True
                    },
                    {
                        '$set': {
                            'is_active': False,
                            'used_for_flow': flow,
                            'used_at': datetime.now(),
                            'status': 'used'
                        }
                    }
                )
                if result.modified_count > 0:
                    print(f"✅ Manual activation marked as used for {flow}")
                    # Also remove from session to prevent reuse
                    session.pop(session_key, None)
            except Exception as e:
                print(f"❌ Error expiring manual activation: {str(e)}")
        
        return True
    
    # Also check by email in session
    for key in session.keys():
        if key.startswith('manual_activation_'):
            activation_data = session.get(key)
            if (isinstance(activation_data, dict) and 
                (activation_data.get('email') == email or activation_data.get('index_number') == index_number)):
                print(f"✅ Manual activation found in session by email/index match")
                
                # Mark as used if flow is specified
                if flow and database_connected and admin_activations_collection is not None:
                    try:
                        result = admin_activations_collection.update_one(
                            {
                                '$or': [
                                    {'email': email},
                                    {'index_number': index_number}
                                ],
                                'is_active': True
                            },
                            {
                                '$set': {
                                    'is_active': False,
                                    'used_for_flow': flow,
                                    'used_at': datetime.now(),
                                    'status': 'used'
                                }
                            }
                        )
                        if result.modified_count > 0:
                            print(f"✅ Manual activation marked as used for {flow}")
                            session.pop(key, None)
                    except Exception as e:
                        print(f"❌ Error expiring manual activation: {str(e)}")
                
                return True
    
    if not database_connected:
        print("ℹ️ Database not connected, only checking session")
        return False
    
    try:
        # Check database for active manual activation (not used yet)
        activation = admin_activations_collection.find_one({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ],
            'is_active': True,
            'status': 'active'
        })
        
        if activation:
            print(f"✅ Manual activation found in database for {email}/{index_number}")
            
            # If flow is specified, mark as used immediately
            if flow:
                result = admin_activations_collection.update_one(
                    {'_id': activation['_id']},
                    {
                        '$set': {
                            'is_active': False,
                            'used_for_flow': flow,
                            'used_at': datetime.now(),
                            'status': 'used'
                        }
                    }
                )
                if result.modified_count > 0:
                    print(f"✅ Manual activation marked as used for {flow}")
            else:
                # Store in session for faster future access (only if not using immediately)
                session[session_key] = {
                    'email': activation.get('email'),
                    'index_number': activation.get('index_number'),
                    'mpesa_receipt': activation.get('mpesa_receipt'),
                    'activated_at': activation.get('activated_at')
                }
            
            return True
        else:
            print(f"❌ No active manual activation found for {email}/{index_number}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking manual activation in database: {str(e)}")
        return False
def create_manual_activation_payment(email, index_number, flow, mpesa_receipt):
    """Create a payment record for manual activations using ORIGINAL receipt with payment_confirmed=True"""
    print(f"💰 Creating payment record for manual activation: {email}, {index_number}, {flow}")
    print(f"💰 Using original receipt: {mpesa_receipt}")
    
    # Check if payment record already exists
    existing_payment = None
    if database_connected and user_payments_collection is not None:
        try:
            existing_payment = user_payments_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': flow
            })
            
            if existing_payment:
                print(f"⚠️ Payment record already exists for {email}, updating instead of creating new")
        except Exception as e:
            print(f"⚠️ Error checking existing payment: {e}")
    
    # 🔥 CRITICAL: payment_confirmed MUST be True for manual activations
    payment_record = {
        'email': email,
        'index_number': index_number,
        'level': flow,
        'transaction_ref': f"MANUAL_{mpesa_receipt}",
        'mpesa_receipt': mpesa_receipt,
        'payment_amount': existing_payment.get('payment_amount', 100) if existing_payment else 100,
        'payment_confirmed': True,  # 🔥 FIXED: Set to True
        'payment_method': 'manual_activation',
        'activated_by': 'admin',
        'created_at': existing_payment.get('created_at', datetime.now()) if existing_payment else datetime.now(),
        'payment_date': datetime.now(),
        'is_manual_activation': True,
        'original_receipt': mpesa_receipt
    }
    
    if database_connected and user_payments_collection is not None:
        try:
            if existing_payment:
                # Update existing record
                result = user_payments_collection.update_one(
                    {'_id': existing_payment['_id']},
                    {'$set': payment_record}
                )
                if result.modified_count > 0:
                    print(f"✅ Updated existing payment record - Receipt: {mpesa_receipt}, payment_confirmed=True")
                else:
                    print(f"⚠️ No changes made to existing payment record")
            else:
                # Insert new record
                result = user_payments_collection.insert_one(payment_record)
                if result.inserted_id:
                    print(f"✅ Created new payment record - Receipt: {mpesa_receipt}, payment_confirmed=True")
                else:
                    print(f"❌ Failed to create payment record")
            return True
        except Exception as e:
            print(f"❌ Error saving manual activation payment: {str(e)}")
            # Fallback to session
            session_key = f'{flow}_payment_{index_number}'
            session[session_key] = payment_record
            return False
    else:
        # Session fallback
        session_key = f'{flow}_payment_{index_number}'
        session[session_key] = payment_record
        return True

# Site Configuration
class Config:
    SITE_NAME = "KUCCPS Courses Checker"
    SITE_DESCRIPTION = "Find KUCCPS courses that match your KCSE grades. Degree, Diploma, Certificate, KMTC, Artisan and TTC programs in Kenya."
    SITE_URL = "https://www.studentsplacement.co.ke"
    
    # SEO Settings
    META_AUTHOR = "Hean Njuki"
    META_KEYWORDS = "KUCCPS, courses, KCSE, Kenya, degree, diploma, certificate, artisan, TTC, KMTC, university, college"
    
app.config.from_object(Config)  

def has_user_paid_for_category(email, index_number, category):
    """Check if user has already paid for a specific category - STRICTER VERSION"""
    # 🔥 NEW: Check manual activation first (without marking as used)
    manual_active = False
    if database_connected and admin_activations_collection is not None:
        try:
            manual_activation = admin_activations_collection.find_one({
                '$or': [
                    {'email': email},
                    {'index_number': index_number}
                ],
                'is_active': True
            })
            manual_active = manual_activation is not None
        except Exception as e:
            print(f"❌ Error checking manual activation in has_user_paid: {str(e)}")
    
    if manual_active:
        print(f"✅ Active manual activation found for {email}, allowing access to {category}")
        return True
    
    # First check session
    session_paid = session.get(f'paid_{category}')
    if session_paid:
        print(f"✅ Session shows paid for {category}")
        return True
    
    if not database_connected:
        return False
    
    try:
        # STRICTER database check - must have confirmed payment
        payment_data = user_payments_collection.find_one({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ],
            'level': category,
            'payment_confirmed': True
        })
        
        if payment_data:
            print(f"✅ Database shows confirmed payment for {category}")
            # Update session to reflect this
            session[f'paid_{category}'] = True
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error checking category payment: {str(e)}")
        return False
    
@app.route('/clear-session')
def clear_session():
    """Clear session data - useful for testing and preventing session issues"""
    session.clear()
    flash("Session cleared successfully", "info")
    return redirect(url_for('index'))

def get_user_paid_categories(email, index_number):
    """Get list of course levels that user has already paid for"""
    paid_categories = []
    
    if not database_connected:
        # Check session for paid categories
        for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
            if session.get(f'paid_{level}'):
                paid_categories.append(level)
        return paid_categories
    
    try:
        # Check database for paid categories
        paid_payments = user_payments_collection.find({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ],
            'payment_confirmed': True
        })
        
        for payment in paid_payments:
            level = payment.get('level')
            if level and level not in paid_categories:
                paid_categories.append(level)
                
    except Exception as e:
        print(f"❌ Error getting user paid categories: {str(e)}")
    
    return paid_categories

def get_user_existing_data(email, index_number):
    """Get all existing user data including payments and courses"""
    user_data = {
        'payments': [],
        'courses': [],
        'paid_categories': []
    }
    
    if not database_connected:
        return user_data
    
    try:
        # Get payment records
        payments = user_payments_collection.find({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ]
        })
        user_data['payments'] = list(payments)
        
        # Get course records
        courses = user_courses_collection.find({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ]
        })
        user_data['courses'] = list(courses)
        
        # Get paid categories
        user_data['paid_categories'] = get_user_paid_categories(email, index_number)
        
    except Exception as e:
        print(f"❌ Error getting user existing data: {str(e)}")
    
    return user_data

# --- Basket Database Functions ---
def save_user_basket(email, index_number, basket_data):
    """Save user basket to database with enhanced validation"""
    print(f"💾 Saving basket for {index_number} with {len(basket_data)} items")
    
    # Validate basket data
    if not isinstance(basket_data, list):
        print(f"⚠️ basket_data is not a list: {type(basket_data)}")
        basket_data = []
    
    # Clean up basket items - ensure they're serializable
    clean_basket = []
    for item in basket_data:
        if isinstance(item, dict):
            # Convert any non-serializable objects
            clean_item = {}
            for key, value in item.items():
                if isinstance(value, ObjectId):
                    clean_item[key] = str(value)
                elif isinstance(value, datetime):
                    clean_item[key] = value.isoformat()
                else:
                    clean_item[key] = value
            clean_basket.append(clean_item)
        else:
            print(f"⚠️ Skipping non-dict item: {type(item)}")
    
    if not database_connected:
        session['course_basket'] = clean_basket
        print(f"💾 Basket saved to session: {len(clean_basket)} items")
        return True
    
    basket_record = {
        'email': email,
        'index_number': index_number,
        'basket': clean_basket,
        'updated_at': datetime.now(),
        'is_active': True
    }
    
    try:
        # Check if record exists
        existing = user_baskets_collection.find_one({'index_number': index_number})
        
        if existing:
            # Update existing record
            result = user_baskets_collection.update_one(
                {'index_number': index_number},
                {'$set': {
                    'basket': clean_basket,
                    'updated_at': datetime.now(),
                    'is_active': True
                }}
            )
            print(f"✅ Updated basket in database for {index_number}")
        else:
            # Create new record
            basket_record['created_at'] = datetime.now()
            result = user_baskets_collection.insert_one(basket_record)
            print(f"✅ Created new basket in database for {index_number}")
        
        # Also update session
        session['course_basket'] = clean_basket
        session.modified = True
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving user basket: {str(e)}")
        # Fallback to session
        session['course_basket'] = clean_basket
        return False
def get_user_basket_by_index(index_number):
    """Get user basket from database by index number with enhanced error handling"""
    print(f"🛒 ENHANCED: Loading basket for index: {index_number}")
    
    # Initialize default return value
    processed_basket = []
    
    # Check if database is connected
    if not database_connected:
        print("ℹ️ Database not connected, using session basket")
        session_basket = session.get('course_basket')
        
        return validate_and_process_basket(session_basket, "session")
    
    # Database is connected - try to load from database with enhanced error handling
    try:
        print(f"🔍 Searching database for basket of index: {index_number}")
        basket_data = user_baskets_collection.find_one({
            'index_number': index_number,
            'is_active': True
        })
        
        if basket_data:
            print(f"✅ Found basket data in database for {index_number}")
            basket_items = basket_data.get('basket', [])
            
            processed_basket = validate_and_process_basket(basket_items, "database")
            
            # Update session with the database basket for consistency
            session['course_basket'] = processed_basket
            session.modified = True
            print("🔄 Updated session with database basket")
            
        else:
            print(f"ℹ️ No active basket found in database for {index_number}")
            # If no basket in database, check session as fallback
            session_basket = session.get('course_basket', [])
            processed_basket = validate_and_process_basket(session_basket, "session_fallback")
                
    except Exception as e:
        print(f"❌ Error getting user basket from database: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback to session basket on database error
        session_basket = session.get('course_basket', [])
        processed_basket = validate_and_process_basket(session_basket, "error_fallback")
    
    print(f"🎯 Final enhanced basket count: {len(processed_basket)} items")
    
    # Log basket contents for debugging
    if processed_basket:
        course_names = [item.get('programme_name', item.get('course_name', 'Unknown')) for item in processed_basket]
        print(f"📋 Basket contents: {course_names}")
    
    return processed_basket

def validate_and_process_basket(basket_data, source):
    """Validate and process basket data from any source"""
    print(f"🔧 Processing basket from {source}")
    
    if basket_data is None:
        print(f"⚠️ {source}: Basket data is None")
        return []
    
    if not isinstance(basket_data, list):
        print(f"⚠️ {source}: Basket is not a list, converting: {type(basket_data)}")
        if isinstance(basket_data, dict):
            basket_data = [basket_data]
        else:
            basket_data = []
    
    # Validate and process each item
    processed_items = []
    for item in basket_data:
        if isinstance(item, dict):
            # Ensure required fields exist
            if not (item.get('programme_name') or item.get('course_name')):
                print(f"⚠️ {source}: Skipping item missing name: {item}")
                continue
            
            if not (item.get('programme_code') or item.get('course_code')):
                print(f"⚠️ {source}: Skipping item missing code: {item}")
                continue
            
            # Ensure basket_id exists
            if 'basket_id' not in item:
                item['basket_id'] = str(ObjectId())
                print(f"🔧 {source}: Added missing basket_id")
            
            # Ensure added_at exists
            if 'added_at' not in item:
                item['added_at'] = datetime.now().isoformat()
                print(f"🔧 {source}: Added missing added_at")
            
            processed_items.append(item)
        else:
            print(f"⚠️ {source}: Skipping non-dict item: {type(item)}")
    
    print(f"✅ {source}: Processed {len(processed_items)} valid items from {len(basket_data)} original")
    return processed_items

def clear_user_basket(index_number):
    """Clear user basket from database without affecting session"""
    if database_connected:
        try:
            result = user_baskets_collection.update_one(
                {'index_number': index_number},
                {'$set': {
                    'basket': [],
                    'updated_at': datetime.now(),
                    'is_active': False
                }}
            )
            print(f"✅ Basket database record cleared for {index_number}")
            return True
        except Exception as e:
            print(f"❌ Error clearing user basket from database: {str(e)}")
            return False
    
    # Clear from session (only basket, not other data)
    if 'course_basket' in session:
        session['course_basket'] = []
        session.modified = True
    return True
# --- Routes ---
@app.route('/')
@cache.cached(timeout=3600, query_string=False)  # Cache homepage for 1 hour
def index():
    canonical = get_canonical_url('index')
    return render_template('index.html', 
                         title='KUCCPS Courses Checker | Home',
                         meta_description='Find KUCCPS courses that match your KCSE grades. Degree, Diploma, Certificate, KMTC, Artisan and TTC programs in Kenya.',
                         canonical_url=canonical)

# ============================================
# UNIQUE CONTENT HELPER FOR SEO
# ============================================

def get_unique_content_for_flow(flow):
    """Return unique content for each course flow to avoid duplicate content issues"""
    unique_content = {
        'degree': {
            'h1': 'KUCCPS University Degree Programs Qualification Checker',
            'intro': 'Find university degree programs matching your KCSE grades and cluster points.',
            'key_features': ['4-year programs', 'University education', 'Bachelor degrees', 'Research-focused']
        },
        'diploma': {
            'h1': 'KUCCPS Diploma & Technical Programs Qualification Checker',
            'intro': 'Find technical diploma programs matching your KCSE grades for 2-year college education.',
            'key_features': ['2-year programs', 'Technical colleges', 'Practical skills', 'Career-focused']
        },
        'kmtc': {
            'h1': 'KMTC Medical & Healthcare Programs Qualification Checker',
            'intro': 'Find Kenya Medical Training College healthcare programs matching your KCSE grades.',
            'key_features': ['Medical training', 'Healthcare careers', 'Clinical practice', 'Ministry of Health accredited']
        },
        'certificate': {
            'h1': 'KUCCPS Certificate Programs Qualification Checker',
            'intro': 'Find certificate programs matching your KCSE grades for vocational training.',
            'key_features': ['1-2 year programs', 'Vocational training', 'Skills development', 'Employment ready']
        },
        'artisan': {
            'h1': 'KUCCPS Artisan & Trade Programs Qualification Checker',
            'intro': 'Find artisan trade programs matching your KCSE grades for hands-on technical skills.',
            'key_features': ['Trade skills', 'Practical training', 'Self-employment', 'Technical crafts']
        },
        'ttc': {
            'h1': 'Teacher Training College (TTC) Programs Qualification Checker',
            'intro': 'Find teacher training programs matching your KCSE grades for education careers.',
            'key_features': ['Teacher education', 'Classroom training', 'Education diploma', 'Teaching practice']
        }
    }
    
    return unique_content.get(flow, unique_content['degree'])

@app.route('/degree')
@cache.cached(timeout=3600, query_string=False)  # Cache for 1 hour
def degree():
    canonical = get_canonical_url('degree')
    unique_content = get_unique_content_for_flow('degree')
    return render_template('degree.html',
                         title='KUCCPS Degree Courses | University Programs in Kenya',
                         meta_description='Find KUCCPS university degree programs in Kenya. Match your KCSE grades and cluster points with bachelor degree courses in engineering, medicine, business, education, and more.',
                         canonical_url=canonical,
                         unique_content=unique_content)

@app.route('/diploma')
@cache.cached(timeout=3600, query_string=False)  # Cache for 1 hour
def diploma():
    canonical = get_canonical_url('diploma')
    unique_content = get_unique_content_for_flow('diploma')
    return render_template('diploma.html',
                         title='KUCCPS Diploma Courses | Technical Programs in Kenya',
                         meta_description='Find KUCCPS diploma courses and technical programs in Kenya. Match your KCSE grades with 2-year diploma programs in engineering, business, IT, hospitality, and more.',
                         canonical_url=canonical,
                         unique_content=unique_content)

@app.route('/kmtc')
@cache.cached(timeout=3600, query_string=False)  # Cache for 1 hour
def kmtc():
    canonical = get_canonical_url('kmtc')
    unique_content = get_unique_content_for_flow('kmtc')
    return render_template('kmtc.html',
                         title='KMTC Courses | Kenya Medical Training College Programs',
                         meta_description='Browse KMTC medical courses and healthcare training programs available through KUCCPS. Find nursing, clinical medicine, lab technology programs matching your KCSE grades.',
                         canonical_url=canonical,
                         unique_content=unique_content)

@app.route('/certificate')
@cache.cached(timeout=3600, query_string=False)  # Cache for 1 hour
def certificate():
    canonical = get_canonical_url('certificate')
    unique_content = get_unique_content_for_flow('certificate')
    return render_template('certificate.html',
                         title='KUCCPS Certificate Courses | Vocational Programs in Kenya',
                         meta_description='Find KUCCPS certificate courses and vocational programs in Kenya. Match your KCSE grades with 1-2 year certificate programs in business, IT, hospitality, beauty, and skilled trades.',
                         canonical_url=canonical,
                         unique_content=unique_content)
@app.route('/artisan')
@cache.cached(timeout=3600, query_string=False)  # Cache for 1 hour
def artisan():
    canonical = get_canonical_url('artisan')
    unique_content = get_unique_content_for_flow('artisan')
    return render_template('artisan.html',
                         title='KUCCPS Artisan Courses | Skills Training in Kenya',
                         meta_description='Find KUCCPS artisan courses and vocational skills training programs in Kenya. Match your KCSE grades with practical trade programs in plumbing, electrical, carpentry, and more.',
                         canonical_url=canonical,
                         unique_content=unique_content)
@app.route('/results')
def results():
    canonical = get_canonical_url('results')
    return render_template('results.html',
                         title='KUCCPS Course Results | View Your Qualified Courses',
                         meta_description='View your KUCCPS qualified courses based on your KCSE grades. See degree, diploma, certificate, and artisan courses that match your results.',
                         canonical_url=canonical)

@app.route('/sitemap-courses.xml')
@cache.cached(timeout=86400)
def sitemap_courses():
    """Generate sitemap for course-related content (NOT main category pages)
    
    NOTE: Main course category pages (/degree, /diploma, /certificate, /artisan, /kmtc, /ttc)
    are already included in sitemap.xml to avoid duplication.
    This sitemap is reserved for course-specific subpages if needed in the future.
    """
    base_url = 'https://www.studentsplacement.co.ke'
    today = datetime.now().strftime('%Y-%m-%d')
    
    xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml_parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    # This sitemap is intentionally minimal to avoid duplicates with sitemap.xml
    # The main course category pages are in sitemap.xml
    # Add only course-specific subpages here if they are created in the future
    
    xml_parts.append('</urlset>')
    
    response = make_response('\n'.join(xml_parts))
    response.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return response
@app.route('/user-guide')
def userguide():
    canonical = get_canonical_url('userguide')
    return render_template('user-guide.html',
                         title='KUCCPS User Guide | How to Use This Platform',
                         meta_description='Learn how to use KUCCPS Courses Checker to find courses that match your KCSE grades. Step-by-step guide.',
                         canonical_url=canonical)

# --- Grade Submission Routes ---
@app.route('/submit-grades', methods=['POST'])
def submit_grades():
    try:
        form_data = request.form.to_dict()
        
        user_grades = {}
        for subject_name, subject_code in SUBJECTS.items():
            if subject_name in form_data and form_data[subject_name]:
                grade = form_data[subject_name].upper()
                if grade in GRADE_VALUES:
                    user_grades[subject_code] = grade
        
        user_cluster_points = {}
        for i in range(1, 21):
            cluster_key = f"cl{i}"
            if cluster_key in form_data and form_data[cluster_key]:
                try:
                    user_cluster_points[f"cluster_{i}"] = float(form_data[cluster_key])
                except ValueError:
                    user_cluster_points[f"cluster_{i}"] = 0.0
        
        session['degree_grades'] = user_grades
        session['degree_cluster_points'] = user_cluster_points
        session['degree_data_submitted'] = True
        return redirect(url_for('enter_details', flow='degree'))
        
    except Exception as e:
        print(f"❌ Error in submit_grades: {str(e)}")
        flash("An error occurred while processing your grades", "error")
        return redirect(url_for('degree'))
    
@app.route('/submit-ttc-grades', methods=['POST'])
def submit_ttc_grades():
    try:
        form_data = request.form.to_dict()
        
        user_mean_grade = form_data.get('overall', '').upper()
        if user_mean_grade not in GRADE_VALUES:
            flash("Please select a valid overall grade", "error")
            return redirect(url_for('ttc'))
        
        user_grades = {}
        for subject_name, subject_code in SUBJECTS.items():
            if subject_name in form_data and form_data[subject_name]:
                grade = form_data[subject_name].upper()
                if grade in GRADE_VALUES:
                    user_grades[subject_code] = grade
        
        # Enhanced session management
        session.permanent = True
        
        session['ttc_grades'] = user_grades
        session['ttc_mean_grade'] = user_mean_grade
        session['ttc_data_submitted'] = True
        
        session.modified = True
        
        print(f"✅ TTC grades submitted successfully: {user_mean_grade}")
        
        return redirect(url_for('enter_details', flow='ttc'))
        
    except Exception as e:
        print(f"❌ Error in submit_ttc_grades: {str(e)}")
        import traceback
        traceback.print_exc()
        flash("An error occurred while processing your request", "error")
        return redirect(url_for('ttc'))
@app.route('/ttc')
@cache.cached(timeout=3600, query_string=False)  # Cache for 1 hour
def ttc():
    canonical = get_canonical_url('ttc')
    unique_content = get_unique_content_for_flow('ttc')
    return render_template('ttc.html',
                         title='TTC Courses | Teacher Training Colleges in Kenya',
                         meta_description='Find KUCCPS teacher training college (TTC) programs in Kenya. Match your KCSE grades with 2-year education diploma programs for primary, secondary, and technical teacher training.',
                         canonical_url=canonical,
                         unique_content=unique_content)

@app.route('/submit-diploma-grades', methods=['POST'])
def submit_diploma_grades():
    try:
        form_data = request.form.to_dict()
        
        user_mean_grade = form_data.get('overall', '').upper()
        if user_mean_grade not in GRADE_VALUES:
            flash("Please select a valid overall grade", "error")
            return redirect(url_for('diploma'))
        
        user_grades = {}
        for subject_name, subject_code in SUBJECTS.items():
            if subject_name in form_data and form_data[subject_name]:
                grade = form_data[subject_name].upper()
                if grade in GRADE_VALUES:
                    user_grades[subject_code] = grade
        
        session['diploma_grades'] = user_grades
        session['diploma_mean_grade'] = user_mean_grade
        session['diploma_data_submitted'] = True
        return redirect(url_for('enter_details', flow='diploma'))
        
    except Exception as e:
        print(f"❌ Error in submit_diploma-grades: {str(e)}")
        flash("An error occurred while processing your request", "error")
        return redirect(url_for('diploma'))

@app.route('/submit-certificate-grades', methods=['POST'])
def submit_certificate_grades():
    try:
        form_data = request.form.to_dict()
        
        user_mean_grade = form_data.get('overall', '').upper()
        if user_mean_grade not in GRADE_VALUES:
            flash("Please select a valid overall grade", "error")
            return redirect(url_for('certificate'))
        
        user_grades = {}
        for subject_name, subject_code in SUBJECTS.items():
            if subject_name in form_data and form_data[subject_name]:
                grade = form_data[subject_name].upper()
                if grade in GRADE_VALUES:
                    user_grades[subject_code] = grade
        
        session['certificate_grades'] = user_grades
        session['certificate_mean_grade'] = user_mean_grade
        session['certificate_data_submitted'] = True
        return redirect(url_for('enter_details', flow='certificate'))
        
    except Exception as e:
        print(f"❌ Error in submit_certificate-grades: {str(e)}")
        flash("An error occurred while processing your request", "error")
        return redirect(url_for('certificate'))
    
@app.route('/submit-artisan-grades', methods=['POST'])
def submit_artisan_grades():
    try:
        form_data = request.form.to_dict()
        print(f"🛠️ Artisan form data received: {form_data}")  # Debug log
        
        # Validate overall grade first
        user_mean_grade = form_data.get('overall', '').upper()
        print(f"🛠️ Artisan mean grade: {user_mean_grade}")  # Debug log
        
        if user_mean_grade not in GRADE_VALUES:
            flash("Please select a valid overall grade", "error")
            print("❌ Invalid mean grade selected")  # Debug log
            return redirect(url_for('artisan'))
        
        # Process subject grades
        user_grades = {}
        for subject_name, subject_code in SUBJECTS.items():
            if subject_name in form_data and form_data[subject_name]:
                grade = form_data[subject_name].upper()
                if grade in GRADE_VALUES:
                    user_grades[subject_code] = grade
        
        print(f"🛠️ Artisan user grades: {user_grades}")  # Debug log
        
        # 🔥 CRITICAL FIX: Enhanced session management
        session.permanent = True  # Ensure session persists
        
        # Store data in session with explicit modification
        session['artisan_grades'] = user_grades
        session['artisan_mean_grade'] = user_mean_grade
        session['artisan_data_submitted'] = True
        
        # 🔥 CRITICAL: Force session save
        session.modified = True
        
        # Verify session data was saved
        print(f"🛠️ Session verification - artisan_data_submitted: {session.get('artisan_data_submitted')}")
        print(f"🛠️ Session verification - artisan_mean_grade: {session.get('artisan_mean_grade')}")
        print(f"🛠️ Session verification - artisan_grades keys: {len(session.get('artisan_grades', {}))}")
        
        # Double-check session persistence
        if not session.get('artisan_data_submitted'):
            print("❌ CRITICAL: Session data not persisted!")
            flash("Session error - please try again", "error")
            return redirect(url_for('artisan'))
        
        print("✅ Artisan grades submitted successfully, redirecting to enter_details")  
        
        # Redirect to enter_details with artisan flow
        return redirect(url_for('enter_details', flow='artisan'))
        
    except Exception as e:
        print(f"❌ Error in submit_artisan_grades: {str(e)}")
        import traceback
        traceback.print_exc()
        flash("An error occurred while processing your request", "error")
        return redirect(url_for('artisan'))
    
@app.route('/submit-kmtc-grades', methods=['POST'])
def submit_kmtc_grades():
    try:
        form_data = request.form.to_dict()
        
        user_mean_grade = form_data.get('overall', '').upper()
        if user_mean_grade not in GRADE_VALUES:
            flash("Please select a valid overall grade", "error")
            return redirect(url_for('kmtc'))
        
        user_grades = {}
        for subject_name, subject_code in SUBJECTS.items():
            if subject_name in form_data and form_data[subject_name]:
                grade = form_data[subject_name].upper()
                if grade in GRADE_VALUES:
                    user_grades[subject_code] = grade
        
        session['kmtc_grades'] = user_grades
        session['kmtc_mean_grade'] = user_mean_grade
        session['kmtc_data_submitted'] = True
        return redirect(url_for('enter_details', flow='kmtc'))
        
    except Exception as e:
        print(f"❌ Error in submit_kmtc-grades: {str(e)}")
        flash("An error occurred while processing your request", "error")
        return redirect(url_for('kmtc'))

# --- User Details and Payment Routes ---
# --- User Details and Payment Routes ---
@app.route('/enter-details/<flow>', methods=['GET', 'POST'])
def enter_details(flow):
    """Handle user details entry with strict validation and legitimate manual activation support."""
 
    # ── GET ──
    if request.method == 'GET':
        if not session.get(f'{flow}_data_submitted'):
            flash("Please submit your grades first", "error")
            return redirect(url_for(flow))
        return render_template('enter_details.html', flow=flow)
 
    # ── POST ──
    try:
        email        = request.form.get('email', '').strip().lower()
        index_number = request.form.get('index_number', '').strip()

        if not email or not index_number:
            flash("Email and KCSE Index Number are required.", "error")
            return redirect(url_for('enter_details', flow=flow))
 
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            flash("Invalid index number format (e.g. 12345678901/2024)", "error")
            return redirect(url_for('enter_details', flow=flow))
 
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for('enter_details', flow=flow))
 
        # ── Uniqueness check ──
        is_valid, msg = validate_user_uniqueness(email, index_number, flow)
        if not is_valid:
            flash(msg, "error")
            return redirect(url_for('enter_details', flow=flow))
 
        # ── Save grades to DB now (before payment) ──
        if flow == 'degree':
            save_user_grades_before_payment(
                email, index_number, flow,
                session.get('degree_grades', {}),
                cluster_points=session.get('degree_cluster_points', {})
            )
        elif flow == 'diploma':
            save_user_grades_before_payment(
                email, index_number, flow,
                session.get('diploma_grades', {}),
                session.get('diploma_mean_grade', '')
            )
        elif flow == 'certificate':
            save_user_grades_before_payment(
                email, index_number, flow,
                session.get('certificate_grades', {}),
                session.get('certificate_mean_grade', '')
            )
        elif flow == 'artisan':
            save_user_grades_before_payment(
                email, index_number, flow,
                session.get('artisan_grades', {}),
                session.get('artisan_mean_grade', '')
            )
        elif flow == 'kmtc':
            save_user_grades_before_payment(
                email, index_number, flow,
                session.get('kmtc_grades', {}),
                session.get('kmtc_mean_grade', '')
            )
        elif flow == 'ttc':
            save_user_grades_before_payment(
                email, index_number, flow,
                session.get('ttc_grades', {}),
                session.get('ttc_mean_grade', '')
            )
 
        # ══════════════════════════════════════════════════════
        # User verified payment but had no grades stored.
        # Grades just submitted → go straight to results, skip payment.
        # ══════════════════════════════════════════════════════
        if session.get(f'verified_no_grades_{flow}') and session.get(f'paid_{flow}'):
            print(f"✅ Verified-no-grades path: grades now saved, going to results for {flow}")
            session['email']         = email
            session['index_number']  = index_number
            session['current_flow']  = flow
            session['current_level'] = flow
            session.pop(f'verified_no_grades_{flow}', None)
            session.modified = True
            flash("✅ Grades submitted! Generating your results…", "success")
            return redirect(url_for('show_results', flow=flow))
 
        # ══════════════════════════════════════════════════════
        # STEP 1: Check for LEGITIMATE manual activation only
        # ══════════════════════════════════════════════════════
        activation_record    = None
        original_mpesa_receipt = None
 
        if is_legitimate_manual_activation(email, index_number):
            if database_connected and admin_activations_collection is not None:
                try:
                    activation_record = admin_activations_collection.find_one({
                        '$or': [{'email': email}, {'index_number': index_number}],
                        'is_active': True,
                        'status': 'active'
                    })
                    if activation_record:
                        original_mpesa_receipt = activation_record.get('mpesa_receipt')
                except Exception as e:
                    print(f"⚠️ Activation check error: {e}")
 
        if activation_record and original_mpesa_receipt:
            print(f"🎯 Legitimate manual activation found — bypassing payment for {flow}")
            session['manual_activation_active']  = True
            session['manual_activation_receipt'] = original_mpesa_receipt
            session['manual_activation_id']      = str(activation_record['_id'])
            session['email']          = email
            session['index_number']   = index_number
            session['current_flow']   = flow
            session['current_level']  = flow
            session[f'paid_{flow}']   = True
            session['mpesa_receipt']  = original_mpesa_receipt
            session['verified_receipt'] = original_mpesa_receipt
            session.modified = True
 
            create_manual_activation_payment(email, index_number, flow, original_mpesa_receipt)
            process_courses_after_payment(email, index_number, flow, original_mpesa_receipt)
 
            try:
                admin_activations_collection.update_one(
                    {'_id': activation_record['_id']},
                    {'$set': {
                        'used_for_flow': flow,
                        'used_at': datetime.now(),
                        'status': 'used'
                    }}
                )
            except Exception as e:
                print(f"⚠️ Could not mark activation as used: {e}")
 
            flash("✅ Access granted! Generating your courses…", "success")
            return redirect(url_for('payment_wait', flow=flow, transaction_ref='manual'))
 
        # ══════════════════════════════════════════════════════
        # STEP 2: Already paid? (Strict check - real payments only)
        # ══════════════════════════════════════════════════════
        if has_user_paid_for_category_strict(email, index_number, flow):
            paid = get_user_paid_categories_strict(email, index_number)
            flash(
                f"You have already paid for {flow.upper()} courses. "
                f"Paid categories: {', '.join(paid)}",
                "error"
            )
            return redirect(url_for('index'))
 
        # ══════════════════════════════════════════════════════
        # STEP 3: Normal payment flow
        # ══════════════════════════════════════════════════════
        existing    = get_user_paid_categories_strict(email, index_number)
        is_first    = len(existing) == 0
        amount      = 1 if is_first else 1
 
        session['email']            = email
        session['index_number']     = index_number
        session['current_flow']     = flow
        session['current_level']    = flow
        session['payment_amount']   = amount
        session['is_first_category'] = is_first
        session[f'paid_{flow}']     = False
        session.modified = True
 
        save_user_payment(email, index_number, flow, amount=amount)
 
        flash(
            f"{'First category' if is_first else 'Additional category'} price: Ksh {amount}",
            "info"
        )
        return redirect(url_for('payment', flow=flow))
 
    except Exception as e:
        print(f"❌ enter_details POST error: {e}")
        import traceback
        traceback.print_exc()
        flash("An error occurred while processing your request", "error")
        return redirect(url_for('enter_details', flow=flow))
@app.route('/debug/session')
def debug_session():
    """Debug route to check session status"""
    session_info = {
        'all_keys': list(session.keys()),
        'artisan_specific': {
            'artisan_data_submitted': session.get('artisan_data_submitted'),
            'artisan_grades': session.get('artisan_grades'),
            'artisan_mean_grade': session.get('artisan_mean_grade')
        },
        'session_id': session.sid if hasattr(session, 'sid') else 'N/A',
        'session_permanent': session.permanent
    }
    return jsonify(session_info)

@app.route('/admin/activations')
def admin_activations():
    """View all manual activations"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        activations_data = []
        
        if database_connected and admin_activations_collection is not None:
            activations = list(admin_activations_collection.find().sort('activated_at', -1))
            
            for activation in activations:
                activation_data = {
                    'email': activation.get('email', 'N/A'),
                    'index_number': activation.get('index_number', 'N/A'),
                    'mpesa_receipt': activation.get('mpesa_receipt', 'N/A'),
                    'activation_type': activation.get('activation_type', 'manual'),
                    'activated_by': activation.get('activated_by', 'N/A'),
                    'activated_at': activation.get('activated_at', 'N/A'),
                    'is_active': activation.get('is_active', False),
                    'status': activation.get('status', 'unknown'),
                    'used_for_flow': activation.get('used_for_flow', 'Not used'),
                    'used_at': activation.get('used_at', 'N/A')
                }
                activations_data.append(activation_data)
        
        return render_template('admin_activations.html', activations=activations_data)
        
    except Exception as e:
        print(f"❌ Error loading admin activations: {str(e)}")
        flash("Error loading activation data", "error")
        return render_template('admin_activations.html', activations=[])
    

@app.route('/payment/<flow>', methods=['GET', 'POST'])
def payment(flow):
    """Payment page - accepts both GET and POST requests"""
    
    # Handle GET request - display payment page
    if request.method == 'GET':
        # Check if user has submitted grades and details
        if not session.get('email') or not session.get('index_number'):
            flash("Please complete the previous steps first", "error")
            return redirect(url_for('enter_details', flow=flow))
        
        # Check if grades data is submitted for this flow
        if not session.get(f'{flow}_data_submitted'):
            flash("Please submit your grades first", "error")
            return redirect(url_for(flow))
        
        # Get payment amount from session
        amount = session.get('payment_amount', 1)
        is_first_category = session.get('is_first_category', False)
        
        print(f"💰 Payment page for {flow} - Amount: {amount}, First category: {is_first_category}")
        
        return render_template('payment.html', 
                             flow=flow, 
                             amount=amount,
                             is_first_category=is_first_category)
    
    # Handle POST request - process payment
    elif request.method == 'POST':
        if not session.get('email') or not session.get('index_number'):
            return {'success': False, 'error': 'Session data missing'}, 400

        phone = request.form.get('phone', '').strip()
        if not phone:
            return {'success': False, 'error': 'Phone number is required for payment.'}, 400

        # Get the dynamic amount from session
        amount = session.get('payment_amount', 1)
        email = session.get('email')
        index_number = session.get('index_number')
        
        print(f"💳 Processing payment for {flow}, amount: {amount}, phone: {phone}")
        
        # 🔥 CRITICAL: Force session save and re-save grades before payment
        session.modified = True
        session.permanent = True
        
        # Re-save grades to ensure they're in database (in case session expires)
        if email and index_number:
            print(f"💾 Re-saving grades to database before payment for {flow}")
            if flow == 'degree':
                user_grades = session.get('degree_grades', {})
                user_cluster_points = session.get('degree_cluster_points', {})
                save_user_grades_before_payment(email, index_number, flow, user_grades, cluster_points=user_cluster_points)
            elif flow == 'diploma':
                user_grades = session.get('diploma_grades', {})
                user_mean_grade = session.get('diploma_mean_grade', '')
                save_user_grades_before_payment(email, index_number, flow, user_grades, user_mean_grade)
            elif flow == 'certificate':
                user_grades = session.get('certificate_grades', {})
                user_mean_grade = session.get('certificate_mean_grade', '')
                save_user_grades_before_payment(email, index_number, flow, user_grades, user_mean_grade)
            elif flow == 'artisan':
                user_grades = session.get('artisan_grades', {})
                user_mean_grade = session.get('artisan_mean_grade', '')
                save_user_grades_before_payment(email, index_number, flow, user_grades, user_mean_grade)
            elif flow == 'kmtc':
                user_grades = session.get('kmtc_grades', {})
                user_mean_grade = session.get('kmtc_mean_grade', '')
                save_user_grades_before_payment(email, index_number, flow, user_grades, user_mean_grade)
            elif flow == 'ttc':
                user_grades = session.get('ttc_grades', {})
                user_mean_grade = session.get('ttc_mean_grade', '')
                save_user_grades_before_payment(email, index_number, flow, user_grades, user_mean_grade)
        
        # 🔥 PASS THE FLOW PARAMETER to initiate_stk_push
        result = initiate_stk_push(phone, amount=amount, flow=flow)
        
        if result.get('ResponseCode') == '0':
            transaction_ref = result.get('CheckoutRequestID')
            
            # Note: Payment confirmation is now handled in initiate_stk_push
            # No need to call update_transaction_ref again here

            return {
                'success': True,
                'ResponseCode': '0', 
                'transaction_ref': transaction_ref,
                'amount': amount,
                'redirect_url': url_for('payment_wait', flow=flow, transaction_ref=transaction_ref)
            }

        error_message = result.get('errorDescription') or result.get('errorMessage') or 'Failed to initiate payment. Try again.'
        return {'success': False, 'error': error_message}, 400
@app.route('/payment-wait/<flow>')
def payment_wait(flow):
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        flash("Session expired. Please start again.", "error")
        return redirect(url_for('enter_details', flow=flow))
    
    amount = session.get('payment_amount', 1)
    transaction_ref = request.args.get('transaction_ref', '')
    
    # If no transaction_ref in URL, try to get from session or DB
    if not transaction_ref:
        session_ref = session.get('transaction_ref')
        if session_ref:
            transaction_ref = session_ref
        elif database_connected and user_payments_collection is not None:
            try:
                payment = user_payments_collection.find_one({
                    'email': email,
                    'index_number': index_number,
                    'level': flow
                }, {'transaction_ref': 1})
                if payment and payment.get('transaction_ref'):
                    transaction_ref = payment['transaction_ref']
                    session['transaction_ref'] = transaction_ref
            except Exception:
                pass
    
    # ============================================
    # CHECK DATABASE FOR CONFIRMED PAYMENT
    # ============================================
    if database_connected and user_payments_collection is not None:
        try:
            payment = user_payments_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': flow,
                'payment_confirmed': True
            })
            if payment:
                print(f"✅ Payment already confirmed in DB, redirecting to results for {email}")
                
                # Update session
                session[f'paid_{flow}'] = True
                session['current_flow'] = flow
                session['current_level'] = flow
                if payment.get('mpesa_receipt'):
                    session['mpesa_receipt'] = payment['mpesa_receipt']
                    session['verified_receipt'] = payment['mpesa_receipt']
                session.modified = True
                
                # Queue course processing
                process_courses_after_payment(email, index_number, flow, payment.get('mpesa_receipt'))
                
                # 🔥 CRITICAL: Use redirect with 302 status to force browser to actually navigate
                return redirect(url_for('goto_results', flow=flow), code=302)
        except Exception as e:
            print(f"⚠️ payment_wait DB check error: {e}")
    
    # Check manual activation
    if is_legitimate_manual_activation(email, index_number):
        session[f'paid_{flow}'] = True
        session['current_flow'] = flow
        session['current_level'] = flow
        session.modified = True
        process_courses_after_payment(email, index_number, flow)
        return redirect(url_for('goto_results', flow=flow), code=302)
    
    # If already confirmed in session, redirect
    if session.get(f'paid_{flow}'):
        return redirect(url_for('goto_results', flow=flow), code=302)
    
    return render_template(
        'payment_wait.html',
        flow=flow,
        email=email,
        index_number=index_number,
        transaction_ref=transaction_ref,
        amount=amount
    )

@app.route('/check-courses-ready/<flow>')
def check_courses_ready(flow):
    """Poll endpoint — returns ready=True the MOMENT payment is confirmed anywhere"""
    email = session.get('email')
    index_number = session.get('index_number')

    if not email or not index_number:
        return jsonify({
            'ready': False,
            'error': True,
            'message': 'Session expired',
            'should_redirect': True,
            'redirect_url': url_for('index')
        })

    cache_key = f"{email}_{index_number}_{flow}"

    # ══════════════════════════════════════════════════════
    # PRIORITY 1: Database confirmed payment (MOST RELIABLE)
    # ══════════════════════════════════════════════════════
    if database_connected and user_payments_collection is not None:
        try:
            # Look for ANY confirmed payment for this user+level
            payment = user_payments_collection.find_one({
                '$or': [
                    {'email': email, 'index_number': index_number, 'level': flow},
                    {'index_number': index_number, 'level': flow}  # fallback
                ],
                'payment_confirmed': True
            }, {'mpesa_receipt': 1, 'transaction_ref': 1})

            if payment:
                # PAYMENT IS CONFIRMED — always return ready, no exceptions
                session[f'paid_{flow}'] = True
                session['current_flow'] = flow
                session['current_level'] = flow
                if payment.get('mpesa_receipt'):
                    session['mpesa_receipt'] = payment['mpesa_receipt']
                    session['verified_receipt'] = payment['mpesa_receipt']
                session.modified = True

                # Queue course generation (idempotent — won't duplicate)
                process_courses_after_payment(
                    email, index_number, flow, payment.get('mpesa_receipt')
                )

                return jsonify({
                    'ready': True,
                    'paid': True,
                    'redirect_url': url_for('goto_results', flow=flow),
                    'status': 'db_confirmed',
                    'message': 'Payment confirmed! Redirecting...'
                })
        except Exception as e:
            print(f"⚠️ check_courses_ready DB error: {e}")

    # ══════════════════════════════════════════════════════
    # PRIORITY 2: Memory cache — courses already generated
    # ══════════════════════════════════════════════════════
    status_data = course_processing_status.get(cache_key, {})
    if isinstance(status_data, dict) and status_data.get('status') == 'completed':
        _sync_session_after_completion(email, index_number, flow)
        return jsonify({
            'ready': True,
            'paid': True,
            'redirect_url': url_for('goto_results', flow=flow),
            'status': 'memory_completed',
            'message': 'Courses ready! Redirecting...'
        })

    # ══════════════════════════════════════════════════════
    # PRIORITY 3: Session says paid but DB doesn't confirm yet
    # ══════════════════════════════════════════════════════
    if session.get(f'paid_{flow}'):
        return jsonify({
            'ready': False,
            'processing': True,
            'message': 'Payment confirmed, generating courses...',
            'status': 'session_paid_processing'
        })

    # ══════════════════════════════════════════════════════
    # PRIORITY 4: Pending transaction still waiting for callback
    # ══════════════════════════════════════════════════════
    if database_connected and user_payments_collection is not None:
        try:
            pending = user_payments_collection.find_one({
                '$or': [
                    {'email': email, 'index_number': index_number, 'level': flow},
                    {'index_number': index_number, 'level': flow}
                ],
                'transaction_ref': {'$exists': True, '$ne': None},
                'payment_confirmed': False
            }, {'created_at': 1})

            if pending:
                created_at = pending.get('created_at')
                elapsed = (datetime.now() - created_at).total_seconds() if created_at else 0
                
                if elapsed > 120:
                    return jsonify({
                        'ready': False,
                        'status': 'timeout',
                        'message': 'Payment is taking longer than expected. Check your M-Pesa messages.',
                        'should_retry': True
                    })
                
                return jsonify({
                    'ready': False,
                    'status': 'pending',
                    'message': 'Waiting for M-Pesa confirmation...',
                    'check_again': 1800
                })
        except Exception as e:
            print(f"⚠️ Pending check error: {e}")

    # ══════════════════════════════════════════════════════
    # FALLBACK: Nothing found yet
    # ══════════════════════════════════════════════════════
    return jsonify({
        'ready': False,
        'status': 'waiting',
        'message': 'Waiting for payment confirmation on your phone...',
        'check_again': 1800
    })
@app.route('/force-check-payment/<flow>')
def force_check_payment(flow):
    """Emergency endpoint to recover stuck payments"""
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        return jsonify({'success': False, 'error': 'No session'})
    
    if database_connected and user_payments_collection is not None:
        # Try exact match first
        payment = user_payments_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': flow,
            'payment_confirmed': True
        })
        
        # Fallback: any confirmed payment for this index/level
        if not payment:
            payment = user_payments_collection.find_one({
                'index_number': index_number,
                'level': flow,
                'payment_confirmed': True
            })
        
        if payment:
            session[f'paid_{flow}'] = True
            session['current_flow'] = flow
            session['current_level'] = flow
            session['mpesa_receipt'] = payment.get('mpesa_receipt')
            session.modified = True
            
            process_courses_after_payment(
                email, index_number, flow, payment.get('mpesa_receipt')
            )
            
            return jsonify({
                'success': True,
                'found': True,
                'redirect_url': url_for('goto_results', flow=flow)
            })
    
    return jsonify({'success': True, 'found': False})
def _sync_session_after_completion(email, index_number, flow):
    """Helper: set session flags after courses are confirmed ready."""
    session[f'paid_{flow}']  = True
    session['current_flow']  = flow
    session['current_level'] = flow
 
    # Grab receipt for display (best-effort, non-blocking)
    if not session.get('mpesa_receipt') and database_connected and user_payments_collection is not None:
        try:
            p = user_payments_collection.find_one(
                {'email': email, 'index_number': index_number, 'level': flow},
                {'mpesa_receipt': 1}
            )
            if p and p.get('mpesa_receipt'):
                session['mpesa_receipt']    = p['mpesa_receipt']
                session['verified_receipt'] = p['mpesa_receipt']
        except Exception:
            pass
 
    session.modified = True
 
@app.route('/goto-results/<flow>')
def goto_results(flow):
    email        = session.get('email')
    index_number = session.get('index_number')
 
    if not email or not index_number:
        flash("Session expired. Please start again.", "error")
        return redirect(url_for('index'))
 
    # ── Try DB confirmed payment first ──
    if database_connected and user_payments_collection is not None:
        try:
            p = user_payments_collection.find_one(
                {'email': email, 'index_number': index_number,
                 'level': flow, 'payment_confirmed': True},
                {'mpesa_receipt': 1}
            )
            if p:
                session[f'paid_{flow}']  = True
                session['current_flow']  = flow
                session['current_level'] = flow
                if p.get('mpesa_receipt'):
                    session['mpesa_receipt']    = p['mpesa_receipt']
                    session['verified_receipt'] = p['mpesa_receipt']
                session.modified = True
                return redirect(url_for('show_results', flow=flow))
        except Exception as e:
            print(f"⚠️  goto_results DB: {e}")
 
    # ── Session paid flag ──
    if session.get(f'paid_{flow}'):
        session['current_flow']  = flow
        session['current_level'] = flow
        session.modified = True
        return redirect(url_for('show_results', flow=flow))
 
    # ── LEGITIMATE manual activation only (not automatic) ──
    if is_legitimate_manual_activation(email, index_number):
        session[f'paid_{flow}']  = True
        session['current_flow']  = flow
        session['current_level'] = flow
        session.modified = True
        return redirect(url_for('show_results', flow=flow))
 
    flash("Payment not confirmed yet. Please complete the M-Pesa payment.", "warning")
    return redirect(url_for('payment', flow=flow))
 
@app.route('/test-gemini')
def test_gemini():
    """Test if Gemini is working"""
    test_messages = [
        "What courses can I do with C plain?",
        "How much does it cost for diploma?",
        "What are cluster points?"
    ]
    
    results = {}
    
    for msg in test_messages:
        start_time = time.time()
        try:
            response = get_gemini_response(msg)
        except Exception as e:
            response = None
        elapsed = time.time() - start_time
        
        results[msg] = {
            'success': response is not None,
            'response': response if response else 'Failed',
            'response_length': len(response) if response else 0,
            'time_taken': f"{elapsed:.2f}s"
        }
    
    return jsonify({
        'api_key_configured': bool(GEMINI_API_KEY),
        'api_key_preview': GEMINI_API_KEY[:10] + '...' if GEMINI_API_KEY else None,
        'calls_today': gemini_calls_today,
        'daily_limit': MAX_GEMINI_DAILY,
        'cache_size': len(gemini_response_cache),
        'results': results
    })

@app.route('/gemini-stats')
def gemini_stats():
    """View Gemini usage statistics"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({
        'calls_today': gemini_calls_today,
        'daily_limit': MAX_GEMINI_DAILY,
        'remaining': MAX_GEMINI_DAILY - gemini_calls_today,
        'cache_size': len(gemini_response_cache),
        'cache_keys': list(gemini_response_cache.keys())[:10],  # First 10 for preview
        'reset_date': str(gemini_calls_today_reset)
    })
@app.route('/api/chat', methods=['POST'])
def chat_api():
    """API endpoint for chatbot interactions"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({
                'success': False,
                'error': 'No message provided'
            }), 400

        # Add a small delay to prevent rate limiting
        time.sleep(1)
        
        # Get chatbot response
        response = get_chatbot_response(user_message)

        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"❌ Error in chat API: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'response': 'Sorry, I encountered an error. Please try again.'
        }), 500
    
@app.route('/chat')
def chat():
    """AI Chatbot page"""
    canonical = get_canonical_url('chat')
    return render_template('chat.html',
                         title='AI Course Assistant | KUCCPS Courses Checker',
                         meta_description='Chat with our AI assistant to get instant answers about KUCCPS courses, admission requirements, and course selection guidance.',
                         canonical_url=canonical)

@app.route('/debug-gemini-key')
def debug_gemini_key():
    """Debug Gemini API key and connection (updated for new API)"""
    try:
        if not GEMINI_API_KEY:
            return jsonify({'error': 'API key not configured'}), 500
        
        # Use the new client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # List available models
        models = client.models.list()
        
        available_models = []
        for model in models:
            available_models.append(model.name)
        
        return jsonify({
            'api_key_configured': True,
            'api_key_preview': GEMINI_API_KEY[:10] + '...',
            'available_models': available_models[:10],
            'total_models_found': len(available_models),
            'message': 'API key is valid and working with new API!'
        })
    except Exception as e:
        return jsonify({
            'api_key_configured': True,
            'error': str(e),
            'error_type': type(e).__name__,
            'suggestion': 'Check your API key and ensure the new google-genai package is installed'
        }), 500

@app.route('/check-payment-status/<flow>')
def check_payment_status(flow):
    email        = session.get('email')
    index_number = session.get('index_number')
 
    if not email or not index_number:
        return jsonify({'paid': False, 'error': 'Session missing', 'status': 'session_missing'})
 
    # ── 1. Session cache ──
    if session.get(f'paid_{flow}'):
        return jsonify({
            'paid':         True,
            'redirect_url': url_for('goto_results', flow=flow),
            'status':       'session_cache',
            'message':      'Payment confirmed! Loading your courses…'
        })
 
    # ── 2. In-memory status map ──
    cache_key   = f"{email}_{index_number}_{flow}"
    status_data = course_processing_status.get(cache_key, {})
    if isinstance(status_data, dict) and status_data.get('status') in ('pending', 'processing', 'completed'):
        session[f'paid_{flow}']  = True
        session['current_flow']  = flow
        session['current_level'] = flow
        session.modified = True
        return jsonify({
            'paid':         True,
            'redirect_url': url_for('goto_results', flow=flow),
            'status':       'processing_map',
            'message':      'Payment confirmed! Generating courses…'
        })
 
    # ── 3. DB confirmed payment ──
    if database_connected and user_payments_collection is not None:
        try:
            p = user_payments_collection.find_one(
                {
                    'email': email,
                    'index_number': index_number,
                    'level': flow,
                    'payment_confirmed': True
                },
                {'mpesa_receipt': 1}
            )
            if p:
                session[f'paid_{flow}']  = True
                session['current_flow']  = flow
                session['current_level'] = flow
                if p.get('mpesa_receipt'):
                    session['mpesa_receipt']    = p['mpesa_receipt']
                    session['verified_receipt'] = p['mpesa_receipt']
                session.modified = True
                process_courses_after_payment(
                    email, index_number, flow, p.get('mpesa_receipt')
                )
                return jsonify({
                    'paid':         True,
                    'redirect_url': url_for('goto_results', flow=flow),
                    'status':       'db_confirmed',
                    'message':      'Payment confirmed! Generating courses…'
                })
        except Exception as e:
            print(f"⚠️ check_payment_status DB: {e}")
 
    # ── 4. LEGITIMATE manual activation only (not automatic) ──
    if is_legitimate_manual_activation(email, index_number):
        session[f'paid_{flow}']  = True
        session['current_flow']  = flow
        session['current_level'] = flow
        session.modified = True
        process_courses_after_payment(email, index_number, flow)
        return jsonify({
            'paid':         True,
            'redirect_url': url_for('goto_results', flow=flow),
            'status':       'manual_activation',
            'message':      'Access confirmed! Processing courses…'
        })
 
    # ── 5. Pending transaction timeout check ──
    if database_connected and user_payments_collection is not None:
        try:
            pending = user_payments_collection.find_one(
                {
                    'email': email,
                    'index_number': index_number,
                    'level': flow,
                    'payment_confirmed': False,
                    'transaction_ref': {'$exists': True, '$ne': None}
                },
                {'created_at': 1}
            )
            if pending:
                created_at = pending.get('created_at')
                if created_at and (datetime.now() - created_at).total_seconds() > 90:
                    return jsonify({
                        'paid':         False,
                        'status':       'timeout',
                        'message':      'Payment is taking longer than expected. Check your M-Pesa messages.',
                        'should_retry': True
                    })
                return jsonify({
                    'paid':        False,
                    'status':      'pending',
                    'message':     'Waiting for M-Pesa confirmation…',
                    'check_again': True,
                    'check_delay': 1200
                })
        except Exception:
            pass
 
    return jsonify({
        'paid':        False,
        'status':      'not_found',
        'message':     'Waiting for M-Pesa confirmation on your phone…',
        'check_delay': 1200
    })
@app.route('/admin/verify-payment-only/<issue_id>', methods=['POST'])
def verify_payment_only(issue_id):
    """Verify ONLY if payment exists in database - no course checking"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        if not database_connected or user_payments_collection is None:
            return jsonify({'success': False, 'error': 'Database not connected'})
        
        from bson import ObjectId
        obj_id = ObjectId(issue_id)
        
        issue = payment_issues_collection.find_one({'_id': obj_id, 'status': 'pending'})
        
        if not issue:
            return jsonify({'success': False, 'error': 'Issue not found or already processed'})
        
        email = issue.get('email')
        index_number = issue.get('index_number')
        mpesa_receipt = issue.get('mpesa_receipt')
        
        # Check if payment exists in database
        payment_found = False
        payment_data = None
        
        if user_payments_collection is not None:
            payment_data = user_payments_collection.find_one({
                '$or': [
                    {'mpesa_receipt': mpesa_receipt},
                    {'email': email, 'index_number': index_number}
                ],
                'payment_confirmed': True
            })
            payment_found = payment_data is not None
        
        if payment_found:
            # Update the issue status
            payment_issues_collection.update_one(
                {'_id': obj_id},
                {'$set': {
                    'status': 'verified',
                    'payment_verified': True,
                    'payment_verified_at': datetime.now(),
                    'payment_verified_by': session.get('admin_username', 'admin'),
                    'verified_payment_data': {
                        'level': payment_data.get('level'),
                        'amount': payment_data.get('payment_amount'),
                        'payment_date': str(payment_data.get('payment_date')) if payment_data.get('payment_date') else None
                    }
                }}
            )
            
            return jsonify({
                'success': True,
                'payment_found': True,
                'message': f'Payment verified! Found in database (Receipt: {mpesa_receipt})',
                'payment_details': {
                    'level': payment_data.get('level'),
                    'amount': payment_data.get('payment_amount')
                }
            })
        else:
            return jsonify({
                'success': True,
                'payment_found': False,
                'message': f'No payment found with receipt {mpesa_receipt}'
            })
            
    except Exception as e:
        print(f"❌ Error verifying payment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/batch-verify-payments', methods=['POST'])
def batch_verify_payments():
    """Batch verify all pending payment issues - payment only, no courses"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        if not database_connected or payment_issues_collection is None:
            return jsonify({'success': False, 'error': 'Database not connected'})
        
        # Get all pending issues
        pending_issues = list(payment_issues_collection.find({'status': 'pending'}))
        
        processed_count = 0
        verified_count = 0
        not_found_count = 0
        
        for issue in pending_issues:
            processed_count += 1
            email = issue.get('email')
            index_number = issue.get('index_number')
            mpesa_receipt = issue.get('mpesa_receipt')
            
            if not email or not index_number or not mpesa_receipt:
                not_found_count += 1
                continue
            
            # Check if payment exists in database
            payment_found = False
            
            if user_payments_collection is not None:
                payment = user_payments_collection.find_one({
                    '$or': [
                        {'mpesa_receipt': mpesa_receipt},
                        {'email': email, 'index_number': index_number}
                    ],
                    'payment_confirmed': True
                })
                payment_found = payment is not None
            
            if payment_found:
                # Update issue status
                payment_issues_collection.update_one(
                    {'_id': issue['_id']},
                    {'$set': {
                        'status': 'verified',
                        'payment_verified': True,
                        'payment_verified_at': datetime.now(),
                        'payment_verified_by': 'batch_processor'
                    }}
                )
                verified_count += 1
                print(f"✅ Verified payment for {email} - Receipt: {mpesa_receipt}")
            else:
                not_found_count += 1
                print(f"⚠️ No payment found for {email} - Receipt: {mpesa_receipt}")
        
        return jsonify({
            'success': True,
            'processed': processed_count,
            'verified': verified_count,
            'not_found': not_found_count,
            'message': f'Processed {processed_count} issues. Verified {verified_count}. No payment found for {not_found_count}.'
        })
        
    except Exception as e:
        print(f"❌ Error in batch verify: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
@app.route('/ultra-fast-check/<flow>')
def ultra_fast_check(flow):
    """ULTRA-FAST endpoint for instant payment confirmation"""
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        return jsonify({'success': False, 'paid': False, 'error': 'No session'})
    
    # STEP 1: Check session cache (INSTANT)
    if session.get(f'paid_{flow}'):
        return jsonify({
            'success': True,
            'paid': True,
            'redirect': url_for('show_results', flow=flow),
            'reason': 'session_cache',
            'instant': True
        })
    
    # STEP 2: Check memory cache (FAST)
    cache_key = f"{email}_{index_number}_{flow}"
    if cache_key in course_processing_cache:
        cache_data = course_processing_cache[cache_key]
        if isinstance(cache_data, dict):
            status = cache_data.get('status')
            if status == 'completed':
                # Update session
                session[f'paid_{flow}'] = True
                return jsonify({
                    'success': True,
                    'paid': True,
                    'redirect': url_for('show_results', flow=flow),
                    'reason': 'memory_cache_completed',
                    'instant': True
                })
            elif status == 'processing':
                return jsonify({
                    'success': True,
                    'paid': False,
                    'processing': True,
                    'message': 'Courses being processed...',
                    'check_again': 1000  # Check in 1 second
                })
    
    # STEP 3: Quick database check (FAST with projection)
    if database_connected:
        try:
            # Ultra-fast query with only _id field
            payment_data = user_payments_collection.find_one(
                {
                    'email': email,
                    'index_number': index_number,
                    'level': flow,
                    'payment_confirmed': True
                },
                {'_id': 1}  # Only need to know if it exists
            )
            
            if payment_data:
                # Update session and cache
                session[f'paid_{flow}'] = True
                course_processing_cache[cache_key] = {
                    'status': 'processing',
                    'started_at': datetime.now().isoformat()
                }
                return jsonify({
                    'success': True,
                    'paid': True,
                    'redirect': url_for('show_results', flow=flow),
                    'reason': 'database_confirmed',
                    'instant': True
                })
        except Exception as e:
            print(f"⚠️ Ultra-fast DB error: {e}")
    
    # STEP 4: Check for pending transaction (for UI updates)
    if database_connected:
        try:
            pending = user_payments_collection.find_one(
                {
                    'email': email,
                    'index_number': index_number,
                    'level': flow,
                    'transaction_ref': {'$exists': True, '$ne': None},
                    'payment_confirmed': False
                },
                {'transaction_ref': 1}
            )
            
            if pending:
                return jsonify({
                    'success': True,
                    'paid': False,
                    'pending': True,
                    'message': 'Waiting for M-Pesa confirmation...',
                    'check_again': 1000  # Check in 1 second
                })
        except Exception as e:
            print(f"⚠️ Pending check error: {e}")
    
    # No payment found yet
    return jsonify({
        'success': True,
        'paid': False,
        'message': 'Payment not yet confirmed',
        'check_again': 2000  # Check in 2 seconds
    })
def ultra_fast_process_courses(email, index_number, flow):
    """Ultra-fast course processing that runs in under 1 second"""
    try:
        # Check cache first
        cache_key = f"{email}_{index_number}_{flow}"
        if cache_key in course_processing_cache:
            cache_data = course_processing_cache[cache_key]
            if isinstance(cache_data, dict) and cache_data.get('status') == 'completed':
                return True
        
        print(f"⚡ Ultra-fast processing for {flow}")
        
        # Get qualifying courses
        qualifying_courses = []
        
        if flow == 'degree':
            user_grades = session.get('degree_grades', {})
            user_cluster_points = session.get('degree_cluster_points', {})
            if user_grades and user_cluster_points:
                qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
        
        elif flow == 'diploma':
            user_grades = session.get('diploma_grades', {})
            user_mean_grade = session.get('diploma_mean_grade', '')
            if user_grades and user_mean_grade:
                qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
        
        elif flow == 'certificate':
            user_grades = session.get('certificate_grades', {})
            user_mean_grade = session.get('certificate_mean_grade', '')
            if user_grades and user_mean_grade:
                qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
        
        elif flow == 'artisan':
            user_grades = session.get('artisan_grades', {})
            user_mean_grade = session.get('artisan_mean_grade', '')
            if user_grades and user_mean_grade:
                qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
        
        elif flow == 'kmtc':
            user_grades = session.get('kmtc_grades', {})
            user_mean_grade = session.get('kmtc_mean_grade', '')
            if user_grades and user_mean_grade:
                qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
        
        elif flow == 'ttc':
            user_grades = session.get('ttc_grades', {})
            user_mean_grade = session.get('ttc_mean_grade', '')
            if user_grades and user_mean_grade:
                qualifying_courses = get_qualifying_ttc(user_grades, user_mean_grade)
        
        # Save to database if we have courses
        if qualifying_courses:
            try:
                save_user_courses(email, index_number, flow, qualifying_courses)
                print(f"⚡ Saved {len(qualifying_courses)} courses")
            except Exception as e:
                print(f"⚠️ Error saving courses: {e}")
                # Still mark as success
        
        # Update cache
        course_processing_cache[cache_key] = {
            'status': 'completed',
            'courses_count': len(qualifying_courses),
            'completed_at': datetime.now().isoformat(),
            'ultra_fast': True
        }
        
        # Update session
        session[f'paid_{flow}'] = True
        
        return True
        
    except Exception as e:
        print(f"❌ Ultra-fast processing error: {e}")
        return False
# --- MPesa Callback Routes ---
@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """
    Returns 200 to Safaricom in < 50ms.
    All work happens in a daemon thread.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
 
    threading.Thread(
        target=_process_mpesa_callback,
        args=(data,),
        daemon=True
    ).start()
 
    return {'ResultCode': 0, 'ResultDesc': 'Accepted'}, 200
 
 
def _process_mpesa_callback(data):
    """
    Runs in daemon thread. Confirms payment in DB then queues
    course processing. Never blocks the HTTP response.
    """
    try:
        stk         = data.get('Body', {}).get('stkCallback', {})
        txn_ref     = stk.get('CheckoutRequestID')
        result_code = stk.get('ResultCode')
 
        if result_code != 0 or not txn_ref:
            print(f"⚠️ Callback: result_code={result_code}, no action")
            return
 
        # Extract receipt and amount
        mpesa_receipt = None
        amount        = None
        for item in stk.get('CallbackMetadata', {}).get('Item', []):
            name = item.get('Name')
            if name == 'MpesaReceiptNumber':
                mpesa_receipt = item.get('Value')
            elif name == 'Amount':
                amount = item.get('Value')
 
        if not mpesa_receipt:
            print("⚠️ Callback: no receipt in metadata")
            return
 
        if not database_connected:
            print("⚠️ Callback: DB not connected, cannot confirm payment")
            return
 
        # ── Single DB write ──
        result = user_payments_collection.update_one(
            {'transaction_ref': txn_ref},
            {'$set': {
                'payment_confirmed': True,
                'mpesa_receipt':     mpesa_receipt,
                'payment_amount':    amount,
                'payment_date':      datetime.now(),
                'callback_received': True,
                'callback_time':     datetime.now()
            }}
        )
 
        if result.modified_count == 0:
            print(f"⚠️ Callback: no payment record for txn_ref={txn_ref}")
            return
 
        print(f"✅ Payment confirmed in DB: {mpesa_receipt}")
 
        # ── Single projection read ──
        payment = user_payments_collection.find_one(
            {'transaction_ref': txn_ref},
            {'email': 1, 'index_number': 1, 'level': 1}
        )
        if not payment:
            return
 
        email        = payment.get('email')
        index_number = payment.get('index_number')
        flow         = payment.get('level')
 
        if not (email and index_number and flow):
            print("⚠️ Callback: payment record missing email/index/level")
            return
 
        # ── Queue processing (deduplication handled inside) ──
        process_courses_after_payment(email, index_number, flow, mpesa_receipt)
 
        # 🔥 REMOVED: Backup activation record block
        # Users will ONLY get access to the specific category they paid for
 
    except Exception as e:
        print(f"❌ Callback processing error: {e}")
        import traceback
        traceback.print_exc()
 
 
def send_consolidated_results_email(email, index_number, mpesa_receipt):
    """Send consolidated email with all paid categories"""
    try:
        # Get all paid categories for this user
        all_courses_by_level = {}
        total_courses = 0
        
        if database_connected:
            levels = ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']
            
            for level in levels:
                courses_data = user_courses_collection.find_one({
                    'email': email,
                    'index_number': index_number,
                    'level': level
                })
                
                if courses_data and courses_data.get('courses'):
                    all_courses_by_level[level] = courses_data['courses']
                    total_courses += len(courses_data['courses'])
        
        if total_courses > 0:
            print(f"📧 Sending consolidated email with {total_courses} courses across {len(all_courses_by_level)} levels")
            
            # Generate PDF with all courses
            pdf_buffer = generate_courses_pdf(
                email=email,
                index_number=index_number,
                courses_by_level=all_courses_by_level,
                total_courses=total_courses,
                mpesa_receipt=mpesa_receipt
            )
            
            # Send email
            success = send_courses_report(
                email=email,
                index_number=index_number,
                courses_by_level=all_courses_by_level,
                total_courses=total_courses,
                mpesa_receipt=mpesa_receipt,
                pdf_buffer=pdf_buffer
            )
            
            if success:
                print(f"✅ Consolidated email sent to {email}")
                # Mark email as sent
                email_sent_key = f"email_sent_{email}_{index_number}"
                session[email_sent_key] = True
            else:
                print(f"⚠️ Failed to send consolidated email to {email}")
        else:
            print(f"⚠️ No courses found to send in consolidated email for {email}")
            
    except Exception as e:
        print(f"❌ Error in _send_consolidated_results_email: {e}")
        import traceback
        traceback.print_exc()
@app.route('/about')
def about():
    """About page"""
    canonical = get_canonical_url('about')
    return render_template('about.html',
                         title='About KUCCPS Courses Checker | Our Mission',
                         meta_description='Learn about KUCCPS Courses Checker - helping Kenyan students find suitable university, college, and technical courses based on KCSE results.',
                         canonical_url=canonical)


@app.route('/mpesa/confirmation', methods=['POST'])
def mpesa_confirmation():
    data = request.get_json(force=True)
    trans_id = data.get('TransID')
    account = data.get('BillRefNumber')
    
    if account:
        mark_payment_confirmed_by_account(account, trans_id)
    
    return {'ResultCode': 0, 'ResultDesc': 'Accepted'}

@app.route('/mpesa/validation', methods=['POST'])
def mpesa_validation():
    return {
        "ResultCode": 0,
        "ResultDesc": "Accepted"
    }

# --- Results Display Routes ---
@app.route('/results/<flow>')
def show_results(flow):
    """Display results — courses generated on-the-fly, never stored in DB."""
    from bson import ObjectId
 
    print(f"🎯 show_results called for flow: {flow}")
 
    email        = session.get('email')
    index_number = session.get('index_number')
 
    # ── Try to recover from manual activation ID ──
    if not email or not index_number:
        manual_id = session.get('manual_activation_id')
        if manual_id and database_connected and admin_activations_collection is not None:
            try:
                activation = admin_activations_collection.find_one({'_id': ObjectId(manual_id)})
                if activation and activation.get('is_legitimate_manual', False):
                    email        = activation.get('email')
                    index_number = activation.get('index_number')
                    session.clear()
                    session['email']          = email
                    session['index_number']   = index_number
                    session[f'paid_{flow}']   = True
                    session['current_flow']   = flow
                    session['current_level']  = flow
                    session['initialized']    = True
                    session['last_activity']  = datetime.now().isoformat()
                    session.modified = True
                else:
                    flash("Session expired. Please start again.", "error")
                    return redirect(url_for('index'))
            except Exception as e:
                print(f"❌ Recovery failed: {e}")
                flash("Session expired. Please start again.", "error")
                return redirect(url_for('index'))
        else:
            flash("Session expired. Please start again.", "error")
            return redirect(url_for('index'))
 
    # ── Access verification with LEGITIMATE manual activation only ──
    has_access = False
 
    # Check 1: Session paid flag
    if session.get(f'paid_{flow}'):
        has_access = True
 
    # Check 2: Database confirmed payment (real payment)
    if not has_access and database_connected and user_payments_collection is not None:
        try:
            payment = user_payments_collection.find_one({
                '$or': [{'email': email}, {'index_number': index_number}],
                'level': flow,
                'payment_confirmed': True
            })
            if payment:
                has_access = True
                session[f'paid_{flow}'] = True
                session.modified = True
        except Exception as e:
            print(f"⚠️ Error checking payment: {e}")
 
    # Check 3: LEGITIMATE manual activation only (not automatic)
    if not has_access and is_legitimate_manual_activation(email, index_number):
        has_access = True
        session[f'paid_{flow}'] = True
        # Get activation details for session
        if database_connected and admin_activations_collection is not None:
            try:
                activation = admin_activations_collection.find_one({
                    '$or': [{'email': email}, {'index_number': index_number}],
                    'is_active': True,
                    'status': 'active'
                })
                if activation:
                    session['manual_activation_id'] = str(activation['_id'])
                    session['manual_activation_receipt'] = activation.get('mpesa_receipt')
            except Exception as e:
                print(f"⚠️ Error getting activation details: {e}")
        session.modified = True
 
    # Check 4: Verified payment from "Already Made Payment" button
    if not has_access and session.get('verified_payment') and session.get('verified_index') == index_number:
        has_access = True
        session[f'paid_{flow}'] = True
        session.modified = True
 
    if not has_access:
        flash('Please complete payment to view your results.', 'error')
        return redirect(url_for('payment', flow=flow) if flow else url_for('index'))
 
    # ── Mark manual activation as used (once) - ONLY for legitimate ones ──
    activation_id = session.get('manual_activation_id')
    if activation_id and database_connected and admin_activations_collection is not None:
        try:
            act = admin_activations_collection.find_one({'_id': ObjectId(activation_id)})
            if act and act.get('is_active') and act.get('status') == 'active' and act.get('is_legitimate_manual', False):
                admin_activations_collection.update_one(
                    {'_id': ObjectId(activation_id)},
                    {'$set': {
                        'is_active': False,
                        'used_for_flow': flow,
                        'used_at': datetime.now(),
                        'status': 'used'
                    }}
                )
                session.pop('manual_activation_id', None)
                session.modified = True
        except Exception as e:
            print(f"⚠️ Error marking activation used: {e}")
 
    # ══════════════════════════════════════════════════════
    # CORE: get courses from memory → re-generate if needed
    # NEVER reads user_courses_collection
    # ══════════════════════════════════════════════════════
    qualifying_courses = []
 
    # 1. Check in-memory status map first (fastest path)
    cache_key   = f"{email}_{index_number}_{flow}"
    status_data = course_processing_status.get(cache_key, {})
    if isinstance(status_data, dict) and status_data.get('status') == 'completed':
        qualifying_courses = status_data.get('courses', [])
        print(f"✅ Loaded {len(qualifying_courses)} courses from in-memory cache")
 
    # 2. Re-generate from saved grades if not in memory
    if not qualifying_courses:
        print(f"🔄 Not in memory — re-generating from saved grades for {flow}")
        user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(
            email, index_number, flow
        )
 
        # Also try session grades as fallback
        if not user_grades:
            if flow == 'degree':
                user_grades         = session.get('degree_grades', {})
                user_cluster_points = session.get('degree_cluster_points', {})
            elif flow == 'diploma':
                user_grades      = session.get('diploma_grades', {})
                user_mean_grade  = session.get('diploma_mean_grade', '')
            elif flow == 'certificate':
                user_grades      = session.get('certificate_grades', {})
                user_mean_grade  = session.get('certificate_mean_grade', '')
            elif flow == 'artisan':
                user_grades      = session.get('artisan_grades', {})
                user_mean_grade  = session.get('artisan_mean_grade', '')
            elif flow == 'kmtc':
                user_grades      = session.get('kmtc_grades', {})
                user_mean_grade  = session.get('kmtc_mean_grade', '')
            elif flow == 'ttc':
                user_grades      = session.get('ttc_grades', {})
                user_mean_grade  = session.get('ttc_mean_grade', '')
 
        if user_grades:
            qualifying_courses = _generate_courses_for_flow(
                flow, user_grades, user_mean_grade, user_cluster_points
            )
            # Cache in memory for this session
            course_processing_status[cache_key] = {
                'status': 'completed',
                'courses': qualifying_courses,
                'courses_count': len(qualifying_courses),
                'completed_at': datetime.now()
            }
            print(f"✅ Re-generated {len(qualifying_courses)} courses")
        else:
            print(f"⚠️ No grades available for {flow} — cannot generate courses")
 
    # ── Ensure codes are strings ──
    for course in qualifying_courses:
        _stringify_course_codes(course)
        if '_id' in course and isinstance(course.get('_id'), ObjectId):
            course['_id'] = str(course['_id'])
 
    if not qualifying_courses:
        flash(f"No {flow.upper()} courses found. Please try again.", "warning")
        return redirect(url_for('index'))
 
    # ── Group by collection for display ──
    courses_by_collection = {}
    for course in qualifying_courses:
        if flow == 'degree':
            collection_key  = course.get('cluster', 'Other')
            collection_name = CLUSTER_NAMES.get(collection_key, collection_key)
        else:
            collection_key  = course.get('collection', 'Other')
            collection_name = collection_key.replace('_', ' ').title()
 
        if collection_key not in courses_by_collection:
            courses_by_collection[collection_key] = {'name': collection_name, 'courses': []}
        courses_by_collection[collection_key]['courses'].append(course)
 
    session['current_level'] = flow
    session['current_flow']  = flow
    session.modified = True
 
    print(f"🎯 Displaying {len(qualifying_courses)} courses for {flow}")
 
    return render_template(
        'collection_results.html',
        courses=qualifying_courses,
        courses_by_collection=courses_by_collection,
        user_grades={},
        user_mean_grade=None,
        user_cluster_points={},
        subjects=SUBJECTS,
        email=email,
        index_number=index_number,
        flow=flow,
        cluster_names=CLUSTER_NAMES
    )
# --- Collection-based Results Routes ---
@app.route('/collection-courses/<flow>/<collection_name>')
def show_collection_courses(flow, collection_name):
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        flash("Please complete the qualification process first", "error")
        return redirect(url_for('index'))
    
    user_payment = get_user_payment(email, index_number, flow)
    if not user_payment or not user_payment.get('payment_confirmed'):
        flash('Please complete payment to view your results.', 'error')
        return redirect(url_for('payment', flow=flow))

    user_courses_data = get_user_courses_data(email, index_number, flow)
    if user_courses_data and user_courses_data.get('courses'):
        qualifying_courses = user_courses_data['courses']
    else:
        if flow == 'degree':
            user_grades = session.get('degree_grades', {})
            user_cluster_points = session.get('degree_cluster_points', {})
            qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
        elif flow == 'diploma':
            user_grades = session.get('diploma_grades', {})
            user_mean_grade = session.get('diploma_mean_grade', '')
            qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
        elif flow == 'certificate':
            user_grades = session.get('certificate_grades', {})
            user_mean_grade = session.get('certificate_mean_grade', '')
            qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
        elif flow == 'artisan':
            user_grades = session.get('artisan_grades', {})
            user_mean_grade = session.get('artisan_mean_grade', '')
            qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
        elif flow == 'kmtc':
            user_grades = session.get('kmtc_grades', {})
            user_mean_grade = session.get('kmtc_mean_grade', '')
            qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
        elif flow == 'ttc':
            user_grades = session.get('ttc_grades', {})
            user_mean_grade = session.get('ttc_mean_grade', '')
            qualifying_courses = get_qualifying_ttc(user_grades, user_mean_grade)

        else:
            qualifying_courses = []
    
    collection_courses = [course for course in qualifying_courses if course.get('collection') == collection_name]
    
    return render_template('collection_courses.html',
                         flow=flow,
                         collection_name=collection_name,
                         courses=collection_courses,
                         email=email,
                         index_number=index_number)

# --- Payment Verification Routes ---
@app.route('/verify-payment', methods=['POST'])
def verify_payment():
    """Verify payment and redirect to results (re-generates courses from grades)."""
    try:
        mpesa_receipt = request.form.get('mpesa_receipt', '').strip().upper()
        index_number  = request.form.get('index_number', '').strip()
 
        if not mpesa_receipt or not index_number:
            return jsonify({'success': False, 'error': 'M-Pesa receipt and index number are required'})
 
        if len(mpesa_receipt) != 10 or not mpesa_receipt.isalnum():
            return jsonify({'success': False,
                            'error': 'Invalid M-Pesa receipt. Must be 10 alphanumeric characters.'})
 
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            return jsonify({'success': False,
                            'error': 'Invalid index number format (e.g. 12345678901/2024)'})
 
        print(f"🔍 Verifying payment: index={index_number} receipt={mpesa_receipt}")
 
        # ── Find confirmed payment ──
        payment_found  = False
        paid_levels    = []
        email          = None
 
        if database_connected and user_payments_collection is not None:
            payments = list(user_payments_collection.find({
                'index_number': index_number,
                'mpesa_receipt': mpesa_receipt,
                'payment_confirmed': True
            }))
            if payments:
                payment_found = True
                email = payments[0].get('email', '')
                for p in payments:
                    lvl = p.get('level')
                    if lvl and lvl not in paid_levels:
                        paid_levels.append(lvl)
 
        if not payment_found:
            return jsonify({'success': False,
                            'error': 'No confirmed payment found with these details.'})
 
        # ── For each paid level, check whether grades exist ──
        # We'll redirect to the FIRST level's results (or grades page if no grades)
        target_flow = paid_levels[0] if paid_levels else None
        if not target_flow:
            return jsonify({'success': False, 'error': 'No course level found for this payment.'})
 
        # Check grades for target_flow
        user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(
            email, index_number, target_flow
        )
 
        # Restore minimal session
        session['email']           = email
        session['index_number']    = index_number
        session['verified_payment'] = True
        session['verified_index']   = index_number
        session['verified_receipt'] = mpesa_receipt
        session['mpesa_receipt']    = mpesa_receipt
        for lvl in paid_levels:
            session[f'paid_{lvl}'] = True
        session['current_flow']  = target_flow
        session['current_level'] = target_flow
        session.modified = True
 
        if user_grades:
            # Grades exist → go straight to results (will re-generate)
            print(f"✅ Grades exist for {target_flow}, redirecting to results")
            return jsonify({
                'success': True,
                'payment_confirmed': True,
                'levels': paid_levels,
                'redirect_url': url_for('show_results', flow=target_flow)
            })
        else:
            # No grades → redirect to grade-entry page for this flow
            # Mark session so grade-entry skips payment
            session[f'verified_no_grades_{target_flow}'] = True
            session[f'{target_flow}_data_submitted'] = False
            session.modified = True
            print(f"⚠️ No grades found for {target_flow}, redirecting to grade entry")
            return jsonify({
                'success': True,
                'payment_confirmed': True,
                'no_grades': True,
                'levels': paid_levels,
                'redirect_url': url_for(target_flow),   # e.g. /diploma, /kmtc …
                'message': (
                    f'Payment verified! Please re-enter your {target_flow.upper()} grades '
                    f'to view your results (you will NOT be charged again).'
                )
            })
 
    except Exception as e:
        print(f"❌ Error verifying payment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Internal server error. Please try again.'})
 

@app.route('/verified-dashboard')
def verified_results_dashboard():
    """Dashboard for all course levels available for a verified payment."""
    index_number = request.args.get('index')
    receipt      = request.args.get('receipt')
 
    if not index_number or not receipt:
        flash("Invalid verification parameters", "error")
        return redirect(url_for('index'))
 
    print(f"📊 Loading verified dashboard for index: {index_number}")
 
    # Find the real email associated with the payment
    real_email = f"verified_{index_number}@temp.com"
    if database_connected and user_payments_collection is not None:
        try:
            p = user_payments_collection.find_one(
                {'index_number': index_number, 'mpesa_receipt': receipt},
                {'email': 1}
            )
            if p and p.get('email'):
                real_email = p['email']
        except Exception:
            pass
 
    # Build info for each paid level (check grades existence, not courses)
    user_courses_info = {}     # level → {'count': N, 'has_grades': bool}
    total_courses     = 0
 
    levels_to_check = ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']
 
    for level in levels_to_check:
        # Check if payment exists for this level
        has_payment = False
        if database_connected and user_payments_collection is not None:
            try:
                p = user_payments_collection.find_one({
                    'index_number': index_number,
                    'mpesa_receipt': receipt,
                    'level': level,
                    'payment_confirmed': True
                })
                has_payment = p is not None
            except Exception:
                pass
 
        if not has_payment:
            continue
 
        # Check grades
        g, m, cp = get_user_grades_from_db(real_email, index_number, level)
        has_grades = bool(g)
 
        # Estimate count from in-memory cache if available
        cache_key   = f"{real_email}_{index_number}_{level}"
        status_data = course_processing_status.get(cache_key, {})
        count       = status_data.get('courses_count', 0) if isinstance(status_data, dict) else 0
 
        if has_grades and count == 0:
            # Quick generation to get count
            courses = _generate_courses_for_flow(level, g, m, cp)
            count   = len(courses)
            course_processing_status[cache_key] = {
                'status': 'completed',
                'courses': courses,
                'courses_count': count,
                'completed_at': datetime.now()
            }
 
        user_courses_info[level] = {
            'count': count,
            'has_grades': has_grades
        }
        total_courses += count
 
    if not user_courses_info:
        flash("No course results found for your payment details", "error")
        return redirect(url_for('index'))
 
    # Restore session
    session['verified_payment'] = True
    session['verified_index']   = index_number
    session['verified_receipt'] = receipt
    session['email']            = real_email
    session['index_number']     = index_number
    for lvl in user_courses_info:
        session[f'paid_{lvl}'] = True
 
    basket = get_user_basket_by_index(index_number)
    session['course_basket'] = basket
 
    return render_template(
        'verified_dashboard.html',
        user_courses=user_courses_info,
        index_number=index_number,
        receipt=receipt,
        total_courses=total_courses,
        basket_count=len(basket)
    )
 

@app.route('/verified-results/<level>')
def show_verified_level_results(level):
    """Show verified results for a specific course level — re-generated."""
    index_number = request.args.get('index')
    receipt      = request.args.get('receipt')
 
    if level not in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
        flash("Invalid course level", "error")
        return redirect(url_for('index'))
 
    if not index_number or not receipt:
        flash("Invalid verification parameters", "error")
        return redirect(url_for('index'))
 
    # Restore session
    session['current_level']  = level
    session['email']          = f"verified_{index_number}@temp.com"
    session['index_number']   = index_number
    session['verified_payment'] = True
    session[f'paid_{level}']  = True
    session.modified = True
 
    email = f"verified_{index_number}@temp.com"
 
    # ── Get grades from DB ──
    user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(
        email, index_number, level
    )
 
    # Also check with the real email (payment records may have real email)
    if not user_grades and database_connected and user_payments_collection is not None:
        try:
            p = user_payments_collection.find_one(
                {'index_number': index_number, 'mpesa_receipt': receipt},
                {'email': 1}
            )
            if p and p.get('email'):
                real_email = p['email']
                user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(
                    real_email, index_number, level
                )
                if user_grades:
                    session['email'] = real_email
                    session.modified = True
                    email = real_email
        except Exception:
            pass
 
    if not user_grades:
        # Redirect to grade entry; mark as verified-no-grades
        session[f'verified_no_grades_{level}'] = True
        session[f'{level}_data_submitted'] = False
        session.modified = True
        flash(
            f"Payment verified! Please enter your {level.upper()} grades to view your results "
            f"(you will NOT be charged again).",
            "info"
        )
        return redirect(url_for(level))
 
    # ── Re-generate ──
    cache_key   = f"{email}_{index_number}_{level}"
    status_data = course_processing_status.get(cache_key, {})
    if isinstance(status_data, dict) and status_data.get('status') == 'completed':
        qualifying_courses = status_data.get('courses', [])
    else:
        qualifying_courses = _generate_courses_for_flow(
            level, user_grades, user_mean_grade, user_cluster_points
        )
        course_processing_status[cache_key] = {
            'status': 'completed',
            'courses': qualifying_courses,
            'courses_count': len(qualifying_courses),
            'completed_at': datetime.now()
        }
 
    if not qualifying_courses:
        flash(f"No {level} course results found. Please try again.", "error")
        return redirect(url_for('verified_results_dashboard', index=index_number, receipt=receipt))
 
    # Stringify codes and ids
    for course in qualifying_courses:
        _stringify_course_codes(course)
        if '_id' in course and isinstance(course.get('_id'), ObjectId):
            course['_id'] = str(course['_id'])
 
    # Group by collection
    courses_by_collection = {}
    for course in qualifying_courses:
        if level == 'degree':
            ck   = course.get('cluster', 'Other')
            cname = CLUSTER_NAMES.get(ck, ck)
        else:
            ck    = course.get('collection', 'Other')
            cname = ck.replace('_', ' ').title()
        if ck not in courses_by_collection:
            courses_by_collection[ck] = {'name': cname, 'courses': []}
        courses_by_collection[ck]['courses'].append(course)
 
    print(f"✅ Loaded {len(qualifying_courses)} {level} courses (verified user, re-generated)")
 
    return render_template(
        'collection_results.html',
        courses=qualifying_courses,
        courses_by_collection=courses_by_collection,
        user_grades={}, user_mean_grade=None, user_cluster_points={},
        subjects=SUBJECTS,
        email=email,
        index_number=index_number,
        flow=level,
        cluster_names=CLUSTER_NAMES
    )
 
 

# --- Course Basket Routes ---
@app.route('/add-to-basket', methods=['POST'])
def add_to_basket():
    """Add course to basket - FIXED VERSION for all categories"""
    try:
        course_data = request.get_json()
        print(f"📥 Received course data: {course_data.get('programme_name', 'Unknown')}")
        
        # Get user identification
        email = session.get('email')
        index_number = session.get('index_number')
        
        # For verified users (via "Already Made Payment" button)
        if not index_number:
            index_number = session.get('verified_index')
            if index_number:
                email = f"verified_{index_number}@temp.com"
                print(f"🔑 Using verified user: {index_number}")
        
        # Get current level from multiple possible sources
        current_level = session.get('current_level') or session.get('current_flow')
        
        # Also check if course data has level
        if not current_level and course_data.get('level'):
            current_level = course_data.get('level')
        
        # Last resort - try to infer from session
        if not current_level:
            for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
                if session.get(f'paid_{level}') or session.get(f'{level}_data_submitted'):
                    current_level = level
                    break
        
        print(f"📂 Current level: {current_level}")
        print(f"👤 User: {email}, Index: {index_number}")
        
        # Initialize basket if needed
        if 'course_basket' not in session:
            session['course_basket'] = []
            print("🆕 Created new basket in session")
        
        basket = session['course_basket']
        
        # Ensure basket is a list
        if not isinstance(basket, list):
            print(f"⚠️ Basket was {type(basket)}, converting to list")
            if isinstance(basket, dict):
                basket = [basket] if basket else []
            else:
                basket = []
            session['course_basket'] = basket
        
        # Get course code for duplicate checking
        course_code = course_data.get('programme_code') or course_data.get('course_code')
        if not course_code:
            print(f"⚠️ No course code found in data: {course_data.keys()}")
            # Try to generate a unique ID from course name if no code
            course_code = str(hash(course_data.get('programme_name', '')))
        
        # Check for duplicates
        existing_course = None
        for item in basket:
            item_code = item.get('programme_code') or item.get('course_code')
            if item_code and item_code == course_code:
                existing_course = item
                break
        
        if existing_course:
            print(f"⚠️ Course already in basket: {course_code}")
            return jsonify({
                'success': False,
                'error': 'Course already in basket',
                'basket_count': len(basket)
            })
        
        # Prepare course data for storage
        basket_item = {
            'basket_id': str(ObjectId()),
            'added_at': datetime.now().isoformat(),
            'level': current_level,
            'programme_name': course_data.get('programme_name') or course_data.get('course_name', 'Unknown Course'),
            'programme_code': course_code,
            'institution_name': course_data.get('institution_name', 'Not Specified'),
            'cut_off_points': course_data.get('cut_off_points'),
            'minimum_grade': course_data.get('minimum_grade'),
            'minimum_subject_requirements': course_data.get('minimum_subject_requirements', {}),
            'duration': course_data.get('duration'),
            'cluster': course_data.get('cluster'),
            'collection': course_data.get('collection')
        }
        
        # Add to basket
        basket.append(basket_item)
        session['course_basket'] = basket
        session.modified = True
        
        print(f"✅ Added course to basket. Total: {len(basket)}")
        
        # Save to database if user is identified
        if index_number:
            saved = save_user_basket(email, index_number, basket)
            print(f"💾 Database save {'successful' if saved else 'failed'}")
        
        return jsonify({
            'success': True,
            'basket_count': len(basket),
            'message': 'Course added to basket successfully',
            'basket_id': basket_item['basket_id']
        })
        
    except Exception as e:
        print(f"❌ Error adding to basket: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'basket_count': len(session.get('course_basket', []))
        }), 500

@app.route('/remove-from-basket', methods=['POST'])
def remove_from_basket():
    """Remove a specific course from user's basket"""
    try:
        data = request.get_json()
        basket_id = data.get('basket_id')
        
        if not basket_id:
            return jsonify({'success': False, 'error': 'No basket ID provided'})
        
        # Get user info
        email = session.get('email')
        index_number = session.get('index_number')
        
        # For verified users, get from verified_index
        if not index_number:
            index_number = session.get('verified_index')
            if index_number:
                email = f"verified_{index_number}@temp.com"
        
        if not index_number:
            return jsonify({'success': False, 'error': 'User not identified'})
        
        print(f"🗑️ Removing item {basket_id} from basket for user: {index_number}")
        
        # Remove from session first
        basket_count = 0
        if 'course_basket' in session:
            session['course_basket'] = [course for course in session['course_basket'] 
                                      if course.get('basket_id') != basket_id]
            basket_count = len(session['course_basket'])
            session.modified = True
            print(f"✅ Removed from session. New count: {basket_count}")
        
        # Remove from database
        if database_connected:
            try:
                # Get current basket from database
                basket_data = user_baskets_collection.find_one({
                    'index_number': index_number,
                    'is_active': True
                })
                
                if basket_data and 'basket' in basket_data:
                    # Filter out the item to remove
                    updated_basket = [course for course in basket_data['basket'] 
                                    if course.get('basket_id') != basket_id]
                    
                    # Update database
                    result = user_baskets_collection.update_one(
                        {'index_number': index_number},
                        {'$set': {
                            'basket': updated_basket,
                            'updated_at': datetime.now()
                        }}
                    )
                    
                    basket_count = len(updated_basket)
                    print(f"✅ Removed from database. New count: {basket_count}")
                    
                    # Update session with the database state
                    session['course_basket'] = updated_basket
                    
            except Exception as db_error:
                print(f"❌ Error removing from database: {db_error}")
                # If database fails, we still have the session updated
        
        return jsonify({
            'success': True, 
            'message': 'Course removed from basket',
            'basket_count': basket_count
        })
        
    except Exception as e:
        print(f"❌ Error removing from basket: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    

@app.route('/clear-basket', methods=['POST'])
def clear_basket():
    try:
        print("🛒 Starting ENHANCED basket clearing process...")
        
        # Get user identification first
        email = session.get('email')
        index_number = session.get('index_number')
        
        # For verified users, get from verified_index
        if not index_number:
            index_number = session.get('verified_index')
            if index_number:
                email = f"verified_{index_number}@temp.com"
        
        if not index_number:
            print("❌ No user identified for basket clearing")
            return jsonify({
                'success': False,
                'error': 'User not identified'
            })
        
        print(f"🗑️ Clearing basket for user: {index_number}")
        
        # 🔥 ENHANCED: Create comprehensive backup of ALL session data
        session_backup = dict(session)  # Create a full copy of session
        
        print(f"🔐 Backed up ALL session data: {len(session_backup)} keys")
        print(f"📋 Session keys backed up: {list(session_backup.keys())}")
        
        # Clear from database first (if connected)
        db_cleared = False
        if database_connected:
            try:
                result = user_baskets_collection.update_one(
                    {'index_number': index_number},
                    {'$set': {
                        'basket': [],
                        'updated_at': datetime.now(),
                        'is_active': False
                    }}
                )
                if result.modified_count > 0:
                    print("✅ Basket cleared from database")
                    db_cleared = True
                else:
                    print("ℹ️ No basket found in database to clear")
            except Exception as db_error:
                print(f"❌ Error clearing basket from database: {db_error}")
        
        # Clear from session - CAREFULLY preserve all other data
        if 'course_basket' in session:
            # Only clear the basket, preserve everything else
            old_basket = session.get('course_basket', [])
            print(f"🗑️ Clearing {len(old_basket)} items from session basket")
            
            session['course_basket'] = []
            session.modified = True
            print("✅ Basket cleared from session")
        
        # 🔥 CRITICAL: Verify and restore ALL session data
        restored_keys = 0
        for key, value in session_backup.items():
            # Skip the basket itself since we just cleared it
            if key == 'course_basket':
                continue
            
            # Restore all other session data
            if key not in session or session[key] != value:
                session[key] = value
                restored_keys += 1
        
        print(f"🔄 Restored {restored_keys} session keys")
        
        # 🔥 EXTRA VERIFICATION: Ensure paid categories are preserved
        paid_categories = []
        for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
            if session_backup.get(f'paid_{level}'):
                session[f'paid_{level}'] = True
                paid_categories.append(level)
        
        print(f"💰 Verified paid categories: {paid_categories}")
        
        # Final verification
        final_basket = session.get('course_basket', [])
        final_count = len(final_basket)
        
        print(f"🎯 Final basket count: {final_count} items")
        print(f"✅ Enhanced basket clearing completed successfully")
        
        return jsonify({
            'success': True,
            'message': 'Basket cleared successfully',
            'basket_count': final_count,
            'paid_categories_preserved': len(paid_categories)
        })
        
    except Exception as e:
        print(f"❌ Error in enhanced basket clearing: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Emergency restoration - clear everything and restore from backup if possible
        try:
            if 'session_backup' in locals():
                session.clear()
                for key, value in session_backup.items():
                    session[key] = value
                print("🆘 Emergency session restoration completed")
        except:
            print("💥 Critical: Emergency restoration failed")
        
        return jsonify({
            'success': False,
            'error': f'Basket clearing failed: {str(e)}'
        }), 500
@app.route('/basket')
def view_basket():
    """Display basket page - only accessible via verified payment or results"""
    try:
        print("🛒 ENHANCED: Accessing basket page...")
        
        # Get user identification
        email = session.get('email')
        index_number = session.get('index_number')
        
        # For verified users, get from verified_index
        if not index_number:
            index_number = session.get('verified_index')
            if index_number:
                email = f"verified_{index_number}@temp.com"
        
        if not index_number:
            print("🚫 No user identified for basket access")
            flash("Please browse your qualified courses first to use the basket", "warning")
            return redirect(url_for('index'))
        
        print(f"👤 User identified: {index_number}")
        
        # Load basket from appropriate source
        basket = []
        
        # Priority 1: Database (for verified users)
        if session.get('verified_payment') or database_connected:
            basket = get_user_basket_by_index(index_number)
            print(f"🛒 Loaded basket from database: {len(basket)} items")
        
        # Priority 2: Session fallback
        if not basket:
            session_basket = session.get('course_basket', [])
            basket = validate_and_process_basket(session_basket, "session_final")
            print(f"🛒 Loaded basket from session: {len(basket)} items")
        
        # Check access permissions
        has_paid_access = any(session.get(f'paid_{level}') for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc'])
        has_verified_access = session.get('verified_payment')
        has_basket_items = len(basket) > 0
        
        print(f"🔑 Access check - Paid: {has_paid_access}, Verified: {has_verified_access}, Basket items: {has_basket_items}")
        
        if not (has_paid_access or has_verified_access or has_basket_items):
            print("🚫 No access - user hasn't paid and basket is empty")
            flash("Please browse your qualified courses first or verify your payment to use the basket", "warning")
            return redirect(url_for('index'))
        
        print(f"✅ Granting basket access to user")
        
        # Final processing of basket items
        processed_basket = []
        for item in basket:
            if isinstance(item, dict):
                # Ensure all required fields are present
                item_copy = item.copy()
                
                # Ensure basket_id exists
                if 'basket_id' not in item_copy:
                    item_copy['basket_id'] = str(ObjectId())
                
                # Ensure added_at exists
                if 'added_at' not in item_copy:
                    item_copy['added_at'] = datetime.now().isoformat()
                
                # Ensure level exists
                if 'level' not in item_copy:
                    item_copy['level'] = session.get('current_level', session.get('current_flow', 'degree'))
                
                processed_basket.append(item_copy)
        
        basket_count = len(processed_basket)
        print(f"🎯 Final basket count for display: {basket_count}")
        
        # Update session with processed basket
        session['course_basket'] = processed_basket
        session.modified = True
        
        return render_template('basket.html', 
                             basket=processed_basket, 
                             basket_count=basket_count,
                             title='My Basket | KUCCPS Courses Checker',
                             meta_description='Review and manage your selected KUCCPS courses in your basket.',
                             canonical_url=get_canonical_url('view_basket'))
    
    except Exception as e:
        print(f"❌ Critical error in view_basket: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Emergency session preservation
        critical_keys = ['email', 'index_number', 'verified_payment', 'verified_index', 'current_flow']
        critical_data = {}
        
        for key in critical_keys:
            if key in session:
                critical_data[key] = session[key]
        
        # Clear and restore critical data only
        session.clear()
        for key, value in critical_data.items():
            session[key] = value
        
        # Initialize empty basket
        session['course_basket'] = []
        session.modified = True
        
        flash("There was an error loading your basket. Please try again.", "error")
        return redirect(url_for('index'))
    
@app.route('/get-basket')
def get_basket():
    """Get user's current basket"""
    basket = session.get('course_basket', [])
    return jsonify({
        'success': True,
        'basket': basket,
        'count': len(basket)
    })

@app.route('/save-basket', methods=['POST'])
def save_basket():
    try:
        data = request.get_json()
        action = data.get('action', '')
        
        basket = session.get('course_basket', [])
        
        # Ensure basket is a list
        if not isinstance(basket, list):
            basket = []
            session['course_basket'] = basket
        
        print(f"💾 Saving basket with {len(basket)} items")
        
        # Save to database if user is identified
        email = session.get('email')
        index_number = session.get('index_number')
        if email and index_number:
            save_user_basket(email, index_number, basket)
        
        session.modified = True
        
        return jsonify({
            'success': True,
            'message': 'Basket saved successfully',
            'basket_count': len(basket)
        })
        
    except Exception as e:
        print(f"❌ Error saving basket: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/load-basket')
def load_basket():
    try:
        basket = session.get('course_basket', [])
        
        # Ensure basket is a list
        if not isinstance(basket, list):
            basket = []
            session['course_basket'] = basket
            session.modified = True
        
        print(f"📥 Loading basket with {len(basket)} items")
        
        return jsonify({
            'success': True,
            'basket': basket,
            'basket_count': len(basket)
        })
        
    except Exception as e:
        print(f"❌ Error loading basket: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'basket': [],
            'basket_count': 0
        })

@app.route('/reset-basket')
def reset_basket():
    session['course_basket'] = []
    session.modified = True
    return redirect('/basket')

# --- Search Function ---
def search_courses(query, courses):
    """Search courses by name, code, institution, or programme name"""
    if not query:
        return courses
    
    if not courses:
        return []
    
    query = query.lower().strip()
    results = []
    
    for course in courses:
        # Handle case where course might be None or invalid
        if not course:
            continue
            
        # Search in multiple possible field names - with safe defaults
        course_name = str(course.get('course_name', '')).lower()
        programme_name = str(course.get('programme_name', '')).lower()
        course_code = str(course.get('course_code', '')).lower()
        programme_code = str(course.get('programme_code', '')).lower()
        institution = str(course.get('institution_name', '')).lower()
        cluster = str(course.get('cluster', '')).lower()
        collection = str(course.get('collection', '')).lower()
        
        # Check all possible fields
        matches = (
            query in course_name or 
            query in programme_name or
            query in course_code or 
            query in programme_code or
            query in institution or
            query in cluster or
            query in collection
        )
        
        if matches:
            results.append(course)
    
    return results

@app.route('/search-courses/<flow>')
def search_courses_route(flow):
    """Search courses within a specific flow"""
    try:
        query = request.args.get('q', '').strip()
        
        print(f"🔍 Received search request for flow: {flow}, query: '{query}'")
        
        # Get user info for course filtering
        email = session.get('email')
        index_number = session.get('index_number')
        
        qualifying_courses = []
        
        # For verified users (accessed via Already Made Payment)
        if not email or not index_number:
            verified_index = session.get('verified_index')
            print(f"🔍 User verification status - verified_index: {verified_index}")
            
            if verified_index:
                # Get courses from database for verified users
                courses_data = user_courses_collection.find_one({
                    'index_number': verified_index,
                    'level': flow
                })
                if courses_data and courses_data.get('courses'):
                    qualifying_courses = courses_data['courses']
                    # Convert ObjectId to string for JSON serialization
                    converted_courses = []
                    for course in qualifying_courses:
                        if course:  # Check if course is not None
                            course_dict = dict(course)
                            if '_id' in course_dict and isinstance(course_dict['_id'], ObjectId):
                                course_dict['_id'] = str(course_dict['_id'])
                            converted_courses.append(course_dict)
                    qualifying_courses = converted_courses
                    print(f"✅ Loaded {len(qualifying_courses)} courses from database for verified user")
                else:
                    print(f"⚠️ No courses found in database for {flow} level")
                    qualifying_courses = []
            else:
                # Regular users without verification - get courses based on flow from session
                print(f"🔍 Regular user - checking session data for {flow}")
                if flow == 'degree':
                    user_grades = session.get('degree_grades', {})
                    user_cluster_points = session.get('degree_cluster_points', {})
                    if user_grades and user_cluster_points:
                        qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
                        print(f"✅ Loaded {len(qualifying_courses)} degree courses from qualification check")
                    else:
                        qualifying_courses = []
                        print("⚠️ No degree grades or cluster points in session")
                elif flow == 'diploma':
                    user_grades = session.get('diploma_grades', {})
                    user_mean_grade = session.get('diploma_mean_grade', '')
                    if user_grades and user_mean_grade:
                        qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
                        print(f"✅ Loaded {len(qualifying_courses)} diploma courses from qualification check")
                    else:
                        qualifying_courses = []
                        print("⚠️ No diploma grades or mean grade in session")
                elif flow == 'certificate':
                    user_grades = session.get('certificate_grades', {})
                    user_mean_grade = session.get('certificate_mean_grade', '')
                    if user_grades and user_mean_grade:
                        qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
                        print(f"✅ Loaded {len(qualifying_courses)} certificate courses from qualification check")
                    else:
                        qualifying_courses = []
                        print("⚠️ No certificate grades or mean grade in session")

                elif flow == 'ttc':
                    user_grades = session.get('ttc_grades', {})
                    user_mean_grade = session.get('ttc_mean_grade', '')
                    if user_grades and user_mean_grade:
                        qualifying_courses = get_qualifying_ttc(user_grades, user_mean_grade)
                    else:
                         qualifying_courses = []
                         print("⚠️ No TTC grades or mean grade in session")

                elif flow == 'artisan':
                    user_grades = session.get('artisan_grades', {})
                    user_mean_grade = session.get('artisan_mean_grade', '')
                    if user_grades and user_mean_grade:
                        qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
                        print(f"✅ Loaded {len(qualifying_courses)} artisan courses from qualification check")
                    else:
                        qualifying_courses = []
                        print("⚠️ No artisan grades or mean grade in session")

                
                
                elif flow == 'kmtc':
                    user_grades = session.get('kmtc_grades', {})
                    user_mean_grade = session.get('kmtc_mean_grade', '')
                    if user_grades and user_mean_grade:
                        qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
                        print(f"✅ Loaded {len(qualifying_courses)} KMTC courses from qualification check")
                    else:
                        qualifying_courses = []
                        print("⚠️ No KMTC grades or mean grade in session")
                else:
                    qualifying_courses = []
                    print(f"⚠️ Unknown flow type: {flow}")
               

        else:
            # Regular users with session data - get courses based on flow
            print(f"🔍 Regular user with session - getting {flow} courses")
            if flow == 'degree':
                user_grades = session.get('degree_grades', {})
                user_cluster_points = session.get('degree_cluster_points', {})
                qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
            elif flow == 'diploma':
                user_grades = session.get('diploma_grades', {})
                user_mean_grade = session.get('diploma_mean_grade', '')
                qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
            elif flow == 'certificate':
                user_grades = session.get('certificate_grades', {})
                user_mean_grade = session.get('certificate_mean_grade', '')
                qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
            elif flow == 'artisan':
                user_grades = session.get('artisan_grades', {})
                user_mean_grade = session.get('artisan_mean_grade', '')
                qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
            elif flow == 'kmtc':
                user_grades = session.get('kmtc_grades', {})
                user_mean_grade = session.get('kmtc_mean_grade', '')
                qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
            else:
                qualifying_courses = []
        
        # Ensure qualifying_courses is a list
        if not isinstance(qualifying_courses, list):
            print(f"⚠️ qualifying_courses is not a list, converting: {type(qualifying_courses)}")
            qualifying_courses = []
        
        print(f"🔍 Before search: {len(qualifying_courses)} courses available")
        
        # Perform search
        if query:
            search_results = search_courses(query, qualifying_courses)
            print(f"🔍 After search: {len(search_results)} courses match '{query}'")
        else:
            search_results = qualifying_courses
            print(f"🔍 No query, returning all {len(search_results)} courses")
        
        # Ensure all courses have proper string IDs
        final_results = []
        for course in search_results:
            if course and isinstance(course, dict):
                course_copy = course.copy()
                if '_id' in course_copy and isinstance(course_copy['_id'], ObjectId):
                    course_copy['_id'] = str(course_copy['_id'])
                final_results.append(course_copy)
            elif course:
                final_results.append(course)
        
        print(f"🔍 Final results: {len(final_results)} courses")
        
        return jsonify({
            'success': True,
            'results': final_results,
            'count': len(final_results),
            'query': query
        })
        
    except Exception as e:
        print(f"❌ Error searching courses in {flow}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': f'Search failed: {str(e)}',
            'results': [],
            'count': 0,
            'query': query or ''
        })

# --- Admin Routes ---
@app.route('/admin')
def admin_login():
    """Admin login page"""
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    """Admin dashboard - protected route"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    return render_template('admin_dashboard.html')

@app.route('/admin/auth', methods=['POST'])
def admin_authentication():
    """Admin authentication endpoint"""
    username = request.form.get('username')
    password = request.form.get('password')
    
    # Simple hardcoded credentials (replace with secure authentication)
    if username == 'admin' and password == 'kuccps2025':
        session['admin_logged_in'] = True
        session['admin_username'] = username
        flash("Admin login successful", "success")
        return redirect(url_for('admin_dashboard'))
    else:
        flash("Invalid admin credentials", "error")
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash("Admin logged out successfully", "info")
    return redirect(url_for('admin_login'))

@app.route('/admin/clear-cache', methods=['GET', 'POST'])
def admin_clear_cache():
    """Clear all server-side and CDN cache - Admin only"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    if request.method == 'POST':
        try:
            # Clear server-side cache
            server_cleared = clear_all_cache()
            
            # Log the cache clearing action
            print(f"🧹 Cache clearing initiated by admin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            if server_cleared:
                flash("✅ All cache has been cleared successfully! Server-side and CDN cache will be refreshed.", "success")
            else:
                flash("⚠️ Server-side cache cleared, but there were some issues.", "warning")
            
            return redirect(url_for('admin_clear_cache'))
        except Exception as e:
            print(f"❌ Error during cache clearing: {str(e)}")
            flash(f"❌ Error clearing cache: {str(e)}", "error")
            return redirect(url_for('admin_clear_cache'))
    
    # Display cache status on GET request
    try:
        cache_status = {
            'cache_type': cache_config.get('CACHE_TYPE', 'Unknown'),
            'last_cleared': session.get('cache_last_cleared', 'Never'),
            'redis_available': bool(REDIS_URL),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except:
        cache_status = {
            'cache_type': 'Unknown',
            'last_cleared': 'Error retrieving status',
            'redis_available': False,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    return render_template('admin_clear_cache.html', cache_status=cache_status)

@app.route('/admin/clear-cache-api', methods=['POST'])
def admin_clear_cache_api():
    """API endpoint to clear cache - requires admin authentication"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Clear server-side cache
        clear_all_cache()
        
        # Update last cleared timestamp in session
        session['cache_last_cleared'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'success': True,
            'message': 'Cache cleared successfully',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'cache_type': cache_config.get('CACHE_TYPE', 'Unknown')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/debug/admin-activations')
def debug_admin_activations():
    """Debug route to check admin activations"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Not authorized'}), 403
    
    debug_info = {
        'database_connected': database_connected,
        'admin_activations_collection_exists': admin_activations_collection is not None,
        'total_activations': 0,
        'activations': []
    }
    
    if database_connected and admin_activations_collection is not None:
        try:
            activations = list(admin_activations_collection.find().sort('activated_at', -1).limit(10))
            debug_info['total_activations'] = admin_activations_collection.count_documents({})
            debug_info['activations'] = activations
        except Exception as e:
            debug_info['error'] = str(e)
    
    return jsonify(debug_info)


@app.route('/admin/payments')
def admin_payments():
    """View all payments and statistics"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        payments_data = []
        statistics = {
            'total_payments': 0,
            'total_amount': 0,
            'first_category_count': 0,
            'additional_category_count': 0,
            'failed_payments': 0,
            'confirmed_payments': 0,
            'manual_activations': 0
        }
        
        if database_connected:
            # Get all payments
            all_payments = list(user_payments_collection.find().sort('created_at', -1))
            
            for payment in all_payments:
                payment_data = {
                    'email': payment.get('email', 'N/A'),
                    'index_number': payment.get('index_number', 'N/A'),
                    'level': payment.get('level', 'N/A'),
                    'payment_amount': payment.get('payment_amount', 0),
                    'payment_confirmed': payment.get('payment_confirmed', False),
                    'mpesa_receipt': payment.get('mpesa_receipt', 'N/A'),
                    'transaction_ref': payment.get('transaction_ref', 'N/A'),
                    'created_at': payment.get('created_at', 'N/A'),
                    'payment_date': payment.get('payment_date', 'N/A')
                }
                payments_data.append(payment_data)
                
                # Calculate statistics
                statistics['total_payments'] += 1
                statistics['total_amount'] += payment_data['payment_amount']
                
                if payment_data['payment_confirmed']:
                    statistics['confirmed_payments'] += 1
                    # Determine if first or additional category
                    if payment_data['payment_amount'] == 2:
                        statistics['first_category_count'] += 1
                    else:
                        statistics['additional_category_count'] += 1
                else:
                    statistics['failed_payments'] += 1
            
            # Get manual activations count
            statistics['manual_activations'] = admin_activations_collection.count_documents({'is_active': True})
                
        else:
            # Session fallback for statistics
            payments_data = []
        
        return render_template('admin_payments.html', 
                             payments=payments_data, 
                             statistics=statistics)
                             
    except Exception as e:
        print(f"❌ Error loading admin payments: {str(e)}")
        flash("Error loading payment data", "error")
        return render_template('admin_payments.html', payments=[], statistics={})

@app.route('/admin/users')
def admin_users():
    """View all users and their activities"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        users_data = []
        
        if database_connected:
            # Get all unique users with their activities
            pipeline = [
                {
                    '$group': {
                        '_id': '$index_number',
                        'email': {'$first': '$email'},
                        'payment_count': {'$sum': 1},
                        'confirmed_payments': {
                            '$sum': {'$cond': [{'$eq': ['$payment_confirmed', True]}, 1, 0]}
                        },
                        'total_amount': {'$sum': '$payment_amount'},
                        'last_activity': {'$max': '$created_at'},
                        'levels': {'$addToSet': '$level'}
                    }
                },
                {'$sort': {'last_activity': -1}}
            ]
            
            user_activities = list(user_payments_collection.aggregate(pipeline))
            
            for user in user_activities:
                user_data = {
                    'index_number': user['_id'],
                    'email': user.get('email', 'N/A'),
                    'payment_count': user.get('payment_count', 0),
                    'confirmed_payments': user.get('confirmed_payments', 0),
                    'total_amount': user.get('total_amount', 0),
                    'last_activity': user.get('last_activity', 'N/A'),
                    'levels': user.get('levels', [])
                }
                users_data.append(user_data)
        
        return render_template('admin_users.html', users=users_data)
        
    except Exception as e:
        print(f"❌ Error loading admin users: {str(e)}")
        flash("Error loading user data", "error")
        return render_template('admin_users.html', users=[])
# --- Enhanced Admin Payment Management Routes ---
@app.route('/admin/payment-management', methods=['GET', 'POST'])
def admin_payment_management():
    """Comprehensive payment management with filtering, deletion, and analytics"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    # Initialize default values
    stats = {}
    payment_records = []
    daily_payments = []
    start_date_str = ''
    end_date_str = ''
    status_filter = ''
    page = 1
    total_pages = 1
    total_records = 0
    
    try:
        # Statistics for dashboard
        stats = calculate_payment_statistics()
        
        # Handle deletion of failed payments
        if request.method == 'POST' and 'delete_failed' in request.form:
            deleted_count = delete_failed_payments()
            if deleted_count > 0:
                flash(f"Successfully deleted {deleted_count} failed payment records", "success")
            else:
                flash("No failed payments to delete", "info")
            return redirect(url_for('admin_payment_management'))
        
        # Handle date range filtering
        start_date_str = request.args.get('start_date', '')
        end_date_str = request.args.get('end_date', '')
        status_filter = request.args.get('status', '')
        
        # Calculate daily payments for chart
        daily_payments = get_daily_payment_summary()
        
        # FIX: Compare with None instead of bool()
        if database_connected and user_payments_collection is not None:
            # Build filter query
            filter_query = {}
            
            # Date filter
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                    filter_query['created_at'] = {'$gte': start_date}
                except ValueError:
                    flash("Invalid start date format", "error")
            
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                    end_date = end_date.replace(hour=23, minute=59, second=59)
                    if 'created_at' in filter_query:
                        filter_query['created_at']['$lte'] = end_date
                    else:
                        filter_query['created_at'] = {'$lte': end_date}
                except ValueError:
                    flash("Invalid end date format", "error")
            
            # Status filter
            if status_filter == 'confirmed':
                filter_query['payment_confirmed'] = True
            elif status_filter == 'failed':
                filter_query['payment_confirmed'] = False
            
            # Get payments with pagination
            page = int(request.args.get('page', 1))
            limit = 50
            skip = (page - 1) * limit
            
            payment_records = list(user_payments_collection.find(filter_query)
                                  .sort('created_at', -1)
                                  .skip(skip)
                                  .limit(limit))
            
            total_records = user_payments_collection.count_documents(filter_query)
            total_pages = (total_records + limit - 1) // limit if total_records > 0 else 1
        
    except Exception as e:
        print(f"❌ Error in payment management: {str(e)}")
        import traceback
        traceback.print_exc()
        flash("Error loading payment management data", "error")
    
    # Ensure all variables are defined
    stats = stats or {}
    payment_records = payment_records or []
    daily_payments = daily_payments or []
    
    return render_template('admin_payment_management.html',
                         payments=payment_records,
                         stats=stats,
                         daily_payments=daily_payments,
                         start_date=start_date_str,
                         end_date=end_date_str,
                         status_filter=status_filter,
                         page=page,
                         total_pages=total_pages,
                         total_records=total_records)

def calculate_payment_statistics():
    """Calculate comprehensive payment statistics with safe defaults"""
    # Initialize stats with default values
    stats = {
        'total_payments': 0,
        'total_revenue': 0.0,
        'confirmed_payments': 0,
        'failed_payments': 0,
        'today_payments': 0,
        'today_revenue': 0.0,
        'weekly_payments': 0,
        'weekly_revenue': 0.0,
        'monthly_payments': 0,
        'monthly_revenue': 0.0,
        'average_transaction': 0.0,
        'top_categories': []
    }
    
    # FIX: Compare with None instead of not
    if not database_connected or user_payments_collection is None:
        print("⚠️ Database not connected for statistics calculation")
        return stats
    
    try:
        print("📊 Calculating payment statistics...")
        
        # Get all payments
        all_payments = list(user_payments_collection.find({}))
        stats['total_payments'] = len(all_payments)
        
        print(f"📊 Total payments found: {stats['total_payments']}")
        
        # Calculate confirmed vs failed
        confirmed_count = 0
        total_revenue = 0.0
        
        for payment in all_payments:
            amount = float(payment.get('payment_amount', 0))
            if payment.get('payment_confirmed'):
                confirmed_count += 1
                total_revenue += amount
        
        stats['confirmed_payments'] = confirmed_count
        stats['failed_payments'] = stats['total_payments'] - confirmed_count
        stats['total_revenue'] = total_revenue
        stats['average_transaction'] = total_revenue / confirmed_count if confirmed_count > 0 else 0.0
        
        print(f"📊 Confirmed: {confirmed_count}, Failed: {stats['failed_payments']}, Revenue: {total_revenue}")
        
        # Today's statistics
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_payments = list(user_payments_collection.find({
            'created_at': {'$gte': today_start},
            'payment_confirmed': True
        }))
        
        stats['today_payments'] = len(today_payments)
        stats['today_revenue'] = sum(float(p.get('payment_amount', 0)) for p in today_payments)
        
        # Weekly statistics (last 7 days)
        week_start = today_start - timedelta(days=7)
        weekly_payments = list(user_payments_collection.find({
            'created_at': {'$gte': week_start},
            'payment_confirmed': True
        }))
        
        stats['weekly_payments'] = len(weekly_payments)
        stats['weekly_revenue'] = sum(float(p.get('payment_amount', 0)) for p in weekly_payments)
        
        # Monthly statistics (last 30 days)
        month_start = today_start - timedelta(days=30)
        monthly_payments = list(user_payments_collection.find({
            'created_at': {'$gte': month_start},
            'payment_confirmed': True
        }))
        
        stats['monthly_payments'] = len(monthly_payments)
        stats['monthly_revenue'] = sum(float(p.get('payment_amount', 0)) for p in monthly_payments)
        
        # Top categories by revenue
        try:
            pipeline = [
                {'$match': {'payment_confirmed': True}},
                {'$group': {
                    '_id': '$level',
                    'total_revenue': {'$sum': '$payment_amount'},
                    'payment_count': {'$sum': 1}
                }},
                {'$sort': {'total_revenue': -1}},
                {'$limit': 5}
            ]
            
            top_categories = list(user_payments_collection.aggregate(pipeline))
            stats['top_categories'] = top_categories
            print(f"📊 Top categories: {len(top_categories)}")
        except Exception as e:
            print(f"⚠️ Error calculating top categories: {e}")
            stats['top_categories'] = []
        
        print(f"✅ Statistics calculation completed")
        
    except Exception as e:
        print(f"❌ Error calculating payment statistics: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return stats
def get_daily_payment_summary(days=30):
    """Get daily payment summary for chart"""
    daily_data = []
    
    # FIX: Compare with None instead of bool()
    if not database_connected or user_payments_collection is None:
        return daily_data
    
    try:
        # Get payments for last N days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        pipeline = [
            {'$match': {
                'created_at': {'$gte': start_date},
                'payment_confirmed': True
            }},
            {'$group': {
                '_id': {
                    'year': {'$year': '$created_at'},
                    'month': {'$month': '$created_at'},
                    'day': {'$dayOfMonth': '$created_at'}
                },
                'total_revenue': {'$sum': '$payment_amount'},
                'payment_count': {'$sum': 1}
            }},
            {'$sort': {'_id': 1}}
        ]
        
        daily_results = list(user_payments_collection.aggregate(pipeline))
        
        for result in daily_results:
            date_id = result['_id']
            date_str = f"{date_id['year']}-{date_id['month']:02d}-{date_id['day']:02d}"
            daily_data.append({
                'date': date_str,
                'revenue': float(result.get('total_revenue', 0)),
                'count': result.get('payment_count', 0)
            })
        
    except Exception as e:
        print(f"❌ Error getting daily summary: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return daily_data
def delete_failed_payments():
    """Delete all payments with payment_confirmed=False"""
    if not database_connected:
        return 0
    
    try:
        result = user_payments_collection.delete_many({'payment_confirmed': False})
        deleted_count = result.deleted_count
        print(f"🗑️ Deleted {deleted_count} failed payment records")
        return deleted_count
    except Exception as e:
        print(f"❌ Error deleting failed payments: {str(e)}")
        return 0

@app.route('/admin/export-payments')
def admin_export_payments():
    """Export payments to CSV"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        # FIX: Compare with None instead of bool()
        if not database_connected or user_payments_collection is None:
            flash("Database not available for export", "error")
            return redirect(url_for('admin_payment_management'))
        
        # Get all confirmed payments
        payments = list(user_payments_collection.find({'payment_confirmed': True}))
        
        # Create CSV content
        csv_content = "Index Number,Email,Level,Amount,M-Pesa Receipt,Transaction Ref,Date\n"
        
        for payment in payments:
            index_number = payment.get('index_number', '')
            email = payment.get('email', '')
            level = payment.get('level', '')
            amount = payment.get('payment_amount', 0)
            receipt = payment.get('mpesa_receipt', '')
            transaction_ref = payment.get('transaction_ref', '')
            date = payment.get('created_at', datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
            
            csv_content += f'"{index_number}","{email}","{level}",{amount},"{receipt}","{transaction_ref}","{date}"\n'
        
        # Create response with CSV file
        response = make_response(csv_content)
        response.headers['Content-Disposition'] = 'attachment; filename=payments_export.csv'
        response.headers['Content-Type'] = 'text/csv'
        
        return response
        
    except Exception as e:
        print(f"❌ Error exporting payments: {str(e)}")
        flash("Error exporting payments", "error")
        return redirect(url_for('admin_payment_management'))
# Add to admin dashboard menu
@app.route('/admin/view-payments')
def admin_view_payments():
    """Legacy redirect to new payment management"""
    return redirect(url_for('admin_payment_management'))
@app.route("/health") 
def health(): 
    return "OK", 200

@app.route('/admin/system-health')
def admin_system_health():
    """System health and monitoring dashboard"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        health_data = {
            'database_connected': database_connected,
            'session_keys_count': len(session.keys()) if session else 0,
            'current_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'application_uptime': 'N/A'
        }
        
        if database_connected:
            # Database statistics
            health_data['database_stats'] = {
                'user_payments': user_payments_collection.count_documents({}),
                'user_courses': user_courses_collection.count_documents({}),
                'user_baskets': user_baskets_collection.count_documents({}),
                'admin_activations': admin_activations_collection.count_documents({})
            }
            
            # Recent activities
            health_data['recent_activities'] = list(user_payments_collection.find()
                                                  .sort('created_at', -1)
                                                  .limit(10))
        
        return render_template('admin_system_health.html', health_data=health_data)
        
    except Exception as e:
        print(f"❌ Error loading system health: {str(e)}")
        flash("Error loading system health data", "error")
        return render_template('admin_system_health.html', health_data={})

# --- Debug and Testing Routes ---
@app.route('/debug/database')
def debug_database():
    status = {
        'database_connected': database_connected,
        'collections_initialized': {
            'user_payments': user_payments_collection is not None,
            'user_courses': user_courses_collection is not None,
            'user_baskets': user_baskets_collection is not None,
            'admin_activations': admin_activations_collection is not None
        },
        'session_keys': list(session.keys()) if session else []
    }
    
    if database_connected:
        try:
            status['document_counts'] = {
                'user_payments': user_payments_collection.count_documents({}),
                'user_courses': user_courses_collection.count_documents({}),
                'user_baskets': user_baskets_collection.count_documents({}),
                'admin_activations': admin_activations_collection.count_documents({})
            }
        except Exception as e:
            status['error'] = str(e)
    
    return jsonify(status)



@app.route('/debug/basket-status')
def debug_basket_status():
    """Debug route to check basket status"""
    status = {
        'session_keys': list(session.keys()),
        'session_basket': session.get('course_basket', []),
        'session_basket_count': len(session.get('course_basket', [])),
        'verified_payment': session.get('verified_payment'),
        'verified_index': session.get('verified_index'),
        'email': session.get('email'),
        'index_number': session.get('index_number')
    }
    
    if session.get('verified_index'):
        db_basket = get_user_basket_by_index(session['verified_index'])
        status['database_basket'] = db_basket
        status['database_basket_count'] = len(db_basket)
    
    return jsonify(status)

@app.route('/contact')
def contact():
    """Contact page"""
    canonical = get_canonical_url('contact')
    return render_template('contact.html',
                         title='Contact KUCCPS Courses Checker | Support',
                         meta_description='Contact our support team for help with KUCCPS course selection, payment issues, or general inquiries about degree, diploma, and certificate programs.',
                         canonical_url=canonical)
    
@app.route('/temp-bypass/<flow>')
def temp_bypass(flow):
    session[f'paid_{flow}'] = True
    session['email'] = 'test@example.com' 
    session['index_number'] = '123456/2024'
    
    if flow == 'diploma':
        session['diploma_grades'] = {'MAT': 'B', 'ENG': 'B', 'KIS': 'B'}
        session['diploma_mean_grade'] = 'B'
        session['diploma_data_submitted'] = True
    
    flash("Temporarily bypassed payment for testing", "info")
    return redirect(url_for('show_results', flow=flow))
@app.route('/health')
def health_check():
    """Comprehensive health check endpoint"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'KUCCPS Courses API',
        'version': '2.0',
        'database_connected': database_connected,
        'endpoints_working': True,
        'environment': os.environ.get('FLASK_ENV', 'production')
    }
    
    # Add database health check if connected
    if database_connected:
        try:
            user_payments_collection.find_one({}, {'_id': 1})
            health_status['database_status'] = 'connected_and_responding'
        except Exception as e:
            health_status['database_status'] = 'error'
            health_status['database_error'] = str(e)
            health_status['status'] = 'degraded'
    
    return jsonify(health_status)

@app.route('/ping')
def ping():
    """Simple ping endpoint for keep-alive services"""
    return jsonify({
        'status': 'pong', 
        'timestamp': datetime.now().isoformat(),
        'service': 'KUCCPS Courses API',
        'alive': True
    })

@app.route('/keep-alive')
def keep_alive():
    """Endpoint specifically for keep-alive services"""
    return jsonify({
        'alive': True,
        'timestamp': datetime.now().isoformat(),
        'message': 'Service is alive and responsive',
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    })


@app.route('/api/offline/sync', methods=['POST'])
def sync_offline_data():
    """Sync data from offline storage when back online"""
    data = request.get_json()
    
    # Process offline actions (basket updates, etc.)
    # You'd need to implement this based on your needs
    
    return jsonify({
        'success': True,
        'message': 'Offline data synced'
    })
@app.route('/api/status')
def api_status():
    """API status endpoint"""
    return jsonify({
        'status': 'operational',
        'timestamp': datetime.now().isoformat(),
        'service': 'KUCCPS Courses API',
        'version': '2.0',
        'environment': os.environ.get('FLASK_ENV', 'production')
    })

# --- Offline Support Routes ---
@app.route('/api/offline/courses/<flow>')
def get_offline_courses(flow):
    """Get courses for offline caching"""
    try:
        # For offline mode, return limited course data
        if flow == 'degree':
            return jsonify({
                'flow': flow,
                'message': 'Load courses when online first',
                'cached': False
            })
        
        # You could implement a more comprehensive offline cache here
        return jsonify({
            'flow': flow,
            'courses': [],
            'cached_at': datetime.now().isoformat(),
            'message': 'Go online to load courses for this level'
        })
    except Exception as e:
        print(f"❌ Error getting offline courses: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/offline/basket')
def get_offline_basket():
    """Get basket data for offline access"""
    basket = session.get('course_basket', [])
    return jsonify({
        'basket': basket,
        'count': len(basket),
        'offline': True
    })

@app.route('/static/js/offline-storage.js')
def serve_offline_storage():
    """Serve offline storage JS file"""
    return send_from_directory('static/js', 'offline-storage.js')

@app.route('/static/js/pwa.js')
def serve_pwa_js():
    """Serve PWA JS file"""
    return send_from_directory('static/js', 'pwa.js')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/service-worker.js')
def serve_service_worker():
    response = make_response(send_from_directory('static', 'service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/offline')
def offline():
    return render_template('offline.html')

@app.route('/api/pwa/install-status')
def pwa_install_status():
    """Check if app is installed"""
    display_mode = request.headers.get('Sec-Ch-Ua-Mobile') or request.headers.get('User-Agent', '')
    is_installed = request.headers.get('X-Requested-With') == 'pwa' or 'standalone' in request.headers.get('Accept', '')
    
    return jsonify({
        'is_installed': is_installed,
        'display_mode': 'standalone' if is_installed else 'browser'
    })

# --- Admin News Management Routes ---
@app.route('/admin/news', methods=['GET', 'POST'])
def admin_news():
    """Admin news management - list, create, edit, delete news articles"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    # Handle POST requests (create/update news)
    if request.method == 'POST':
        action = request.form.get('action', '')
        
        if action == 'create':
            return create_news_article(request)
        elif action == 'update':
            return update_news_article(request)
        elif action == 'delete':
            return delete_news_article(request)
        elif action == 'toggle_feature':
            return toggle_feature_news(request)
        elif action == 'toggle_publish':
            return toggle_publish_news(request)
    
    # GET request - display news management page
    try:
        # Get all news articles sorted by date
        # FIX: Use 'is not None' instead of truthiness testing
        news_articles = []
        if database_connected and news_collection is not None:
            news_articles = list(news_collection.find().sort('created_at', -1))
        
        return render_template('admin_news.html', news_articles=news_articles)
    
    except Exception as e:
        print(f"❌ Error loading admin news: {str(e)}")
        flash("Error loading news articles", "error")
        return render_template('admin_news.html', news_articles=[])

@app.route('/admin/news/create', methods=['GET'])
def admin_create_news():
    """Create new news article page"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    return render_template('admin_create_news.html')

@app.route('/admin/news/edit/<news_id>', methods=['GET'])
def admin_edit_news(news_id):
    """Edit news article page"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            news_article = news_collection.find_one({'_id': ObjectId(news_id)})
            # FIX: Check if article is not None
            if news_article is not None:
                return render_template('admin_edit_news.html', article=news_article)
        
        flash("News article not found", "error")
        return redirect(url_for('admin_news'))
    
    except Exception as e:
        print(f"❌ Error loading news for editing: {str(e)}")
        flash("Error loading news article", "error")
        return redirect(url_for('admin_news'))

def create_news_article(request):
    """Create a new news article"""
    try:
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        image_url = request.form.get('image_url', '').strip()
        external_link = request.form.get('external_link', '').strip()
        is_featured = request.form.get('is_featured') == 'on'
        is_published = request.form.get('is_published') == 'on'
        priority = int(request.form.get('priority', 5))
        
        if not title or not content:
            flash("Title and content are required", "error")
            return redirect(url_for('admin_news'))
        
        # Create news article
        news_article = {
            'title': title,
            'content': content,
            'excerpt': excerpt or content[:150] + '...',
            'image_url': image_url,
            'external_link': external_link,
            'is_featured': is_featured,
            'is_published': is_published,
            'priority': min(max(priority, 1), 10),  # Limit between 1-10
            'created_by': session.get('admin_username', 'admin'),
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'published_at': datetime.now() if is_published else None,
            'views': 0
        }
        
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            result = news_collection.insert_one(news_article)
            if result.inserted_id:
                flash(f"News article '{title}' created successfully", "success")
            else:
                flash("Failed to create news article", "error")
        else:
            flash("Database not available. News saved to session only.", "warning")
            # Store in session as fallback
            session_key = f'news_{int(datetime.now().timestamp())}'
            session[session_key] = news_article
        
        return redirect(url_for('admin_news'))
    
    except Exception as e:
        print(f"❌ Error creating news article: {str(e)}")
        flash("Error creating news article", "error")
        return redirect(url_for('admin_news'))

def update_news_article(request):
    """Update existing news article"""
    try:
        news_id = request.form.get('news_id')
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        excerpt = request.form.get('excerpt', '').strip()
        image_url = request.form.get('image_url', '').strip()
        external_link = request.form.get('external_link', '').strip()
        is_featured = request.form.get('is_featured') == 'on'
        is_published = request.form.get('is_published') == 'on'
        priority = int(request.form.get('priority', 5))
        
        if not news_id or not title or not content:
            flash("News ID, title and content are required", "error")
            return redirect(url_for('admin_news'))
        
        update_data = {
            'title': title,
            'content': content,
            'excerpt': excerpt or content[:150] + '...',
            'image_url': image_url,
            'external_link': external_link,
            'is_featured': is_featured,
            'is_published': is_published,
            'priority': min(max(priority, 1), 10),
            'updated_at': datetime.now()
        }
        
        # If publishing for first time, set publish date
        # FIX: Use 'is not None' instead of truthiness testing
        if is_published and database_connected and news_collection is not None:
            existing = news_collection.find_one({'_id': ObjectId(news_id)})
            # FIX: Check if existing is not None
            if existing is not None and not existing.get('published_at'):
                update_data['published_at'] = datetime.now()
        
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            result = news_collection.update_one(
                {'_id': ObjectId(news_id)},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                flash(f"News article '{title}' updated successfully", "success")
            else:
                flash("No changes made or article not found", "info")
        else:
            flash("Database not available. Update failed.", "error")
        
        return redirect(url_for('admin_news'))
    
    except Exception as e:
        print(f"❌ Error updating news article: {str(e)}")
        flash("Error updating news article", "error")
        return redirect(url_for('admin_news'))

def delete_news_article(request):
    """Delete news article"""
    try:
        news_id = request.form.get('news_id')
        
        if not news_id:
            flash("News ID is required", "error")
            return redirect(url_for('admin_news'))
        
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            result = news_collection.delete_one({'_id': ObjectId(news_id)})
            
            if result.deleted_count > 0:
                flash("News article deleted successfully", "success")
            else:
                flash("News article not found", "error")
        else:
            flash("Database not available. Delete failed.", "error")
        
        return redirect(url_for('admin_news'))
    
    except Exception as e:
        print(f"❌ Error deleting news article: {str(e)}")
        flash("Error deleting news article", "error")
        return redirect(url_for('admin_news'))

def toggle_feature_news(request):
    """Toggle featured status of news article"""
    try:
        news_id = request.form.get('news_id')
        
        if not news_id:
            flash("News ID is required", "error")
            return redirect(url_for('admin_news'))
        
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            # Get current featured status
            article = news_collection.find_one({'_id': ObjectId(news_id)})
            # FIX: Check if article is not None
            if article is not None:
                new_status = not article.get('is_featured', False)
                
                result = news_collection.update_one(
                    {'_id': ObjectId(news_id)},
                    {'$set': {'is_featured': new_status, 'updated_at': datetime.now()}}
                )
                
                status_text = "featured" if new_status else "unfeatured"
                if result.modified_count > 0:
                    flash(f"News article {status_text} successfully", "success")
                else:
                    flash("Failed to update featured status", "error")
            else:
                flash("News article not found", "error")
        
        return redirect(url_for('admin_news'))
    
    except Exception as e:
        print(f"❌ Error toggling featured status: {str(e)}")
        flash("Error updating featured status", "error")
        return redirect(url_for('admin_news'))

def toggle_publish_news(request):
    """Toggle publish status of news article"""
    try:
        news_id = request.form.get('news_id')
        
        if not news_id:
            flash("News ID is required", "error")
            return redirect(url_for('admin_news'))
        
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            # Get current publish status
            article = news_collection.find_one({'_id': ObjectId(news_id)})
            # FIX: Check if article is not None
            if article is not None:
                new_status = not article.get('is_published', False)
                update_data = {
                    'is_published': new_status,
                    'updated_at': datetime.now()
                }
                
                # Set or clear publish date
                if new_status and not article.get('published_at'):
                    update_data['published_at'] = datetime.now()
                elif not new_status:
                    update_data['published_at'] = None
                
                result = news_collection.update_one(
                    {'_id': ObjectId(news_id)},
                    {'$set': update_data}
                )
                
                status_text = "published" if new_status else "unpublished"
                if result.modified_count > 0:
                    flash(f"News article {status_text} successfully", "success")
                else:
                    flash("Failed to update publish status", "error")
            else:
                flash("News article not found", "error")
        
        return redirect(url_for('admin_news'))
    
    except Exception as e:
        print(f"❌ Error toggling publish status: {str(e)}")
        flash("Error updating publish status", "error")
        return redirect(url_for('admin_news'))

@app.route('/api/news/latest')
def get_latest_news():
    """API endpoint to get latest news for frontend"""
    try:
        limit = int(request.args.get('limit', 5))
        featured_only = request.args.get('featured', '').lower() == 'true'
        
        news_articles = []
        
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            query = {'is_published': True}
            if featured_only:
                query['is_featured'] = True
            
            news_articles = list(news_collection.find(query)
                                .sort([('priority', -1), ('published_at', -1)])
                                .limit(limit))
        
        # Convert ObjectId to string for JSON
        for article in news_articles:
            if '_id' in article and isinstance(article['_id'], ObjectId):
                article['_id'] = str(article['_id'])
            if 'published_at' in article and isinstance(article['published_at'], datetime):
                article['published_at'] = article['published_at'].isoformat()
            if 'created_at' in article and isinstance(article['created_at'], datetime):
                article['created_at'] = article['created_at'].isoformat()
            if 'updated_at' in article and isinstance(article['updated_at'], datetime):
                article['updated_at'] = article['updated_at'].isoformat()
        
        return jsonify({
            'success': True,
            'news': news_articles,
            'count': len(news_articles)
        })
    
    except Exception as e:
        print(f"❌ Error getting latest news: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'news': []
        })
@app.route('/admin/ai-stats')
def admin_ai_stats():
    """Admin route to view AI/Chat Assistant statistics"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Get AI statistics
        ai_stats = {
            'gemini_calls_today': gemini_calls_today,
            'gemini_daily_limit': MAX_GEMINI_DAILY,
            'gemini_remaining': MAX_GEMINI_DAILY - gemini_calls_today,
            'gemini_cache_size': len(gemini_response_cache),
            'search_cache_size': len(search_cache),
            'gemini_reset_date': str(gemini_calls_today_reset),
            'openrouter_enabled': True,
        }
        
        # Get sample cached responses
        cached_samples = []
        count = 0
        for key, response in list(gemini_response_cache.items())[-10:]:
            if count < 10:
                timestamp = gemini_cache_timestamps.get(key, datetime.now())
                cached_samples.append({
                    'hash': key[:8] + '...',
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(timestamp, datetime) else str(timestamp),
                    'preview': response[:50] + '...' if len(response) > 50 else response
                })
                count += 1
        
        return render_template('admin_ai_stats.html', 
                             ai_stats=ai_stats,
                             cached_samples=cached_samples)
    except Exception as e:
        print(f"❌ Error in admin_ai_stats: {str(e)}")
        flash(f"Error loading AI stats: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/cached-answers')
def admin_cached_answers():
    """View all cached AI answers"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        cached_answers = []
        for key, response in list(gemini_response_cache.items())[-50:]:  # Last 50
            timestamp = gemini_cache_timestamps.get(key, datetime.now())
            cached_answers.append({
                'hash': key,
                'short_hash': key[:8] + '...',
                'response': response,
                'preview': response[:100] + '...' if len(response) > 100 else response,
                'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S') if isinstance(timestamp, datetime) else str(timestamp),
                'length': len(response)
            })
        
        # Sort by timestamp (newest first)
        cached_answers.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return render_template('admin_cached_answers.html', cached_answers=cached_answers)
    except Exception as e:
        print(f"❌ Error in admin_cached_answers: {str(e)}")
        flash(f"Error loading cached answers: {str(e)}", "error")
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/clear-ai-cache', methods=['POST'])
def admin_clear_ai_cache():
    """Clear AI response cache"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        global gemini_response_cache, gemini_cache_timestamps
        cache_size = len(gemini_response_cache)
        gemini_response_cache.clear()
        gemini_cache_timestamps.clear()
        
        flash(f"✅ AI cache cleared successfully. Removed {cache_size} entries.", "success")
        return redirect(url_for('admin_ai_stats'))
    except Exception as e:
        print(f"❌ Error clearing AI cache: {str(e)}")
        flash(f"Error clearing cache: {str(e)}", "error")
        return redirect(url_for('admin_ai_stats'))
@app.route('/api/news/increment-views/<news_id>', methods=['POST'])
def increment_news_views(news_id):
    """Increment view count for a news article"""
    try:
        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            result = news_collection.update_one(
                {'_id': ObjectId(news_id)},
                {'$inc': {'views': 1}}
            )
            
            return jsonify({
                'success': result.modified_count > 0
            })
        
        return jsonify({'success': False})
    
    except Exception as e:
        print(f"❌ Error incrementing news views: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/news')
def all_news():
    """Display all news articles"""
    try:
        news_articles = []
        canonical = get_canonical_url('all_news')

        # FIX: Use 'is not None' instead of truthiness testing
        if database_connected and news_collection is not None:
            news_articles = list(
                news_collection.find({'is_published': True})
                .sort([('priority', -1), ('published_at', -1)])
            )

            # Convert ObjectId to string for template
            for article in news_articles:
                if '_id' in article and isinstance(article['_id'], ObjectId):
                    article['_id'] = str(article['_id'])

        return render_template(
            'news.html',
            news_articles=news_articles,
            title='Latest KUCCPS News & Updates',
            meta_description='Stay updated with the latest KUCCPS news, course announcements, and placement information.',
            canonical_url=canonical
        )

    except Exception as e:
        print(f"❌ Error loading news page: {str(e)}")
        canonical = get_canonical_url('all_news')
        return render_template(
            'news.html',
            news_articles=[],
            title='Latest KUCCPS News & Updates',
            meta_description='Stay updated with the latest KUCCPS news, course announcements, and placement information.',
            canonical_url=canonical
        )
from flask import request, make_response
import gzip
from io import BytesIO
 
@app.after_request
def after_request_handler(response):
    """Single after_request: gzip + cache headers, no conflict."""
 
    # --- Cache headers ---
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response  # skip gzip for already-tiny static assets usually
 
    if request.path.startswith('/sitemap') or request.path == '/robots.txt':
        response.headers['Cache-Control'] = 'public, max-age=86400'
 
    # Don't cache admin or API mutation endpoints
    if request.path.startswith('/admin') or request.method in ('POST', 'PUT', 'DELETE'):
        response.headers['Cache-Control'] = 'no-store'
 
    # --- Gzip (only for text responses >= 1 KB) ---
    content_length = response.content_length or 0
    if (
        content_length >= 1000
        and 'gzip' in request.headers.get('Accept-Encoding', '')
        and response.is_sequence
        and not response.direct_passthrough
        and any(response.content_type.startswith(t) for t in [
            'text/html', 'text/css', 'application/javascript',
            'application/json', 'text/plain', 'text/xml'
        ])
    ):
        try:
            buf = BytesIO()
            with gzip.GzipFile(mode='wb', fileobj=buf) as f:
                f.write(response.get_data())
            response.set_data(buf.getvalue())
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = len(response.get_data())
        except Exception:
            pass
 
    return response
 
 

# ============================================
# FETCH CONFIRMED PAYMENTS WITH NO COURSES
# ============================================

# Cache for missing courses
_missing_courses_cache = {
    'count': None,
    'last_updated': None,
    'payments': None
}
CACHE_DURATION = 300  # 5 minutes

@app.route('/admin/missing-courses')
def admin_missing_courses():
    """Admin page - confirmed payments with receipt but no courses"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    return render_template('admin_missing_courses.html')

@app.route('/api/missing-courses/fix-notified-user', methods=['POST'])
def api_fix_notified_user():
    """Fix previously notified users by cleaning up their records and creating proper manual activation"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        email = data.get('email')
        receipt = data.get('receipt')
        index_number = data.get('index_number')
        level = data.get('level')
        
        if not email or not index_number or not receipt:
            return jsonify({'success': False, 'error': 'Missing required data'})
        
        print(f"🔧 FIXING previously notified user: {email} for {level} courses")
        print(f"💰 Original receipt: {receipt}")
        
        # ============================================
        # STEP 1: DELETE the bad payment record
        # ============================================
        if database_connected and user_payments_collection is not None:
            result = user_payments_collection.delete_one({
                'index_number': index_number,
                'level': level
            })
            if result.deleted_count > 0:
                print(f"✅ Deleted bad payment record for {index_number}")
        
        # ============================================
        # STEP 2: Delete any existing courses
        # ============================================
        if database_connected and user_courses_collection is not None:
            user_courses_collection.delete_one({
                'index_number': index_number,
                'level': level
            })
            print(f"✅ Deleted existing courses for {index_number}")
        
        # ============================================
        # STEP 3: Create/Update manual activation
        # ============================================
        if database_connected and admin_activations_collection is not None:
            # Check if activation already exists
            existing = admin_activations_collection.find_one({
                'index_number': index_number
            })
            
            activation_record = {
                'email': email,
                'index_number': index_number,
                'mpesa_receipt': receipt,
                'activation_type': 'fixed_notified_user',
                'activated_by': session.get('admin_username', 'admin'),
                'activated_at': datetime.now(),
                'is_active': True,
                'status': 'active',
                'used_for_flow': None,
                'used_at': None,
                'fixed_from_notified': True,
                'original_payment_deleted': True
            }
            
            if existing:
                admin_activations_collection.update_one(
                    {'_id': existing['_id']},
                    {'$set': activation_record}
                )
                print(f"✅ Updated activation for {email}")
            else:
                admin_activations_collection.insert_one(activation_record)
                print(f"✅ Created new activation for {email}")
        
        # ============================================
        # STEP 4: Send new email with instructions
        # ============================================
        subject = "Your KUCCPS Access Has Been Fixed - Please Try Again"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Your Access Has Been Fixed</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">Access Fixed!</h1>
                <p style="color: white; margin: 5px 0 0;">Your account has been repaired</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                <p>Dear Student,</p>
                
                <p>We apologize for the inconvenience. The technical issue preventing you from accessing your courses has been <strong>fixed</strong>.</p>
                
                <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>✅ Your Details:</strong></p>
                    <p style="margin: 5px 0;">📧 Email: <strong>{email}</strong></p>
                    <p style="margin: 5px 0;">📝 KCSE Index Number: <strong>{index_number}</strong></p>
                    <p style="margin: 5px 0;">💰 M-Pesa Receipt: <strong>{receipt}</strong></p>
                    <p style="margin: 5px 0;">📚 Course Level: <strong>{level.upper()}</strong></p>
                </div>
                
                <p><strong>To get your course results NOW:</strong></p>
                <ol>
                    <li>Go to <a href="https://www.studentsplacement.co.ke/{level}">https://www.studentsplacement.co.ke/{level}</a></li>
                    <li>Enter your KCSE grades for {level.upper()} courses</li>
                    <li>Enter your email: <strong>{email}</strong></li>
                    <li>Enter your KCSE Index Number: <strong>{index_number}</strong></li>
                    <li>Click <strong>"Continue"</strong> - Your courses will be generated instantly!</li>
                </ol>
                
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #856404;">
                        <strong>📌 You will NOT be charged again.</strong> Your payment has been verified and your access is free.
                    </p>
                </div>
                
                <p>Need help? Contact us: kuccpscourses@gmail.com | +254750732841</p>
                
                <hr style="margin: 20px 0;">
                
                <p style="font-size: 12px; color: #666; text-align: center;">
                    © 2025 KUCCPS Courses Checker. All rights reserved.
                </p>
            </div>
        </body>
        </html>
        """
        
        email_sent = send_brevo_email(email, "Student", subject, html_content)
        
        if email_sent:
            print(f"✅ Fix email sent to {email}")
        else:
            print(f"⚠️ Fix email failed for {email}")
        
        return jsonify({
            'success': True,
            'message': f'User {email} fixed and notified',
            'email_sent': email_sent
        })
        
    except Exception as e:
        print(f"❌ Error fixing notified user: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})
@app.route('/api/missing-courses/confirmed-only')
def api_confirmed_missing_courses():
    """API: Get ONLY confirmed payments with receipt but NO courses"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        skip = (page - 1) * per_page
        
        if not database_connected or user_payments_collection is None:
            return jsonify({'payments': [], 'total': 0})
        
        # Get ALL confirmed payments with mpesa_receipt
        all_confirmed_payments = list(user_payments_collection.find({
            'payment_confirmed': True,
            'mpesa_receipt': {'$exists': True, '$ne': None, '$ne': ''}
        }).sort('created_at', -1))
        
        # Get all existing courses for quick lookup
        existing_courses_keys = set()
        if user_courses_collection is not None:
            all_courses = user_courses_collection.find({}, {'email': 1, 'index_number': 1, 'level': 1})
            for course in all_courses:
                key = f"{course.get('email')}|{course.get('index_number')}|{course.get('level')}"
                existing_courses_keys.add(key)
        
        # Get notified users
        notified_users = set()
        if 'user_notifications' in db_user_data.list_collection_names():
            notifications_collection = db_user_data['user_notifications']
            all_notifications = notifications_collection.find({}, {'email': 1, 'index_number': 1, 'level': 1})
            for notif in all_notifications:
                key = f"{notif.get('email')}|{notif.get('index_number')}|{notif.get('level')}"
                notified_users.add(key)
        
        # Get activated users
        activated_users = set()
        if admin_activations_collection is not None:
            all_activations = admin_activations_collection.find({'is_active': True}, {'email': 1, 'index_number': 1})
            for activation in all_activations:
                key = f"{activation.get('email')}|{activation.get('index_number')}"
                activated_users.add(key)
        
        # Filter: ONLY payments with NO courses
        missing_payments = []
        for payment in all_confirmed_payments:
            email = payment.get('email')
            index_number = payment.get('index_number')
            level = payment.get('level')
            
            if not email or not index_number or not level:
                continue
            
            # Check if courses exist
            key = f"{email}|{index_number}|{level}"
            courses_exist = key in existing_courses_keys
            
            if not courses_exist:
                # Check if grades exist
                grades_exist = False
                if 'user_grades' in db_user_data.list_collection_names():
                    grades_collection = db_user_data['user_grades']
                    grade_check = grades_collection.find_one({
                        'email': email,
                        'index_number': index_number,
                        'level': level
                    }, {'_id': 1})
                    grades_exist = grade_check is not None
                
                # Check if already notified
                already_notified = key in notified_users
                
                # Check if already activated
                activation_key = f"{email}|{index_number}"
                already_activated = activation_key in activated_users
                
                missing_payments.append({
                    'id': str(payment.get('_id')),
                    'email': email,
                    'index_number': index_number,
                    'level': level,
                    'mpesa_receipt': payment.get('mpesa_receipt'),
                    'transaction_ref': payment.get('transaction_ref', 'N/A'),
                    'created_at': payment.get('created_at').strftime('%Y-%m-%d %H:%M:%S') if payment.get('created_at') else 'N/A',
                    'payment_date': payment.get('payment_date').strftime('%Y-%m-%d %H:%M:%S') if payment.get('payment_date') else 'N/A',
                    'payment_amount': payment.get('payment_amount', 0),
                    'grades_exist': grades_exist,
                    'already_notified': already_notified,
                    'already_activated': already_activated
                })
        
        # Apply pagination
        total = len(missing_payments)
        paginated_payments = missing_payments[skip:skip + per_page]
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'payments': paginated_payments,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'payments': [], 'total': 0, 'error': str(e)})
    
@app.route('/api/missing-courses/count')
def api_missing_courses_count():
    """API: Get count of confirmed payments with receipt but no courses"""
    if not session.get('admin_logged_in'):
        return jsonify({'count': 0, 'error': 'Unauthorized'}), 401
    
    global _missing_courses_cache
    
    # Return cached result
    now = datetime.now()
    if (_missing_courses_cache['last_updated'] and 
        (now - _missing_courses_cache['last_updated']).total_seconds() < CACHE_DURATION and
        _missing_courses_cache['count'] is not None):
        return jsonify({'count': _missing_courses_cache['count']})
    
    try:
        if not database_connected or user_payments_collection is None:
            return jsonify({'count': 0})
        
        # Get confirmed payments with receipts
        confirmed_payments = list(user_payments_collection.find({
            'payment_confirmed': True,
            'mpesa_receipt': {'$exists': True, '$ne': None, '$ne': ''}
        }, {'email': 1, 'index_number': 1, 'level': 1}))
        
        # Get existing courses
        existing_keys = set()
        if user_courses_collection is not None:
            for course in user_courses_collection.find({}, {'email': 1, 'index_number': 1, 'level': 1}):
                key = f"{course.get('email')}|{course.get('index_number')}|{course.get('level')}"
                existing_keys.add(key)
        
        # Count missing
        missing_count = 0
        for payment in confirmed_payments:
            key = f"{payment.get('email')}|{payment.get('index_number')}|{payment.get('level')}"
            if key not in existing_keys:
                missing_count += 1
        
        _missing_courses_cache['count'] = missing_count
        _missing_courses_cache['last_updated'] = now
        
        return jsonify({'count': missing_count})
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'count': 0})


@app.route('/api/missing-courses/regenerate/<payment_id>', methods=['POST'])
def api_regenerate_missing_course(payment_id):
    """Regenerate courses for a confirmed payment with no courses"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        if not database_connected or user_payments_collection is None:
            return jsonify({'success': False, 'error': 'Database not connected'})
        
        payment = user_payments_collection.find_one({'_id': ObjectId(payment_id)})
        
        if not payment:
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        email = payment.get('email')
        index_number = payment.get('index_number')
        level = payment.get('level')
        mpesa_receipt = payment.get('mpesa_receipt')
        
        print(f"🔄 Regenerating for {email} - {level} (Receipt: {mpesa_receipt})")
        
        # Check if courses already exist
        if user_courses_collection is not None:
            existing = user_courses_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': level
            })
            if existing and existing.get('courses'):
                return jsonify({'success': False, 'error': 'Courses already exist'})
        
        # Get grades
        user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(email, index_number, level)
        
        if not user_grades:
            return jsonify({
                'success': False, 
                'error': 'No grades found. User needs to re-enter grades using "Already Made Payment" with receipt: ' + mpesa_receipt
            })
        
        # Generate courses
        qualifying_courses = []
        
        if level == 'degree':
            qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
        elif level == 'diploma':
            qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
        elif level == 'certificate':
            qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
        elif level == 'artisan':
            qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
        elif level == 'kmtc':
            qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
        elif level == 'ttc':
            qualifying_courses = get_qualifying_ttc(user_grades, user_mean_grade)
        
        if qualifying_courses:
            # Save to database
            save_user_courses(email, index_number, level, qualifying_courses)
            
            # Create manual activation as backup
            if admin_activations_collection is not None:
                admin_activations_collection.insert_one({
                    'email': email,
                    'index_number': index_number,
                    'mpesa_receipt': mpesa_receipt,
                    'activation_type': 'admin_regenerated',
                    'activated_by': session.get('admin_username', 'admin'),
                    'activated_at': datetime.now(),
                    'is_active': True,
                    'status': 'active',
                    'used_for_flow': level,
                    'used_at': datetime.now(),
                    'notes': f'Regenerated from missing courses - Payment ID: {payment_id}'
                })
            
            # Clear cache
            global _missing_courses_cache
            _missing_courses_cache['last_updated'] = None
            
            return jsonify({
                'success': True,
                'message': f'✅ Successfully generated {len(qualifying_courses)} courses for {level}',
                'courses_count': len(qualifying_courses)
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'No qualifying courses found for the given grades'
            })
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/missing-courses/notify-user', methods=['POST'])
def api_notify_missing_course_user():
    """Send notification to user about missing courses"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        email = data.get('email')
        receipt = data.get('receipt')
        index_number = data.get('index_number')
        
        if not email or not receipt:
            return jsonify({'success': False, 'error': 'Missing email or receipt'})
        
        # Here you can send an email notification
        # For now, just log it
        print(f"📧 Would notify {email} about missing courses. Receipt: {receipt}, Index: {index_number}")
        
        # You can implement actual email sending here
        # send_email_notification(email, receipt, index_number)
        
        return jsonify({
            'success': True,
            'message': f'Notification prepared for {email}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
# ============================================
# EMAIL NOTIFICATION & MANUAL ACTIVATION API
# ============================================

import requests
import json

# Brevo (Sendinblue) Configuration
BREVO_API_KEY = os.getenv('BREVO_API_KEY')  # Add this to your .env file
BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', 'support@kuccpscourses.co.ke')
BREVO_SENDER_NAME = os.getenv('BREVO_SENDER_NAME', 'KUCCPS Courses Checker')

def send_brevo_email(to_email, to_name, subject, html_content):
    """Send email using Brevo API"""
    if not BREVO_API_KEY:
        print("⚠️ BREVO_API_KEY not configured, skipping email send")
        return False
    
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        
        payload = {
            "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
            "to": [{"email": to_email, "name": to_name}],
            "subject": subject,
            "htmlContent": html_content
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code in [200, 201, 202]:
            print(f"✅ Email sent to {to_email}")
            return True
        else:
            print(f"❌ Failed to send email: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return False


@app.route('/api/missing-courses/send-email', methods=['POST'])
def api_send_missing_courses_email():
    """Send email notification to user about missing courses - with duplicate check"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        email = data.get('email')
        receipt = data.get('receipt')
        index_number = data.get('index_number')
        level = data.get('level', 'diploma')
        
        if not email or not receipt:
            return jsonify({'success': False, 'error': 'Missing email or receipt'})
        
        # Check if already notified
        if check_if_notified(email, index_number, level):
            return jsonify({
                'success': False, 
                'error': f'User {email} has already been notified about missing courses for {level}.'
            })
        
        # Prepare email content (same as before)
        subject = "Action Required: Complete Your KUCCPS Course Selection"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Complete Your Course Selection</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">KUCCPS Courses Checker</h1>
                <p style="color: white; margin: 5px 0 0;">Complete Your Course Qualification Process</p>
            </div>
            
            <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                <p>Dear Student,</p>
                
                <p>We noticed that your payment for <strong>{level.upper()} courses</strong> was successfully processed, but your course results were not generated due to a technical issue.</p>
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0 0 10px 0;"><strong>Your Payment Details:</strong></p>
                    <p style="margin: 5px 0;">📧 Email: {email}</p>
                    <p style="margin: 5px 0;">📝 Index Number: {index_number}</p>
                    <p style="margin: 5px 0;">💰 M-Pesa Receipt: <strong>{receipt}</strong></p>
                    <p style="margin: 5px 0;">📚 Course Level: {level.upper()}</p>
                </div>
                
                <p><strong>To get your course results (at no additional cost):</strong></p>
                <ol>
                    <li>Visit <a href="https://www.studentsplacement.co.ke">www.kuccpscourses.co.ke</a></li>
                    <li>Click on the <strong>{level.upper()}</strong> course category</li>
                    <li>Re-enter your KCSE grades for that category</li>
                    <li>When prompted for payment, use the <strong>"Already Made Payment"</strong> option</li>
                    <li>Enter your M-Pesa receipt number: <strong>{receipt}</strong></li>
                    <li>Enter your KCSE index number: <strong>{index_number}</strong></li>
                    <li>Your course results will be generated instantly!</li>
                </ol>
                
                <div style="background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                    <p style="margin: 0; color: #0056b3;">
                        <strong>💡 Important Note:</strong> You will NOT be charged again. The system will recognize your payment receipt and give you immediate access to your results.
                    </p>
                </div>
                
                <p>If you need any assistance, please contact our support team at kuccpscourses@gmail.com or +254750732841.</p>
                
                <hr style="margin: 20px 0;">
                
                <p style="font-size: 12px; color: #666; text-align: center;">
                    © 2025 KUCCPS Courses Checker. All rights reserved.<br>
                    This is an automated message, please do not reply directly to this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email via Brevo
        success = send_brevo_email(email, "Student", subject, html_content)
        
        if success:
            # Mark as notified
            mark_user_notified(email, index_number, level)
            print(f"✅ Email notification sent to {email}")
            return jsonify({'success': True, 'message': f'Email sent to {email}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to send email'})
        
    except Exception as e:
        print(f"❌ Error sending email: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/missing-courses/activate-and-notify', methods=['POST'])
def api_activate_and_notify():
    """Activate user - CAPTURE receipt first, then delete bad payment record"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        payment_id = data.get('payment_id')
        email = data.get('email')
        receipt = data.get('receipt')  # Original M-Pesa receipt from payment
        index_number = data.get('index_number')
        level = data.get('level')
        
        if not email or not index_number or not receipt:
            return jsonify({'success': False, 'error': 'Missing required data'})
        
        print(f"🔧 Activating user {email} for {level} courses")
        print(f"💰 Captured original receipt: {receipt}")
        
        # ============================================
        # STEP 1: Get the full payment record before deletion
        # ============================================
        original_payment = None
        if database_connected and user_payments_collection is not None:
            original_payment = user_payments_collection.find_one({
                'index_number': index_number,
                'level': level
            })
            
            if original_payment:
                print(f"📋 Found original payment record for {index_number}")
                print(f"   - Receipt: {original_payment.get('mpesa_receipt')}")
                print(f"   - Amount: {original_payment.get('payment_amount')}")
                print(f"   - Date: {original_payment.get('created_at')}")
        
        # ============================================
        # STEP 2: Create manual activation with ORIGINAL receipt
        # ============================================
        activation_record = {
            'email': email,
            'index_number': index_number,
            'mpesa_receipt': receipt,  # Store original receipt
            'original_amount': original_payment.get('payment_amount', 100) if original_payment else 100,
            'original_date': original_payment.get('created_at') if original_payment else datetime.now(),
            'activation_type': 'admin_activated_missing_course',
            'activated_by': session.get('admin_username', 'admin'),
            'activated_at': datetime.now(),
            'is_active': True,
            'status': 'active',
            'used_for_flow': None,
            'used_at': None,
            'notes': f'Original receipt: {receipt} - Payment record will be recreated when user accesses courses'
        }
        
        activation_saved = False
        if database_connected and admin_activations_collection is not None:
            # Check if activation already exists
            existing = admin_activations_collection.find_one({
                'index_number': index_number
            })
            
            if existing:
                # Update existing activation
                admin_activations_collection.update_one(
                    {'_id': existing['_id']},
                    {'$set': {
                        'is_active': True,
                        'status': 'active',
                        'mpesa_receipt': receipt,
                        'activated_at': datetime.now(),
                        'activated_by': session.get('admin_username', 'admin'),
                        'used_for_flow': None,
                        'used_at': None
                    }}
                )
                print(f"✅ Updated existing activation for {email} with receipt {receipt}")
                activation_saved = True
            else:
                # Create new activation
                result = admin_activations_collection.insert_one(activation_record)
                if result.inserted_id:
                    print(f"✅ Created new activation for {email} with receipt {receipt}")
                    activation_saved = True
        
        # ============================================
        # STEP 3: NOW delete the bad payment record (after capturing receipt)
        # ============================================
        payment_deleted = False
        if database_connected and user_payments_collection is not None:
            try:
                result = user_payments_collection.delete_one({
                    'index_number': index_number,
                    'level': level
                })
                if result.deleted_count > 0:
                    payment_deleted = True
                    print(f"✅ Deleted bad payment record for {index_number} (receipt captured)")
                else:
                    print(f"⚠️ No payment record found to delete for {index_number}")
            except Exception as e:
                print(f"⚠️ Error deleting payment record: {e}")
        
        # ============================================
        # STEP 4: Delete any existing courses (to start fresh)
        # ============================================
        if database_connected and user_courses_collection is not None:
            try:
                result = user_courses_collection.delete_one({
                    'index_number': index_number,
                    'level': level
                })
                if result.deleted_count > 0:
                    print(f"✅ Deleted existing courses for {index_number}")
            except Exception as e:
                print(f"⚠️ Error deleting courses: {e}")
        
        # ============================================
        # STEP 5: Mark as activated in tracking
        # ============================================
        if activation_saved:
            mark_user_activated(email, index_number, level, 'admin_manual')
        
        # ============================================
        # STEP 6: Send email with original receipt information
        # ============================================
        already_notified = check_if_notified(email, index_number, level)
        
        if not already_notified and activation_saved:
            subject = "Your KUCCPS Account Has Been Activated - Use Your Original M-Pesa Receipt"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Account Activated - Use Your Original M-Pesa Receipt</title>
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0;">Account Activated!</h1>
                    <p style="color: white; margin: 5px 0 0;">Your access has been restored</p>
                </div>
                
                <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                    <p>Dear Student,</p>
                    
                    <p>Good news! Your account has been <strong>manually activated</strong> by our support team. You can now access your course results using your <strong>original M-Pesa receipt</strong>.</p>
                    
                    <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p style="margin: 0 0 10px 0;"><strong>✅ Your Original Payment Details:</strong></p>
                        <p style="margin: 5px 0;">📧 Email: <strong>{email}</strong></p>
                        <p style="margin: 5px 0;">📝 KCSE Index Number: <strong>{index_number}</strong></p>
                        <p style="margin: 5px 0;">💰 M-Pesa Receipt Number: <strong style="font-size: 1.1em;">{receipt}</strong></p>
                        <p style="margin: 5px 0;">📚 Course Level: <strong>{level.upper()}</strong></p>
                        <p style="margin: 5px 0;">💵 Amount Paid: <strong>KES {original_payment.get('payment_amount', 100) if original_payment else 100}</strong></p>
                    </div>
                    
                    <p><strong>To get your course results NOW (No additional payment needed):</strong></p>
                    <ol>
                        <li>Go to <a href="https://www.studentsplacement.co.ke/{level}">https://www.studentsplacement.co.ke/{level}</a></li>
                        <li>Enter your KCSE grades for {level.upper()} courses</li>
                        <li>Enter your email: <strong>{email}</strong></li>
                        <li>Enter your KCSE Index Number: <strong>{index_number}</strong></li>
                        <li>Click <strong>"Continue"</strong> - The system will automatically detect your manual activation</li>
                        <li>Your courses will be generated instantly and sent to this email as a PDF!</li>
                    </ol>
                    
                    <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <p style="margin: 0; color: #856404;">
                            <strong>📌 IMPORTANT:</strong> Keep your M-Pesa receipt number <strong>{receipt}</strong> safe. 
                            You will NOT be charged again. The system will use this receipt to verify your payment.
                        </p>
                    </div>
                    
                    <p><strong>What to expect after submitting:</strong></p>
                    <ul>
                        <li>✅ Your results will appear immediately on screen</li>
                        <li>✅ You'll receive an email with your results as a PDF attachment</li>
                        <li>✅ You can save courses to your basket for later reference</li>
                        <li>✅ Your results will be available for 30 minutes of active browsing</li>
                    </ul>
                    
                    <hr style="margin: 20px 0;">
                    
                    <p style="font-size: 12px; color: #666; text-align: center;">
                        Need help? Contact us: kuccpscourses@gmail.com | +254750732841<br>
                        © 2025 KUCCPS Courses Checker. All rights reserved.
                    </p>
                </div>
            </body>
            </html>
            """
            
            email_sent = send_brevo_email(email, "Student", subject, html_content)
            
            if email_sent:
                mark_user_notified(email, index_number, level)
                print(f"✅ Activation email sent to {email} with receipt {receipt}")
                message = f'User {email} activated with receipt {receipt} - Email sent'
            else:
                print(f"⚠️ Activation created but email failed for {email}")
                message = f'User {email} activated with receipt {receipt} (email failed)'
        else:
            message = f'User {email} activated with receipt {receipt}'
        
        # Clear cache
        global _missing_courses_cache
        _missing_courses_cache['last_updated'] = None
        
        return jsonify({
            'success': True,
            'message': message,
            'receipt_used': receipt,
            'payment_deleted': payment_deleted,
            'activation_created': activation_saved
        })
        
    except Exception as e:
        print(f"❌ Error in activate and notify: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/missing-courses/delete/<payment_id>', methods=['POST'])
def api_delete_missing_payment(payment_id):
    """Delete a payment record that has no associated courses"""
    if not session.get('admin_logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        if not database_connected or user_payments_collection is None:
            return jsonify({'success': False, 'error': 'Database not connected'})
        
        payment = user_payments_collection.find_one({'_id': ObjectId(payment_id)})
        
        if not payment:
            return jsonify({'success': False, 'error': 'Payment not found'})
        
        # Verify no courses exist
        if user_courses_collection is not None:
            courses = user_courses_collection.find_one({
                'email': payment.get('email'),
                'index_number': payment.get('index_number'),
                'level': payment.get('level')
            })
            if courses and courses.get('courses'):
                return jsonify({'success': False, 'error': 'Cannot delete - courses exist'})
        
        result = user_payments_collection.delete_one({'_id': ObjectId(payment_id)})
        
        if result.deleted_count > 0:
            # Clear cache
            global _missing_courses_cache
            _missing_courses_cache['last_updated'] = None
            return jsonify({'success': True, 'message': 'Payment record deleted'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    
# ============================================
# ADMIN DASHBOARD API ENDPOINTS (MISSING)
# ============================================

@app.route('/api/pending-issues-count')
def api_pending_issues_count():
    """API endpoint to get count of pending payment issues"""
    if not session.get('admin_logged_in'):
        return jsonify({'count': 0, 'error': 'Unauthorized'}), 401
    
    try:
        if database_connected and payment_issues_collection is not None:
            count = payment_issues_collection.count_documents({'status': 'pending'})
            return jsonify({'count': count})
        return jsonify({'count': 0})
    except Exception as e:
        print(f"❌ Error getting pending issues count: {str(e)}")
        return jsonify({'count': 0})


@app.route('/api/recent-activity')
def api_recent_activity():
    """API endpoint to get recent system activity"""
    if not session.get('admin_logged_in'):
        return jsonify({'activities': []}), 401
    
    try:
        activities = []
        
        # Get recent payments
        if database_connected and user_payments_collection is not None:
            recent_payments = list(user_payments_collection.find()
                                  .sort('created_at', -1)
                                  .limit(5))
            
            for payment in recent_payments:
                created_at = payment.get('created_at')
                time_str = created_at.strftime('%H:%M') if created_at else 'Unknown'
                
                activities.append({
                    'title': f"Payment: {payment.get('level', 'Unknown').upper()}",
                    'description': f"{payment.get('email', 'Unknown email')} - {payment.get('payment_amount', 0)} KES",
                    'time': time_str,
                    'icon': 'money-bill-wave',
                    'color': 'success'
                })
        
        # Get recent manual activations
        if database_connected and admin_activations_collection is not None:
            recent_activations = list(admin_activations_collection.find()
                                     .sort('activated_at', -1)
                                     .limit(5))
            
            for activation in recent_activations:
                activated_at = activation.get('activated_at')
                time_str = activated_at.strftime('%H:%M') if activated_at else 'Unknown'
                
                activities.append({
                    'title': "Manual Activation",
                    'description': f"{activation.get('email', 'Unknown email')} - {activation.get('index_number', 'Unknown')}",
                    'time': time_str,
                    'icon': 'user-plus',
                    'color': 'warning'
                })
        
        # Get recent payment issues
        if database_connected and payment_issues_collection is not None:
            recent_issues = list(payment_issues_collection.find({'status': 'pending'})
                                .sort('created_at', -1)
                                .limit(5))
            
            for issue in recent_issues:
                created_at = issue.get('created_at')
                time_str = created_at.strftime('%H:%M') if created_at else 'Unknown'
                
                activities.append({
                    'title': "Payment Issue Reported",
                    'description': f"{issue.get('email', 'Unknown email')} - Receipt: {issue.get('mpesa_receipt', 'N/A')}",
                    'time': time_str,
                    'icon': 'exclamation-triangle',
                    'color': 'danger'
                })
        
        # Sort by time (most recent first) and limit to 10
        activities.sort(key=lambda x: x['time'], reverse=True)
        activities = activities[:10]
        
        return jsonify({'activities': activities})
    except Exception as e:
        print(f"❌ Error getting recent activity: {str(e)}")
        return jsonify({'activities': []})


@app.route('/api/system-stats')
def api_system_stats():
    """API endpoint to get system statistics"""
    if not session.get('admin_logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        stats = {
            'database_connected': database_connected,
            'server_time': datetime.now().strftime('%H:%M:%S'),
            'api_healthy': True
        }
        
        return jsonify(stats)
    except Exception as e:
        print(f"❌ Error getting system stats: {str(e)}")
        return jsonify({
            'database_connected': False,
            'server_time': datetime.now().strftime('%H:%M:%S'),
            'api_healthy': False
        })


# ============================================
# BATCH DELETE FOR MISSING PAYMENTS
# ============================================

@app.route('/admin/fix-missing-courses-batch', methods=['POST'])
def admin_fix_missing_courses_batch():
    """Batch process missing courses - delete all missing payment records"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    try:
        action = request.form.get('action', '')
        
        if action == 'delete_all_missing':
            if not database_connected or user_payments_collection is None:
                flash("Database not connected", "error")
                return redirect(url_for('admin_missing_courses'))
            
            # Get all confirmed payments with mpesa_receipt
            payments_with_receipt = list(user_payments_collection.find({
                'payment_confirmed': True,
                'mpesa_receipt': {'$exists': True, '$ne': None, '$ne': ''}
            }))
            
            deleted_count = 0
            skipped_count = 0
            
            for payment in payments_with_receipt:
                email = payment.get('email')
                index_number = payment.get('index_number')
                level = payment.get('level')
                
                if not email or not index_number or not level:
                    skipped_count += 1
                    continue
                
                # Check if courses exist
                courses_exist = False
                if user_courses_collection is not None:
                    existing = user_courses_collection.find_one({
                        'email': email,
                        'index_number': index_number,
                        'level': level
                    })
                    if existing and existing.get('courses'):
                        courses_exist = True
                
                # Only delete if no courses exist
                if not courses_exist:
                    user_payments_collection.delete_one({'_id': payment['_id']})
                    deleted_count += 1
                else:
                    skipped_count += 1
            
            flash(f"Deleted {deleted_count} payment records with missing courses. Skipped {skipped_count} records that have courses.", "success")
            return redirect(url_for('admin_missing_courses'))
        
        flash("Invalid action", "error")
        return redirect(url_for('admin_missing_courses'))
        
    except Exception as e:
        print(f"❌ Error in batch processing: {str(e)}")
        flash(f"Error: {str(e)}", "error")
        return redirect(url_for('admin_missing_courses'))
    
@app.route('/manual-activation', methods=['GET', 'POST'])
def admin_manual_activation():
    """Manual activation for users who paid but didn't get results"""
    if not session.get('admin_logged_in'):
        flash("Please login as administrator", "error")
        return redirect(url_for('admin_login'))
    
    # Calculate statistics for the template
    stats = {
        'active_count': 0,
        'used_count': 0, 
        'total_count': 0,
        'today_count': 0
    }
    
    if database_connected and admin_activations_collection is not None:
        try:
            stats['active_count'] = admin_activations_collection.count_documents({
                'is_active': True,
                'status': 'active'
            })
            stats['used_count'] = admin_activations_collection.count_documents({
                'status': 'used'
            })
            stats['total_count'] = admin_activations_collection.count_documents({})
            
            # Today's activations
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            stats['today_count'] = admin_activations_collection.count_documents({
                'activated_at': {'$gte': today_start}
            })
        except Exception as e:
            print(f"❌ Error loading activation stats: {str(e)}")
    
    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip().lower()
            index_number = request.form.get('index_number', '').strip()
            mpesa_receipt = request.form.get('mpesa_receipt', '').strip().upper()
            activation_type = request.form.get('activation_type', 'manual')
            send_email = request.form.get('send_email') == 'on'
            
            if not email or not index_number or not mpesa_receipt:
                flash("All fields are required", "error")
                return redirect(url_for('admin_manual_activation'))
            
            # Validate index number format
            if not re.match(r'^\d{11}/\d{4}$', index_number):
                flash("Invalid index number format", "error")
                return redirect(url_for('admin_manual_activation'))
            
            # Validate M-Pesa receipt format
            if len(mpesa_receipt) != 10 or not mpesa_receipt.isalnum():
                flash("Invalid M-Pesa receipt format", "error")
                return redirect(url_for('admin_manual_activation'))
            
            print(f"🔧 Admin manual activation attempt: {email}, {index_number}, {mpesa_receipt}")
            print(f"🔧 Database connected: {database_connected}")
            print(f"🔧 Admin activations collection: {admin_activations_collection is not None}")
            
            # Create manual activation record with LEGITIMATE flag
            activation_record = {
                'email': email,
                'index_number': index_number,
                'mpesa_receipt': mpesa_receipt,
                'activation_type': 'admin_manual',  # 🔥 CRITICAL: Not 'callback_auto'
                'activated_by': session.get('admin_username', 'admin'),
                'activated_at': datetime.now(),
                'is_active': True,
                'status': 'active',
                'used_for_flow': None,
                'used_at': None,
                'email_sent': send_email,
                'is_legitimate_manual': True  # 🔥 CRITICAL: Marks as legitimate
            }
            
            # Save to database
            activation_saved = False
            if database_connected and admin_activations_collection is not None:
                try:
                    # Check if already activated (active or used)
                    existing_activation = admin_activations_collection.find_one({
                        'index_number': index_number
                    })
                    
                    if existing_activation:
                        if existing_activation.get('is_active') and existing_activation.get('status') == 'active':
                            flash(f"User {index_number} already has an active manual activation", "warning")
                            print(f"⚠️ User {index_number} already has active activation")
                        elif existing_activation.get('status') == 'used':
                            # Reactivate used activation
                            result = admin_activations_collection.update_one(
                                {'index_number': index_number},
                                {'$set': {
                                    'is_active': True,
                                    'status': 'active',
                                    'activated_at': datetime.now(),
                                    'activated_by': session.get('admin_username', 'admin'),
                                    'used_for_flow': None,
                                    'used_at': None,
                                    'mpesa_receipt': mpesa_receipt,
                                    'email': email,
                                    'activation_type': 'admin_manual',
                                    'email_sent': send_email,
                                    'is_legitimate_manual': True  # 🔥 CRITICAL
                                }}
                            )
                            if result.modified_count > 0:
                                flash(f"Reactivated manual activation for {email}", "success")
                                print(f"✅ Manual activation reactivated: {index_number}")
                                activation_saved = True
                                
                                # Update statistics after reactivation
                                stats['active_count'] += 1
                                stats['used_count'] -= 1
                            else:
                                flash("Failed to reactivate manual activation", "error")
                        else:
                            # Update existing inactive activation
                            result = admin_activations_collection.update_one(
                                {'index_number': index_number},
                                {'$set': {
                                    'is_active': True,
                                    'status': 'active',
                                    'activated_at': datetime.now(),
                                    'activated_by': session.get('admin_username', 'admin'),
                                    'used_for_flow': None,
                                    'used_at': None,
                                    'mpesa_receipt': mpesa_receipt,
                                    'email': email,
                                    'activation_type': 'admin_manual',
                                    'email_sent': send_email,
                                    'is_legitimate_manual': True  # 🔥 CRITICAL
                                }}
                            )
                            if result.modified_count > 0:
                                flash(f"Manual activation updated for {email}", "success")
                                print(f"✅ Manual activation updated: {index_number}")
                                activation_saved = True
                    else:
                        result = admin_activations_collection.insert_one(activation_record)
                        if result.inserted_id:
                            flash(f"Manual activation successful for {email}", "success")
                            print(f"✅ Manual activation saved to database: {result.inserted_id}")
                            activation_saved = True
                            
                            # Update statistics after new activation
                            stats['active_count'] += 1
                            stats['total_count'] += 1
                            stats['today_count'] += 1
                            
                            # Verify the record was saved
                            saved_record = admin_activations_collection.find_one({'_id': result.inserted_id})
                            if saved_record:
                                print(f"✅ Record verified in database: {saved_record}")
                                print(f"   - is_legitimate_manual: {saved_record.get('is_legitimate_manual')}")
                                print(f"   - activation_type: {saved_record.get('activation_type')}")
                            else:
                                print(f"❌ Record not found after insertion")
                        else:
                            flash("Failed to save manual activation", "error")
                    
                except Exception as e:
                    print(f"❌ Error saving manual activation to database: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    flash("Error saving activation record to database", "error")
            else:
                # Session fallback for manual activations
                session_key = f'manual_activation_{index_number}'
                session[session_key] = activation_record
                flash(f"Manual activation saved to session for {email} (database not available)", "success")
                print(f"✅ Manual activation saved to session: {session_key}")
                activation_saved = True
            
            # Send email notification if requested
            if activation_saved and send_email:
                try:
                    subject = "Your KUCCPS Account Has Been Activated - Complete Your Course Selection"
                    
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>Account Activated - Complete Your Course Selection</title>
                    </head>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); padding: 20px; text-align: center; border-radius: 10px 10px 0 0;">
                            <h1 style="color: white; margin: 0;">Account Activated!</h1>
                            <p style="color: white; margin: 5px 0 0;">Your access has been restored</p>
                        </div>
                        
                        <div style="background: white; padding: 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px;">
                            <p>Dear Student,</p>
                            
                            <p>Good news! Your account has been <strong>manually activated</strong> by our support team. You can now access your course results at no additional cost.</p>
                            
                            <div style="background: #d4edda; padding: 15px; border-radius: 8px; margin: 15px 0;">
                                <p style="margin: 0 0 10px 0;"><strong>✅ Your Activation Details:</strong></p>
                                <p style="margin: 5px 0;">📧 Email: {email}</p>
                                <p style="margin: 5px 0;">📝 Index Number: {index_number}</p>
                                <p style="margin: 5px 0;">💰 M-Pesa Receipt: <strong>{mpesa_receipt}</strong></p>
                            </div>
                            
                            <p><strong>To get your course results:</strong></p>
                            <ol>
                                <li>Visit <a href="https://www.studentsplacement.co.ke">www.kuccpscourses.co.ke</a></li>
                                <li>Click on the course category you originally selected</li>
                                <li>Re-enter your KCSE grades for that category</li>
                                <li>When prompted for payment, use the <strong>"Already Made Payment"</strong> option</li>
                                <li>Enter your M-Pesa receipt number: <strong>{mpesa_receipt}</strong></li>
                                <li>Enter your KCSE index number: <strong>{index_number}</strong></li>
                                <li>Your course results will be generated instantly and sent to your email as a PDF!</li>
                            </ol>
                            
                            <div style="background: #e8f4fd; padding: 15px; border-radius: 8px; margin: 15px 0;">
                                <p style="margin: 0; color: #0056b3;">
                                    <strong>🎉 You will NOT be charged again.</strong> The manual activation gives you free access to complete your course qualification process.
                                </p>
                            </div>
                            
                            <p>If you need any assistance, please contact our support team:</p>
                            <ul>
                                <li>Email: kuccpscourses@gmail.com</li>
                                <li>Phone: +254750732841</li>
                                <li>Live Chat: Available on our website</li>
                            </ul>
                            
                            <hr style="margin: 20px 0;">
                            
                            <p style="font-size: 12px; color: #666; text-align: center;">
                                © 2025 KUCCPS Courses Checker. All rights reserved.<br>
                                This is an automated message, please do not reply directly to this email.
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    email_sent = send_brevo_email(email, "Student", subject, html_content)
                    
                    if email_sent:
                        flash(f"Activation email sent to {email}", "success")
                        print(f"✅ Activation email sent to {email}")
                        
                        # Update email sent status
                        if database_connected and admin_activations_collection is not None:
                            admin_activations_collection.update_one(
                                {'index_number': index_number},
                                {'$set': {'email_sent': True, 'email_sent_at': datetime.now()}}
                            )
                    else:
                        flash(f"Activation created but email failed to send to {email}", "warning")
                        print(f"⚠️ Activation email failed for {email}")
                        
                except Exception as e:
                    print(f"❌ Error sending activation email: {str(e)}")
                    flash(f"Activation created but email failed: {str(e)}", "warning")
            
            return redirect(url_for('admin_manual_activation'))
            
        except Exception as e:
            print(f"❌ Error in manual activation: {str(e)}")
            import traceback
            traceback.print_exc()
            flash("An error occurred during activation", "error")
            return redirect(url_for('admin_manual_activation'))
    
    # GET request - display manual activation page
    recent_activations = []
    if database_connected and admin_activations_collection is not None:
        try:
            recent_activations = list(admin_activations_collection.find()
                                     .sort('activated_at', -1)
                                     .limit(20))
            
            # Convert ObjectId to string for template
            for activation in recent_activations:
                if '_id' in activation and isinstance(activation['_id'], ObjectId):
                    activation['_id'] = str(activation['_id'])
        except Exception as e:
            print(f"❌ Error loading recent activations: {str(e)}")
    
    return render_template('admin_manual_activation.html', 
                         active_count=stats['active_count'],
                         used_count=stats['used_count'],
                         total_count=stats['total_count'],
                         today_count=stats['today_count'],
                         recent_activations=recent_activations)
if __name__ == "__main__":
    # Check if running on Render
    is_render = os.environ.get('RENDER') == 'true'
    
    if is_render:
        # On Render, let gunicorn handle the server
        print("🚀 Running on Render - starting with gunicorn...")
        # Don't start Flask server here - gunicorn will do it
        pass
    else:
        # Local development only
        print("🚀 Starting KUCCPS Application (Development)...")
        print(f"📊 Database Connection Status: {'✅ Connected' if database_connected else '❌ Disconnected'}")
        
        port = int(os.environ.get('PORT', 8080))
        debug_mode = True  # Local development
        use_reloader = True
        
        print(f"🌐 Starting Flask server on port {port} (debug={debug_mode}, reloader={use_reloader})...")
        
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=debug_mode,
            use_reloader=use_reloader, 
            threaded=True
        )