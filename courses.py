# --- Course Management Functions ---
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
import logging
import json
import traceback
import atexit

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
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
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
    """Verify course data consistency (session is NOT used for courses)"""
    logger.info(f"Verifying course consistency for {email}, {index_number}, {level}")
    
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
        logger.info(f"✅ Database has {db_count} courses for {level}")
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
atexit.register(cleanup_database)

def get_user_courses(email, index_number, level):
    """Get user courses from DATABASE ONLY - NEVER from session"""
    logger.info(f"Getting courses for {email}, {index_number}, {level}")
    
    # ALWAYS get from database - NEVER from session
    if database_connected:
        try:
            # Ensure fresh database connection
            if client:
                try:
                    client.admin.command('ping')
                except:
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
                    
                    # Write backup for manual inspection
                    try:
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
                    
                    # Mark record for review without changing courses
                    try:
                        user_courses_collection.update_one(
                            {'email': email, 'index_number': index_number, 'level': level},
                            {'$set': {'last_validated': datetime.now(), 'needs_review': True}}
                        )
                        logger.info("✅ Marked DB record with last_validated and needs_review flag")
                    except Exception as me:
                        logger.error(f"❌ Failed to mark DB record for review: {me}", exc_info=True)
                
                return valid_courses
                
        except Exception as e:
            logger.error(f"❌ Error getting courses from database: {str(e)}", exc_info=True)
    
    logger.warning("No courses found in database")
    return []

def save_user_courses(email, index_number, level, courses):
    """Save user courses to DATABASE ONLY - NEVER store in session"""
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
    
    # Save to database ONLY - NEVER to session
    if database_connected:
        try:
            # Ensure fresh database connection
            if client:
                try:
                    client.admin.command('ping')
                except:
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
            
            # Log caller for debugging
            try:
                stack = ''.join(traceback.format_stack(limit=6))
            except Exception:
                stack = ''
            logger.info(f"🛠️ Saving {len(valid_courses)} courses to DB for {email}/{index_number}/{level}")
            
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
                return True
            else:
                logger.error("❌ Database save verification failed")
                return False
            
        except Exception as e:
            logger.error(f"❌ Error saving courses to database: {str(e)}", exc_info=True)
            return False
    
    # If no database connection, log error
    logger.error(f"❌ No database connection - cannot save {len(valid_courses)} courses!")
    return False

def clear_user_courses_session(email, index_number, level):
    """
    Clear user courses from session - DEPRECATED: Courses are never stored in session.
    This function exists for compatibility but does nothing.
    """
    logger.info(f"clear_user_courses_session called for {level} - DEPRECATED: Courses are not stored in session")
    return True

def course_exists_in_db(email, index_number, level):
    """Check if courses exist in database for this user"""
    if not database_connected:
        return False
    
    try:
        result = user_courses_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        }, {'_id': 1})
        return result is not None
    except Exception as e:
        logger.error(f"❌ Error checking course existence: {str(e)}")
        return False

def get_courses_count(email, index_number, level):
    """Get count of courses for this user from database"""
    if not database_connected:
        return 0
    
    try:
        result = user_courses_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        }, {'courses_count': 1})
        return result.get('courses_count', 0) if result else 0
    except Exception as e:
        logger.error(f"❌ Error getting courses count: {str(e)}")
        return 0

def delete_user_courses(email, index_number, level):
    """Delete user courses from database"""
    if not database_connected:
        return False
    
    try:
        result = user_courses_collection.delete_one({
            'email': email,
            'index_number': index_number,
            'level': level
        })
        if result.deleted_count > 0:
            logger.info(f"✅ Deleted courses for {email}, {index_number}, {level}")
            return True
        else:
            logger.warning(f"⚠️ No courses found to delete for {email}, {index_number}, {level}")
            return False
    except Exception as e:
        logger.error(f"❌ Error deleting courses: {str(e)}")
        return False