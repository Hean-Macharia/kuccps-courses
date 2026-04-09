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
import google.generativeai as genai
from google.generativeai import types   
import random                           
import time
import hashlib
import logging
import threading
import gzip
from io import BytesIO
from queue import Queue
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
SUBJECTS = {
    'mathematics': 'MAT', 'english': 'ENG', 'kiswahili': 'KIS', 'chemistry': 'CHE',
    'biology': 'BIO', 'physics': 'PHY', 'geography': 'GEO', 'history': 'HAG',
    'cre': 'CRE', 'hre': 'HRE', 'ire': 'IRE', 'agriculture': 'AGR', 'computer': 'COM',
    'arts': 'ARD', 'business': 'BST', 'music': 'MUC', 'homescience': 'HSC',
    'french': 'FRE', 'german': 'GER', 'aviation': 'AVI', 'woodwork': 'ARD',
    'building': 'ARD', 'electronics': 'COM', 'metalwork': 'ARD', 'drawing': 'ARD', 'arabic': 'ARB'
}

GRADE_VALUES = {
    'A': 12, 'A-': 11, 'B+': 10, 'B': 9, 'B-': 8, 'C+': 7, 'C': 6, 'C-': 5,
    'D+': 4, 'D': 3, 'D-': 2, 'E': 1
}
CLUSTER_NAMES = {
    'cluster_1': 'Law',
    'cluster_2': 'Business, Hospitality & Related',
    'cluster_3': 'Social Sciences, Media Studies, Fine Arts, Film, Animation, Graphics & Related',
    'cluster_4': 'Geosciences & Related',
    'cluster_5': 'Engineering, Engineering Technology & Related',
    'cluster_6': 'Architecture, Building Construction & Related',
    'cluster_7': 'Computing, IT & Related',
    'cluster_8': 'Agribusiness & Related',
    'cluster_9': 'General Science, Biological Sciences, Physics, Chemistry & Related',
    'cluster_10': 'Actuarial Science, Accountancy, Mathematics, Economics, Statistics & Related',
    'cluster_11': 'Interior Design, Fashion Design, Textiles & Related',
    'cluster_12': 'Sport Science & Related',
    'cluster_13': 'Medicine, Health, Veterinary Medicine & Related',
    'cluster_14': 'History, Archeology & Related',
    'cluster_15': 'Agriculture, Animal Health, Food Science, Nutrition Dietetics, Environmental Sciences, Natural Resources & Related',
    'cluster_16': 'Music & Related',
    'cluster_17': 'Education & Related',
    'cluster_18': 'Religious Studies, Theology, Islamic Studies & Related'
}

CLUSTERS = [f"cluster_{i}" for i in range(1, 21)]

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
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000,
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
    - Marks status 'completed' RIGHT AFTER DB save (not after email)
    - Sends email in a separate daemon thread so user is not blocked
    - Deduplicates jobs using the status map
    """
    print("✅ Background course processor started (fast version)")
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
 
            # Skip if already completed (duplicate job from queue)
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
                user_grades        = job.get('user_grades', {})
                user_mean_grade    = job.get('user_mean_grade')
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
                if flow == 'degree':
                    qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points or {})
                elif flow == 'diploma':
                    qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
                elif flow == 'certificate':
                    qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
                elif flow == 'artisan':
                    qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
                elif flow == 'kmtc':
                    qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
                elif flow == 'ttc':
                    qualifying_courses = get_qualifying_ttc(user_grades, user_mean_grade)
            except Exception as gen_err:
                print(f"❌ Course generation error for {flow}: {gen_err}")
                import traceback
                traceback.print_exc()
 
            # ── Save to DB ──
            courses_to_save = qualifying_courses if qualifying_courses else []
            try:
                save_user_courses(email, index_number, flow, courses_to_save)
            except Exception as save_err:
                print(f"⚠️ Save error: {save_err}")
 
            elapsed = time.time() - start_time
            print(f"✅ {flow} completed in {elapsed:.2f}s — {len(qualifying_courses)} courses")
 
            # ── CRITICAL: Mark completed IMMEDIATELY after save ──
            # This is what allows check_courses_ready to detect completion
            # The email is sent in a daemon thread and does NOT block the user
            course_processing_status[cache_key] = {
                'status': 'completed',
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
    """Strict check - user cannot view same category twice"""
    # Check if email+index pair already paid for this category
    if database_connected and user_payments_collection is not None:
        try:
            existing_payment = user_payments_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': category,
                'payment_confirmed': True
            })
            
            if existing_payment:
                print(f"⚠️ User {email} already paid for {category} on {existing_payment.get('payment_date')}")
                return True
        except Exception as e:
            print(f"❌ Error checking category payment: {str(e)}")
    
    # Check session as fallback
    if session.get(f'paid_{category}'):
        print(f"⚠️ Session shows already paid for {category}")
        return True
    
    return False

def get_user_paid_categories_strict(email, index_number):
    """Get all categories user has already paid for with this email-index pair"""
    paid_categories = []
    
    if not database_connected:
        for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
            if session.get(f'paid_{level}'):
                paid_categories.append(level)
        return paid_categories
    
    try:
        payments = user_payments_collection.find({
            'email': email,
            'index_number': index_number,
            'payment_confirmed': True
        })
        
        for payment in payments:
            level = payment.get('level')
            if level and level not in paid_categories:
                paid_categories.append(level)
                
    except Exception as e:
        print(f"❌ Error getting paid categories: {str(e)}")
    
    return paid_categories 
def save_payment_issue(email, index_number, mpesa_receipt, screenshot_data=None):
    """Save payment issue submitted by user"""
    print(f"💾 Saving payment issue for {email}")
    
    issue_record = {
        'email': email,
        'index_number': index_number,
        'mpesa_receipt': mpesa_receipt,
        'screenshot': screenshot_data,  # Base64 encoded screenshot
        'status': 'pending',  # pending, approved, deleted
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'processed_by': None,
        'processed_at': None,
        'notes': None
    }
    
    if database_connected and payment_issues_collection is not None:
        try:
            result = payment_issues_collection.insert_one(issue_record)
            print(f"✅ Payment issue saved with ID: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            print(f"❌ Error saving payment issue: {str(e)}")
            return None
    else:
        # Session fallback
        session_key = f'payment_issue_{int(datetime.now().timestamp())}'
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
        issue = payment_issues_collection.find_one({'_id': ObjectId(issue_id), 'status': 'pending'})
        
        if not issue:
            print(f"❌ Payment issue not found: {issue_id}")
            return False
        
        # Update issue status
        result = payment_issues_collection.update_one(
            {'_id': ObjectId(issue_id)},
            {'$set': {
                'status': 'approved',
                'processed_by': admin_username,
                'processed_at': datetime.now(),
                'updated_at': datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            print(f"✅ Payment issue approved: {issue_id}")
            
            # Create manual activation for the user
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
                    'issue_id': issue_id
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
    """Delete a payment issue (mark as deleted)"""
    if not database_connected or payment_issues_collection is None:
        return False
    
    try:
        result = payment_issues_collection.update_one(
            {'_id': ObjectId(issue_id)},
            {'$set': {
                'status': 'deleted',
                'processed_by': admin_username,
                'processed_at': datetime.now(),
                'updated_at': datetime.now(),
                'notes': 'Details not found - payment issue deleted'
            }}
        )
        
        if result.modified_count > 0:
            print(f"✅ Payment issue deleted: {issue_id}")
            return True
        
        return False
        
    except Exception as e:
        print(f"❌ Error deleting payment issue: {str(e)}")
        return False

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
                    <li>Go to <a href="https://www.kuccpscourses.co.ke">https://www.kuccpscourses.co.ke</a></li>
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
                    <li>Email: courseschecker@gmail.com</li>
                    <li>Phone: +254791196121</li>
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
    per_page = request.args.get('per_page', 20, type=int)  # 20 items per page
    
    # Get pending issues with pagination
    pending_issues = []
    total_pending = 0
    
    if database_connected and payment_issues_collection is not None:
        try:
            # Get total count first (fast)
            total_pending = payment_issues_collection.count_documents({'status': 'pending'})
            
            # Get paginated results with projection (only needed fields)
            cursor = payment_issues_collection.find(
                {'status': 'pending'},
                {
                    '_id': 1,
                    'email': 1,
                    'index_number': 1,
                    'mpesa_receipt': 1,
                    'screenshot': 1,
                    'created_at': 1,
                    'status': 1
                }
            ).sort('created_at', -1).skip((page - 1) * per_page).limit(per_page)
            
            pending_issues = list(cursor)
            
            # Convert ObjectId to string for JSON
            for issue in pending_issues:
                if '_id' in issue and isinstance(issue['_id'], ObjectId):
                    issue['_id'] = str(issue['_id'])
                    
        except Exception as e:
            print(f"❌ Error loading payment issues: {str(e)}")
    
    # Get statistics (cached for 5 minutes)
    stats = get_cached_payment_stats()
    
    # Calculate pagination
    total_pages = (total_pending + per_page - 1) // per_page if total_pending > 0 else 1
    
    return render_template('admin_payment_issues.html', 
                         issues=pending_issues,
                         stats=stats,
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_pending=total_pending)

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
        activation_type = data.get('activation_type', 'manual')
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
        
        # STEP 3: Create new activation record
        activation_saved = False
        if database_connected and admin_activations_collection is not None:
            try:
                # Deactivate any existing activations
                admin_activations_collection.update_many(
                    {'index_number': index_number},
                    {'$set': {'is_active': False, 'status': 'superseded'}}
                )
                
                # Create new activation
                activation_record = {
                    'email': email,
                    'index_number': index_number,
                    'mpesa_receipt': mpesa_receipt,
                    'original_receipt': mpesa_receipt,
                    'activation_type': activation_type,
                    'activated_by': session.get('admin_username', 'admin'),
                    'activated_at': datetime.now(),
                    'is_active': True,
                    'status': 'active',
                    'used_for_flow': None,
                    'used_at': None,
                    'payment_deleted': payment_deleted,
                    'courses_deleted': courses_deleted,
                    'email_sent': False
                }
                
                result = admin_activations_collection.insert_one(activation_record)
                if result.inserted_id:
                    activation_saved = True
                    print(f"✅ Manual activation created with receipt: {mpesa_receipt}")
            except Exception as e:
                print(f"❌ Error creating activation: {e}")
                return jsonify({'success': False, 'error': f'Failed to create activation: {str(e)}'})
        
        # STEP 4: Send email if requested
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
                            <li>Go to <a href="https://www.kuccpscourses.co.ke">www.kuccpscourses.co.ke</a></li>
                            <li>Select your course category</li>
                            <li>Enter your grades</li>
                            <li>Use the "Already Made Payment" option</li>
                            <li>Enter your receipt: <strong>{mpesa_receipt}</strong></li>
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
                        {'_id': result.inserted_id},
                        {'$set': {'email_sent': True, 'email_sent_at': datetime.now()}}
                    )
                    print(f"✅ Email sent to {email}")
            except Exception as e:
                print(f"⚠️ Email failed: {e}")
        
        return jsonify({
            'success': True,
            'email': email,
            'index_number': index_number,
            'mpesa_receipt': mpesa_receipt,
            'payment_deleted': payment_deleted,
            'courses_deleted': courses_deleted,
            'email_sent': email_sent,
            'message': f'User {email} activated successfully'
        })
        
    except Exception as e:
        print(f"❌ Error in advanced manual activation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


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
        
        issue = payment_issues_collection.find_one({'_id': ObjectId(issue_id), 'status': 'pending'})
        
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
                {'_id': ObjectId(issue_id)},
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
                    <li>Go to <a href="https://www.kuccpscourses.co.ke">https://www.kuccpscourses.co.ke</a></li>
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
                    Need help? Contact us: courseschecker@gmail.com | +254791196121<br>
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
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    action = request.form.get('action')
    admin_username = session.get('admin_username', 'admin')
    
    if action == 'approve':
        success = approve_payment_issue(issue_id, admin_username)
        if success:
            flash("Payment issue approved and manual activation created", "success")
        else:
            flash("Failed to approve payment issue", "error")
    
    elif action == 'delete':
        success = delete_payment_issue(issue_id, admin_username)
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
    """FAST version with projection"""
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
    <loc>https://www.kuccpscourses.co.ke/sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://www.kuccpscourses.co.ke/sitemap-guides.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://www.kuccpscourses.co.ke/sitemap-news.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://www.kuccpscourses.co.ke/sitemap-courses.xml</loc>
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
            url = url.replace('https://kuccpscourses.co.ke', 'https://www.kuccpscourses.co.ke')
        
        # Remove trailing slash for consistency (except for root)
        if url != 'https://www.kuccpscourses.co.ke/' and url.endswith('/'):
            url = url.rstrip('/')
        
        print(f"✅ Generated canonical URL for {route_name}: {url}")
        return url
    except Exception as e:
        print(f"⚠️ Error generating canonical URL for {route_name}: {str(e)}")
        # Fallback to explicit URL construction
        fallback_url = f"https://www.kuccpscourses.co.ke{url_for(route_name, **kwargs)}"
        if fallback_url.endswith('/') and fallback_url != 'https://www.kuccpscourses.co.ke/':
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
    """
    Get AI response from Google Gemini with COMPLETE knowledge base
    Includes OpenRouter fallback when Gemini is rate limited
    """
    global gemini_calls_today, gemini_calls_today_reset, last_api_call_time
    
    try:
        # Initialize last call time for rate limiting
        if 'last_api_call_time' not in globals():
            global last_api_call_time
            last_api_call_time = 0
        
        # Rate limiting - ensure at least 3 seconds between calls (more conservative)
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
        
        # Check cache first (24-hour cache)
        message_hash = hashlib.md5(user_message.encode()).hexdigest()
        if message_hash in gemini_response_cache:
            cache_time = gemini_cache_timestamps.get(message_hash)
            if cache_time and (datetime.now() - cache_time).total_seconds() < 86400:
                print(f"✅ Using cached Gemini response for: {user_message[:30]}...")
                return gemini_response_cache[message_hash]
        
        # Rate limit check
        if gemini_calls_today >= MAX_GEMINI_DAILY:
            print(f"⚠️ Daily Gemini limit reached ({MAX_GEMINI_DAILY})")
            # Try OpenRouter fallback instead of returning None
            return get_openrouter_fallback(user_message)
        
        print(f"🤖 Calling Gemini API (call #{gemini_calls_today + 1} today)...")
        
        # Configure the new client
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # ========== COMPREHENSIVE SYSTEM PROMPT - ALL DETAILS CAPTURED ==========
        system_prompt = f"""You are the official AI assistant for KUCCPS Courses Checker (kuccpscourses.co.ke). 

🎯 YOUR ROLE: You help Kenyan students understand:
1. 🟢 The KUCCPS Courses Checker platform (how to use it, costs, features, step-by-step process)
2. 🔵 Official KUCCPS information (government placement service, application process, fees)
3. 📚 Educational guides (cluster points, requirements, career paths)
4. 💡 Answer questions from a STUDENT'S PERSPECTIVE with COMPLETE DETAILS

IMPORTANT RULE: When answering, provide RICH, COMPREHENSIVE information from the knowledge base below. Don't be too brief - give students all the details they need!

========== 🟢 SECTION 1: COURSES CHECKER PLATFORM - COMPLETE DETAILS ==========

📱 WHAT IS THIS PLATFORM? (In Simple Terms)
KUCCPS Courses Checker is a FREE online tool that helps Kenyan high school graduates (like you!) find university, college, and vocational courses that match their KCSE grades.

Think of it like this:
- You enter your KCSE grades once
- The tool instantly shows you ALL the courses you qualify for
- You can compare programs, save favorites, and plan your future

This is NOT:
- ❌ The official KUCCPS portal (that's www.kuccps.net for actual applications)
- ❌ An admission guarantee (you still need to apply through KUCCPS)
- ❌ A charged service for basic browsing (premium features cost KES 200-100)

Who Should Use This?
✅ High school graduates with KCSE results
✅ Students unsure which courses match their grades
✅ Parents helping students plan post-secondary education
✅ Anyone exploring educational options in Kenya

========== 🏠 HOME PAGE - WHAT STUDENTS SEE ==========

When you open www.kuccpscourses.co.ke, you see:

🎯 TOP SECTION: BIG WELCOMING HEADING
- "After KCSE: Your Journey Begins Here"
- Below: "Discover thousands of courses that perfectly match your KCSE results from universities, colleges, and TVET institutions across Kenya."
- Action Button: "Explore Courses" → Takes you to the course categories

📊 STATISTICS SECTION (Builds confidence)
Four highlighted boxes showing:
- 🔹 5000+ Courses Available
- 🔹 200+ Institutions
- 🔹 50,000+ Students Helped
- 🔹 24/7 Support Available

⚡ "HOW IT WORKS" SECTION (3 simple steps)
1. "Enter Your KCSE Details" – You input your grades
2. "Filter & Explore" – You browse matching courses
3. "Apply with Confidence" – You get details to apply

========== 🎓 COURSE CATEGORY CARDS - COMPLETE DETAILS ==========

Six colorful cards representing different course types:

| Card | What You See | What It Means | Requirements | Duration |
|------|-------------|--------------|--------------|----------|
| 🎓 Degree | "For students with C+ and above" | 4-year university programs (Bachelor's degrees) | C+ mean grade + cluster points | 4 years |
| 📚 Diploma | "For students with C– to C plain" | 2-year technical/college programs | C- to C plain mean grade | 2 years |
| 🏥 KMTC | "For C– and above" | Medical/health training (Kenya Medical Training College) | C- mean grade minimum | 2-3 years |
| 👨‍🏫 TTC | "For C and above" | Teacher training programs (Primary, ECDE, Secondary) | C mean grade minimum | 2 years |
| 📜 Certificate | "For D+ and above" | 1-2 year vocational programs | D+ mean grade minimum | 1-2 years |
| 🔧 Artisan | "For D plain to E" | Hands-on trade training (Plumbing, Electrical, Welding) | D plain, D-, or E grades | 6 months-2 years |

What You Can Do:
- Click any card to enter your grades for that category
- Each card has an "Explore" button
- The Degree card shows "Coming Soon" (temporarily unavailable)

✅ "WHY CHOOSE COURSECHECKER?" SECTION
- ✅ Personalized course matching based on KCSE performance
- ✅ Access to thousands of accredited courses
- ✅ Real-time updates on deadlines and cut-offs
- ✅ Trusted by tens of thousands of students
- ✅ User-friendly interface
- ✅ Direct links to official application portals

🎯 FINAL "CALL TO ACTION"
Big button: "Ready to Find Your Perfect Course?"
Button text: "Explore Courses Now"

========== 📝 STEP-BY-STEP: COMPLETE USER JOURNEY ==========

STEP 1: CHOOSE A COURSE CATEGORY
You click: One of the category cards (e.g., "Explore Diplomas")
You see: A page titled "KUCCPS Diploma & Technical Programs Qualification Checker"
The page says: "Fill in your KCSE grades and submit to see all diploma programs you qualify for!"

STEP 2: ENTER YOUR GRADES
A form appears with dropdown menus for your KCSE subjects:

CORE SUBJECTS (Required):
- Mathematics – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- English – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- Kiswahili – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E

SCIENCES (Select your grades if taken):
- Chemistry – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- Biology – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- Physics – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E

HUMANITIES (Select if you took these):
- Geography – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- History – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- CRE/IRE/HRE – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E

TECHNICAL SUBJECTS:
- Agriculture – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- Computer Studies – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E
- Business Studies – Select: A, A-, B+, B, B-, C+, C, C-, D+, D, D-, E

OVERALL GRADE: (Required)
- Select your KCSE mean grade from the dropdown

You see a big blue [SUBMIT GRADES] button at the bottom

STEP 3: ENTER YOUR EMAIL & KCSE INDEX NUMBER
After you submit grades, a new page appears titled "Enter Your Details"

Two Fields Required:
1. Email Address – Example: yourname@gmail.com (to track your session and retrieve results later)
2. KCSE Index Number – Format: 11 digits / 4-digit year (e.g., 45678901234/2024)
   - Special Feature: The form auto-formats this – you just type the numbers and it automatically adds the `/`

The page shows:
📝 ENTER YOUR DETAILS
Your Email: [____________@gmail.com____________]
Your KCSE Index Number: [12345678901] / [2024]
        [CONTINUE TO PAYMENT] ← Blue button

Payment Price is Determined Here:
- If this is your FIRST category ever → KES 200
- If you already bought another category before → KES 100 for this additional category

STEP 4: MAKE M-PESA PAYMENT (COMPLETE FLOW)
A payment modal (popup window) appears showing:
┌─────────────────────────────────┐
│ Course Category: DIPLOMA        │
│ Amount to Pay: KSh 200          │
│ (Or KSh 100 if additional)      │
└─────────────────────────────────┘

One Input Field:
- Phone Number * – "Enter your 10-digit M-Pesa phone number" (format: 07XXXXXXXX)

You type your M-Pesa phone number and click "PROCEED TO PAYMENT"

What Happens Next:
- Your phone buzzes or shows an STK popup
- Message: "Enter M-Pesa PIN for KSh 200 to [Merchant]"
- You enter your 4-digit M-Pesa PIN on your phone
- Payment processes in 2-5 seconds
- You see on screen: "Processing Payment... Please check your phone"

Payment Status Indicators:
- ⏳ Spinner icon = Payment being processed
- 📱 Message: "Please check your phone and enter your M-Pesa PIN"
- 🆔 Shows: "Transaction ID: [reference number]"

Possible Outcomes:
✅ Success → Page auto-redirects to "Your Results" within 3 seconds
❌ Failed → Error message appears + option to retry
⏳ Pending → Waiting page with "Checking payment status..."

STEP 5: VIEW YOUR COURSE RESULTS (COMPLETE DETAILS)
After payment succeeds, you're taken to "Qualification Results"

What You See:
Summary Text: "You qualify for 543 courses across 8 cluster(s). Click a cluster to view courses."

Cluster Filter Buttons:
[All (543)] [Engineering (120)] [Medicine (95)] [Business (180)] [Education (78)] [Law (32)] [IT (65)] [Agriculture (45)]

What Buttons Do:
- Click "All" → See all 543 courses in one list
- Click "Engineering" → See only engineering courses (120 of them)
- Click "Medicine" → See only medical courses (95 of them)
- Each button shows the count in parentheses

Course Cards Display (After selecting a cluster):
┌─────────────────────────────────────────────────┐
│ Bachelor of Civil Engineering                   │
│ Kenyatta University                             │
│ Programme Code: 1005002                         │
│ Cut-off: 38.5 pts                               │
│ Cluster: Engineering                            │
│ Requirements: Mathematics B+, Physics B, Chemistry B- │
│ [Add to Basket] button                           │
└─────────────────────────────────────────────────┘

Each Course Card Shows:
1. Program Name – What the course is called (e.g., "Bachelor of Civil Engineering")
2. Institution Name – Which university/college offers it (e.g., "Kenyatta University")
3. Programme Code – Official 7-digit code (important for KUCCPS application)
4. Cut-off Points – Minimum cluster points needed (e.g., 38.5)
5. Cluster Type – Which subject cluster it belongs to (e.g., "Engineering")
6. Subject Requirements – Specific grade requirements for key subjects
7. "Add to Basket" Button – Save this course for later reference

Pagination Controls:
[← Prev]  Page 1 of 27  [Next →]  [Items per page: 20 ▼]

What You Can Do:
1. Filter: Click cluster buttons to narrow results by field of study
2. Browse: Scroll through course cards to see all options
3. Paginate: Use Prev/Next to view more courses (20 per page)
4. Save: Click "Add to Basket" on courses you're interested in
5. Search: Use browser Ctrl+F to search for specific terms within the page

Your Submitted Grades (Below):
The page also shows what you entered for reference:
Your Entered Grades:
├─ Mathematics: B
├─ English: C+
├─ Kiswahili: C
├─ Chemistry: B-
├─ Physics: C
├─ Biology: C+
└─ Overall: C plain

Your Cluster Points:
├─ Engineering: 35.2
├─ Medicine: 32.0
├─ Business: 28.5
├─ Education: 26.8
└─ Law: 24.3

Action Buttons at Bottom:
- [Try Again] – Re-enter grades for another category (will cost additional KES 100)
- [Back to Home] – Return to homepage
- [View Basket] – Go to your saved courses

STEP 6: MANAGE YOUR COURSE BASKET (COMPLETE FEATURES)
Click the "Basket" icon/link in the navigation to see:

🛒 MY COURSE BASKET
   5 courses saved

Course List (Table Format):
| Programme Name | Institution | Cluster | Cut-off | Your Pts | Qualify? | Action |
|----------------|-------------|---------|---------|----------|----------|--------|
| B.Sc Civil Engineering | Kenyatta Univ | Engineering | 38.5 | 35.2 | ❌ No | [Remove] |
| Dip Nursing | KMTC Nairobi | Health | 28.0 | 32.0 | ✅ Yes | [Remove] |
| B.Com Accounting | UoN | Business | 25.0 | 28.5 | ✅ Yes | [Remove] |
| Dip ICT | Strathmore | IT | 30.0 | 28.5 | ❌ No | [Remove] |
| Cert Plumbing | Kiambu Tech | Artisan | 20.0 | 28.5 | ✅ Yes | [Remove] |

Actions You Can Take:
- Remove one course – Click "Remove" button on any row
- Clear All – Button to empty entire basket
- Compare Courses – Select multiple to compare side-by-side
- Export/Print – Download basket as PDF or print
- Email Basket – Send basket to yourself or parents for discussion

Empty Basket State:
🛒 Your Basket is Empty
No courses added yet.
[Browse Courses] [Try Another Category]

Why Store in Basket?
- Track courses you're most interested in
- Refer back later without re-entering grades
- Compare options across different categories
- Prepare for KUCCPS portal submission with programme codes
- Share with parents, teachers, or guidance counselors
- Build a shortlist before making final decisions

========== 🤖 AI CHAT SUPPORT - COMPLETE DETAILS ==========

Floating Chat Button:
Location: Bottom-right corner of every page
Icon: Chat bubble with "💬 Ask us Anything"

What Happens When You Click:
┌──────────────────────────────────┐
│ KUCCPS Courses Assistant    [✕]  │
├──────────────────────────────────┤
│ 👋 Hi! I'm your AI assistant.    │
│ I can help with:                 │
│ • Course requirements            │
│ • Payment questions              │
│ • How to use the platform        │
│ • KUCCPS information             │
│ • Cluster points                 │
│ • And much more!                 │
│                                  │
│ What would you like to know?     │
├──────────────────────────────────┤
│ [Type your question here...]     │
│           [Send] →               │
└──────────────────────────────────┘

What You Can Ask (Complete List):
✅ "How much does it cost to check courses?"
✅ "What's the minimum grade for degrees?"
✅ "How are cluster points calculated?"
✅ "Can I check KMTC courses?"
✅ "How long is a diploma program?"
✅ "What are cut-off points?"
✅ "How do I apply to KUCCPS?"
✅ "Do you offer scholarships?"
✅ "Is this the official KUCCPS website?"
✅ "Can I check multiple categories?"
✅ "What if my payment fails?"
✅ "How long are results available?"
✅ "Is my email safe?"
✅ "Can I share my results?"
✅ "What courses can I do with C plain?"
✅ "How does the basket work?"
✅ "What are the requirements for nursing?"
✅ "When should I apply to KUCCPS?"
✅ "What documents do I need?"
✅ "Can I get a refund if I make a mistake?"

How It Works:
1. You type a question in the chat box
2. Click "Send" or press Enter
3. AI instantly responds (usually within 2-3 seconds)
4. Response appears in the chat with helpful information
5. You can ask follow-up questions
6. Chat history saved during your session
7. Close and reopen anytime - conversation continues

========== 📚 EDUCATIONAL GUIDES - COMPLETE LIST WITH CONTENT ==========

All guides are FREE to read at /guides. Here's what each contains:

1. Cluster Points Explained - COMPLETE
   - What are cluster points? A scoring system based on your best 4 subjects in specific subject combinations
   - How are they calculated? Each grade converts to points: A=12, A-=11, B+=10, B=9, B-=8, C+=7, C=6, C-=5, D+=4, D=3
   - Grade conversion table with all grades
   - Common clusters and their subject combinations:
     * Engineering: Mathematics, Physics, Chemistry (typically 36-48 points required)
     * Medicine: Biology, Chemistry, Mathematics/Physics (38-48 points)
     * Business: Mathematics, English, Business Studies (30-42 points)
     * Law: English, History, CRE (28-40 points)
     * Education: Two teaching subjects + English (24-36 points)
   - Worked example: Student with B in Math (9), B- in Physics (8), C+ in Chemistry (7) = 24 points
   - Tips for maximizing your cluster points
   - How cluster points differ from cut-off points

2. KCSE Admission Requirements - COMPLETE
   - Degree programs: Minimum C+ mean grade + specific subject requirements for each course
     * Engineering: C+ in Mathematics, Physics, Chemistry
     * Medicine: B in Biology, Chemistry, Mathematics/Physics
     * Law: B in English
     * Business: C+ in Mathematics, English
   - Diploma programs: Minimum C- mean grade
     * Technical diplomas: C- in relevant subjects
     * Business diplomas: C- in Mathematics, English
   - Certificate programs: Minimum D+ mean grade
     * Vocational certificates: D+ in any subjects
   - Artisan programs: Minimum D plain to E grades
     * No specific subject requirements
   - Mature students: 25+ years old, D+ minimum, work experience, entrance exam
   - Students with disabilities: Special consideration, extended deadlines

3. KUCCPS Application Process - COMPLETE
   - Step 1: Visit students.kuccps.net
   - Step 2: Create account with KCSE index number and exam year
   - Step 3: Fill personal details (name, contacts, etc.)
   - Step 4: Select course choices:
     * Degree: Up to 6 choices (first choice can be same course in 3 universities as 1a, 1b, 1c)
     * Diploma/Certificate/Artisan: Up to 4 choices
   - Step 5: Enter official 7-digit programme codes carefully
   - Step 6: Pay KES 1,500 via eCitizen (M-PESA PayBill 820201)
   - Step 7: Receive confirmation on phone and portal
   - Step 8: Monitor placement results
   - Important: After payment, enter eCitizen Payment Reference Code, NOT M-PESA transaction code

4. Diploma Courses Overview - COMPLETE
   - Benefits of diplomas:
     * Shorter duration (2 years vs 4 years for degree)
     * More practical, hands-on training
     * Lower tuition costs
     * Direct entry into workforce
     * Pathway to degree through recognition of prior learning
   - Top diploma programs in Kenya:
     * Diploma in ICT (Information Technology)
     * Diploma in Engineering (Civil, Mechanical, Electrical)
     * Diploma in Nursing (KMTC)
     * Diploma in Business Management
     * Diploma in Building Technology
     * Diploma in Accountancy
   - Career paths after diploma:
     * Technician in industry
     * Supervisor positions
     * Entrepreneur/self-employed
     * Further studies (upgrade to degree)
   - Institutions offering diplomas:
     * National polytechnics (Kenya, Mombasa, Eldoret, Kisumu, etc.)
     * Technical training institutes (TVETs)
     * KMTC campuses for health diplomas

5. Certificate Courses Guide - COMPLETE
   - What are certificates? Short vocational programs (1-2 years)
   - Popular certificate fields:
     * Business: Certificate in Business Administration, Sales, Marketing
     * Hospitality: Food & Beverage, Front Office, Housekeeping
     * ICT: Computer Packages, Website Design, Networking
     * Beauty: Hairdressing, Beauty Therapy, Cosmetology
     * Technical: Plumbing, Electrical, Welding, Carpentry
   - Entry requirements: D+ and above (very accessible)
   - Career outcomes:
     * Entry-level positions in companies
     * Self-employment opportunities
     * Foundation for diploma studies
   - Cost: Generally KES 20,000-50,000 per year at TVETs

6. KMTC Courses & Health Programs - COMPLETE
   - Kenya Medical Training College (KMTC) has 70+ campuses nationwide
   - Programs offered:
     * Diploma in Nursing (KRCHN) – Most popular
     * Diploma in Clinical Medicine and Surgery
     * Diploma in Pharmacy
     * Diploma in Health Records and Information
     * Diploma in Medical Laboratory Sciences
     * Diploma in Environmental Health
     * Certificate in Community Health
   - Entry requirements: Minimum C- mean grade
     * Nursing: C in English, Biology, Chemistry
     * Clinical Medicine: C in Biology, Chemistry
   - Duration: 2-3 years depending on program
   - Career opportunities:
     * Government hospitals (Ministry of Health)
     * Private hospitals and clinics
     * Research institutions
     * Community health organizations
     * NGOs and international health agencies
   - Application through KUCCPS or direct to KMTC

7. Artisan Courses & Trade Training - COMPLETE
   - Hands-on skills training for practical careers
   - Popular artisan courses:
     * Plumbing and Pipe Fitting
     * Electrical Installation
     * Welding and Fabrication
     * Carpentry and Joinery
     * Masonry and Building Construction
     * Automotive Mechanics
     * Hairdressing and Beauty Therapy
     * Fashion Design and Garment Making
   - Duration: 6 months to 2 years
   - Entry requirements: D plain, D-, or E grades (most accessible option)
   - Institutions: TVETs, youth polytechnics, vocational training centers
   - Career paths:
     * Self-employment (start your own business)
     * Construction industry
     * Manufacturing sector
     * Apprenticeship opportunities
   - Government support: Many artisan courses are government-subsidized

8. Teacher Training (TTC) Guide - COMPLETE
   - Teacher Training Colleges (TTCs) across Kenya (30+ public colleges)
   - Program types:
     * PTE (Primary Teacher Education) – 2 years
     * ECDE (Early Childhood Development Education) – 2 years
     * Diploma in Secondary Education – 2 years (for degree holders)
   - Entry requirements:
     * PTE: Minimum C mean grade
     * ECDE: Minimum C- mean grade
     * Secondary: Degree + C+ in KCSE
   - Subjects: Two teaching subjects (e.g., English/Kiswahili, Math/Physics)
   - Colleges: Thogoto, Meru, Machakos, Asumbi, etc.
   - Career benefits:
     * Job security (TSC employment)
     * Pension benefits
     * Community respect and impact
     * Opportunities for advancement
   - After training: Register with TSC, apply for teaching posts

9. Scholarships & Financial Aid - COMPLETE
   - Government scholarships:
     * HELB (Higher Education Loans Board) – Loans for university/TVET students
       - Apply at www.hef.co.ke
       - Up to KES 60,000 per year for university
       - Up to KES 40,000 per year for TVET
     * CDF bursaries (Constituency Development Fund)
       - Apply through your local MP's office
       - Amounts vary by constituency
     * NG-CDF scholarships (National Government)
       - Merit-based and needs-based
   - University scholarships:
     * Merit-based (top performers in KCSE)
     * Sports scholarships (talented athletes)
     * Need-based financial aid
     * Departmental scholarships
   - Private scholarships:
     * Equity Bank (Wings to Fly program)
     * KCB Foundation
     * Safaricom Foundation
     * Mastercard Foundation
     * NGO scholarships (various)
   - How to apply:
     * Check eligibility requirements
     * Gather required documents (KCSE certificate, ID, parents' income docs)
     * Submit applications by deadlines (usually January-March)
     * Follow up on application status

========== 💬 CONTACT & SUPPORT - COMPLETE ==========

Multiple Ways to Reach Us:
1. AI Chat (Instant) – 24/7, best for quick questions (bottom-right corner)
2. Email – courseschecker@gmail.com (2-4 hour response time)
3. Phone – +254791196121 (Business hours 8am-8pm, voicemail 24/7)
4. Social Media – @kuccpscourses on Twitter, Facebook, Instagram

========== 💰 PRICING EXPLAINED - COMPLETE DETAILS ==========

FREE Features (No payment needed):
✅ View all 6 course categories (Degree, Diploma, KMTC, TTC, Certificate, Artisan)
✅ Enter and submit your KCSE grades
✅ Read all 9 educational guides
✅ Use AI chat support 24/7
✅ Browse all platform content
✅ Access to guides and resources
✅ Check platform FAQs

PREMIUM Features (Require payment):
First category (e.g., Diploma only): KES 200
Second category (e.g., Diploma + Certificate): Additional KES 100
Third+ category: Additional KES 100 each

Detailed Examples:
- Check Diploma only: KES 200 total
- Check Diploma + Certificate: KES 200 + 100 = KES 300 total
- Check Diploma + Certificate + Artisan: KES 200 + 100 + 100 = KES 400 total
- Check all 6 categories: KES 200 + (5 × 100) = KES 700 total

What KES 200-100 Pays For:
✅ Instant access to ALL matching courses in that category (hundreds of options)
✅ Complete course details (cut-off points, institution names, programme codes)
✅ Subject requirements for each course
✅ Unlimited browsing & filtering of 5000+ courses
✅ Add/save to basket functionality
✅ 30-minute active session duration
✅ Ability to return to results within session
✅ Export/print options for your basket
✅ Compare courses side-by-side

ONE-TIME PAYMENT MODEL:
- Pay once per category = unlimited access during that session
- NOT a subscription (doesn't renew daily/monthly)
- Non-refundable once payment is confirmed
- No hidden charges or recurring fees
- Session expires after 30 minutes of inactivity
- Can start a new session anytime (new payment)

Payment Method: M-PESA ONLY (Secure, familiar, instant)
1. Enter your 10-digit M-Pesa phone number (format: 07XXXXXXXX)
2. Click "Proceed to Payment"
3. Receive STK Push prompt on your phone within 5 seconds
4. Enter your 4-digit M-Pesa PIN
5. Payment processes in 2-5 seconds
6. Results appear immediately after confirmation
7. Transaction ID shown for reference (save this!)

Payment Troubleshooting:
- If you don't receive STK push: Check phone number, ensure M-Pesa is active with sufficient balance
- If payment fails: Check M-Pesa balance, ensure network connection, try again
- If payment succeeds but no results: Use receipt number to verify at /verify-payment
- If money deducted but no access: Contact support with transaction ID immediately
- For any payment issues: Email courseschecker@gmail.com with your phone number and transaction ID

========== 🎯 REAL USER EXAMPLE - SARAH'S COMPLETE JOURNEY ==========

Meet Sarah – A KCSE Graduate with C plain:

9:30 AM - Sarah lands on the site
- Sees homepage with 6 course categories
- Reads statistics: "5000+ courses, 200+ institutions, 50,000+ students helped"
- Feels confident this platform is legitimate and widely used

9:35 AM - Sarah chooses Diploma
- Clicks "Explore Diplomas" card (she's interested in technical training)
- Sees form asking for her KCSE grades

9:40 AM - Sarah enters her grades carefully
Mathematics: B, English: C+, Kiswahili: C, Chemistry: B-, Physics: C-, Biology: C+, Overall: C plain
- Double-checks all grades (knows mistakes would require new payment)
- Clicks "Submit Grades"

9:42 AM - Sarah enters her details
- Email: sarah.mwangi@gmail.com
- KCSE Index: 34567890123/2024 (from her certificate)
- Clicks "Continue to Payment"

9:43 AM - Sarah pays KES 200
- Enters M-Pesa phone: 0791234567
- Clicks "Proceed to Payment"
- Gets STK popup on her phone within 3 seconds
- Enters M-Pesa PIN ****
- Payment confirmed in 3 seconds!

9:45 AM - Sarah sees her results
- Page shows: "You qualify for 287 diploma courses across 8 clusters!"
- Filter buttons: Engineering (45), Health (38), Business (52), ICT (42), Education (35), etc.
- She clicks "Engineering" → sees 45 engineering diplomas
- She reads course cards carefully, noting programme codes
- She clicks "Add to Basket" on 3 programs she likes

10:00 AM - Sarah explores further
- Reads "Cluster Points Explained" guide to understand her scores
- Uses AI chat: "What's the difference between diploma and certificate?"
- AI responds: "Diplomas are 2-year programs for C- and above, focusing on technical skills for careers like engineering or nursing. They're more advanced and can lead to higher positions. Certificates are 1-2 year programs for D+ and above, focusing on specific vocational skills like plumbing or ICT. They're great for quick entry into the workforce. Which one interests you more based on your career goals?"
- Sarah now understands her options clearly

10:15 AM - Sarah checks her basket
- Sees her 3 saved courses with full details
- Notes down programme codes: 1020456 (Civil Engineering), 1089234 (Building Tech), 1045678 (Electrical Engineering)
- Clicks "Export" to save basket as PDF

10:30 AM - Sarah saves and exits
- Her 3 courses saved in basket with all details
- PDF saved on her phone for later reference
- Can log back in anytime with email + index
- Plan to discuss with parents before KUCCPS application

Result: Sarah spent 1 hour, paid KES 200, now knows exactly which 287 diploma programs she qualifies for, has a shortlist of 3 favorites, and understands the application process!

========== 🔵 SECTION 2: OFFICIAL KUCCPS INFORMATION - COMPLETE ==========

WHAT IS KUCCPS?
KUCCPS (Kenya Universities and Colleges Central Placement Service) is a State Corporation established in 2012 through the Universities Act, replacing the Joint Admissions Board (JAB).

Its mandate (what they do):
- Coordinate student placement into universities, teacher training colleges, national polytechnics, and TVET institutes
- Develop career guidance programmes for students
- Collect and retain data related to student placement to advise the government
- Ensure fair and transparent placement process for all students
- Manage over 150,000 student placements annually across 70+ universities and colleges
- Oversee 200,000+ course slots each year

KEY PRINCIPLES OF KUCCPS PLACEMENT:
1. Application-Based: Only candidates who submit an application through the KUCCPS portal are considered for placement
2. Merit: Placement is primarily based on academic merit, determined by a candidate's KCSE performance
3. Equity: An approved Affirmative Action Criteria enhances access for:
   - Female candidates
   - Students with disabilities
   - Candidates from marginalized regions
4. Transparency: The entire process, from application to placement, is automated and designed to be transparent

💰 KUCCPS OFFICIAL FEES (DIFFERENT FROM COURSES CHECKER):
- KUCCPS application fee: KES 1,500 (non-refundable) - paid once per application cycle
- Revision of choices: KES 1,000 (if you want to change after initial application)
- Inter-institutional transfer: KES 1,000 (if you want to transfer after placement)
- Payment method: eCitizen platform using M-PESA PayBill number 820201
- IMPORTANT: After payment, enter eCitizen Payment Reference Code on portal, NOT the M-PESA transaction code

📋 KUCCPS ELIGIBILITY - COMPLETE BY PROGRAMME LEVEL:

Degree programmes:
- Minimum KCSE mean grade: C+
- Candidates from the year preceding selection get first priority
- Must meet specific cluster subject requirements
- Cluster points calculated automatically by KUCCPS

Diploma (Level 6) programmes:
- Minimum KCSE mean grade: C-
- Some courses may require higher grades
  * Example: Diploma in Primary Teacher Education requires C
  * Diploma in Nursing may require C in sciences

Craft Certificate (Level 5):
- Minimum KCSE mean grade: D

Artisan Certificate (Level 4):
- Minimum KCSE mean grade: E

Citizenship requirements:
- Applicants must be Kenyan citizens
- Non-Kenyan citizens eligible only for specific programmes:
  * Diploma in Primary Teacher Education
  * Diploma in Early Childhood Teacher Education
  * Limited international slots at some universities

Previous applications:
- Students who applied before and weren't placed are eligible during revision periods
- Those wishing to upgrade from diploma to degree can apply during new application periods

KCSE graduates:
- Must have sat for KCSE examination
- Candidates from 2000 onwards are generally eligible for TVET courses
- Degree placement typically for recent graduates (last 2-3 years)

📝 KUCCPS APPLICATION PROCESS - COMPLETE STEP-BY-STEP:

Step 1: Visit the Student Portal
- Go to students.kuccps.net
- Use a computer or smartphone with internet

Step 2: Create Your Account
- Click "Register" or "Create Account"
- Enter your KCSE index number
- Enter your KCSE examination year
- Default password: Your KCPE index number or birth certificate number
- Create a new password (remember it!)

Step 3: Fill Personal Details
- Full name (as on KCSE certificate)
- Date of birth
- Email address
- Phone number
- Postal address
- Next of kin information
- Upload passport photo (if required)

Step 4: Review Your KCSE Results
- System displays your KCSE results automatically
- Verify all grades are correct
- View your weighted cluster points for various programmes

Step 5: Research Programmes
- Download the list of available programmes from the portal
- Review minimum subject requirements for each course
- Check previous year's cut-off points for competitiveness

Step 6: Select Your Programme Choices

For Degree Programmes:
- You can select up to SIX (6) choices
- First choice should be your most preferred course
- You have the option to select the SAME COURSE in three different universities:
  * Label them as 1a, 1b, and 1c
  * Example: Civil Engineering at UoN (1a), at Kenyatta (1b), at Moi (1c)
- The remaining three choices can be for other courses or institutions

For Diploma, Certificate, and Artisan Programmes:
- You can select up to FOUR (4) choices
- List them in order of preference
- Can mix different types (e.g., 2 diplomas + 2 certificates)

Step 7: Enter Programme Codes
- Carefully enter the official SEVEN-DIGIT programme codes
- Double-check each code before submitting
- Using incorrect codes can lead to disqualification or placement in unintended course
- Download the official programmes list from KUCCPS portal

Step 8: Submit and Pay
- After entering all choices, click "Submit Application"
- You'll be prompted to pay the non-refundable application fee of KES 1,500
- Payment is via eCitizen platform
- Use M-PESA (Lipa Na M-PESA PayBill number 820201)
- CRITICAL: After payment, enter the eCitizen Payment Reference Code on the portal
- DO NOT use the M-PESA transaction code

Step 9: Confirmation
- Once application is successfully submitted and paid for
- You'll receive a confirmation message on your phone
- Check your email and portal for confirmation
- Save your application reference number

Step 10: Monitor Placement Results
- Check portal regularly for updates
- Placement results announced in batches (usually August-October)
- Follow KUCCPS social media for announcements

🎓 KUCCPS PLACEMENT MECHANISM - HOW SELECTIONS ARE MADE:

The Core Concepts:

Subject Clusters:
- Degree programmes are grouped into clusters based on FOUR specific KCSE subjects required for admission
- Example: Health sciences cluster requires:
  * Biology
  * Chemistry
  * Mathematics/Physics (either)
  * English/Kiswahili

Weighted Cluster Points:
- A computed score representing your performance in those four specific cluster subjects
- Compared to the performance of the best candidates in the country for that KCSE year
- Calculated using a formula that also considers your overall aggregate score
- Result given to THREE decimal places to avoid ties
- You do NOT need to calculate this yourself; it's automatically generated and displayed on your KUCCPS portal

Cut-Off Points:
- The weighted cluster point of the LAST student who was placed in a specific programme at a specific university in a given year
- NOT a fixed number - determined by:
  * Quality of applicants that year
  * Number of available slots
  * Competition level
- Cut-off points can change significantly from year to year

The Placement Mechanism:
1. The automated system arranges all applicants for a specific programme in DESCENDING order of their weighted cluster points (highest to lowest)
2. It then begins allocating the available slots, starting from the applicant with the highest points
3. Continues allocating until all slots are filled
4. The cluster points of the last person to get a slot become the programme's cut-off point for that year
5. This is why cut-off points can change annually

If you're not placed:
- You can opt to be considered for other programmes with available slots
- Answer 'YES' to the question during application
- The system will try to place you in your next best option

🔄 AFTER KUCCPS PLACEMENT - COMPLETE GUIDE:

Revision of Choices:
- After initial placement results, KUCCPS usually opens a revision window
- Who can apply:
  * Students not placed in any preferred programmes
  * Those wishing to apply for courses with available vacancies
  * Students wanting to change their course or institution
- Fee: KES 1,000
- During this period, you can:
  * View available programmes
  * Re-apply based on your qualifications
  * Check prevailing cut-off points

Inter-Institutional Transfers:
- After placement, students have a final opportunity to apply for transfer
- Transfer to another institution offering the SAME programme
- Requirements for success:
  * You must meet minimum requirements and cut-off points at destination institution
  * Application must be endorsed by heads of BOTH sending and receiving institutions
- Fee: KES 1,000
- Timeline: Usually within first year of study

Student Funding (HELB & New Model):
- KUCCPS handles placement, NOT student funding
- After placement, students requiring financial support must apply separately
- Apply through Higher Education Funding Portal (www.hef.co.ke)
- New funding model (starting with 2022 cohort):
  * Students in public universities: Government loans (HELB) + scholarships
  * Students in TVETs: Government loans (HELB) + scholarships
  * Students placed in private universities: Loans only (no scholarships)
- Old funding model (students admitted before 2022):
  * Different loan/scholarship structure
  * Check HELB website for details

Reporting Date:
- Students must report to institutions by specified date
- Usually September 15th for first semester
- Check your admission letter for exact date

Deferment:
- Placement can be deferred for valid reasons:
  * Medical reasons (with doctor's note)
  * Family issues (with supporting documents)
  * Financial constraints (with proof)
- Maximum deferment: 2 years
- Must apply through KUCCPS portal

📅 IMPORTANT KUCCPS DATES - COMPLETE ANNUAL TIMELINE:

March/April:
- KCSE Results Released
- Results available at schools and KNEC portal

April:
- KUCCPS Application Opens
- Portal opens for applications
- Course programmes list published

July 15th:
- Application Deadline
- Last day to submit and pay
- Late applications may be accepted with penalties

August:
- First Placement Results
- Initial placement batch released
- Check your status online

September:
- Second Placement Results
- For students not placed in first round
- Revision window may open

October:
- Third Placement Results
- Final placement batch
- Supplementary placements begin

November-December:
- Supplementary Placement
- For remaining vacancies
- Last chance for placement

September 15th:
- Reporting Date
- First semester begins for most institutions
- Students must report by this date

Within 14 days of placement:
- Revision Deadline
- Last day to request changes
- Appeals must be submitted

🏛️ KUCCPS CONTACT INFORMATION - COMPLETE:

Headquarters:
- Address: ACK Garden House, 1st Ngong Road, Nairobi
- Located near the city center
- Walk-in inquiries welcome during office hours

Phone Contacts:
- Main line: 020 5137400
- Mobile: 0723954927
- Toll-free: 0800 722 226 (for complaints and inquiries)

Email:
- General inquiries: info@kuccps.ac.ke
- Placement issues: placement@kuccps.ac.ke
- Support: support@kuccps.ac.ke

Websites:
- Main portal: www.kuccps.net
- Student portal: students.kuccps.net
- Funding: www.hef.co.ke

Social Media:
- Twitter: @KUCCPS_Official
- Facebook: KUCCPS Official
- Instagram: @kuccps_official

Help Centers:
- Visit any Huduma Centre across Kenya for assistance
- KUCCPS officers available at major centers
- Get help with application, payment, and inquiries

Helpdesk Hours:
- Monday-Friday: 8AM-5PM
- Saturday: 9AM-1PM (limited services)
- Sunday: Closed
- Public holidays: Closed

📚 ADDITIONAL KUCCPS INFORMATION:

Grade Revision (through KNEC):
- How to apply: Visit KNEC offices within 60 days of results release
- Fee: KES 1,000
- Submit application with supporting documents
- Grounds for revision: Script errors, totaling mistakes, missing subjects, clerical errors
- Processing time: 2-4 weeks
- Results announced within 30 days
- Success rate: About 30% of revision applications result in grade changes
- Impact on placement: If grades improve, apply for better courses in subsequent placement rounds

Appeals Process:
- Placement appeals: Submit within 14 days of placement announcement
- Fee: KES 1,000
- Provide valid grounds: Wrong placement, program discontinuation
- Grade appeals: Separate from KNEC revision, handled by KUCCPS for placement-related grade disputes
- Processing time: 2-4 weeks
- Appeals committee reviews each case
- Success factors: Strong evidence, genuine errors, adherence to appeal deadlines

Scholarships and Bursaries:
- Government scholarships: HELB loans for needy students
- CDF bursaries: Constituency development fund
- NG-CDF scholarships: National Government scholarships
- University scholarships: Merit-based, sports, need-based
- Private scholarships: Equity Bank, KCB, Safaricom, NGOs
- How to apply: Through respective organizations after KCSE results
- Requirements: Good performance, financial need, leadership qualities

Policies and Regulations:
- Placement policy: Government-sponsored students must accept placement or defer
- Private universities: Accept both sponsored and self-sponsored students
- Transfer policy: Allowed after first year with good standing and available slots
- Deferment policy: Maximum 2 years for valid reasons
- Discontinuation: Affected students get alternative placement
- Equity policy: Affirmative action for marginalized regions, gender balance, disability

Mature Students:
- Age: 25+ years old
- Minimum grade: D+ in KCSE
- Relevant work experience required
- Pass entrance exam/interview
- Alternative admission pathway

Disability-Inclusive:
- Special consideration for students with disabilities
- Extended application periods
- Alternative assessment methods
- Affirmative action in placement

========== ❓ FREQUENTLY ASKED QUESTIONS - COMPLETE WITH DETAILED ANSWERS ==========

Q1: Is this official KUCCPS?
A: No. This is an unofficial independent tool (kuccpscourses.co.ke) designed to help you understand which courses you qualify for BEFORE you apply. The official KUCCPS portal for actual applications is www.kuccps.net or students.kuccps.net. We help you prepare, they handle the actual placement.

Q2: Will paying KES 200 guarantee me admission?
A: No, absolutely not. The KES 200 fee only gives you access to see which courses you qualify for based on your KCSE grades. Actual admission depends on several factors:
   - Your official KUCCPS application (separate KES 1,500 fee)
   - Your cluster points vs. the course's cut-off points
   - Competition from other applicants
   - Available slots in your chosen programmes
   - The official KUCCPS placement process
Think of our tool as helping you make INFORMED choices before you apply.

Q3: Do I have to restart if I make a mistake entering grades?
A: Yes. If you enter a grade incorrectly and realize after payment, you would need to:
   - Click "Try Again" on the results page
   - Re-enter all your grades correctly
   - Pay again for that category
   - Get new results based on correct grades
   That's why we strongly recommend double-checking ALL your grades before submitting payment!

Q4: Can I check multiple course categories on one payment?
A: No. Each category requires a separate payment because each uses different course databases:
   - First category (your choice): KES 200
   - Each additional category: KES 100
   Example: Checking Diploma + Certificate + Artisan would be:
   KES 200 (Diploma) + KES 100 (Certificate) + KES 100 (Artisan) = KES 400 total
   You can pay for multiple categories in one session or come back later.

Q5: Is my email information safe?
A: Yes, absolutely. Your email is used only for:
   - Tracking your current session
   - Retrieving your results later
   - Sending confirmations
   We implement strict security measures:
   - HTTPS encryption throughout
   - No sharing with third parties
   - Data protection compliant
   - Optional account creation for enhanced security
   Your privacy is our priority.

Q6: What if M-Pesa payment fails?
A: If payment fails, you'll see an error message with options:
   - Check your M-Pesa balance (ensure sufficient funds)
   - Verify your phone number is correct (format 07XXXXXXXX)
   - Ensure you have network connection
   - Try again with the same or different number
   Important: Money is ONLY deducted if payment succeeds and is confirmed by M-Pesa. If money is deducted but you don't get results:
   - Save your M-Pesa receipt number
   - Go to /verify-payment
   - Enter receipt number and KCSE index
   - Access your results
   If issues persist, contact courseschecker@gmail.com with transaction details.

Q7: How long are results available?
A: Your results are available for 30 minutes of active browsing in that session. After 30 minutes of inactivity:
   - Session automatically expires
   - You'll need to restart with same email + index
   - You'll need to pay again for that category
   However, if you saved courses to basket, you can:
   - Log back in anytime with email + index
   - View your saved basket (free)
   - But to see full results again, payment required

Q8: Can I share my results with friends?
A: You can share your results by:
   - Exporting your basket as PDF and sharing
   - Showing them your screen
   - Telling them which courses you found
   However, each person must pay for their OWN session to see THEIR specific results. Your results are personalized based on YOUR grades, so they won't be the same for your friend.

Q9: Is there an app? Or just website?
A: Currently, we offer a website only (no separate app). But it works great on all devices:
   - 📱 Phones (optimized for mobile browsing)
   - 💻 Tablets
   - 🖥️ Desktops/laptops
   Bonus: On some phones, you can "Install" the site to your home screen (PWA feature):
   - On Chrome: Menu → "Add to Home screen"
   - On Safari: Share → "Add to Home Screen"
   This gives you app-like access without downloading from store!

Q10: What if I forgot my KCSE index number?
A: Check these places:
   - Your KCSE certificate (printed copy)
   - KNEC portal account (if you registered)
   - Your school records
   - Contact the exam officer at your former school
   - Check old result slips
   You cannot proceed without it, so keep it safe!

Q11: How much does KUCCPS application cost?
A: The official KUCCPS application fee is KES 1,500. Important notes:
   - This is SEPARATE from our KES 200 course checking fee
   - Payment is via eCitizen platform (M-PESA PayBill 820201)
   - Non-refundable once paid
   - Covers your entire application (up to 6 choices)
   - Paid once per application cycle
   - Different from our platform's course checking fee

Q12: What's the difference between cluster points and cut-off points?
A: Great question! Here's the difference:
   - Cluster points: YOUR personal score based on your KCSE grades in 4 specific subjects. You earn these points - they're your achievement.
   - Cut-off points: The MINIMUM score required for a specific course at a specific university. This is set by the competition - the last person admitted's score becomes the cut-off.
   Example: If Engineering at UoN has cut-off 38.5, and your cluster points are 40.2, you qualify. If your points are 37.8, you don't meet the cut-off.

Q13: Can I apply to KUCCPS through this platform?
A: No, you cannot. We are a separate platform that helps you:
   - Discover which courses match your grades
   - Understand requirements and cut-offs
   - Prepare for your KUCCPS application
   - Save courses for later reference
   For actual KUCCPS application, you MUST use the official portal at students.kuccps.net. Think of us as your preparation tool before the real thing.

Q14: What if I have a disability?
A: KUCCPS has strong affirmative action for students with disabilities:
   - Extended application periods
   - Alternative assessment methods
   - Special consideration in placement
   - Reserved slots in some programmes
   - Additional support at institutions
   When applying, indicate your disability and provide documentation. This may improve your chances of placement.

Q15: Are there scholarships available?
A: Yes, many scholarship opportunities exist:
   Government:
   - HELB loans (apply at www.hef.co.ke)
   - CDF bursaries (through your MP's office)
   - NG-CDF scholarships (national government)
   University:
   - Merit-based scholarships (top performers)
   - Sports scholarships (talented athletes)
   - Need-based financial aid
   - Departmental awards
   Private:
   - Equity Bank "Wings to Fly"
   - KCB Foundation
   - Safaricom Foundation
   - Mastercard Foundation
   - Various NGO scholarships
   Apply early, check eligibility, and submit all required documents!

Q16: What courses can I do with C plain?
A: With a C plain, you have many options:
   - Diploma programs (minimum C- requirement) - most diplomas accept C plain
   - Certificate programs (D+ and above)
   - Artisan courses (D- and above)
   - Some specific degree programs at private universities (check individually)
   Examples: Diploma in Business, Certificate in ICT, Artisan in Plumbing, KMTC Health Records (some campuses)
   Use our course checker with your exact grades to see ALL your options!

Q17: How does the basket work?
A: The basket is your personal course storage:
   - Click "Add to Basket" on any course to save it
   - Basket shows: Course name, institution, code, cut-off, your points, qualification status
   - Remove individual courses anytime
   - Clear entire basket with one click
   - Compare selected courses side-by-side
   - Export as PDF or print
   - Email basket to yourself or parents
   - Basket saves even after session ends
   Perfect for building your shortlist!

Q18: What are the requirements for nursing?
A: Nursing requirements vary by level:
   Diploma in Nursing (KRCHN) - KMTC:
   - Minimum C plain mean grade
   - C in English, Biology, Chemistry
   - C- in Mathematics/Physics
   - Duration: 3 years
   - Campuses: 70+ nationwide
   Degree in Nursing - Universities:
   - Minimum C+ mean grade
   - B in Biology, Chemistry
   - C+ in English, Mathematics
   - Duration: 4 years
   Use our KMTC course checker with your grades to see specific options!

Q19: When should I apply to KUCCPS?
A: Follow this timeline:
   March/April: KCSE results released
   April: KUCCPS application OPENS
   April-June: Best time to apply (avoid last minute rush)
   July 15th: Application DEADLINE
   Don't wait until the last day! Apply early to avoid:
   - System crashes
   - Network issues
   - Payment delays
   - Missing deadline

Q20: What documents do I need for KUCCPS application?
A: Prepare these documents:
   Essential:
   - KCSE certificate or result slip (original and copy)
   - Birth certificate
   - National ID (if 18+)
   - Passport photos (2-4 copies)
   - Proof of disability (if applicable)
   For online application:
   - Scan or photo of each document
   - Clear, readable images
   - PDF format preferred
   - Under 2MB per file
   Keep originals safe for when you report to institution!

========== 📊 COMPARISON: KUCCPS vs COURSES CHECKER - COMPLETE TABLE ==========

| Aspect | 🔵 KUCCPS (Official) | 🟢 Courses Checker (Platform) |
|--------|---------------------|------------------------------|
| Purpose | Government placement service | Course matching tool |
| Website | students.kuccps.net | kuccpscourses.co.ke |
| What it does | Places students into institutions | Shows which courses match your grades |
| Application Fee | KES 1,500 | N/A |
| Course Checking Fee | N/A | KES 200 first, KES 100 additional |
| Payment Method | eCitizen (PayBill 820201) | M-PESA STK Push |
| When to Use | To officially apply for courses (Jan-July) | To research before applying (anytime) |
| Result | Placement into ONE institution | List of ALL courses you qualify for |
| Number of Choices | Up to 6 degree choices | Unlimited browsing |
| Timeline | Annual application window | Available 24/7, 365 days |
| Support | Official KUCCPS contacts | AI chat + email + phone |
| Guides | Limited information | Comprehensive educational guides |
| Cost per use | KES 1,500 per application cycle | KES 200-700 per session |
| Grade Entry | System auto-fetches your results | You enter grades manually |
| Course Basket | No | Yes - save favorites |
| Payment Verification | Through eCitizen | M-Pesa receipt verification |
| Mobile Experience | Basic | Optimized for phones |

========== 🚀 KEY FEATURES AT A GLANCE - COMPLETE LIST ==========

| Feature | What It Does | Benefit |
|---------|-------------|---------|
| Grade Checker | Match KCSE grades to courses | Know exactly what you qualify for |
| 6 Categories | Degree, Diploma, KMTC, Certificate, Artisan, TTC | Find your perfect path |
| 5000+ Courses | Browse all KUCCPS-approved programs | Compare all options in one place |
| Cluster Points | See if you qualify for each program | Make informed, data-driven choices |
| Cut-off Points | View minimum requirements per course | Know what you need to achieve |
| Basket/Wishlist | Save favorite courses | Organize your research efficiently |
| AI Chat | Get instant answers 24/7 | No waiting for email responses |
| Educational Guides | Learn about admissions, requirements | Become an expert on the process |
| M-Pesa Payment | Pay via phone (KES 200-100) | Fast, familiar, secure transaction |
| Responsive Mobile | Works on any device | Study on-the-go anywhere |
| Payment Verification | Access results anytime with receipt | Never lose your results |
| Search & Filter | Find specific courses quickly | Navigate through options easily |
| Export/Print | Save or print your basket | Share with parents/counselors |
| Grade History | See what you entered | Double-check for accuracy |
| Pagination | Browse 20 courses per page | Easy to manage large lists |
| Session Tracking | 30-minute active sessions | Focused research time |
| Email Support | courseschecker@gmail.com | Human help when needed |
| Phone Support | +254791196121 | Direct assistance |
| PWA Capable | Install on phone home screen | App-like experience |
| Free Resources | All guides and chat free | No cost to learn |
| Real Examples | Sarah's journey included | See how it works for real students |
| Testimonials | Student voices | Builds trust and confidence |

========== 🎓 WHAT HAPPENS AFTER YOU USE THE TOOL? ==========

Next Steps - Complete Guide:

1. Take Notes (Right after getting results)
   - Write down top 10-20 courses you're interested in
   - Note programme codes (7-digit codes) for each
   - Note cut-off points for each course
   - Note institutions offering them
   - Note subject requirements
   - Create a shortlist of 5-8 favorites

2. Do More Research (1-2 weeks)
   - Visit institutions' websites
   - Check tuition fees and accommodation costs
   - Research career paths from each course
   - Look into job market demand
   - Read student reviews if available
   - Check institution rankings and reputation
   - Visit campuses if possible

3. Discuss with Family (Week 2-3)
   - Share your basket with parents
   - Discuss financial considerations (fees, upkeep, transport)
   - Talk about career goals and interests
   - Consider location preferences (near home vs far)
   - Get input from teachers or guidance counselors
   - Consider long-term career prospects
   - Discuss backup options

4. Prepare Documents for KUCCPS (Week 3-4)
   Essential documents:
   - Original KCSE certificate (or result slip)
   - Birth certificate (certified copy)
   - National ID (if you have one)
   - Passport photos (4 copies)
   - Proof of disability (if applicable)
   - Bank/M-Pesa for application fee (KES 1,500)
   Digital copies:
   - Scan or clear photos of all documents
   - Save as PDF (under 2MB each)
   - Label clearly for upload

5. Apply on Official KUCCPS Portal (January-April)
   Website: www.kuccps.net or students.kuccps.net
   Process:
   a. Create account with KCSE index
   b. Fill personal details accurately
   c. Verify your KCSE results (system auto-fetches)
   d. Select up to 6 course choices:
      - Use programme codes from your results
      - Order by preference (1 = most wanted)
      - Include reach, match, and safety schools
   e. Upload required documents
   f. Pay KES 1,500 via eCitizen
   g. Submit and save confirmation
   h. Print application summary

6. Wait for Placement Results (May-August)
   - KUCCPS publishes results in batches
   - You'll be placed in ONE institution and course
   - Check your portal regularly (daily)
   - Results usually released:
     * First batch: August
     * Second batch: September
     * Third batch: October
   - You may get your 2nd, 3rd, or lower choice based on competition
   - If not placed: Apply for revision (KES 1,000)
   - If unhappy: Option to appeal (KES 1,000)

7. Report to Institution (September)
   - Accept your offer (deadline given)
   - Pay required fees/deposits
   - Attend orientation (usually September)
   - Register for classes
   - Apply for HELB funding if needed
   - Find accommodation
   - Buy required materials
   - Begin your educational journey!

========== 🌟 WHY THIS PLATFORM EXISTS - THE PROBLEM IT SOLVES ==========

The Problem (Before This Tool):
❌ Students had to manually search each institution's website separately (time-consuming)
❌ Hard to know if you qualify for a program (cut-off points confusing)
❌ Cluster points were complicated to understand (math-heavy explanations)
❌ Hours of research without a clear picture of options (frustrating)
❌ Many students made blind applications without knowing realistic options (wasted choices)
❌ Parents couldn't easily help with course selection (information scattered)
❌ Information scattered across different websites (no single source)
❌ Students often missed deadlines due to poor planning
❌ Wrong course selections led to transfers or dropouts
❌ Many qualified students missed opportunities they didn't know existed

The Solution (What This Tool Does):
✅ Instant Matching – See all 5000+ courses you qualify for in just 5 minutes
✅ Clarity on Requirements – Know exactly what grades and points are needed for each course
✅ Saves Time – No more hours of manual research across different websites
✅ Builds Confidence – Know your realistic options before applying
✅ Affordable – Just KES 200-100, pays for itself in saved time and better decisions
✅ Accessible – Works on any phone with internet, no app needed
✅ Support 24/7 – AI chat always available if confused
✅ Educational – Guides teach you about the whole process from start to finish
✅ Shareable – Save basket and share with parents/counselors
✅ Real Examples – Sarah's journey shows exactly how it works
✅ Trust Building – Testimonials from real students who succeeded
✅ Mobile First – Designed for phone users (most Kenyan students)
✅ Payment Ease – M-Pesa integration (familiar to all Kenyans)
✅ Never Lost – Payment verification ensures you can always access results

========== 📊 STUDENT TESTIMONIALS - REAL VOICES ==========

> "I was so confused about cluster points. This tool showed me instantly that I qualify for 450 courses! The AI chatbot explained cluster points in simple language - turns out I had been calculating them wrong. Worth every shilling!" – Amos, Former Student (now in Engineering)

> "Saved me months of research. I was only considering engineering because my dad is an engineer. But the tool showed I could do nursing too, and I discovered my true passion. Now in my second year at KMTC!" – Grace, Current KMTC Nursing Student

> "My parents were unsure which courses I qualified for with my C plain. This tool gave us a clear list to discuss at the dinner table. We made a shortlist together, and I got my second choice at Kiambu Institute. Much better than guessing!" – Peter, Diploma Student

> "The M-Pesa payment is so easy. No complicated bank transfers. Just press, enter PIN, done. Results instantly! I helped three friends use it too, and we all got placed. Best KES 200 I ever spent." – Susan, Recent Graduate

> "As a teacher, I recommend this tool to all my Form 4 leavers. It saves them from making blind applications and helps them make informed decisions about their future. The guides are excellent for class discussions." – Mr. Omondi, High School Teacher

> "I checked five different categories for my daughter. The pricing was clear and fair - KES 200 first, then KES 100 each. Now she has a complete list of options to consider. Thank you for making this so simple!" – Mrs. Akinyi, Parent

> "The basket feature is a game-changer. I saved 15 courses, compared them with my parents, and narrowed down to 6 for my KUCCPS application. Got my first choice at Kenyatta University!" – James, First-Year University Student

> "I almost gave up on education because I thought my D+ was useless. This tool showed me 200+ artisan and certificate courses I qualify for. Now I'm a qualified plumber with my own business. Changed my life." – Michael, Artisan Graduate

========== ✅ SITE MAP - WHERE TO FIND EVERYTHING ==========

Main Navigation Menu (Top of every page):
Home | Guides | About | Contact | AI Chat

From Home Page:
├─ 🎓 Degree Courses → Grade entry form (Coming Soon)
├─ 📚 Diploma Courses → Grade entry form
├─ 🏥 KMTC Courses → Grade entry form
├─ 👨‍🏫 TTC Courses → Grade entry form
├─ 📜 Certificate Courses → Grade entry form
├─ 🔧 Artisan Courses → Grade entry form
├─ 📖 Guides
│  ├─ Cluster Points Explained
│  ├─ KCSE Admission Requirements
│  ├─ KUCCPS Application Process
│  ├─ Diploma Courses Overview
│  ├─ Certificate Courses Guide
│  ├─ KMTC Courses & Health Programs
│  ├─ Artisan Courses & Trade Training
│  ├─ Teacher Training (TTC) Guide
│  └─ Scholarships & Financial Aid
├─ 💬 AI Chat (floating button bottom-right)
├─ 📧 Contact Us
└─ ℹ️ About Platform

After Payment:
└─ Results Page
   ├─ Filter by cluster buttons (8+ options)
   ├─ Browse courses (paginated 20 per page)
   ├─ Add to Basket button on each course
   ├─ View Submitted Grades section
   └─ Navigation: [Back to Home] [Try Again] [View Basket]

User Dashboard (when logged in/verified):
├─ Basket/Favorites 🛒 (with all saved courses)
├─ My Previous Results (with email verification)
├─ Payment History (receipts and transactions)
└─ Download/Print Results (PDF option)

========== 🎯 FINAL SUMMARY - ONE SENTENCE ==========

KUCCPS Courses Checker in one sentence:
"A fast, affordable online tool that instantly shows Kenyan students which of 5000+ KUCCPS-approved courses they qualify for based on their KCSE grades, with helpful guides and 24/7 AI support."

What makes it special (Complete List):
⚡ Speed: Results in under 5 minutes (much faster than manual research)
💰 Affordable: KES 200-100 one-time fee (pays for itself)
📱 Mobile-first: Works perfectly on phones (designed for Kenyan students)
🤖 AI Powered: Instant 24/7 support (always available when you need help)
📚 Educational: Comprehensive guides teach real concepts (become an expert)
✅ Trusted: 50,000+ students helped (proven track record)
🔒 Safe: Secure M-Pesa payment (familiar and trusted payment method)
🔄 Never lose results: Verify anytime with receipt (peace of mind)
👪 Shareable: Save basket and share with family (involve your support system)
🎓 6 Categories: Degree, Diploma, KMTC, TTC, Certificate, Artisan (all options covered)
📊 5000+ Courses: Complete KUCCPS database (no missed opportunities)
🏛️ 200+ Institutions: All universities and colleges (comprehensive coverage)
💬 24/7 Chat: Always available support (never left waiting)
📝 Guides: 9 comprehensive resources (learn everything)
💰 Clear Pricing: KES 200 first, KES 100 additional (transparent and fair)
💳 M-PESA: Instant payment, instant results (no delays)
🛒 Basket: Save and compare courses (organize your research)
📱 PWA: Install on phone (app-like experience)
🔐 Secure: HTTPS encryption (your data is safe)
📧 Email Support: Human help when needed (real people care)
📞 Phone: Direct assistance (talk to someone)

========== ⚠️ RESPONSE GUIDELINES - HOW TO ANSWER ==========

1. ALWAYS answer from a STUDENT'S PERSPECTIVE (use "you", "your", as if talking directly to a student)
2. Be FRIENDLY, HELPFUL, and WELCOMING (students are often anxious about their future)
3. Be CONCISE but COMPLETE (2-4 sentences usually, but provide full details when needed)
4. Use SIMPLE, CLEAR language - no technical jargon without explanation
5. For payment questions, CLEARLY DISTINGUISH between:
   - 🟢 Courses Checker fees (KES 200 first category, KES 100 additional)
   - 🔵 KUCCPS official fees (KES 1,500 application fee, KES 1,000 revision)
6. If a question could apply to both, EXPLAIN THE DIFFERENCE clearly
7. If ambiguous, ASK FOR CLARIFICATION: "Are you asking about our platform or official KUCCPS?"
8. For technical issues, SUGGEST: courseschecker@gmail.com or phone +254791196121
9. If asked about unrelated topics, POLITELY REDIRECT to KUCCPS/courses
10. Use EMOJIS sparingly to make responses friendly and scannable
11. Always be ENCOURAGING and SUPPORTIVE - students are making important life decisions!
12. When giving examples, use REAL numbers and scenarios (like Sarah's journey)
13. If you don't know something, be HONEST and suggest where they might find the information
14. Always end with an OPEN INVITATION for follow-up questions
15. Remember: You're not just answering questions - you're helping shape futures!

========== 🚫 OUT OF SCOPE HANDLING ==========

If asked about anything NOT in the knowledge above (weather, news, sports, politics, entertainment, etc.):
"I'm specifically designed to help with KUCCPS courses and our Courses Checker platform only. I can answer questions about:
• Course requirements for different levels (degree, diploma, certificate, artisan, KMTC, TTC)
• How to use our course checker platform step-by-step
• Payment information (KES 200/100 for our platform, KES 1,500 for KUCCPS)
• Cluster points and how they're calculated
• Cut-off points and what they mean
• KUCCPS application process, dates, and requirements
• Our educational guides (cluster points, admission requirements, scholarships, etc.)
• Saving courses to basket and managing your shortlist
• Contact information for support

What would you like to know about your educational journey?"

If asked about something vague:
"Could you please be more specific? I'm here to help with:
✅ Course requirements for different levels
✅ How to use our platform
✅ Payment information
✅ Cluster points and cut-offs
✅ KUCCPS application process
✅ Our educational guides
✅ Saving courses to basket

Just let me know what you'd like to learn about!"

========== 📝 USER QUESTION ==========
{user_message}

========== ✅ YOUR ANSWER ==========
(Provide a concise, helpful answer following all guidelines above. Use the COMPLETE knowledge base to give rich, detailed responses that would actually help a student.)"""

        # Try multiple models with fallback
        models_to_try = ['gemini-2.5-flash', 'gemini-2.0-flash', 'gemini-2.0-flash-001']
        last_error = None
        
        for model_name in models_to_try:
            try:
                print(f"🔄 Trying model: {model_name}")
                
                response = client.models.generate_content(
                    model=model_name,
                    contents=system_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.5,
                        max_output_tokens=1500,  # Allow longer, detailed responses
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
                last_error = e
                error_str = str(e)
                print(f"❌ Model {model_name} failed: {error_str[:100]}...")
                
                if "429" in error_str:
                    import re
                    retry_match = re.search(r'retry in (\d+\.?\d*)s', error_str)
                    if retry_match:
                        wait_time = float(retry_match.group(1))
                        print(f"⏱️ Rate limited on {model_name}. Waiting {min(wait_time, 3):.1f}s...")
                        time.sleep(min(wait_time, 3))
                continue
        
        # If all Gemini models failed, try OpenRouter
        print("⚠️ All Gemini models failed, trying OpenRouter fallback...")
        openrouter_response = get_openrouter_fallback(user_message)
        if openrouter_response:
            return openrouter_response
        
        # Ultimate fallback message
        return ("I'm currently experiencing high demand across all AI services. " +
                "Please try again in a few minutes. In the meantime, you can check our " +
                "comprehensive guides at /guides for detailed information about " +
                "course requirements, cluster points, and the KUCCPS application process.")
        
    except Exception as e:
        print(f"❌ Critical error in get_gemini_response: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Try OpenRouter as last resort
        try:
            return get_openrouter_fallback(user_message)
        except:
            return "I'm experiencing technical difficulties. Please try again later or contact support at courseschecker@gmail.com."


def get_openrouter_fallback(user_message):
    """Enhanced OpenRouter fallback with CORRECT free models from your account"""
    try:
        # Fetch API key from environment variables
        OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
        
        if not OPENROUTER_API_KEY:
            print("⚠️ No OpenRouter API key found in environment variables")
            print("💡 Set OPENROUTER_API_KEY in your .env file")
            return None
            
        print(f"🔑 OpenRouter API key found (starts with: {OPENROUTER_API_KEY[:10]}...)")
        print("🔄 Calling OpenRouter fallback with CORRECT free models...")
        
        # Create a condensed but comprehensive prompt
        condensed_prompt = """You are the official AI assistant for KUCCPS Courses Checker (kuccpscourses.co.ke). 

CRITICAL: You MUST answer using ONLY the information below. Be helpful, friendly, and concise (2-3 sentences).

KEY PLATFORM INFORMATION:
- First category check: KES 200
- Additional categories: KES 100 each
- Payment: M-PESA STK Push
- 6 categories: Degree(C+), Diploma(C-), KMTC(C-), TTC(C), Certificate(D+), Artisan(D/E)
- 5000+ courses, 200+ institutions, 50,000+ students helped
- Email: courseschecker@gmail.com | Phone: +254791196121

HOW TO USE:
1. Choose category → 2. Enter grades → 3. Pay → 4. View results → 5. Save to basket

KUCCPS INFO (OFFICIAL):
- Application fee: KES 1,500 (eCitizen)
- Website: students.kuccps.net
- Degree: C+ minimum | Diploma: C- | Certificate: D+ | Artisan: D/E
- Cluster points: A=12, A-=11, B+=10, B=9, B-=8, C+=7, C=6, C-=5, D+=4, D=3

FAQ QUICK ANSWERS:
- C plain students can do: Diploma, Certificate, Artisan courses
- Results last: 30 minutes active browsing
- Payment fails? Check balance, retry, or verify with receipt
- Basket: Save and compare courses"""

        # ✅ CORRECT FREE MODELS FROM YOUR ACCOUNT
        openrouter_models = [
            "arcee-ai/trinity-large-preview:free",
            "stepfun/step-3.5-flash:free",
            "upstage/solar-pro-3:free",
            "liquid/lfm-2.5-1.2b-thinking:free",
            "liquid/lfm-2.5-1.2b-instruct:free",
            "nvidia/nemotron-3-nano-30b-a3b:free",
            "arcee-ai/trinity-mini:free"
        ]
        
        for model in openrouter_models:
            try:
                print(f"🔄 Trying OpenRouter model: {model}")
                
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://www.kuccpscourses.co.ke",
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
                    
                    # Validate response isn't generic
                    generic_phrases = [
                        "i'm here to help",
                        "i can help you with",
                        "what would you like to know",
                        "ask me about"
                    ]
                    
                    # Check if response is too generic
                    is_generic = any(phrase in ai_response.lower() for phrase in generic_phrases)
                    
                    if ai_response and len(ai_response) > 20 and not is_generic:
                        print(f"✅ Got GOOD response from OpenRouter {model}")
                        print(f"📝 Response preview: {ai_response[:100]}...")
                        return ai_response
                    elif ai_response and len(ai_response) > 20:
                        print(f"⚠️ Response from {model} was generic, trying next model...")
                        print(f"📝 Generic response: {ai_response[:100]}...")
                        continue
                    else:
                        print(f"⚠️ Response from {model} was empty or too short")
                    
                elif response.status_code == 429:
                    print(f"❌ OpenRouter model {model} failed - RATE LIMITED (429)")
                    print(f"⏱️ Rate limited on {model}. Waiting 3 seconds...")
                    time.sleep(3)
                    continue
                    
                elif response.status_code == 401:
                    print(f"❌ OpenRouter model {model} failed - UNAUTHORIZED (401)")
                    print("🔑 Your OpenRouter API key is invalid. Please check:")
                    print("   1. Go to https://openrouter.ai/keys")
                    print("   2. Generate a new key")
                    print("   3. Update OPENROUTER_API_KEY in your .env file")
                    # Continue to next model instead of breaking
                    continue
                    
                else:
                    print(f"❌ OpenRouter model {model} failed with status {response.status_code}")
                    print(f"📄 Error response: {response.text[:200]}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"⏱️ OpenRouter model {model} timed out")
                continue
                
            except requests.exceptions.ConnectionError:
                print(f"🔌 OpenRouter model {model} connection error")
                continue
                
            except Exception as e:
                print(f"❌ OpenRouter model {model} threw exception: {str(e)}")
                continue
        
        # If all OpenRouter models fail, return None to allow Gemini to try
        print("⚠️ All OpenRouter models failed, will try Gemini")
        return None  # ← CRITICAL: Return None, not curated response
        
    except Exception as e:
        print(f"❌ OpenRouter fallback critical error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None  # ← Return None on error
    
    
def get_curated_response(user_message):
    """Return curated responses based on common questions - UPDATED WITH CORRECT INFO"""
    user_message_lower = user_message.lower()
    
    # C plain questions
    if "c plain" in user_message_lower or "c plain" in user_message_lower:
        return ("With a C plain in KCSE, you can apply for Diploma programs (minimum C-), " +
               "Certificate programs (D+ and above), and Artisan courses. Popular options include " +
               "Diploma in Business, Certificate in ICT, or Artisan in Plumbing. " +
               "Use our course checker (KES 200) to see ALL courses matching your exact grades!")
    
    # Cost/payment questions
    elif any(word in user_message_lower for word in ["cost", "pay", "fee", "price", "how much"]):
        return ("Our course checking service costs KES 200 for your first category, " +
               "and KES 100 for each additional category. Payment is via M-PESA STK Push. " +
               "This is DIFFERENT from the official KUCCPS application fee of KES 1,500.")
    
    # Multiple categories
    elif "multiple" in user_message_lower or "categories" in user_message_lower or "more than one" in user_message_lower:
        return ("Yes! You can check multiple course categories. " +
               "First category costs KES 200, and each additional category costs KES 100. " +
               "For example: Diploma (KES 200) + Certificate (KES 100) = KES 300 total.")
    
    # ===== FIXED: KMTC / NURSING SECTION WITH CORRECT REQUIREMENTS =====
    elif any(word in user_message_lower for word in ["kmtc", "nursing", "medical", "health", "clinical"]):
        
        # Check for specific nursing questions
        if "nursing" in user_message_lower and ("requirement" in user_message_lower or "need" in user_message_lower or "grade" in user_message_lower):
            return ("For Diploma in Nursing (KRCHN) at KMTC, you need:\n" +
                   "• KCSE mean grade: **C plain** (not C-)\n" +
                   "• C plain in English, Biology, and Chemistry\n" +
                   "• C- in Mathematics or Physics\n" +
                   "Duration: 3 years with clinical training.\n" +
                   "Use our KMTC course checker (KES 200) to see all options matching your exact grades!")
        
        # General KMTC info
        else:
            return ("KMTC courses require minimum C- mean grade, but Nursing specifically needs C plain. " +
                   "Popular programs include Diploma in Nursing (C plain in English, Biology, Chemistry), " +
                   "Clinical Medicine (C in Biology, Chemistry), and Pharmacy. " +
                   "Use our KMTC course checker (KES 200) to see all options matching your grades.")
    
    # Degree requirements
    elif "degree" in user_message_lower and any(word in user_message_lower for word in ["requirement", "need", "grade", "qualify"]):
        return ("Degree programs require a minimum of C+ mean grade and specific cluster points. " +
               "For example, Engineering typically needs C+ in Mathematics, Physics, and Chemistry. " +
               "Medicine requires B in Biology, Chemistry, and Mathematics/Physics. " +
               "Use our degree course checker (KES 200) to see all programs matching your grades.")
    
    # Diploma requirements (general)
    elif "diploma" in user_message_lower and any(word in user_message_lower for word in ["requirement", "need", "grade", "qualify"]):
        return ("Diploma programs require a minimum of C- mean grade. Most diplomas accept C plain, " +
               "but some like Nursing require C plain in specific subjects. " +
               "Use our diploma course checker (KES 200) to see all your options.")
    
    # Certificate requirements
    elif "certificate" in user_message_lower and any(word in user_message_lower for word in ["requirement", "need", "grade", "qualify"]):
        return ("Certificate programs require a minimum of D+ mean grade. These are 1-2 year programs " +
               "in fields like ICT, Business, Hospitality, and Technical trades. " +
               "Use our certificate course checker (KES 200) to see all options.")
    
    # Artisan requirements
    elif "artisan" in user_message_lower and any(word in user_message_lower for word in ["requirement", "need", "grade", "qualify"]):
        return ("Artisan courses accept D plain, D-, or E grades. These are hands-on training programs " +
               "in trades like Plumbing, Electrical, Welding, Carpentry, and Masonry. " +
               "Use our artisan course checker (KES 200) to see all options.")
    
    # TTC / Teacher training
    elif any(word in user_message_lower for word in ["ttc", "teacher", "teaching", "pte", "ecde"]):
        return ("Teacher Training College (TTC) programs require minimum C mean grade. " +
               "Options include Primary Teacher Education (PTE), ECDE, and Diploma in Secondary Education. " +
               "Use our TTC course checker (KES 200) to see all options.")
    
    # Basket feature
    elif "basket" in user_message_lower:
        return ("The basket lets you save and compare courses you're interested in. " +
               "Click 'Add to Basket' on any course, then view your basket to see all saved courses, " +
               "compare them side-by-side, and export as PDF to share with parents or counselors.")
    
    # Payment failure
    elif "payment fail" in user_message_lower or "mpesa fail" in user_message_lower or "transaction fail" in user_message_lower:
        return ("If your M-Pesa payment fails, first check your balance and ensure you have sufficient funds. " +
               "Verify your phone number is correct (format 07XXXXXXXX). If money was deducted but you didn't get results, " +
               "use your receipt number at /verify-payment to access your results. Contact courseschecker@gmail.com if issues persist.")
    
    # How long results last
    elif "how long" in user_message_lower and ("result" in user_message_lower or "available" in user_message_lower):
        return ("Your results are available for 30 minutes of active browsing in that session. " +
               "After 30 minutes of inactivity, the session expires and you'd need to pay again. " +
               "However, courses saved to your basket remain accessible anytime you log in with your email and index number.")
    
    # Email safety
    elif "email safe" in user_message_lower or "privacy" in user_message_lower or "data" in user_message_lower:
        return ("Yes, your email is safe. We use HTTPS encryption throughout, never share your data with third parties, " +
               "and only use your email for session tracking and result retrieval. Your privacy is our priority.")
    
    # Share results
    elif "share" in user_message_lower and ("result" in user_message_lower or "basket" in user_message_lower):
        return ("You can share your results by exporting your basket as PDF and sharing it with others. " +
               "However, each person must pay for their own session to see their specific results, " +
               "as results are personalized based on individual grades.")
    
    # App vs website
    elif "app" in user_message_lower:
        return ("We currently offer a website only, not a separate app. But it works great on all devices! " +
               "On some phones, you can 'Install' the site to your home screen (PWA feature) for app-like access. " +
               "On Chrome: Menu → 'Add to Home screen'. On Safari: Share → 'Add to Home Screen'.")
    
    # KUCCPS application
    elif "kuccps" in user_message_lower and ("apply" in user_message_lower or "application" in user_message_lower):
        return ("To apply to KUCCPS officially, visit students.kuccps.net. The application fee is KES 1,500 via eCitizen. " +
               "You can select up to 6 degree choices or 4 diploma/certificate choices. " +
               "Applications typically open in April and close July 15th. This is SEPARATE from our KES 200 course checking fee.")
    
    # Cluster points
    elif "cluster" in user_message_lower and ("point" in user_message_lower or "calculate" in user_message_lower):
        return ("Cluster points are your score based on your best 4 subjects. Grade conversion: A=12, A-=11, B+=10, B=9, " +
               "B-=8, C+=7, C=6, C-=5, D+=4, D=3. For example, Engineering cluster requires Math, Physics, Chemistry " +
               "(typically 36-48 points). Check our 'Cluster Points Explained' guide at /guides for more details.")
    
    # Cut-off points
    elif "cut off" in user_message_lower or "cutoff" in user_message_lower:
        return ("Cut-off points are the minimum score required for a specific course at a specific university. " +
               "They are determined by competition - the last person admitted's score becomes the cut-off. " +
               "Cut-off points change every year based on applicant quality and available slots.")
    
    # Medicine and Surgery
    elif "medicine" in user_message_lower or "surgery" in user_message_lower or "mbchb" in user_message_lower:
        return ("Bachelor of Medicine and Surgery (MBChB) requires a minimum of B in Biology, Chemistry, " +
               "and Mathematics/Physics, with an overall mean grade of B+. It's a 6-year program offered at " +
               "University of Nairobi, Moi University, Kenyatta University, and other institutions. " +
               "Cut-off points are typically 42-48 cluster points.")
    
    # Computer Science
    elif "computer science" in user_message_lower or "cs" in user_message_lower:
        return ("Computer Science is a degree program focusing on software development, algorithms, " +
               "and computational theory. It requires a minimum of C+ in Mathematics, with cut-off points " +
               "typically 35-42 cluster points. Offered at most Kenyan universities.")
    
    # Engineering
    elif "engineering" in user_message_lower and ("civil" in user_message_lower or "mechanical" in user_message_lower or "electrical" in user_message_lower):
        return ("Engineering programs require C+ in Mathematics, Physics, and Chemistry. Cut-off points vary: " +
               "Civil (36-40), Mechanical (38-42), Electrical (38-43). Offered at University of Nairobi, " +
               "JKUAT, Moi University, and Technical University of Kenya.")
    
    # Default response
    else:
        return ("I'm here to help with KUCCPS courses! You can ask me about:\n" +
               "• Course requirements (degree, diploma, certificate, artisan, KMTC, TTC)\n" +
               "• Payment information (KES 200 first, KES 100 additional)\n" +
               "• How to use our platform\n" +
               "• KUCCPS application process\n" +
               "• Cluster points and cut-off points\n\n" +
               "What would you like to know specifically?")
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
    
    # Try OpenRouter FIRST (unlimited, won't hit daily limits)
    openrouter_response = get_openrouter_fallback(user_message)
    if openrouter_response:  # Only use if OpenRouter returned something
        return openrouter_response
    
    # If OpenRouter fails or returns None, try Gemini as backup
    print("⚠️ OpenRouter failed or returned None, trying Gemini...")
    gemini_response = get_gemini_response(user_message)
    if gemini_response:
        return gemini_response
    
    # Ultimate fallback only if both AI services fail
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
    """FAST parallel degree version"""
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
                qualifying_courses.extend(future.result())
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
    """FAST parallel version - replaces the slow sequential loop"""
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
                qualifying_courses.extend(future.result())
            except Exception as e:
                print(f"⚠️ Diploma future error: {e}")
 
    print(f"📚 Diploma: found {len(qualifying_courses)} courses (parallel)")
    return qualifying_courses
 

def get_qualifying_kmtc_courses(user_grades, user_mean_grade):
    """FAST version - KMTC only has one collection so no parallel needed,
       but we add projection for speed"""
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
    """FAST parallel version"""
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
                qualifying_courses.extend(future.result())
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
    """FAST parallel version"""
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
                qualifying_courses.extend(future.result())
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
    base_url = 'https://www.kuccpscourses.co.ke'
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
    base_url = 'https://www.kuccpscourses.co.ke'
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
    base_url = 'https://www.kuccpscourses.co.ke'
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
    base_url = 'https://www.kuccpscourses.co.ke'
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
    base_url = 'https://www.kuccpscourses.co.ke'
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

Sitemap: https://www.kuccpscourses.co.ke/sitemap-index.xml
Sitemap: https://www.kuccpscourses.co.ke/sitemap.xml
Sitemap: https://www.kuccpscourses.co.ke/sitemap-guides.xml
Sitemap: https://www.kuccpscourses.co.ke/sitemap-news.xml
Sitemap: https://www.kuccpscourses.co.ke/sitemap-courses.xml

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
            base_url = 'https://www.kuccpscourses.co.ke'
        else:
            ngrok_url = os.getenv('NGROK_URL')
            if ngrok_url:
                base_url = ngrok_url
                print(f"🔗 Using ngrok URL for callbacks: {base_url}")
            else:
                base_url = 'https://www.kuccpscourses.co.ke'
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
    """Create a payment record for manual activations using ORIGINAL receipt"""
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
    
    payment_record = {
        'email': email,
        'index_number': index_number,
        'level': flow,
        'transaction_ref': f"MANUAL_{mpesa_receipt}",
        'mpesa_receipt': mpesa_receipt,  # Store the ORIGINAL receipt
        'payment_amount': existing_payment.get('payment_amount', 100) if existing_payment else 100,
        'payment_confirmed': True,
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
                    print(f"✅ Updated existing payment record with receipt: {mpesa_receipt}")
                else:
                    print(f"⚠️ No changes made to existing payment record")
            else:
                # Insert new record
                result = user_payments_collection.insert_one(payment_record)
                if result.inserted_id:
                    print(f"✅ Created new payment record with receipt: {mpesa_receipt}")
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
    SITE_URL = "https://www.kuccpscourses.co.ke"
    
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
    print(f"💾 ENHANCED: Saving basket for {index_number}")
    
    # Validate and process basket data first
    processed_basket = validate_and_process_basket(basket_data, "save")
    
    if not database_connected:
        session['course_basket'] = processed_basket
        print(f"💾 Basket saved to session: {len(processed_basket)} items")
        return True
        
    basket_record = {
        'email': email,
        'index_number': index_number,
        'basket': processed_basket,
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
        'is_active': True
    }
    
    try:
        result = user_baskets_collection.update_one(
            {'index_number': index_number},
            {'$set': basket_record},
            upsert=True
        )
        print(f"✅ Basket saved to database for {index_number} with {len(processed_basket)} courses")
        
        # Also update session for consistency
        session['course_basket'] = processed_basket
        return True
        
    except Exception as e:
        print(f"❌ Error saving user basket: {str(e)}")
        # Fallback to session
        session['course_basket'] = processed_basket
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
    base_url = 'https://www.kuccpscourses.co.ke'
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
    """Handle user details entry with strict validation and manual activation support."""
 
    # ── GET: show the form ──
    if request.method == 'GET':
        if not session.get(f'{flow}_data_submitted'):
            flash("Please submit your grades first", "error")
            return redirect(url_for(flow))
        return render_template('enter_details.html', flow=flow)
 
    # ── POST: process details ──
    try:
        email        = request.form.get('email', '').strip().lower()
        index_number = request.form.get('index_number', '').strip()
 
        # Validate
        if not email or not index_number:
            flash("Email and KCSE Index Number are required.", "error")
            return redirect(url_for('enter_details', flow=flow))
 
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            flash("Invalid index number format. Must be 11 digits, slash, 4 digits (e.g. 12345678901/2024)", "error")
            return redirect(url_for('enter_details', flow=flow))
 
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for('enter_details', flow=flow))
 
        # ── Uniqueness check ──
        is_valid, msg = validate_user_uniqueness(email, index_number, flow)
        if not is_valid:
            flash(msg, "error")
            return redirect(url_for('enter_details', flow=flow))
 
        # ── Save grades to DB BEFORE anything else ──
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
 
        # ============================================
        # STEP 1: CHECK MANUAL ACTIVATION FIRST
        # This overrides any payment checks
        # ============================================
        activation_record = None
        original_mpesa_receipt = None
 
        if database_connected and admin_activations_collection is not None:
            try:
                activation_record = admin_activations_collection.find_one({
                    '$or': [
                        {'email': email},
                        {'index_number': index_number}
                    ],
                    'is_active': True,
                    'status': 'active'
                })
                if activation_record:
                    original_mpesa_receipt = activation_record.get('mpesa_receipt')
                    print(f"✅ Manual activation found in DB for {email}: receipt={original_mpesa_receipt}")
                    print(f"   Activation ID: {activation_record.get('_id')}")
                    print(f"   Flow: {flow}")
            except Exception as e:
                print(f"⚠️ Activation DB check error: {e}")
 
        # ============================================
        # STEP 2: IF MANUAL ACTIVATION EXISTS - BYPASS PAYMENT
        # ============================================
        if activation_record and original_mpesa_receipt:
            print(f"🎯 Manual activation detected - bypassing payment for {flow}")
            
            # Store manual activation info in session
            session['manual_activation_active'] = True
            session['manual_activation_receipt'] = original_mpesa_receipt
            session['manual_activation_id'] = str(activation_record['_id'])
            session['email'] = email
            session['index_number'] = index_number
            session['current_flow'] = flow
            session['current_level'] = flow
            session[f'paid_{flow}'] = True
            session['mpesa_receipt'] = original_mpesa_receipt
            session['verified_receipt'] = original_mpesa_receipt
            session.modified = True
            
            # Create/update payment record with original receipt
            create_manual_activation_payment(email, index_number, flow, original_mpesa_receipt)
            
            # Queue course generation immediately
            process_courses_after_payment(email, index_number, flow, original_mpesa_receipt)
            
            # Mark activation as used (so it can't be reused for another flow)
            try:
                admin_activations_collection.update_one(
                    {'_id': activation_record['_id']},
                    {'$set': {
                        'used_for_flow': flow,
                        'used_at': datetime.now(),
                        'status': 'used'
                    }}
                )
                print(f"✅ Manual activation marked as used for {flow}")
            except Exception as e:
                print(f"⚠️ Could not mark activation as used: {e}")
            
            flash("✅ Access granted via manual activation! Generating your courses...", "success")
            return redirect(url_for('payment_wait', flow=flow, transaction_ref='manual'))
 
        # ============================================
        # STEP 3: CHECK IF ALREADY PAID (Normal flow)
        # ============================================
        if has_user_paid_for_category_strict(email, index_number, flow):
            paid = get_user_paid_categories_strict(email, index_number)
            flash(
                f"You have already paid for {flow.upper()} courses. "
                f"Paid categories: {', '.join(paid)}",
                "error"
            )
            return redirect(url_for('index'))
 
        # ============================================
        # STEP 4: NORMAL PAYMENT FLOW
        # ============================================
        existing = get_user_paid_categories_strict(email, index_number)
        is_first = len(existing) == 0
        amount =  200 if is_first else 100
 
        # Store minimal data in session
        session['email'] = email
        session['index_number'] = index_number
        session['current_flow'] = flow
        session['current_level'] = flow
        session['payment_amount'] = amount
        session['is_first_category'] = is_first
        session[f'paid_{flow}'] = False
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
    email        = session.get('email')
    index_number = session.get('index_number')
 
    if not email or not index_number:
        flash("Session expired. Please start again.", "error")
        return redirect(url_for('enter_details', flow=flow))
 
    amount       = session.get('payment_amount', 200)
    txn_ref      = request.args.get('transaction_ref', '')
 
    # If txn_ref not in URL args, try DB
    if not txn_ref and database_connected and user_payments_collection is not None:
        try:
            p = user_payments_collection.find_one(
                {'email': email, 'index_number': index_number, 'level': flow},
                {'transaction_ref': 1}
            )
            if p:
                txn_ref = p.get('transaction_ref', '')
        except Exception:
            pass
 
    return render_template(
        'payment_wait.html',
        flow=flow,
        email=email,
        index_number=index_number,
        transaction_ref=txn_ref,
        amount=amount
    )
 
 

@app.route('/check-courses-ready/<flow>')
def check_courses_ready(flow):
    email        = session.get('email')
    index_number = session.get('index_number')
 
    if not email or not index_number:
        return jsonify({
            'ready': False,
            'error': 'Session missing',
            'should_redirect': True,
            'redirect_url': url_for('index')
        })
 
    cache_key   = f"{email}_{index_number}_{flow}"
    status_data = course_processing_status.get(cache_key)
 
    # ── TIER 1: In-memory status map (zero DB cost, instant) ──
    if isinstance(status_data, dict):
        status = status_data.get('status')
 
        if status == 'completed':
            _sync_session_after_completion(email, index_number, flow)
            return jsonify({
                'ready':         True,
                'courses_count': status_data.get('courses_count', 0),
                'redirect_url':  url_for('goto_results', flow=flow),
                'status':        'memory_completed'
            })
 
        if status == 'processing':
            elapsed = (datetime.now() - status_data.get('started_at', datetime.now())).total_seconds()
            return jsonify({
                'ready':      False,
                'message':    f'Generating your courses… ({int(elapsed)}s)',
                'processing': True,
                'elapsed':    int(elapsed),
                'status':     'processing'
            })
 
        if status in ('pending', 'queued'):
            return jsonify({
                'ready':      False,
                'message':    'Queued for processing…',
                'processing': True,
                'status':     'queued'
            })
 
        if status == 'failed':
            return jsonify({
                'ready':   False,
                'message': 'Processing failed. Please contact support.',
                'error':   True,
                'status':  'failed'
            })
 
    # ── TIER 2: Courses already in DB (fast projection check) ──
    if database_connected and user_courses_collection is not None:
        try:
            doc = user_courses_collection.find_one(
                {'email': email, 'index_number': index_number, 'level': flow},
                {'courses': {'$slice': 1}}
            )
            if doc and doc.get('courses'):
                # Update memory map immediately so future polls are instant
                course_processing_status[cache_key] = {
                    'status': 'completed',
                    'courses_count': -1,
                    'completed_at': datetime.now()
                }
                _sync_session_after_completion(email, index_number, flow)
                return jsonify({
                    'ready':        True,
                    'redirect_url': url_for('goto_results', flow=flow),
                    'status':       'db_courses_found'
                })
        except Exception as e:
            print(f"⚠️ check_courses_ready DB courses check: {e}")
 
    # ── TIER 3: Confirmed payment in DB → trigger queue (only once) ──
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
                session[f'paid_{flow}'] = True
                session.modified = True
                process_courses_after_payment(
                    email, index_number, flow, p.get('mpesa_receipt')
                )
                return jsonify({
                    'ready':      False,
                    'message':    'Payment confirmed. Generating courses…',
                    'processing': True,
                    'status':     'queued_from_db'
                })
        except Exception as e:
            print(f"⚠️ check_courses_ready DB payment check: {e}")
 
    # ── TIER 4: Manual activation in DB ──
    if database_connected and admin_activations_collection is not None:
        try:
            act = admin_activations_collection.find_one(
                {
                    '$or': [{'email': email}, {'index_number': index_number}],
                    'is_active': True,
                    'status': 'active'
                },
                {'_id': 1}
            )
            if act:
                session[f'paid_{flow}'] = True
                session.modified = True
                process_courses_after_payment(email, index_number, flow)
                return jsonify({
                    'ready':      False,
                    'message':    'Access confirmed. Generating courses…',
                    'processing': True,
                    'status':     'manual_activation_queued'
                })
        except Exception as e:
            print(f"⚠️ check_courses_ready activation check: {e}")
 
    # ── TIER 5: Session paid flag only ──
    if session.get(f'paid_{flow}'):
        process_courses_after_payment(email, index_number, flow)
        return jsonify({
            'ready':      False,
            'message':    'Starting course processing…',
            'processing': True,
            'status':     'starting'
        })
 
    # ── Nothing found ──
    return jsonify({
        'ready':   False,
        'message': 'Waiting for payment confirmation on your phone…',
        'status':  'waiting_for_payment'
    })
 
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
 
    # ── Manual activation ──
    if database_connected and admin_activations_collection is not None:
        try:
            act = admin_activations_collection.find_one(
                {'$or': [{'email': email}, {'index_number': index_number}],
                 'is_active': True},
                {'_id': 1}
            )
            if act:
                session[f'paid_{flow}']  = True
                session['current_flow']  = flow
                session['current_level'] = flow
                session.modified = True
                return redirect(url_for('show_results', flow=flow))
        except Exception as e:
            print(f"⚠️  goto_results activation: {e}")
 
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
 
    # ── 4. Manual activation ──
    if database_connected and admin_activations_collection is not None:
        try:
            act = admin_activations_collection.find_one(
                {
                    '$or': [{'email': email}, {'index_number': index_number}],
                    'is_active': True,
                    'status': 'active'
                },
                {'_id': 1}
            )
            if act:
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
        except Exception as e:
            print(f"⚠️ check_payment_status activation: {e}")
 
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
 
        # ── Backup activation record ──
        if admin_activations_collection is not None:
            try:
                exists = admin_activations_collection.find_one(
                    {
                        '$or': [
                            {'index_number': index_number},
                            {'mpesa_receipt': mpesa_receipt}
                        ]
                    },
                    {'_id': 1}
                )
                if not exists:
                    admin_activations_collection.insert_one({
                        'email':           email,
                        'index_number':    index_number,
                        'mpesa_receipt':   mpesa_receipt,
                        'activation_type': 'callback_auto',
                        'activated_by':    'system',
                        'activated_at':    datetime.now(),
                        'is_active':       True,
                        'status':          'active',
                        'used_for_flow':   None,
                        'used_at':         None
                    })
            except Exception as act_err:
                print(f"⚠️ Could not create backup activation: {act_err}")
 
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
    from bson import ObjectId
    """Display results - SESSION SAFE - courses always from database only"""
    
    print(f"🎯 show_results called for flow: {flow}")
    
    # Get user identification from session
    email = session.get('email')
    index_number = session.get('index_number')
    
    print(f"📧 Email from session: {email}")
    print(f"📝 Index from session: {index_number}")
    print(f"🔑 Session paid_{flow}: {session.get(f'paid_{flow}')}")
    print(f"📋 All session keys: {list(session.keys())}")
    
    if not email or not index_number:
        print(f"❌ Session expired - email={email}, index={index_number}")
        
        # Try to recover from manual activation ID
        manual_id = session.get('manual_activation_id')
        if manual_id and database_connected and admin_activations_collection is not None:
            try:
                from bson import ObjectId
                activation = admin_activations_collection.find_one({'_id': ObjectId(manual_id)})
                if activation:
                    email = activation.get('email')
                    index_number = activation.get('index_number')
                    print(f"🔄 Recovered user data from activation: {email}, {index_number}")
                    
                    # Clear and restore minimal session
                    session.clear()
                    session['email'] = email
                    session['index_number'] = index_number
                    session[f'paid_{flow}'] = True
                    session['current_flow'] = flow
                    session['current_level'] = flow
                    session['initialized'] = True
                    session['last_activity'] = datetime.now().isoformat()
                    session.modified = True
                    print(f"✅ Session restored with keys: {list(session.keys())}")
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
    
    # ============================================
    # MULTIPLE ACCESS VERIFICATION METHODS
    # ============================================
    has_access = False
    
    # Method 1: Check session paid flag
    if session.get(f'paid_{flow}'):
        has_access = True
        print(f"✅ Access granted via session paid flag")
    
    # Method 2: Check database for confirmed payment
    if not has_access and database_connected and user_payments_collection is not None:
        try:
            payment = user_payments_collection.find_one({
                '$or': [
                    {'email': email},
                    {'index_number': index_number}
                ],
                'level': flow,
                'payment_confirmed': True
            })
            if payment:
                has_access = True
                session[f'paid_{flow}'] = True
                session.modified = True
                print(f"✅ Access granted via confirmed payment in DB")
        except Exception as e:
            print(f"⚠️ Error checking payment in DB: {e}")
    
    # Method 3: Check database for manual activation
    if not has_access and database_connected and admin_activations_collection is not None:
        try:
            activation = admin_activations_collection.find_one({
                '$or': [
                    {'email': email},
                    {'index_number': index_number}
                ],
                'is_active': True,
                'status': 'active'
            })
            if activation:
                has_access = True
                session[f'paid_{flow}'] = True
                session['manual_activation_id'] = str(activation['_id'])
                session['manual_activation_receipt'] = activation.get('mpesa_receipt')
                session.modified = True
                print(f"✅ Access granted via manual activation in DB")
        except Exception as e:
            print(f"⚠️ Error checking manual activation in DB: {e}")
    
    # Method 4: Check verified payment
    if not has_access and session.get('verified_payment'):
        if session.get('verified_index') == index_number:
            has_access = True
            session[f'paid_{flow}'] = True
            session.modified = True
            print(f"✅ Access granted via verified payment")
    
    if not has_access:
        flash('Please complete payment to view your results.', 'error')
        if flow:
            return redirect(url_for('payment', flow=flow))
        return redirect(url_for('index'))
    
    # ============================================
    # MARK MANUAL ACTIVATION AS USED (only once)
    # ============================================
    activation_id = session.get('manual_activation_id')
    if activation_id and database_connected and admin_activations_collection is not None:
        try:
            from bson import ObjectId
            activation = admin_activations_collection.find_one({
                '_id': ObjectId(activation_id)
            })
            
            if activation and activation.get('is_active') and activation.get('status') == 'active':
                admin_activations_collection.update_one(
                    {'_id': ObjectId(activation_id)},
                    {'$set': {
                        'is_active': False,
                        'used_for_flow': flow,
                        'used_at': datetime.now(),
                        'status': 'used'
                    }}
                )
                print(f"✅ Manual activation {activation_id} marked as used")
                session.pop('manual_activation_id', None)
                session.modified = True
        except Exception as e:
            print(f"⚠️ Error marking activation as used: {e}")
    
    # ============================================
    # LOAD COURSES FROM DATABASE ONLY
    # ============================================
    qualifying_courses = []
    
    if database_connected and user_courses_collection is not None:
        try:
            courses_data = user_courses_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': flow
            })
            
            if courses_data and courses_data.get('courses'):
                qualifying_courses = courses_data['courses']
                print(f"✅ Loaded {len(qualifying_courses)} courses from database")
                
                # Convert ObjectId to string for template
                for course in qualifying_courses:
                    if '_id' in course and isinstance(course['_id'], ObjectId):
                        course['_id'] = str(course['_id'])
            else:
                print(f"⚠️ No courses found in database for {flow}")
                
                # Try to generate courses on the fly if grades exist
                user_grades, user_mean_grade, user_cluster_points = get_user_grades_from_db(email, index_number, flow)
                
                if user_grades:
                    print(f"🔄 Found grades in DB, generating courses on the fly")
                    
                    if flow == 'degree':
                        qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
                    elif flow == 'diploma':
                        qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
                    elif flow == 'certificate':
                        qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
                    elif flow == 'artisan':
                        qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
                    elif flow == 'kmtc':
                        qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
                    elif flow == 'ttc':
                        qualifying_courses = get_qualifying_ttc(user_grades, user_mean_grade)
                    
                    if qualifying_courses:
                        save_user_courses(email, index_number, flow, qualifying_courses)
                        print(f"✅ Generated and saved {len(qualifying_courses)} courses on the fly")
        except Exception as e:
            print(f"❌ Error getting courses from database: {e}")
    
    # IMPORTANT: NEVER store courses in session - causes cookie overflow!
    # DO NOT: session[f'{flow}_courses_{index_number}'] = qualifying_courses
    
    if not qualifying_courses:
        flash(f"No {flow.upper()} courses found. Please try again.", "warning")
        return redirect(url_for('index'))
    
    # ============================================
    # GROUP COURSES BY COLLECTION FOR DISPLAY
    # ============================================
    courses_by_collection = {}
    for course in qualifying_courses:
        if flow == 'degree':
            collection_key = course.get('cluster', 'Other')
            collection_name = CLUSTER_NAMES.get(collection_key, collection_key)
        else:
            collection_key = course.get('collection', 'Other')
            collection_name = collection_key.replace('_', ' ').title()
        
        if collection_key not in courses_by_collection:
            courses_by_collection[collection_key] = {
                'name': collection_name,
                'courses': []
            }
        courses_by_collection[collection_key]['courses'].append(course)
    
    # Store current level for basket functionality (but NOT courses!)
    session['current_level'] = flow
    session['current_flow'] = flow
    session.modified = True
    
    print(f"🎯 Displaying {len(qualifying_courses)} courses for {flow}")
    
    return render_template('collection_results.html', 
                         courses=qualifying_courses,
                         courses_by_collection=courses_by_collection,
                         user_grades={}, 
                         user_mean_grade=None,
                         user_cluster_points={},
                         subjects=SUBJECTS, 
                         email=email, 
                         index_number=index_number,
                         flow=flow,
                         cluster_names=CLUSTER_NAMES)
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
    """Verify payment and return course information for all levels"""
    try:
        mpesa_receipt = request.form.get('mpesa_receipt', '').strip().upper()
        index_number = request.form.get('index_number', '').strip()
        
        if not mpesa_receipt or not index_number:
            return jsonify({'success': False, 'error': 'M-Pesa receipt and index number are required'})
        
        # Validate M-Pesa receipt format
        if len(mpesa_receipt) != 10 or not mpesa_receipt.isalnum():
            return jsonify({'success': False, 'error': 'Invalid M-Pesa receipt format. Must be 10 alphanumeric characters.'})
        
        # Validate index number format
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            return jsonify({'success': False, 'error': 'Invalid index number format. Must be 11 digits, slash, 4 digits (e.g., 12345678901/2024)'})
        
        print(f"🔍 Verifying payment for index: {index_number}, receipt: {mpesa_receipt}")
        
        # Find confirmed payments for this index number and receipt
        payment_found = False
        paid_categories = []
        
        if database_connected:
            payment_data = user_payments_collection.find({
                'index_number': index_number,
                'mpesa_receipt': mpesa_receipt,
                'payment_confirmed': True
            })
            
            for payment in payment_data:
                payment_found = True
                level = payment.get('level')
                if level and level not in paid_categories:
                    paid_categories.append(level)
        else:
            # Session fallback
            for key in session:
                if isinstance(session.get(key), dict):
                    payment_data = session[key]
                    if (payment_data.get('index_number') == index_number and 
                        payment_data.get('mpesa_receipt') == mpesa_receipt and
                        payment_data.get('payment_confirmed')):
                        payment_found = True
                        level = payment_data.get('level')
                        if level and level not in paid_categories:
                            paid_categories.append(level)
        
        if not payment_found:
            print(f"❌ No confirmed payment found for index: {index_number}, receipt: {mpesa_receipt}")
            return jsonify({'success': False, 'error': 'No confirmed payment found with these details. Please ensure payment was successful and try again.'})
        
        print(f"✅ Payment confirmed for index: {index_number}, categories: {paid_categories}")
        
        # Get courses for all paid categories
        user_courses = {}
        total_courses = 0
        
        if database_connected:
            for level in paid_categories:
                courses_data = user_courses_collection.find_one({
                    'index_number': index_number,
                    'level': level
                })
                if courses_data and courses_data.get('courses'):
                    course_count = len(courses_data['courses'])
                    user_courses[level] = {
                        'count': course_count
                    }
                    total_courses += course_count
                    print(f"📚 Found {course_count} {level} courses")
        
        if total_courses == 0:
            return jsonify({'success': False, 'error': 'No course results found for your payment. Please ensure you completed the qualification process.'})
        
        print(f"🎓 Total courses found: {total_courses} across {len(paid_categories)} categories")
        
        # Return success response with available categories
        return jsonify({
            'success': True,
            'payment_confirmed': True,
            'courses_count': total_courses,
            'levels': paid_categories,
            'level_details': user_courses,
            'redirect_url': url_for('verified_results_dashboard', index=index_number, receipt=mpesa_receipt)
        })
        
    except Exception as e:
        print(f"❌ Error verifying payment: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Internal server error. Please try again later.'})

@app.route('/verified-dashboard')
def verified_results_dashboard():
    """Dashboard showing all available course levels for verified payment"""
    index_number = request.args.get('index')
    receipt = request.args.get('receipt')
    
    if not index_number or not receipt:
        flash("Invalid verification parameters", "error")
        return redirect(url_for('index'))
    
    print(f"📊 Loading dashboard for index: {index_number}")
    
    # Get all courses for this user across all levels
    user_courses = {}
    total_courses = 0
    
    if database_connected:
        levels = ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']
        for level in levels:
            courses_data = user_courses_collection.find_one({
                'index_number': index_number,
                'level': level
            })
            if courses_data and courses_data.get('courses'):
                course_count = len(courses_data['courses'])
                user_courses[level] = {
                    'courses': courses_data['courses'],
                    'count': course_count
                }
                total_courses += course_count
                print(f"📚 Loaded {course_count} {level} courses")
    
    if not user_courses:
        flash("No course results found for your payment details", "error")
        return redirect(url_for('index'))
    
    print(f"🎓 Dashboard ready with {total_courses} total courses")
    
    # Store verification in session
    session['verified_payment'] = True
    session['verified_index'] = index_number
    session['verified_receipt'] = receipt
    session['email'] = f"verified_{index_number}@temp.com"
    session['index_number'] = index_number
    
    # Load user's saved basket from database
    basket = get_user_basket_by_index(index_number)
    session['course_basket'] = basket
    
    return render_template('verified_dashboard.html',
                         user_courses=user_courses,
                         index_number=index_number,
                         receipt=receipt,
                         total_courses=total_courses,
                         basket_count=len(basket))

@app.route('/verified-results/<level>')
def show_verified_level_results(level):
    """Show verified results for a specific course level"""
    index_number = request.args.get('index')
    receipt = request.args.get('receipt')
    
    if level not in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc', 'ttc']:
        flash("Invalid course level", "error")
        return redirect(url_for('index'))
    
    if not index_number or not receipt:
        flash("Invalid verification parameters", "error")
        return redirect(url_for('index'))
    
    print(f"🎓 Loading {level} courses for index: {index_number}")
    
    # Store the current level for basket redirects
    session['current_level'] = level
    print(f"🔗 Stored current level for verified user: {level}")
    
    # Get courses for the specific level
    courses_data = None
    if database_connected:
        courses_data = user_courses_collection.find_one({
            'index_number': index_number,
            'level': level
        })
    
    if not courses_data or not courses_data.get('courses'):
        flash(f"No {level} course results found for your payment details", "error")
        return redirect(url_for('verified_results_dashboard', index=index_number, receipt=receipt))
    
    # Convert ObjectId to string for JSON serialization
    qualifying_courses = []
    for course in courses_data['courses']:
        course_dict = dict(course)
        # Convert _id from ObjectId to string if it exists
        if '_id' in course_dict and isinstance(course_dict['_id'], ObjectId):
            course_dict['_id'] = str(course_dict['_id'])
        qualifying_courses.append(course_dict)
    
    # Group courses by collection with proper names
    courses_by_collection = {}
    for course in qualifying_courses:
        if level == 'degree':
            collection_key = course.get('cluster', 'Other')
            # Use the proper cluster name for display
            collection_name = CLUSTER_NAMES.get(collection_key, collection_key)
        else:
            collection_key = course.get('collection', 'Other')
            collection_name = collection_key.replace('_', ' ').title()
        
        if collection_key not in courses_by_collection:
            courses_by_collection[collection_key] = {
                'name': collection_name,
                'courses': []
            }
        courses_by_collection[collection_key]['courses'].append(course)
    
    print(f"✅ Loaded {len(qualifying_courses)} {level} courses")
    
    # Set session data for basket and search functionality
    session['email'] = f"verified_{index_number}@temp.com"
    session['index_number'] = index_number
    session['verified_payment'] = True
    
    return render_template('collection_results.html', 
                         courses=qualifying_courses,
                         courses_by_collection=courses_by_collection,
                         user_grades={}, 
                         user_mean_grade=None,
                         user_cluster_points={},
                         subjects=SUBJECTS, 
                         email=f"verified_{index_number}@temp.com", 
                         index_number=index_number,
                         flow=level,
                         cluster_names=CLUSTER_NAMES)

# --- Course Basket Routes ---
@app.route('/add-to-basket', methods=['POST'])
def add_to_basket():
    try:
        course_data = request.get_json()
        print(f"📥 Adding course to basket: {course_data.get('programme_name', 'Unknown Course')}")
        
        # Get current flow/level
        current_level = session.get('current_level', session.get('current_flow', 'degree'))
        print(f"🔗 Stored current level: {current_level}")
        
        # Initialize course_basket as a list if it doesn't exist or is not a list
        if 'course_basket' not in session:
            session['course_basket'] = []
            print("🆕 Initialized new course basket")
        
        basket = session['course_basket']
        
        # Ensure basket is a list
        if not isinstance(basket, list):
            print(f"⚠️ Basket was not a list, converting: {type(basket)}")
            if isinstance(basket, dict):
                basket = [basket]
            else:
                basket = []
            session['course_basket'] = basket
        
        course_code = course_data.get('programme_code') or course_data.get('course_code')
        
        # Check for duplicates by programme_code
        existing_course = next((item for item in basket if (
            item.get('programme_code') == course_code or 
            item.get('course_code') == course_code
        )), None)
        
        if existing_course:
            print(f"⚠️ Course already in basket: {course_code}")
            return jsonify({
                'success': False,
                'error': 'Course already in basket',
                'basket_count': len(basket)
            })
        
        # Add basket_id and timestamp
        course_data['basket_id'] = str(ObjectId())
        course_data['added_at'] = datetime.now().isoformat()
        course_data['level'] = current_level
        
        # Add course to basket
        basket.append(course_data)
        session['course_basket'] = basket
        session.modified = True
        
        print(f"✅ Added course to basket. Total items: {len(basket)}")
        print(f"📊 Basket contents: {[item.get('programme_name', 'Unknown') for item in basket]}")
        
        # Save to database if user is verified
        email = session.get('email')
        index_number = session.get('index_number')
        if email and index_number:
            save_user_basket(email, index_number, basket)
        
        return jsonify({
            'success': True,
            'basket_count': len(basket),
            'message': 'Course added to basket successfully'
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
                    <li>Go to <a href="https://www.kuccpscourses.co.ke/{level}">https://www.kuccpscourses.co.ke/{level}</a></li>
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
                
                <p>Need help? Contact us: courseschecker@gmail.com | +254791196121</p>
                
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
                    <li>Visit <a href="https://www.kuccpscourses.co.ke">www.kuccpscourses.co.ke</a></li>
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
                
                <p>If you need any assistance, please contact our support team at courseschecker@gmail.com or +254791196121.</p>
                
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
                        <li>Go to <a href="https://www.kuccpscourses.co.ke/{level}">https://www.kuccpscourses.co.ke/{level}</a></li>
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
                        Need help? Contact us: courseschecker@gmail.com | +254791196121<br>
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
            
            # Create manual activation record
            activation_record = {
                'email': email,
                'index_number': index_number,
                'mpesa_receipt': mpesa_receipt,
                'activation_type': activation_type,
                'activated_by': session.get('admin_username', 'admin'),
                'activated_at': datetime.now(),
                'is_active': True,
                'status': 'active',  # Important: Set to 'active'
                'used_for_flow': None,
                'used_at': None,
                'email_sent': send_email
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
                                    'activation_type': activation_type,
                                    'email_sent': send_email
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
                                    'activation_type': activation_type,
                                    'email_sent': send_email
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
                    # Prepare email content
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
                                <li>Visit <a href="https://www.kuccpscourses.co.ke">www.kuccpscourses.co.ke</a></li>
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
                                <li>Email: courseschecker@gmail.com</li>
                                <li>Phone: +254791196121</li>
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
                    
                    # Send email via Brevo
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
    
    # Get recent activations for display
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