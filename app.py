import os
import base64
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from pymongo import MongoClient
from courses import get_user_courses, save_user_courses
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
from bson import ObjectId
import requests
from requests.auth import HTTPBasicAuth
import json
import re
from datetime import timedelta


# --- Configuration and Setup ---
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default_secret_key_not_for_production')
app.config.update(
    SESSION_TYPE='filesystem',
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_REFRESH_EACH_REQUEST=True,
    PREFERRED_URL_SCHEME='https'
)

# --- Constants ---
SUBJECTS = {
    'mathematics': 'MAT', 'english': 'ENG', 'kiswahili': 'KIS', 'chemistry': 'CHE',
    'biology': 'BIO', 'physics': 'PHY', 'geography': 'GEO', 'history': 'HAG',
    'cre': 'CRE', 'hre': 'HRE', 'ire': 'IRE', 'agriculture': 'AGR', 'computer': 'COM',
    'arts': 'ARD', 'business': 'BST', 'music': 'MUC', 'homescience': 'HSC',
    'french': 'FRE', 'german': 'GER', 'aviation': 'AVI', 'woodwork': 'ARD',
    'building': 'ARD', 'electronics': 'COM', 'metalwork': 'ARD'
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
    'cluster_16': 'Geography & Related',
    'cluster_17': 'French & German',
    'cluster_18': 'Music & Related',
    'cluster_19': 'Education & Related',
    'cluster_20': 'Religious Studies, Theology, Islamic Studies & Related'
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
db_certificate = None
db_artisan = None
user_payments_collection = None
user_courses_collection = None
user_baskets_collection = None
admin_activations_collection = None
database_connected = False

def initialize_database():
    """Initialize database connections with robust error handling and fixed index creation"""
    global db, db_user_data, db_diploma, db_kmtc, db_certificate, db_artisan
    global user_payments_collection, user_courses_collection, user_baskets_collection, admin_activations_collection, database_connected
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempting to connect to\\ MongoDB (attempt {attempt + 1}/{max_retries})...")
            
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
            
            # Initialize collections
            collections_initialized = True

            # Partial index filter used when creating partial unique indexes (ensure string-typed fields)
            partial_filter = {
                'email': {'$type': 'string'},
                'index_number': {'$type': 'string'},
                'level': {'$type': 'string'}
            }
            
            try:
                user_courses_collection = db_user_data['user_courses']
                print("✅ User courses collection initialized")
            except Exception as e:
                print(f"❌ Error initializing user_courses collection: {str(e)}")
                collections_initialized = False
            
            try:
                user_payments_collection = db_user_data['user_payments']
                print("✅ User payments collection initialized")
            except Exception as e:
                print(f"❌ Error initializing user_payments collection: {str(e)}")
                collections_initialized = False
            
            try:
                user_baskets_collection = db_user_data['user_baskets']
                print("✅ User baskets collection initialized")
            except Exception as e:
                print(f"❌ Error initializing user_baskets collection: {str(e)}")
                collections_initialized = False
            
            try:
                admin_activations_collection = db_user_data['admin_activations']
                print("✅ Admin activations collection initialized")
            except Exception as e:
                print(f"❌ Error initializing admin_activations collection: {str(e)}")
                admin_activations_collection = None
                collections_initialized = False
            
            # FIXED INDEX CREATION WITH CONFLICT RESOLUTION
            if user_payments_collection is not None:
                try:
                    # Get all existing indexes
                    existing_indexes = list(user_payments_collection.list_indexes())
                    print(f"🔍 Found {len(existing_indexes)} existing indexes")

                    # Desired key pattern for the compound index
                    desired_key = {'email': 1, 'index_number': 1, 'level': 1}

                    # Drop any existing index that uses the same key pattern but has different name or options
                    for index in existing_indexes:
                        index_name = index.get('name', '')
                        index_keys = index.get('key', {})
                        index_unique = index.get('unique', False)
                        index_partial = index.get('partialFilterExpression', None)
                        # If an index uses the same keys but differs from our desired spec, drop it
                        if index_keys == desired_key:
                            needs_drop = False
                            if index_name != 'unique_email_index_level':
                                needs_drop = True
                            # If uniqueness doesn't match or partial filter expression differs, drop
                            elif not index_unique or index_partial != partial_filter:
                                needs_drop = True
                            if needs_drop:
                                try:
                                    print(f"🔄 Dropping existing index '{index_name}' because it conflicts with desired spec")
                                    user_payments_collection.drop_index(index_name)
                                    print(f"✅ Dropped index '{index_name}'")
                                except Exception as drop_err:
                                    print(f"⚠️ Could not drop index '{index_name}': {drop_err}")

                    # partial_filter already defined above

                    # Try to create a unique partial index for non-null/string docs
                    try:
                        user_payments_collection.create_index(
                            [("email", 1), ("index_number", 1), ("level", 1)],
                            name='unique_email_index_level',
                            unique=True,
                            partialFilterExpression=partial_filter
                        )
                        print("✅ Unique partial user_payments index created (name=unique_email_index_level)")
                    except Exception as create_err:
                        print(f"❌ Error creating unique partial user_payments index: {create_err}")
                        # Fallback: try non-unique index (safe) and continue
                        try:
                            user_payments_collection.create_index(
                                [("email", 1), ("index_number", 1), ("level", 1)],
                                name='non_unique_email_index_level',
                                unique=False
                            )
                            print("✅ Created non-unique user_payments index as fallback")
                        except Exception as fallback_error:
                            print(f"⚠️ Fallback user_payments index creation also failed: {fallback_error}")

                    # Other useful indexes (create with safe handling in case index with different name exists)
                    try:
                        # transaction_ref index
                        existing = [i for i in existing_indexes if i.get('key', {}) == {'transaction_ref': 1}]
                        if existing and existing[0].get('name') != 'transaction_ref_index':
                            try:
                                user_payments_collection.drop_index(existing[0].get('name'))
                            except Exception:
                                pass
                        user_payments_collection.create_index([("transaction_ref", 1)], name='transaction_ref_index')
                    except Exception as ie:
                        print(f"❌ Failed to create/ensure transaction_ref index: {str(ie)}")

                    try:
                        existing = [i for i in existing_indexes if i.get('key', {}) == {'payment_confirmed': 1}]
                        if existing and existing[0].get('name') != 'payment_confirmed_index':
                            try:
                                user_payments_collection.drop_index(existing[0].get('name'))
                            except Exception:
                                pass
                        user_payments_collection.create_index([("payment_confirmed", 1)], name='payment_confirmed_index')
                    except Exception as ie:
                        print(f"❌ Failed to create/ensure payment_confirmed index: {str(ie)}")

                except Exception as e:
                    print(f"❌ Error creating user_payments indexes: {str(e)}")
            
            if user_courses_collection is not None:
                try:
                    existing_indexes = list(user_courses_collection.list_indexes())
                    desired_key = {'email': 1, 'index_number': 1, 'level': 1}

                    # Drop any existing index that uses the same key pattern but has different name or options
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
                                    print(f"🔄 Dropping existing courses index '{index_name}' because it conflicts with desired spec")
                                    user_courses_collection.drop_index(index_name)
                                    print(f"✅ Dropped courses index '{index_name}'")
                                except Exception as drop_err:
                                    print(f"⚠️ Could not drop courses index '{index_name}': {drop_err}")

                    partial_filter = {
                        'email': {'$type': 'string'},
                        'index_number': {'$type': 'string'},
                        'level': {'$type': 'string'}
                    }

                    try:
                        user_courses_collection.create_index(
                            [("email", 1), ("index_number", 1), ("level", 1)],
                            name='unique_courses_email_index_level',
                            unique=True,
                            partialFilterExpression=partial_filter
                        )
                        print("✅ Unique partial user_courses index created (name=unique_courses_email_index_level)")
                    except Exception as create_err:
                        print(f"❌ Error creating unique partial user_courses index: {create_err}")
                        try:
                            user_courses_collection.create_index(
                                [("email", 1), ("index_number", 1), ("level", 1)],
                                name='non_unique_courses_email_index_level',
                                unique=False
                            )
                            print("✅ Created non-unique courses index as fallback")
                        except Exception as fallback_error:
                            print(f"⚠️ Fallback courses index creation failed: {fallback_error}")

                except Exception as e:
                    print(f"❌ Error creating user_courses indexes: {str(e)}")
            
            # Other index creations remain the same...
            if user_baskets_collection is not None:
                try:
                    existing_indexes = list(user_baskets_collection.list_indexes())
                    # Ensure index for index_number exists; drop conflicting if necessary
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'index_number': 1}]
                    if existing and existing[0].get('name') != 'basket_index_number':
                        try:
                            user_baskets_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_baskets_collection.create_index([("index_number", 1)], name='basket_index_number')

                    existing = [i for i in existing_indexes if i.get('key', {}) == {'email': 1}]
                    if existing and existing[0].get('name') != 'basket_email':
                        try:
                            user_baskets_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_baskets_collection.create_index([("email", 1)], name='basket_email')

                    existing = [i for i in existing_indexes if i.get('key', {}) == {'created_at': 1}]
                    if existing and existing[0].get('name') != 'basket_created_at':
                        try:
                            user_baskets_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    user_baskets_collection.create_index([("created_at", 1)], name='basket_created_at')
                    print("✅ User baskets indexes created")
                except Exception as e:
                    print(f"❌ Error creating user_baskets indexes: {str(e)}")
            
            if admin_activations_collection is not None:
                try:
                    existing_indexes = list(admin_activations_collection.list_indexes())
                    existing = [i for i in existing_indexes if i.get('key', {}) == {'index_number': 1}]
                    if existing and existing[0].get('name') != 'activation_index_number':
                        try:
                            admin_activations_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    admin_activations_collection.create_index([("index_number", 1)], name='activation_index_number')

                    existing = [i for i in existing_indexes if i.get('key', {}) == {'mpesa_receipt': 1}]
                    if existing and existing[0].get('name') != 'activation_mpesa_receipt':
                        try:
                            admin_activations_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    admin_activations_collection.create_index([("mpesa_receipt", 1)], name='activation_mpesa_receipt')

                    existing = [i for i in existing_indexes if i.get('key', {}) == {'is_active': 1}]
                    if existing and existing[0].get('name') != 'activation_is_active':
                        try:
                            admin_activations_collection.drop_index(existing[0].get('name'))
                        except Exception:
                            pass
                    admin_activations_collection.create_index([("is_active", 1)], name='activation_is_active')
                    print("✅ Admin activations indexes created")
                except Exception as e:
                    print(f"❌ Error creating admin_activations indexes: {str(e)}")
            else:
                print("⚠️ Admin activations collection not available for indexing")
            
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
database_connected = initialize_database()            
            
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
        'kmtc_grades', 'kmtc_mean_grade', 'kmtc_data_submitted'
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

@app.before_request
def check_session_timeout():
    """Check for session timeout and handle accordingly"""
    if 'last_activity' in session:
        last_activity = datetime.fromisoformat(session['last_activity'])
        if datetime.now() - last_activity > timedelta(minutes=30):
            clear_session_data()
            return redirect(url_for('index'))
    
    session['last_activity'] = datetime.now().isoformat()

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
    """Check if user qualifies for a specific artisan course based on mean grade and subject requirements"""
    return check_diploma_course_qualification(course, user_grades, user_mean_grade)

# --- Course Qualification Functions ---
def get_qualifying_courses(user_grades, user_cluster_points):
    """Get all degree courses that the user qualifies for"""
    if not database_connected:
        print("❌ Database not available for degree courses")
        return []
        
    qualifying_courses = []
    
    for collection_name in CLUSTERS:
        try:
            if collection_name not in db.list_collection_names():
                continue
                
            collection = db[collection_name]
            courses = collection.find()
            
            for course in courses:
                course_with_cluster = dict(course)
                course_with_cluster['cluster'] = collection_name
                
                if check_course_qualification(course_with_cluster, user_grades, user_cluster_points):
                    qualifying_courses.append(course_with_cluster)
        
        except Exception as e:
            print(f"Error processing collection {collection_name}: {str(e)}")
            continue
    
    return qualifying_courses

def get_qualifying_diploma_courses(user_grades, user_mean_grade):
    """Get all diploma courses that the user qualifies for"""
    if not database_connected:
        print("❌ Database not available for diploma courses")
        return []
        
    qualifying_courses = []
    
    for collection_name in DIPLOMA_COLLECTIONS:
        try:
            if collection_name not in db_diploma.list_collection_names():
                continue
                
            collection = db_diploma[collection_name]
            courses = collection.find()
            
            for course in courses:
                if check_diploma_course_qualification(course, user_grades, user_mean_grade):
                    course_with_collection = dict(course)
                    course_with_collection['collection'] = collection_name
                    qualifying_courses.append(course_with_collection)
        
        except Exception as e:
            print(f"Error processing diploma collection {collection_name}: {str(e)}")
            continue
    
    return qualifying_courses

def get_qualifying_kmtc_courses(user_grades, user_mean_grade):
    """Get all KMTC courses that the user qualifies for"""
    if not database_connected:
        print("❌ Database not available for KMTC courses")
        return []
        
    qualifying_courses = []
    
    try:
        if 'kmtc_courses' not in db_kmtc.list_collection_names():
            return qualifying_courses
            
        collection = db_kmtc['kmtc_courses']
        courses = collection.find()
        
        for course in courses:
            if check_diploma_course_qualification(course, user_grades, user_mean_grade):
                qualifying_courses.append(course)
                
    except Exception as e:
        print(f"Error processing KMTC collection: {str(e)}")
        
    return qualifying_courses

def get_qualifying_certificate_courses(user_grades, user_mean_grade):
    """Get all certificate courses that the user qualifies for"""
    if not database_connected:
        print("❌ Database not available for certificate courses")
        return []
        
    qualifying_courses = []
    
    for collection_name in CERTIFICATE_COLLECTIONS:
        try:
            if collection_name not in db_certificate.list_collection_names():
                continue
                
            collection = db_certificate[collection_name]
            courses = collection.find()
            
            for course in courses:
                if check_certificate_course_qualification(course, user_grades, user_mean_grade):
                    course_with_collection = dict(course)
                    course_with_collection['collection'] = collection_name
                    qualifying_courses.append(course_with_collection)
        
        except Exception as e:
            print(f"Error processing certificate collection {collection_name}: {str(e)}")
            continue
    
    return qualifying_courses

def get_qualifying_artisan_courses(user_grades, user_mean_grade):
    """Get all artisan courses that the user qualifies for"""
    if not database_connected:
        print("❌ Database not available for artisan courses")
        return []
        
    qualifying_courses = []
    
    for collection_name in ARTISAN_COLLECTIONS:
        try:
            if collection_name not in db_artisan.list_collection_names():
                continue
                
            collection = db_artisan[collection_name]
            courses = collection.find()
            
            for course in courses:
                if check_artisan_course_qualification(course, user_grades, user_mean_grade):
                    course_with_collection = dict(course)
                    course_with_collection['collection'] = collection_name
                    qualifying_courses.append(course_with_collection)
        
        except Exception as e:
            print(f"Error processing artisan collection {collection_name}: {str(e)}")
            continue
    
    return qualifying_courses

# --- Database Operations ---
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
def process_courses_after_payment(email, index_number, flow):
    """Process and save courses after payment confirmation"""
    print(f"🎯 Processing courses for {flow} after payment confirmation")
    
    try:
        qualifying_courses = []
        user_grades = {}
        user_mean_grade = None
        user_cluster_points = {}
        
        # Get the appropriate data based on flow
        if flow == 'degree':
            user_grades = session.get('degree_grades', {})
            user_cluster_points = session.get('degree_cluster_points', {})
            
            # 🔥 VALIDATION: Ensure we have required grade data
            if not user_grades or not user_cluster_points:
                print(f"⚠️ Missing required grade data for degree - Grades: {bool(user_grades)}, Points: {bool(user_cluster_points)}")
                return False
                
            print(f"📊 Processing degree with {len(user_grades)} grades and {len(user_cluster_points)} cluster points")
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
        
        # Save courses to database
        if qualifying_courses:
            save_user_courses(email, index_number, flow, qualifying_courses)
            print(f"✅ Processed and saved {len(qualifying_courses)} {flow} courses")
            return True
        else:
            print(f"⚠️ No qualifying courses found for {flow}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing courses after payment: {str(e)}")
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
        
        # Use correct callback URL
        if os.environ.get('FLASK_ENV') == 'production' or 'render.com' in os.environ.get('RENDER_EXTERNAL_HOSTNAME', ''):
            base_url = 'https://kuccps-courses.onrender.com'
        else:
            base_url = 'https://kuccps-courses.onrender.com'
        
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
                # Mark as expired in database
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
                            'status': 'expired'
                        }
                    }
                )
                if result.modified_count > 0:
                    print(f"✅ Manual activation marked as expired for {flow}")
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
                                    'status': 'expired'
                                }
                            }
                        )
                        if result.modified_count > 0:
                            print(f"✅ Manual activation marked as expired for {flow}")
                            session.pop(key, None)
                    except Exception as e:
                        print(f"❌ Error expiring manual activation: {str(e)}")
                
                return True
    
    if not database_connected:
        print("ℹ️ Database not connected, only checking session")
        return False
    
    try:
        # Check database for active manual activation
        activation = admin_activations_collection.find_one({
            '$or': [
                {'email': email},
                {'index_number': index_number}
            ],
            'is_active': True
        })
        
        if activation:
            print(f"✅ Manual activation found in database for {email}/{index_number}")
            
            # If flow is specified, mark as expired immediately
            if flow:
                result = admin_activations_collection.update_one(
                    {'_id': activation['_id']},
                    {
                        '$set': {
                            'is_active': False,
                            'used_for_flow': flow,
                            'used_at': datetime.now(),
                            'status': 'expired'
                        }
                    }
                )
                if result.modified_count > 0:
                    print(f"✅ Manual activation marked as expired for {flow}")
            else:
                # Store in session for faster future access (only if not expiring immediately)
                session[session_key] = {
                    'email': activation.get('email'),
                    'index_number': activation.get('index_number'),
                    'mpesa_receipt': activation.get('mpesa_receipt'),
                    'activated_at': activation.get('activated_at')
                }
            
            return True
        else:
            print(f"❌ No manual activation found for {email}/{index_number}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking manual activation in database: {str(e)}")
        return False

def create_manual_activation_payment(email, index_number, flow, mpesa_receipt):
    """Create a payment record for manual activations so users can verify later"""
    print(f"💰 Creating payment record for manual activation: {email}, {index_number}, {flow}")
    
    payment_record = {
        'email': email,
        'index_number': index_number,
        'level': flow,
        'transaction_ref': f"MANUAL_{mpesa_receipt}",
        'mpesa_receipt': mpesa_receipt,
        'payment_amount': 0,  # Manual activations are free
        'payment_confirmed': True,
        'payment_method': 'manual_activation',
        'activated_by': 'admin',
        'created_at': datetime.now(),
        'payment_date': datetime.now()
    }
    
    if database_connected:
        try:
            result = user_payments_collection.update_one(
                {
                    'email': email,
                    'index_number': index_number,
                    'level': flow
                },
                {'$set': payment_record},
                upsert=True
            )
            print(f"✅ Manual activation payment record saved for {flow}")
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
        for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc']:
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
def index():
    return render_template('index.html')

@app.route('/degree')
def degree():
    return render_template('degree.html')

@app.route('/diploma')
def diploma():
    return render_template('diploma.html')

@app.route('/kmtc')
def kmtc():
    return render_template('kmtc.html')

@app.route('/certificate')
def certificate():
    return render_template('certificate.html')

@app.route('/artisan')
def artisan():
    return render_template('artisan.html')

@app.route('/results')
def results():
    return render_template('results.html')

@app.route('/user-guide')
def userguide():
    return render_template('user-guide.html')


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
@app.route('/enter-details/<flow>', methods=['GET', 'POST'])
def enter_details(flow):
    print(f"🎯 Enter details accessed for flow: {flow}")
    print(f"🔍 Session check - {flow}_data_submitted: {session.get(f'{flow}_data_submitted')}")
    print(f"🔍 All session keys: {[k for k in session.keys() if not k.startswith('_')]}")
    
    if request.method == 'GET':
        # Check if the specific flow data is submitted
        data_submitted_key = f'{flow}_data_submitted'
        print(f"🔍 Checking data submitted key: {data_submitted_key}")
        
        if not session.get(data_submitted_key):
            print(f"❌ {flow} data not found in session. Redirecting to {flow} page")
            flash("Please submit your grades first", "error")
            return redirect(url_for(flow))
        
        print(f"✅ {flow} data validated successfully")
        return render_template('enter_details.html', flow=flow)
    
    # POST request handling
    try:
        email = request.form.get('email', '').strip().lower()
        index_number = request.form.get('index_number', '').strip()
        
        print(f"📧 Processing details - Email: {email}, Index: {index_number}, Flow: {flow}")

        if not email or not index_number:
            flash("Email and KCSE Index Number are required.", "error")
            return redirect(url_for('enter_details', flow=flow))
        
        # Validate index number format
        if not re.match(r'^\d{11}/\d{4}$', index_number):
            flash("Invalid index number format. Must be 11 digits, slash, 4 digits (e.g., 12345678901/2024)", "error")
            return redirect(url_for('enter_details', flow=flow))
        
        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash("Please enter a valid email address.", "error")
            return redirect(url_for('enter_details', flow=flow))
        
        # 🔥 Check for manual activation first
        print(f"🔍 Checking manual activation for {email}/{index_number}")
        if check_manual_activation(email, index_number, flow):
            print(f"✅ Manual activation found for {email}, generating courses for {flow}")
            
            # Store user details in session
            session['email'] = email
            session['index_number'] = index_number
            session['current_flow'] = flow
            session[f'paid_{flow}'] = True
            session['manual_activation'] = True
            session.modified = True
            
            # Get the M-Pesa receipt from the activation record
            mpesa_receipt = None
            if database_connected and admin_activations_collection is not None:
                try:
                    activation = admin_activations_collection.find_one({
                        '$or': [
                            {'email': email},
                            {'index_number': index_number}
                        ],
                        'mpesa_receipt': {'$exists': True}
                    })
                    if activation:
                        mpesa_receipt = activation.get('mpesa_receipt')
                        print(f"💰 Found M-Pesa receipt: {mpesa_receipt}")
                except Exception as e:
                    print(f"❌ Error getting M-Pesa receipt: {str(e)}")
            
            # Create payment record for manual activation
            if mpesa_receipt:
                create_manual_activation_payment(email, index_number, flow, mpesa_receipt)
            else:
                print("⚠️ No M-Pesa receipt found, creating fallback payment record")
                create_manual_activation_payment(email, index_number, flow, f"MANUAL_{index_number}")
            
            # Generate courses immediately for manually activated users
            try:
                qualifying_courses = []
                print(f"🚀 Generating courses for {flow} flow")
                
                if flow == 'degree':
                    user_grades = session.get('degree_grades', {})
                    user_cluster_points = session.get('degree_cluster_points', {})
                    print(f"📊 Degree grades: {user_grades}, Cluster points: {user_cluster_points}")
                    qualifying_courses = get_qualifying_courses(user_grades, user_cluster_points)
                    
                elif flow == 'diploma':
                    user_grades = session.get('diploma_grades', {})
                    user_mean_grade = session.get('diploma_mean_grade', '')
                    print(f"📊 Diploma grades: {user_grades}, Mean grade: {user_mean_grade}")
                    qualifying_courses = get_qualifying_diploma_courses(user_grades, user_mean_grade)
                    
                elif flow == 'certificate':
                    user_grades = session.get('certificate_grades', {})
                    user_mean_grade = session.get('certificate_mean_grade', '')
                    print(f"📊 Certificate grades: {user_grades}, Mean grade: {user_mean_grade}")
                    qualifying_courses = get_qualifying_certificate_courses(user_grades, user_mean_grade)
                    
                elif flow == 'artisan':
                    user_grades = session.get('artisan_grades', {})
                    user_mean_grade = session.get('artisan_mean_grade', '')
                    print(f"📊 Artisan grades: {user_grades}, Mean grade: {user_mean_grade}")
                    qualifying_courses = get_qualifying_artisan_courses(user_grades, user_mean_grade)
                    
                elif flow == 'kmtc':
                    user_grades = session.get('kmtc_grades', {})
                    user_mean_grade = session.get('kmtc_mean_grade', '')
                    print(f"📊 KMTC grades: {user_grades}, Mean grade: {user_mean_grade}")
                    qualifying_courses = get_qualifying_kmtc_courses(user_grades, user_mean_grade)
                
                print(f"📚 Found {len(qualifying_courses)} qualifying courses for {flow}")
                
                # Save courses to database
                if qualifying_courses:
                    save_user_courses(email, index_number, flow, qualifying_courses)
                    print(f"✅ Generated {len(qualifying_courses)} courses for manually activated user")
                    
                    # Redirect directly to results
                    flash("Manual activation verified! Your courses have been generated. You can now view this category anytime using 'Already Made Payment'.", "success")
                    return redirect(url_for('show_results', flow=flow))
                else:
                    flash("No qualifying courses found for your grades. Please try a different course level.", "warning")
                    return redirect(url_for(flow))
                    
            except Exception as e:
                print(f"❌ Error generating courses for manually activated user: {str(e)}")
                import traceback
                traceback.print_exc()
                flash("Error generating courses. Please try again.", "error")
                return redirect(url_for('enter_details', flow=flow))
        
        # 🔥 STRICTER CHECK: Check if user has already paid for this SPECIFIC category
        print(f"🔍 Checking if user already paid for {flow}")
        if has_user_paid_for_category(email, index_number, flow):
            print(f"🚫 User {email} already paid for {flow}")
            flash(f"You have already paid for {flow.upper()} courses. Please use 'Already Made Payment' to view your results.", "warning")
            return redirect(url_for('index'))
        
        # 🔥 Check if user is currently in process for this category
        existing_session_flow = session.get('current_flow')
        existing_session_email = session.get('email')
        existing_session_index = session.get('index_number')
        
        print(f"🔍 Session check - Flow: {existing_session_flow}, Email: {existing_session_email}, Index: {existing_session_index}")
        
        if (existing_session_flow == flow and 
            existing_session_email == email and 
            existing_session_index == index_number and
            session.get(f'paid_{flow}')):
            print(f"🚫 User trying to access same category again: {flow}")
            flash(f"You are already viewing {flow.upper()} courses. Please use your existing session.", "warning")
            return redirect(url_for('show_results', flow=flow))
        
        # Check if user already has any paid categories to determine pricing
        print(f"🔍 Checking existing paid categories for {email}")
        existing_categories = get_user_paid_categories(email, index_number)
        is_first_category = len(existing_categories) == 0
        amount = 2 if is_first_category else 1
        
        print(f"💰 Pricing - First category: {is_first_category}, Amount: {amount}, Existing categories: {existing_categories}")
        
        # Store in session
        session['email'] = email
        session['index_number'] = index_number
        session['current_flow'] = flow
        session['payment_amount'] = amount
        session['is_first_category'] = is_first_category
        
        # Clear any previous payment status for this flow to prevent conflicts
        session[f'paid_{flow}'] = False
        session.modified = True
        
        print(f"💾 Session updated for {flow} flow")
        
        # Save initial payment record with amount
        save_user_payment(email, index_number, flow, amount=amount)
        
        # Show pricing information
        if is_first_category:
            flash(f"First category price: Ksh {amount}", "info")
        else:
            flash(f"Additional category price: Ksh {amount} (you already have {len(existing_categories)} paid categories)", "info")
        
        print(f"✅ All checks passed, redirecting to payment for {flow}")
        return redirect(url_for('payment', flow=flow))
        
    except Exception as e:
        print(f"❌ Error in enter_details POST: {str(e)}")
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
    
@app.route('/check-payment/<flow>')
def check_payment(flow):
    email = session.get('email')
    index_number = session.get('index_number')
    user_payment = get_user_payment(email, index_number, flow)
    paid = bool(user_payment and user_payment.get('payment_confirmed'))
    return {'paid': paid}

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
        
        print(f"💳 Processing payment for {flow}, amount: {amount}, phone: {phone}")
        
        # 🔥 PASS THE FLOW PARAMETER to initiate_stk_push
        result = initiate_stk_push(phone, amount=amount, flow=flow)
        
        if result.get('ResponseCode') == '0':
            transaction_ref = result.get('CheckoutRequestID')
            email = session.get('email')
            index_number = session.get('index_number')
            
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
    transaction_ref = request.args.get('transaction_ref')
    
    if email and index_number and not transaction_ref:
        user_payment = get_user_payment(email, index_number, flow)
        if user_payment:
            transaction_ref = user_payment.get('transaction_ref')
            
    return render_template('payment_wait.html', 
                         flow=flow, 
                         transaction_ref=transaction_ref,
                         check_status_url=url_for('check_payment_status', flow=flow))

@app.route('/check-courses-ready/<flow>')
def check_courses_ready(flow):
    """Check if courses have been processed and are ready to display"""
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        return jsonify({'ready': False, 'error': 'Session data missing'})
    
    # Check if courses exist in database for this user and flow
    courses_data = get_user_courses_data(email, index_number, flow)
    
    if courses_data and courses_data.get('courses'):
        # Courses are ready
        return jsonify({
            'ready': True,
            'redirect_url': url_for('show_results', flow=flow)
        })
    else:
        # Courses not ready yet - try to process them
        print(f"🔄 Courses not found, attempting to process for {flow}")
        success = process_courses_after_payment(email, index_number, flow)
        
        if success:
            # Check again after processing
            courses_data = get_user_courses_data(email, index_number, flow)
            if courses_data and courses_data.get('courses'):
                return jsonify({
                    'ready': True,
                    'redirect_url': url_for('show_results', flow=flow)
                })
        
        # Courses not ready yet
        return jsonify({'ready': False})
@app.route('/check-payment-status/<flow>')
def check_payment_status(flow):
    """Check payment status - ONLY return True after MPesa callback confirmation"""
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        return {'paid': False, 'error': 'Session data missing'}
    
    print(f"🔍 Checking payment status for {flow} - {email}")
    
    # Get the latest payment record
    user_payment = get_user_payment(email, index_number, flow)
    
    if not user_payment:
        print(f"❌ No payment record found for {flow}")
        return {'paid': False, 'status': 'no_payment_record'}
    
    transaction_ref = user_payment.get('transaction_ref')
    payment_confirmed = user_payment.get('payment_confirmed', False)
    mpesa_receipt = user_payment.get('mpesa_receipt')
    
    print(f"📊 Payment status - Confirmed: {payment_confirmed}, Receipt: {mpesa_receipt}, Transaction: {transaction_ref}")
    
    # 🔥 CRITICAL: Only return True if payment is actually confirmed via MPesa callback WITH receipt
    if payment_confirmed and mpesa_receipt:
        print(f"✅ Payment confirmed via MPesa callback for {flow} with receipt: {mpesa_receipt}")
        
        # Double-check with database for extra security
        if database_connected:
            fresh_payment = user_payments_collection.find_one({
                'email': email, 
                'index_number': index_number, 
                'level': flow,
                'payment_confirmed': True,
                'mpesa_receipt': {'$exists': True, '$ne': None}
            })
            if fresh_payment:
                session[f'paid_{flow}'] = True
                session['payment_confirmed'] = True
                
                # Check if courses need to be processed
                courses_data = get_user_courses_data(email, index_number, flow)
                if not courses_data or not courses_data.get('courses'):
                    print(f"🔄 Payment confirmed but no courses found, processing now...")
                    process_courses_after_payment(email, index_number, flow)
                
                return {
                    'paid': True,
                    'redirect_url': url_for('show_results', flow=flow),
                    'status': 'confirmed',
                    'mpesa_receipt': mpesa_receipt
                }
        
        return {'paid': False, 'status': 'verification_failed'}
    
    # Payment not confirmed yet
    print(f"⏳ Payment not yet confirmed for {flow}")
    return {
        'paid': False, 
        'status': 'pending',
        'message': 'Waiting for payment confirmation...'
    }
# --- MPesa Callback Routes ---
@app.route('/mpesa/callback', methods=['POST'])
def mpesa_callback():
    """MPesa callback handler - ONLY this should mark payments as confirmed"""
    try:
        data = request.get_json(force=True)
        print(f"📥 MPesa callback received: {json.dumps(data, indent=2)}")
        
        callback_metadata = data.get('Body', {}).get('stkCallback', {})
        transaction_ref = callback_metadata.get('CheckoutRequestID')
        result_code = callback_metadata.get('ResultCode')
        
        print(f"🔍 Callback details - Transaction: {transaction_ref}, Result: {result_code}")
        
        # Only process successful payments
        if result_code == 0:
            mpesa_receipt = None
            items = callback_metadata.get('CallbackMetadata', {}).get('Item', [])
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                    break
            
            if transaction_ref and mpesa_receipt:
                print(f"💰 Payment successful - Transaction: {transaction_ref}, Receipt: {mpesa_receipt}")
                
                # Mark payment as confirmed
                result = mark_payment_confirmed(transaction_ref, mpesa_receipt)
                if result:
                    print(f"✅ Payment callback processed successfully: {transaction_ref}")
                    
                    # 🔥 Get user details and process courses
                    if database_connected:
                        payment_data = user_payments_collection.find_one({'transaction_ref': transaction_ref})
                        if payment_data:
                            email = payment_data.get('email')
                            index_number = payment_data.get('index_number')
                            flow = payment_data.get('level')
                            
                            if email and index_number and flow:
                                print(f"🚀 Triggering course processing for {flow}")
                                process_courses_after_payment(email, index_number, flow)
                                print(f"✅ Courses processed for {email}")
                    
                    return {'success': True, 'message': 'Payment processed'}, 200
                else:
                    print(f"❌ Failed to mark payment confirmed: {transaction_ref}")
                    return {'success': False, 'error': 'Payment record not found'}, 400
            else:
                print(f"❌ Missing transaction ref or receipt in callback")
                return {'success': False, 'error': 'Invalid callback data'}, 400
        else:
            # Payment failed or was cancelled
            error_message = callback_metadata.get('ResultDesc', 'Payment failed')
            print(f"❌ Payment failed: {error_message}")
            return {'success': False, 'error': error_message}, 400
            
    except Exception as e:
        print(f"❌ Error processing MPesa callback: {str(e)}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': 'Internal server error'}, 400
    
@app.route('/about')
def about():
    return render_template('about.html')

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
    email = session.get('email')
    index_number = session.get('index_number')
    
    if not email or not index_number:
        flash("Please complete the qualification process first", "error")
        return redirect(url_for('index'))
    
    # 🔥 STRICTER PAYMENT VERIFICATION
    user_payment = get_user_payment(email, index_number, flow)
    session_paid = session.get(f'paid_{flow}')
    
    # Check if payment is confirmed in database OR session
    payment_confirmed = False
    if user_payment and user_payment.get('payment_confirmed'):
        payment_confirmed = True
        # Ensure session is updated
        session[f'paid_{flow}'] = True
    elif session_paid:
        payment_confirmed = True
        # If only in session, try to verify with database
        if database_connected and user_payment:
            # Double-check database
            fresh_payment = user_payments_collection.find_one({
                'email': email, 
                'index_number': index_number, 
                'level': flow,
                'payment_confirmed': True
            })
            if not fresh_payment:
                payment_confirmed = False
                session[f'paid_{flow}'] = False
    
    if not payment_confirmed:
        print(f"❌ Payment not confirmed for {flow}. User payment: {user_payment}, Session paid: {session_paid}")
        flash('Please complete payment to view your results.', 'error')
        return redirect(url_for('payment', flow=flow))
    
    # 🔥 PREVENT DUPLICATE ACCESS TO SAME CATEGORY
    # Check if user is trying to access same category again without proper flow
    current_flow = session.get('current_flow')
    if current_flow != flow:
        # User might be trying to access results directly without proper flow
        print(f"⚠️ Suspicious access: current_flow={current_flow}, requested_flow={flow}")
        # Still allow if they have paid, but log it
        if not has_user_paid_for_category(email, index_number, flow):
            flash('Invalid access attempt. Please complete the qualification process.', 'error')
            return redirect(url_for('index'))

    # Store the current flow for basket redirects
    session['current_flow'] = flow
    print(f"🔗 Stored current flow: {flow}")

    qualifying_courses = []
    user_grades = {}
    user_mean_grade = None
    user_cluster_points = {}
    
    try:
        # Get courses from database first (if they exist)
        courses_data = get_user_courses_data(email, index_number, flow)
        if courses_data and courses_data.get('courses'):
            qualifying_courses = courses_data['courses']
            print(f"✅ Loaded {len(qualifying_courses)} courses from database for {flow}")
        else:
            # Generate courses if not in database
            print(f"🔄 Courses not in database, generating for {flow}")
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
            
            # Save courses to database
            if qualifying_courses:
                save_user_courses(email, index_number, flow, qualifying_courses)
            
        # Convert ObjectId to string for JSON serialization in template
        converted_courses = []
        for course in qualifying_courses:
            course_dict = dict(course)
            if '_id' in course_dict and isinstance(course_dict['_id'], ObjectId):
                course_dict['_id'] = str(course_dict['_id'])
            converted_courses.append(course_dict)
        qualifying_courses = converted_courses
        
        # Group courses by collection with proper names
        courses_by_collection = {}
        for course in qualifying_courses:
            if flow == 'degree':
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

        # Load user's existing basket from database
        if email and index_number:
            existing_basket = get_user_basket_by_index(index_number)
            if existing_basket:
                session['course_basket'] = existing_basket
        
        print(f"🎯 Displaying {len(qualifying_courses)} courses for {flow}")
        
        return render_template('collection_results.html', 
                             courses=qualifying_courses,
                             courses_by_collection=courses_by_collection,
                             user_grades=user_grades, 
                             user_mean_grade=user_mean_grade,
                             user_cluster_points=user_cluster_points,
                             subjects=SUBJECTS, 
                             email=email, 
                             index_number=index_number,
                             flow=flow,
                             cluster_names=CLUSTER_NAMES)
                             
    except Exception as e:
        print(f"❌ Error in show_results: {str(e)}")
        flash("An error occurred while generating your results", "error")
        return redirect(url_for('index'))

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
        levels = ['degree', 'diploma', 'certificate', 'artisan', 'kmtc']
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
    
    if level not in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc']:
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
        for level in ['degree', 'diploma', 'certificate', 'artisan', 'kmtc']:
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
        
        return render_template('basket.html', basket=processed_basket, basket_count=basket_count)
    
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

@app.route('/admin/manual-activation', methods=['GET', 'POST'])
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
            stats['active_count'] = admin_activations_collection.count_documents({'is_active': True})
            stats['used_count'] = admin_activations_collection.count_documents({'is_active': False})
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
                'status': 'active',
                'used_for_flow': None,
                'used_at': None
            }
            
            # Save to database
            if database_connected and admin_activations_collection is not None:
                try:
                    # Check if already activated (active or expired)
                    existing_activation = admin_activations_collection.find_one({
                        'index_number': index_number
                    })
                    
                    if existing_activation:
                        if existing_activation.get('is_active'):
                            flash(f"User {index_number} already has an active manual activation", "warning")
                            print(f"⚠️ User {index_number} already has active activation")
                        else:
                            # Update existing expired activation to active
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
                                    'activation_type': activation_type
                                }}
                            )
                            if result.modified_count > 0:
                                flash(f"Reactivated manual activation for {email}", "success")
                                print(f"✅ Manual activation reactivated: {index_number}")
                                
                                # Update statistics after reactivation
                                stats['active_count'] += 1
                                stats['used_count'] -= 1
                            else:
                                flash("Failed to reactivate manual activation", "error")
                    else:
                        result = admin_activations_collection.insert_one(activation_record)
                        if result.inserted_id:
                            flash(f"Manual activation successful for {email}", "success")
                            print(f"✅ Manual activation saved to database: {result.inserted_id}")
                            
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
            
            return redirect(url_for('admin_manual_activation'))
            
        except Exception as e:
            print(f"❌ Error in manual activation: {str(e)}")
            import traceback
            traceback.print_exc()
            flash("An error occurred during activation", "error")
            return redirect(url_for('admin_manual_activation'))
    
    return render_template('admin_manual_activation.html', 
                         active_count=stats['active_count'],
                         used_count=stats['used_count'],
                         total_count=stats['total_count'],
                         today_count=stats['today_count'])

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
    return render_template("contact.html")
    
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

@app.route('/monitor/health')
def monitor_health():
    """Detailed health monitoring endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'web_server': 'operational',
            'database': 'connected' if database_connected else 'disconnected',
            'api_endpoints': 'responsive'
        }
    })
import threading
import time
import requests
from datetime import datetime, timedelta
import random
import os

class UltimateKeepAliveService:
    def __init__(self):
        """
        Ultimate keep-alive service designed specifically for Render free tier
        """
        self.base_url = "https://kuccps-courses.onrender.com"
        self.is_running = False
        self.thread = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.cycle_count = 0
        
        # Comprehensive list of endpoints to simulate real user traffic
        self.endpoints = [
            "",  # root
            "/",
            "/health",
            "/ping", 
            "/keep-alive",
            "/api/status",
            "/monitor/health",
            "/degree",
            "/diploma",
            "/kmtc",
            "/certificate",
            "/artisan",
            "/results",
            "/about",
            "/contact",
            "/verify-payment"
        ]
        
        # Realistic user agents to simulate browser traffic
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0'
        ]
        
        print("🛡️  Ultimate Keep-Alive Service Initialized")
        
    def get_random_headers(self):
        """Generate realistic browser headers"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }
    
    def smart_request(self, url):
        """Make intelligent requests with multiple fallback strategies"""
        methods = ['GET', 'HEAD']  # Try both GET and HEAD requests
        timeouts = [15, 25, 30]   # Multiple timeout values
        
        for method in methods:
            for timeout in timeouts:
                try:
                    # Random delay to avoid pattern detection
                    time.sleep(random.uniform(1, 4))
                    
                    if method == 'GET':
                        response = requests.get(
                            url,
                            headers=self.get_random_headers(),
                            timeout=timeout,
                            verify=True,
                            allow_redirects=True
                        )
                    else:  # HEAD
                        response = requests.head(
                            url,
                            headers=self.get_random_headers(),
                            timeout=timeout,
                            verify=True,
                            allow_redirects=True
                        )
                    
                    # Consider 2xx, 3xx, and 404 as successful pings (service is responding)
                    if response.status_code < 500:  # Any status under 500 means service is up
                        response_time = response.elapsed.total_seconds() * 1000
                        print(f"✅ {method} {url} - Status: {response.status_code} - Time: {response_time:.0f}ms")
                        return True
                    else:
                        print(f"⚠️  {method} {url} - Server Error: {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    print(f"⏰ {method} {url} - Timeout after {timeout}s")
                    continue
                    
                except requests.exceptions.ConnectionError as e:
                    print(f"🔌 {method} {url} - Connection Error: {e}")
                    continue
                    
                except requests.exceptions.RequestException as e:
                    print(f"❌ {method} {url} - Request Exception: {e}")
                    continue
                    
                except Exception as e:
                    print(f"💥 {method} {url} - Unexpected Error: {e}")
                    continue
        
        return False
    
    def execute_ping_cycle(self):
        """Execute one complete ping cycle"""
        self.cycle_count += 1
        print(f"\n🔄 Keep-Alive Cycle #{self.cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        # Select random endpoints for this cycle (2-4 endpoints per cycle)
        endpoints_to_ping = random.sample(self.endpoints, random.randint(2, 4))
        success_count = 0
        
        for endpoint in endpoints_to_ping:
            full_url = f"{self.base_url}{endpoint}"
            if self.smart_request(full_url):
                success_count += 1
            else:
                print(f"🚨 Failed to ping: {endpoint}")
            
            # Random delay between pings (2-8 seconds)
            time.sleep(random.uniform(2, 8))
        
        # Calculate success rate
        total_attempts = len(endpoints_to_ping)
        success_rate = (success_count / total_attempts) * 100
        
        print(f"📊 Cycle Results: {success_count}/{total_attempts} successful ({success_rate:.1f}%)")
        print(f"📈 Consecutive Failures: {self.consecutive_failures}")
        print("=" * 60)
        
        # Update failure tracking
        if success_count == 0:
            self.consecutive_failures += 1
            print(f"🚨 ALERT: Consecutive failures increased to {self.consecutive_failures}")
        else:
            self.consecutive_failures = max(0, self.consecutive_failures - 1)
        
        return success_count > 0  # Return True if at least one ping succeeded
    
    def calculate_next_interval(self):
        """Dynamically calculate next ping interval based on failure rate"""
        base_interval = 4 * 60  # 4 minutes base in seconds
        
        if self.consecutive_failures >= 3:
            # Emergency mode - ping more frequently
            emergency_interval = max(30, base_interval - (self.consecutive_failures * 30))  # Minimum 30 seconds
            print(f"🚨 EMERGENCY MODE: Next ping in {emergency_interval}s")
            return emergency_interval
        elif self.consecutive_failures >= 1:
            # Warning mode - slightly more frequent
            warning_interval = base_interval - 60  # 3 minutes
            print(f"⚠️  WARNING MODE: Next ping in {warning_interval}s")
            return warning_interval
        else:
            # Normal mode - 4 minutes
            print(f"✅ NORMAL MODE: Next ping in {base_interval}s")
            return base_interval
    
    def run_service(self):
        """Main service loop with intelligent adaptive intervals"""
        self.is_running = True
        
        print("\n" + "🎯" * 20)
        print("🚀 ULTIMATE KEEP-ALIVE SERVICE STARTED")
        print(f"📍 Target: {self.base_url}")
        print(f"📋 Monitoring {len(self.endpoints)} endpoints")
        print("🎯" * 20 + "\n")
        
        # Immediate first ping
        print("🔔 Sending immediate wake-up ping...")
        self.execute_ping_cycle()
        
        while self.is_running:
            try:
                # Calculate dynamic interval based on current health
                sleep_interval = self.calculate_next_interval()
                
                # Sleep in small chunks to allow for graceful shutdown
                chunks = sleep_interval // 5  # Check every 5 seconds if we should stop
                for _ in range(chunks):
                    if not self.is_running:
                        break
                    time.sleep(5)
                
                if self.is_running:
                    # Execute ping cycle
                    cycle_success = self.execute_ping_cycle()
                    
                    # If completely failed for too long, try emergency recovery
                    if self.consecutive_failures >= self.max_consecutive_failures:
                        print(f"💥 CRITICAL FAILURE: {self.consecutive_failures} consecutive failures!")
                        print("🆘 Attempting emergency recovery with aggressive pinging...")
                        self.emergency_recovery()
                        
            except Exception as e:
                print(f"💥 KEEP-ALIVE SERVICE CRASHED: {e}")
                print("🔄 Restarting service in 30 seconds...")
                time.sleep(30)
                continue
    
    def emergency_recovery(self):
        """Aggressive pinging to recover from complete failure"""
        print("🚑 STARTING EMERGENCY RECOVERY PROCEDURE...")
        
        recovery_attempts = 0
        max_recovery_attempts = 10
        
        while recovery_attempts < max_recovery_attempts and self.is_running:
            recovery_attempts += 1
            print(f"🚑 Recovery attempt {recovery_attempts}/{max_recovery_attempts}")
            
            # Try all endpoints aggressively
            for endpoint in random.sample(self.endpoints, min(5, len(self.endpoints))):
                full_url = f"{self.base_url}{endpoint}"
                if self.smart_request(full_url):
                    print("✅ RECOVERY SUCCESSFUL! Service is responding.")
                    self.consecutive_failures = 0
                    return True
                time.sleep(2)  # Short delay between aggressive pings
            
            print(f"🚑 Recovery failed, waiting 10 seconds before next attempt...")
            time.sleep(10)
        
        print("💀 EMERGENCY RECOVERY FAILED - Service appears to be completely offline")
        return False
    
    def start(self):
        """Start the ultimate keep-alive service"""
        if self.thread and self.thread.is_alive():
            print("⚠️  Keep-alive service already running")
            return False
            
        try:
            self.thread = threading.Thread(target=self.run_service, daemon=True)
            self.thread.start()
            print("✅ ULTIMATE KEEP-ALIVE SERVICE STARTED SUCCESSFULLY")
            return True
        except Exception as e:
            print(f"❌ FAILED TO START KEEP-ALIVE SERVICE: {e}")
            return False
    
    def stop(self):
        """Stop the keep-alive service gracefully"""
        self.is_running = False
        print("🛑 ULTIMATE KEEP-ALIVE SERVICE STOPPED")

ultimate_keep_alive = UltimateKeepAliveService()
if __name__ == "__main__":
    print("🚀 Starting KUCCPS Application...")
    print(f"📊 Database Connection Status: {'✅ Connected' if database_connected else '❌ Disconnected'}")
    
    # Start the ultimate keep-alive service
    try:
        success = ultimate_keep_alive.start()
        if success:
            print("✅ Ultimate keep-alive service activated")
        else:
            print("⚠️ Keep-alive service failed to start, but application will continue")
    except Exception as e:
        print(f"⚠️ Keep-alive service initialization error: {e}")
    
    # Start Flask application
    port = int(os.environ.get('PORT', 8080))
    print(f"🌐 Starting Flask server on port {port}...")
    
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=False, 
        threaded=True
    )