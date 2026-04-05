# --- Course Management Functions ---
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
import os
from dotenv import load_dotenv
import logging
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
        client.admin.command('ping')

        db_user_data = client['user_data']
        user_courses_collection = db_user_data['user_courses']

        # Create indexes if they don't exist
        existing = {
            idx['name']
            for idx in user_courses_collection.list_indexes()
        }
        if 'email_1_index_number_1_level_1' not in existing:
            user_courses_collection.create_index(
                [("email", 1), ("index_number", 1), ("level", 1)],
                unique=True
            )

        database_connected = True
        logger.info("✅ Database connection established successfully")
        return True

    except Exception as e:
        logger.error(f"❌ Error connecting to database: {str(e)}")
        database_connected = False
        return False


def _ensure_connection():
    """Ping DB and reconnect if stale. Returns True if connected."""
    global database_connected
    if not database_connected or client is None:
        return initialize_database()
    try:
        client.admin.command('ping')
        return True
    except Exception:
        logger.warning("⚠️ DB ping failed, reconnecting…")
        return initialize_database()


def cleanup_database():
    """Cleanup database connections on exit"""
    global client
    if client:
        try:
            client.close()
        except Exception:
            pass


# Initialize on import
initialize_database()
atexit.register(cleanup_database)


# ─────────────────────────────────────────────────────────────
# SAVE  (no verification read — that was the 11-second killer)
# ─────────────────────────────────────────────────────────────

def save_user_courses(email, index_number, level, courses):
    """
    Save courses to MongoDB.

    KEY CHANGE from old version:
    - Removed the find_one() verification read that ran after every save.
      That read was responsible for the 10-12 second delay between
      '✅ Saved … courses' and '✅ Database save verified' in the logs.
    - The update_one() upsert is atomic and reliable; we trust its
      return value instead of re-reading the document.
    """
    logger.info(f"Saving courses for {email}, {index_number}, {level}")

    if not courses:
        logger.warning("No courses to save")
        return False

    # ── Validate & clean ──
    valid_courses = []
    for course in courses:
        if not isinstance(course, dict):
            continue
        if not (course.get('programme_name') or course.get('course_name')):
            continue

        c = dict(course)

        # Stringify ObjectId so MongoDB won't complain on re-insert
        if '_id' in c:
            if isinstance(c['_id'], ObjectId):
                c['_id'] = str(c['_id'])
            elif not isinstance(c['_id'], str):
                c.pop('_id', None)

        # Strip internal-only fields
        c.pop('from_db', None)
        c.pop('last_update', None)

        valid_courses.append(c)

    if not valid_courses:
        logger.error("No valid courses after validation")
        return False

    if len(valid_courses) != len(courses):
        logger.warning(
            f"⚠️ Course count changed during validation: "
            f"{len(courses)} → {len(valid_courses)}"
        )

    if not _ensure_connection():
        logger.error(
            f"❌ No DB connection — cannot save {len(valid_courses)} courses!"
        )
        return False

    try:
        logger.info(
            f"🛠️ Saving {len(valid_courses)} courses to DB "
            f"for {email}/{index_number}/{level}"
        )

        result = user_courses_collection.update_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'$set': {
                'email':         email,
                'index_number':  index_number,
                'level':         level,
                'courses':       valid_courses,
                'courses_count': len(valid_courses),
                'updated_at':    datetime.now(),
            }},
            upsert=True
        )

        # Trust the driver's acknowledged write — no extra find_one()
        if result.acknowledged:
            logger.info(
                f"✅ Saved {len(valid_courses)} courses to database for {level}"
            )
            return True
        else:
            logger.error("❌ DB write not acknowledged")
            return False

    except Exception as e:
        logger.error(f"❌ Error saving courses: {str(e)}", exc_info=True)
        return False


# ─────────────────────────────────────────────────────────────
# GET
# ─────────────────────────────────────────────────────────────

def get_user_courses(email, index_number, level):
    """Get user courses from DATABASE ONLY — never from session."""
    logger.info(f"Getting courses for {email}, {index_number}, {level}")

    if not _ensure_connection():
        logger.warning("DB not connected, cannot fetch courses")
        return []

    try:
        db_data = user_courses_collection.find_one({
            'email': email,
            'index_number': index_number,
            'level': level
        })

        if not db_data or 'courses' not in db_data:
            logger.warning("No courses found in database")
            return []

        valid_courses = []
        for course in db_data['courses']:
            if not isinstance(course, dict):
                continue
            if not (course.get('programme_name') or course.get('course_name')):
                continue
            c = dict(course)
            if '_id' in c and isinstance(c['_id'], ObjectId):
                c['_id'] = str(c['_id'])
            valid_courses.append(c)

        logger.info(
            f"✅ Loaded {len(valid_courses)} courses from database for {level}"
        )
        return valid_courses

    except Exception as e:
        logger.error(f"❌ Error getting courses: {str(e)}", exc_info=True)
        return []


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def verify_courses_consistency(email, index_number, level):
    """
    Lightweight consistency check — returns True if at least one
    course record exists in the DB for this user/level.
    Does NOT re-read the entire courses array.
    """
    if not _ensure_connection():
        return False
    try:
        result = user_courses_collection.find_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'courses_count': 1}   # projection — cheap read
        )
        exists = result is not None and result.get('courses_count', 0) > 0
        logger.info(
            f"{'✅' if exists else '⚠️'} "
            f"verify_courses_consistency: {level} for {email} → {exists}"
        )
        return exists
    except Exception as e:
        logger.error(f"❌ Error verifying consistency: {str(e)}")
        return False


def course_exists_in_db(email, index_number, level):
    """Return True if a course record exists for this user/level."""
    if not _ensure_connection():
        return False
    try:
        result = user_courses_collection.find_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'_id': 1}
        )
        return result is not None
    except Exception as e:
        logger.error(f"❌ Error checking course existence: {str(e)}")
        return False


def get_courses_count(email, index_number, level):
    """Return stored courses_count without loading the full array."""
    if not _ensure_connection():
        return 0
    try:
        result = user_courses_collection.find_one(
            {'email': email, 'index_number': index_number, 'level': level},
            {'courses_count': 1}
        )
        return result.get('courses_count', 0) if result else 0
    except Exception as e:
        logger.error(f"❌ Error getting courses count: {str(e)}")
        return 0


def delete_user_courses(email, index_number, level):
    """Delete course record for a user/level."""
    if not _ensure_connection():
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
        logger.warning(f"⚠️ No courses to delete for {email}, {index_number}, {level}")
        return False
    except Exception as e:
        logger.error(f"❌ Error deleting courses: {str(e)}")
        return False


def clear_user_courses_session(email, index_number, level):
    """
    DEPRECATED — courses are never stored in session.
    Kept for backwards compatibility; does nothing.
    """
    logger.info(
        f"clear_user_courses_session called for {level} — "
        f"DEPRECATED: courses are not stored in session"
    )
    return True