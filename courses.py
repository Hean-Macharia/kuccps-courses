# --- Course Management Functions ---
from flask import session
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
import logging
import os
import json
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Database connection setup
MONGODB_URI = os.getenv('MONGODB_URI')
database_connected = False
user_courses_collection = None
client = None

def initialize_database():
    """Initialize database connection"""
    global database_connected, user_courses_collection, client
    
    try:
        client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            retryWrites=True,
            retryReads=True
        )
        # Test connection
        client.admin.command('ping')
        
        db_user_data = client['user_data']
        user_courses_collection = db_user_data['user_courses']
        
        # Create indexes if they don't exist
        user_courses_collection.create_index([
            ("email", 1),
            ("index_number", 1),
            ("level", 1)
        ], unique=True)
        
        database_connected = True
        logger.info("✅ Database connection established successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Error connecting to database: {str(e)}")
        database_connected = False
        return False

def verify_courses_consistency(email, index_number, level):
    """Verify course data consistency between session and database"""
    logger.info(f"Verifying course consistency for {email}, {index_number}, {level}")
    
    session_key = f'{level}_courses_{index_number}'
    session_data = session.get(session_key)
    
    if not database_connected:
        logger.warning("Database not connected, cannot verify consistency")
        return False
    
    try:
        db_data = user_courses_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        })
        
        if not db_data or 'courses' not in db_data:
            logger.warning("No courses found in database")
            return False
        
        db_courses = db_data['courses']
        db_count = len(db_courses)
        
        if session_data and 'courses' in session_data:
            session_courses = session_data['courses']
            session_count = len(session_courses)
            
            if session_count != db_count:
                logger.warning(f"⚠️ Course count mismatch - Session: {session_count}, DB: {db_count}")
                # Force session update from database
                # NOTE: Overwriting the per-level session key here to restore DB state into session.
                # This intentionally writes the '{level}_courses_{index_number}' key used across
                # the app. Be aware that session values can later be read and used as inputs to
                # regenerate courses; if session-derived values are incomplete, that may cause
                # smaller course lists to be computed and (if saved) overwrite DB records.
                # We update session here deliberately to keep UI in sync with DB.
                session[session_key] = {
                    'courses': db_courses,
                    'courses_count': db_count,
                    'last_db_fetch': datetime.now().isoformat(),
                    'from_db': True
                }
                logger.info("✅ Session updated from database")
                return True
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verifying course consistency: {str(e)}", exc_info=True)
        return False

def cleanup_database():
    """Cleanup database connections"""
    global client
    if client:
        client.close()

# Initialize database connection
initialize_database()

# Register cleanup on program exit
import atexit
atexit.register(cleanup_database)

def get_user_courses(email, index_number, level, force_refresh=False):
    """Get user courses with strict database preference"""
    logger.info(f"Getting courses for {email}, {index_number}, {level}")
    
    session_key = f'{level}_courses_{index_number}'
    
    # Always try database first if connected
    if database_connected:
        try:
            # Ensure fresh database connection
            if not client.admin.command('ping'):
                logger.warning("Database connection lost, reconnecting...")
                initialize_database()
            
            db_data = user_courses_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': level
            })
            
            if db_data and 'courses' in db_data:
                # Validate and convert courses
                valid_courses = []
                original_count = len(db_data['courses'])
                
                for course in db_data['courses']:
                    if course and isinstance(course, dict):
                        course_copy = dict(course)
                        if '_id' in course_copy:
                            if isinstance(course_copy['_id'], ObjectId):
                                course_copy['_id'] = str(course_copy['_id'])
                        # Ensure all required fields are present
                        if ('programme_name' in course_copy or 'course_name' in course_copy):
                            valid_courses.append(course_copy)
                
                logger.info(f"✅ Loaded {len(valid_courses)} courses from database for {level}")
                
                if len(valid_courses) != original_count:
                    logger.warning(f"⚠️ Course count mismatch: {original_count} -> {len(valid_courses)}")
                    # IMPORTANT: Do NOT automatically overwrite the DB when validation reduces
                    # the number of courses. Overwriting with a smaller set can cause data loss
                    # (we observed full lists being replaced with just a few items). Instead,
                    # write a backup for manual inspection and mark the record as needing review.
                    try:
                        # Ensure backups dir exists
                        backups_dir = os.path.join(os.path.dirname(__file__), 'backups')
                        os.makedirs(backups_dir, exist_ok=True)
                        backup_path = os.path.join(
                            backups_dir,
                            f'user_courses_validation_{index_number.replace("/","_")}_{int(datetime.now().timestamp())}.json'
                        )
                        with open(backup_path, 'w', encoding='utf-8') as f:
                            json.dump({
                                'email': email,
                                'index_number': index_number,
                                'level': level,
                                'original_count': original_count,
                                'validated_count': len(valid_courses),
                                'validated_sample': valid_courses[:20]
                            }, f, default=str, indent=2)
                        logger.warning(f"🔖 Wrote validation backup to {backup_path}")
                    except Exception as be:
                        logger.error(f"❌ Failed to write validation backup: {be}", exc_info=True)

                    # Log a short stack trace to help identify the caller
                    try:
                        stack = ''.join(traceback.format_stack(limit=6))
                        logger.warning(f"🔎 Validation mismatch stack (recent frames):\n{stack}")
                    except Exception:
                        pass

                    # Optionally mark the record with last_validated timestamp without changing courses
                    try:
                        user_courses_collection.update_one(
                            {'email': email, 'index_number': index_number, 'level': level},
                            {'$set': {'last_validated': datetime.now(), 'needs_review': True}}
                        )
                        logger.info("✅ Marked DB record with last_validated and needs_review flag")
                    except Exception as me:
                        logger.error(f"❌ Failed to mark DB record for review: {me}", exc_info=True)
                
                # Only update session with verified database data
                # NOTE: Writing verified DB courses into session cache.
                # This writes the '{level}_courses_{index_number}' session key.
                # This is safe because data here is validated/verified from DB.
                session[session_key] = {
                    'courses': valid_courses,
                    'courses_count': len(valid_courses),
                    'last_db_fetch': datetime.now().isoformat(),
                    'from_db': True
                }
                
                return valid_courses
                
        except Exception as e:
            logger.error(f"❌ Error getting courses from database: {str(e)}", exc_info=True)
    
    # Only use session data if database is unavailable AND not forcing refresh
    if not force_refresh:
        session_data = session.get(session_key)
        if session_data and session_data.get('courses'):
            courses = session_data['courses']
            logger.warning(f"⚠️ Using session data ({len(courses)} courses) - database unavailable")
            return courses
    
    logger.warning("No courses found in database or session")
    return []

def save_user_courses(email, index_number, level, courses, update_session=True):
    """Save user courses with strict validation and database priority"""
    logger.info(f"Saving courses for {email}, {index_number}, {level}")
    
    if not courses:
        logger.warning("No courses to save")
        return False
    
    # Validate and clean courses
    valid_courses = []
    original_count = len(courses)
    
    for course in courses:
        if not isinstance(course, dict):
            continue
            
        # Ensure course has required fields
        if not (course.get('programme_name') or course.get('course_name')):
            continue
            
        course_copy = dict(course)
        
        # Clean ObjectId fields
        if '_id' in course_copy:
            if isinstance(course_copy['_id'], ObjectId):
                course_copy['_id'] = str(course_copy['_id'])
            elif not isinstance(course_copy['_id'], str):
                continue
        
        # Remove any session-specific fields
        course_copy.pop('from_db', None)
        course_copy.pop('last_update', None)
        
        valid_courses.append(course_copy)
    
    if not valid_courses:
        logger.error("No valid courses after validation")
        return False
    
    if len(valid_courses) != original_count:
        logger.warning(f"⚠️ Course count changed during validation: {original_count} -> {len(valid_courses)}")
    
    # Always try to save to database first
    if database_connected:
        try:
            # Ensure fresh database connection
            if not client.admin.command('ping'):
                logger.warning("Database connection lost, reconnecting...")
                initialize_database()
            
            # Prepare the record
            record = {
                'email': email,
                'index_number': index_number,
                'level': level,
                'courses': valid_courses,
                'courses_count': len(valid_courses),
                'updated_at': datetime.now(),
                'last_validated': datetime.now()
            }
            
            # Use update_one with upsert to prevent duplicates
            # Instrumentation: log caller and sizes before updating DB
            try:
                stack = ''.join(traceback.format_stack(limit=6))
            except Exception:
                stack = ''
            logger.info(f"🛠️ About to update DB for {email}/{index_number}/{level}: saving {len(valid_courses)} courses. Caller stack (trimmed):\n{stack}")

            result = user_courses_collection.update_one(
                {
                    'email': email,
                    'index_number': index_number,
                    'level': level
                },
                {'$set': record},
                upsert=True
            )
            
            logger.info(f"✅ Saved {len(valid_courses)} courses to database for {level}")
            
            # Verify the save
            saved_data = user_courses_collection.find_one({
                'email': email,
                'index_number': index_number,
                'level': level
            })
            
            if saved_data and len(saved_data.get('courses', [])) == len(valid_courses):
                logger.info("✅ Database save verified")
                
                if update_session:
                    # Update session with verified database data
                    session[f'{level}_courses_{index_number}'] = {
                        'courses': valid_courses,
                        'courses_count': len(valid_courses),
                        'last_db_fetch': datetime.now().isoformat(),
                        'from_db': True
                    }
                
                return True
            else:
                logger.error("❌ Database save verification failed")
                raise Exception("Save verification failed")
            
        except Exception as e:
            logger.error(f"❌ Error saving courses to database: {str(e)}", exc_info=True)
            
            # Only fallback to session if database save completely fails
            if update_session:
                # NOTE: Error fallback - saving validated courses to session when DB save fails.
                # This is a last-resort cache; prefer to surface/handle DB errors instead of
                # relying on session persistence.
                session[f'{level}_courses_{index_number}'] = {
                    'courses': valid_courses,
                    'courses_count': len(valid_courses),
                    'last_update': datetime.now().isoformat(),
                    'from_db': False,
                    'error': str(e)
                }
            return False
    
    # If no database connection, save to session as last resort
    if update_session:
        # NOTE: No-database case: persist courses to session as a last-resort cache.
        # This writes the '{level}_courses_{index_number}' key. Keep this transient
        # and prefer DB writes when connectivity is restored.
        session[f'{level}_courses_{index_number}'] = {
            'courses': valid_courses,
            'courses_count': len(valid_courses),
            'last_update': datetime.now().isoformat(),
            'from_db': False
        }
        logger.warning(f"⚠️ Saved {len(valid_courses)} courses to session (database unavailable)")
    
    return True